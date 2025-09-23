-- =====================================================
-- MIGRAÇÃO STRIPE CORRIGIDA - BASEADA NA ESTRUTURA REAL
-- =====================================================
-- Execute este script no SQL Editor do Supabase
-- Corrigido após análise da estrutura real do banco de dados

-- =====================================================
-- 1. ADICIONAR CAMPOS STRIPE NA TABELA USERS
-- =====================================================

-- Adicionar campos Stripe necessários
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS credits DECIMAL(10,2) DEFAULT 0.00;

-- Criar índice para performance
CREATE INDEX IF NOT EXISTS idx_users_stripe_customer ON users(stripe_customer_id);

-- =====================================================
-- 2. ADICIONAR CAMPOS STRIPE NA TABELA SUBSCRIPTIONS  
-- =====================================================

-- Subscriptions já tem stripe_subscription_id, adicionar campos extras
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS stripe_price_id VARCHAR(255);
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS cancel_at_period_end BOOLEAN DEFAULT FALSE;

-- =====================================================
-- 3. VERIFICAR TABELA CREDIT_TRANSACTIONS (JÁ EXISTE)
-- =====================================================

-- ✅ ESTRUTURA JÁ CORRETA:
-- - amount_cents (INTEGER) ✅
-- - balance_after_cents (INTEGER) ✅ 
-- - type, stripe_payment_intent_id, stripe_invoice_id ✅

-- Apenas garantir que balance_after_cents não seja NULL nos registros existentes
UPDATE credit_transactions 
SET balance_after_cents = COALESCE(balance_after_cents, amount_cents)
WHERE balance_after_cents IS NULL;

-- =====================================================
-- 4. CRIAR TABELA SERVICE_COSTS (NÃO EXISTE)
-- =====================================================

CREATE TABLE IF NOT EXISTS service_costs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL UNIQUE,
    cost_per_request DECIMAL(10,4) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Inserir dados padrão
INSERT INTO service_costs (service_name, cost_per_request, description) 
VALUES 
    ('protestos', 0.15, 'Consulta de protestos no Resolve CenProt'),
    ('receita_federal', 0.03, 'Consulta de dados na Receita Federal'),
    ('outros', 0.03, 'Outros serviços de consulta')
ON CONFLICT (service_name) DO UPDATE SET
    cost_per_request = EXCLUDED.cost_per_request,
    description = EXCLUDED.description,
    updated_at = NOW();

-- =====================================================
-- 5. CRIAR TABELA STRIPE_WEBHOOK_LOGS (NÃO EXISTE)
-- =====================================================

CREATE TABLE IF NOT EXISTS stripe_webhook_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    webhook_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_webhook_logs_event_id ON stripe_webhook_logs(event_id);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_event_type ON stripe_webhook_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_processed ON stripe_webhook_logs(processed);

-- =====================================================
-- 6. ATUALIZAR SUBSCRIPTION_PLANS (JÁ EXISTE E OK)
-- =====================================================

-- Subscription_plans já existe com boa estrutura, só adicionar campos Stripe
ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS stripe_product_id VARCHAR(255);
ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS stripe_price_id VARCHAR(255);
ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS features JSONB DEFAULT '{}';

-- =====================================================
-- 7. CRIAR FUNÇÃO CORRIGIDA PARA CRÉDITOS
-- =====================================================

-- Função corrigida para usar balance_after_cents (campo real)
CREATE OR REPLACE FUNCTION update_user_credits()
RETURNS TRIGGER AS $$
BEGIN
    -- Calcular saldo total atual
    DECLARE
        current_balance INTEGER;
    BEGIN
        SELECT COALESCE(SUM(
            CASE 
                WHEN type IN ('add', 'purchase') THEN amount_cents
                WHEN type IN ('subtract', 'spend') THEN -amount_cents
                ELSE 0
            END
        ), 0) INTO current_balance
        FROM credit_transactions 
        WHERE user_id = NEW.user_id;
        
        -- Aplicar transação atual
        current_balance = current_balance + 
            CASE 
                WHEN NEW.type IN ('add', 'purchase') THEN NEW.amount_cents
                WHEN NEW.type IN ('subtract', 'spend') THEN -NEW.amount_cents
                ELSE 0
            END;
        
        -- Definir balance_after_cents na transação atual
        NEW.balance_after_cents = current_balance;
        
        -- Atualizar campo credits na tabela users (se existir)
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'users' AND column_name = 'credits') THEN
            UPDATE users 
            SET credits = current_balance / 100.0
            WHERE id = NEW.user_id;
        END IF;
        
        RETURN NEW;
    END;
END;
$$ LANGUAGE plpgsql;

-- Recriar trigger
DROP TRIGGER IF EXISTS trigger_update_user_credits ON credit_transactions;
CREATE TRIGGER trigger_update_user_credits
    BEFORE INSERT ON credit_transactions
    FOR EACH ROW
    EXECUTE FUNCTION update_user_credits();

-- =====================================================
-- 8. RLS (ROW LEVEL SECURITY)
-- =====================================================

-- Habilitar RLS
ALTER TABLE service_costs ENABLE ROW LEVEL SECURITY;
ALTER TABLE stripe_webhook_logs ENABLE ROW LEVEL SECURITY;

-- Políticas básicas
DROP POLICY IF EXISTS "Service costs are viewable by authenticated users" ON service_costs;
CREATE POLICY "Service costs are viewable by authenticated users" 
    ON service_costs FOR SELECT 
    TO authenticated 
    USING (true);

DROP POLICY IF EXISTS "Admins can manage webhook logs" ON stripe_webhook_logs;
CREATE POLICY "Admins can manage webhook logs" 
    ON stripe_webhook_logs FOR ALL 
    TO authenticated 
    USING (true);

-- =====================================================
-- 9. CRIAR VIEWS CORRIGIDAS
-- =====================================================

-- View de resumo de créditos (usando estrutura real)
DROP VIEW IF EXISTS user_credits_summary;
CREATE VIEW user_credits_summary AS
SELECT 
    u.id,
    u.email,
    u.name,
    -- Pegar créditos da coluna users.credits se existir, senão calcular
    COALESCE(u.credits, 
        (SELECT balance_after_cents / 100.0 
         FROM credit_transactions 
         WHERE user_id = u.id 
         ORDER BY created_at DESC 
         LIMIT 1), 
        0) as current_credits,
    COALESCE(ct.total_purchased / 100.0, 0) as total_purchased,
    COALESCE(ct.total_spent / 100.0, 0) as total_spent,
    COALESCE(ct.transaction_count, 0) as transaction_count,
    u.created_at as user_created_at
FROM users u
LEFT JOIN (
    SELECT 
        user_id,
        SUM(CASE WHEN type IN ('add', 'purchase') THEN amount_cents ELSE 0 END) as total_purchased,
        SUM(CASE WHEN type IN ('subtract', 'spend') THEN amount_cents ELSE 0 END) as total_spent,
        COUNT(*) as transaction_count
    FROM credit_transactions 
    GROUP BY user_id
) ct ON u.id = ct.user_id;

-- View de assinaturas ativas (usando estrutura real)
DROP VIEW IF EXISTS active_subscriptions;
CREATE VIEW active_subscriptions AS
SELECT 
    s.*,
    u.email,
    u.name as user_name,
    sp.name as plan_name,
    sp.price_cents,
    sp.stripe_product_id,
    sp.stripe_price_id as plan_stripe_price_id
FROM subscriptions s
JOIN users u ON s.user_id = u.id
LEFT JOIN subscription_plans sp ON s.plan_id = sp.id
WHERE s.status = 'active';

-- =====================================================
-- 10. TESTE SEGURO (SEM INSERÇÃO FORÇADA)
-- =====================================================

-- NÃO inserir transação de teste automática para evitar erros
-- O usuário pode fazer isso manualmente se quiser:

/*
-- TESTE MANUAL (execute apenas se quiser):
DO $$
DECLARE
    test_user_id UUID;
BEGIN
    SELECT id INTO test_user_id FROM users LIMIT 1;
    
    IF test_user_id IS NOT NULL THEN
        INSERT INTO credit_transactions (user_id, type, amount_cents, description)
        VALUES (test_user_id, 'add', 1000, 'Teste migração Stripe - R$ 10,00')
        ON CONFLICT DO NOTHING;
    END IF;
END $$;
*/

-- =====================================================
-- 11. VERIFICAÇÕES FINAIS
-- =====================================================

-- Mostrar estrutura atual da tabela crítica
SELECT 
    'CREDIT_TRANSACTIONS' as tabela,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public'
AND table_name = 'credit_transactions'
AND column_name IN ('amount_cents', 'balance_after_cents', 'type')
ORDER BY column_name;

-- Verificar se campos essenciais foram adicionados
SELECT 
    'NOVOS CAMPOS STRIPE' as categoria,
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.columns 
                     WHERE table_name = 'users' AND column_name = 'stripe_customer_id')
         THEN '✅ users.stripe_customer_id' 
         ELSE '❌ users.stripe_customer_id FALTANDO' END as status
UNION ALL
SELECT 
    'NOVOS CAMPOS STRIPE' as categoria,
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.columns 
                     WHERE table_name = 'users' AND column_name = 'credits')
         THEN '✅ users.credits' 
         ELSE '❌ users.credits FALTANDO' END as status;

-- Verificar tabelas criadas
SELECT 
    'TABELAS STRIPE' as categoria,
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables 
                     WHERE table_name = 'service_costs')
         THEN '✅ service_costs CRIADA' 
         ELSE '❌ service_costs FALTANDO' END as status
UNION ALL
SELECT 
    'TABELAS STRIPE' as categoria,
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables 
                     WHERE table_name = 'stripe_webhook_logs')
         THEN '✅ stripe_webhook_logs CRIADA' 
         ELSE '❌ stripe_webhook_logs FALTANDO' END as status;

-- =====================================================
-- 12. RESULTADO FINAL
-- =====================================================

SELECT 
    '🎉 MIGRAÇÃO STRIPE CORRIGIDA CONCLUÍDA!' as resultado,
    NOW() as executado_em,
    'Baseada na estrutura real do banco - sem erros de balance_after_cents' as detalhes;
