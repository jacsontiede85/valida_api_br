-- =====================================================
-- MIGRAÇÃO DO BANCO DE DADOS - VALIDA SaaS v2.0
-- =====================================================
-- Sistema Simplificado com Renovação Automática
-- Execute este SQL no SQL Editor do Supabase
-- Painel: https://supabase.com/dashboard > SQL Editor

-- =====================================================
-- 1. CRIAÇÃO DAS NOVAS TABELAS
-- =====================================================

-- Tabela de tipos de consulta com custos específicos
CREATE TABLE IF NOT EXISTS consultation_types (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,           -- 'protestos', 'receita_federal', 'simples', etc
    name VARCHAR(100) NOT NULL,                 -- Nome amigável
    description TEXT,                           -- Descrição detalhada
    cost_cents INTEGER NOT NULL,                -- Custo em centavos (15, 5, 5, etc)
    provider VARCHAR(50) NOT NULL,              -- 'resolve_cenprot', 'cnpja', 'receita_federal'
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Inserir tipos de consulta baseados no fluxo
INSERT INTO consultation_types (code, name, description, cost_cents, provider) VALUES
('protestos', 'Consulta de Protestos', 'Consulta protestos via Resolve CenProt', 15, 'resolve_cenprot'),
('receita_federal', 'Receita Federal', 'Dados básicos da empresa via CNPJa', 5, 'cnpja'),
('simples_nacional', 'Simples Nacional', 'Consulta regime tributário via CNPJa', 5, 'cnpja'),
('cadastro_contribuintes', 'Cadastro de Contribuintes', 'Inscrições estaduais via CNPJa', 5, 'cnpja'),
('geocodificacao', 'Geocodificação', 'Coordenadas geográficas via CNPJa', 5, 'cnpja'),
('suframa', 'Suframa', 'Dados da Suframa via CNPJa', 5, 'cnpja')
ON CONFLICT (code) DO NOTHING;

-- Tabela principal de consultas (substitui query_history)
CREATE TABLE IF NOT EXISTS consultations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    cnpj VARCHAR(18) NOT NULL,
    
    -- Metadados da consulta
    total_cost_cents INTEGER NOT NULL DEFAULT 0,   -- Custo total da consulta
    response_time_ms INTEGER,
    status VARCHAR(20) DEFAULT 'success',          -- success, error, partial
    error_message TEXT,
    
    -- Controle de cache e performance
    cache_used BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de detalhes por tipo de consulta
CREATE TABLE IF NOT EXISTS consultation_details (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    consultation_id UUID REFERENCES consultations(id) ON DELETE CASCADE,
    consultation_type_id UUID REFERENCES consultation_types(id),
    
    -- Resultado específico do tipo
    success BOOLEAN NOT NULL DEFAULT true,
    cost_cents INTEGER NOT NULL,               -- Custo específico deste tipo
    response_data JSONB,                       -- Dados retornados (opcional)
    cache_used BOOLEAN DEFAULT false,
    response_time_ms INTEGER,
    error_message TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- 2. SISTEMA DE PLANOS SIMPLIFICADO
-- =====================================================

-- Remover e recriar tabela de planos
DROP TABLE IF EXISTS subscription_plans CASCADE;

CREATE TABLE subscription_plans (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,           -- 'basic', 'professional', 'enterprise'
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Preços em centavos (R$ 100,00 = 10000 centavos)
    price_cents INTEGER NOT NULL,               -- Valor da assinatura
    credits_included_cents INTEGER NOT NULL,    -- Créditos inclusos na assinatura
    
    -- Limites do plano
    api_keys_limit INTEGER DEFAULT 1,
    
    -- Configurações simplificadas
    auto_renew_on_depletion BOOLEAN DEFAULT true, -- Renovar automaticamente quando créditos acabam
    
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Planos baseados no fluxo (quando créditos acabam, renova automaticamente)
INSERT INTO subscription_plans (code, name, description, price_cents, credits_included_cents, api_keys_limit) VALUES
('basic', 'Plano Básico', 'Ideal para começar - R$ 100,00 em créditos, renova automaticamente', 10000, 10000, 1),
('professional', 'Plano Profissional', 'Para uso intensivo - R$ 300,00 em créditos, renova automaticamente', 30000, 30000, 5),
('enterprise', 'Plano Empresarial', 'Uso corporativo - R$ 500,00 em créditos, renova automaticamente', 50000, 50000, 20)
ON CONFLICT (code) DO NOTHING;

-- =====================================================
-- 3. SISTEMA DE CONTROLE DE CRÉDITOS
-- =====================================================

-- Tabela de créditos do usuário (simplificada)
CREATE TABLE IF NOT EXISTS user_credits (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    
    -- Controle de créditos em centavos (simplificado)
    available_credits_cents INTEGER DEFAULT 0,     -- Créditos disponíveis atuais
    total_purchased_cents INTEGER DEFAULT 0,       -- Total de créditos já comprados
    total_used_cents INTEGER DEFAULT 0,            -- Total de créditos já utilizados
    
    -- Controle de renovação automática
    last_auto_renewal TIMESTAMP WITH TIME ZONE,    -- Última renovação automática
    auto_renewal_count INTEGER DEFAULT 0,          -- Quantas renovações automáticas foram feitas
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de transações de crédito (simplificada)
CREATE TABLE IF NOT EXISTS credit_transactions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    consultation_id UUID REFERENCES consultations(id) ON DELETE SET NULL,
    
    -- Transação de crédito
    type VARCHAR(20) NOT NULL,                  -- 'purchase', 'usage', 'auto_renewal'
    amount_cents INTEGER NOT NULL,              -- Valor da transação (positivo para compra, negativo para uso)
    balance_after_cents INTEGER NOT NULL,       -- Saldo após a transação
    
    -- Metadados
    description TEXT,
    stripe_payment_id VARCHAR(255),             -- ID do pagamento no Stripe (para compras)
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- 4. ATUALIZAÇÃO DA TABELA DE ASSINATURAS
-- =====================================================

-- Adicionar colunas para renovação automática
ALTER TABLE subscriptions 
ADD COLUMN IF NOT EXISTS last_auto_renewal TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS auto_renewal_enabled BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS auto_renewal_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_spent_cents INTEGER DEFAULT 0; -- Total gasto pelo usuário

-- =====================================================
-- 5. SISTEMA DE ANALYTICS APRIMORADO
-- =====================================================

-- Tabela de analytics diários (substitui query_analytics)
CREATE TABLE IF NOT EXISTS daily_analytics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    
    -- Estatísticas gerais
    total_consultations INTEGER DEFAULT 0,
    successful_consultations INTEGER DEFAULT 0,
    failed_consultations INTEGER DEFAULT 0,
    
    -- Custos e créditos (simplificado)
    total_cost_cents INTEGER DEFAULT 0,         -- Custo total do dia
    credits_used_cents INTEGER DEFAULT 0,       -- Créditos consumidos
    
    -- Por tipo de consulta (JSONB para flexibilidade)
    consultations_by_type JSONB DEFAULT '{}',   -- {"protestos": 5, "receita_federal": 10}
    costs_by_type JSONB DEFAULT '{}',           -- {"protestos": 75, "receita_federal": 50}
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, date)
);

-- =====================================================
-- 6. ÍNDICES PARA PERFORMANCE
-- =====================================================

-- Índices para consultas
CREATE INDEX IF NOT EXISTS idx_consultations_user_date ON consultations(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_consultations_cnpj ON consultations(cnpj);
CREATE INDEX IF NOT EXISTS idx_consultations_status ON consultations(status);

-- Índices para detalhes de consulta
CREATE INDEX IF NOT EXISTS idx_consultation_details_consultation ON consultation_details(consultation_id);
CREATE INDEX IF NOT EXISTS idx_consultation_details_type ON consultation_details(consultation_type_id);

-- Índices para créditos e transações
CREATE INDEX IF NOT EXISTS idx_user_credits_user ON user_credits(user_id);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_date ON credit_transactions(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_type ON credit_transactions(type);

-- Índices para analytics
CREATE INDEX IF NOT EXISTS idx_daily_analytics_user_date ON daily_analytics(user_id, date);

-- Índices para tipos de consulta
CREATE INDEX IF NOT EXISTS idx_consultation_types_code ON consultation_types(code);
CREATE INDEX IF NOT EXISTS idx_consultation_types_provider ON consultation_types(provider);

-- =====================================================
-- 7. POLÍTICAS RLS (Row Level Security)
-- =====================================================

-- Habilitar RLS nas novas tabelas
ALTER TABLE consultations ENABLE ROW LEVEL SECURITY;
ALTER TABLE consultation_details ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_credits ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_analytics ENABLE ROW LEVEL SECURITY;

-- Políticas para consultations
CREATE POLICY "Users can view own consultations" ON consultations
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own consultations" ON consultations
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Políticas para consultation_details
CREATE POLICY "Users can view own consultation_details" ON consultation_details
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM consultations c 
            WHERE c.id = consultation_id AND c.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert own consultation_details" ON consultation_details
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM consultations c 
            WHERE c.id = consultation_id AND c.user_id = auth.uid()
        )
    );

-- Políticas para user_credits
CREATE POLICY "Users can view own credits" ON user_credits
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own credits" ON user_credits
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own credits" ON user_credits
    FOR UPDATE USING (auth.uid() = user_id);

-- Políticas para credit_transactions
CREATE POLICY "Users can view own credit_transactions" ON credit_transactions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own credit_transactions" ON credit_transactions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Políticas para daily_analytics
CREATE POLICY "Users can view own daily_analytics" ON daily_analytics
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own daily_analytics" ON daily_analytics
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Políticas para consultation_types (público para leitura)
CREATE POLICY "Anyone can view consultation_types" ON consultation_types
    FOR SELECT USING (true);

-- =====================================================
-- 8. FUNÇÕES UTILITÁRIAS
-- =====================================================

-- Função para calcular custo total de uma consulta baseado nos tipos
CREATE OR REPLACE FUNCTION calculate_consultation_cost(
    p_protestos BOOLEAN DEFAULT false,
    p_receita_federal BOOLEAN DEFAULT false,
    p_simples_nacional BOOLEAN DEFAULT false,
    p_cadastro_contribuintes BOOLEAN DEFAULT false,
    p_geocodificacao BOOLEAN DEFAULT false,
    p_suframa BOOLEAN DEFAULT false
) RETURNS INTEGER AS $$
DECLARE
    total_cost INTEGER := 0;
BEGIN
    IF p_protestos THEN
        total_cost := total_cost + 15;
    END IF;
    
    IF p_receita_federal THEN
        total_cost := total_cost + 5;
    END IF;
    
    IF p_simples_nacional THEN
        total_cost := total_cost + 5;
    END IF;
    
    IF p_cadastro_contribuintes THEN
        total_cost := total_cost + 5;
    END IF;
    
    IF p_geocodificacao THEN
        total_cost := total_cost + 5;
    END IF;
    
    IF p_suframa THEN
        total_cost := total_cost + 5;
    END IF;
    
    RETURN total_cost;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 9. TRIGGERS PARA AUDITORIA
-- =====================================================

-- Trigger para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Aplicar trigger nas tabelas relevantes
CREATE TRIGGER update_consultation_types_updated_at BEFORE UPDATE ON consultation_types 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_credits_updated_at BEFORE UPDATE ON user_credits 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_subscription_plans_updated_at BEFORE UPDATE ON subscription_plans 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_daily_analytics_updated_at BEFORE UPDATE ON daily_analytics 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- FINALIZAÇÃO
-- =====================================================

-- Criar registro inicial de créditos para usuários existentes
INSERT INTO user_credits (user_id, available_credits_cents, total_purchased_cents)
SELECT 
    u.id, 
    0, -- Começar com 0 créditos
    0  -- Nenhuma compra inicial
FROM users u
WHERE NOT EXISTS (
    SELECT 1 FROM user_credits uc WHERE uc.user_id = u.id
);

COMMIT;

-- Verificação final
SELECT 'Migração concluída com sucesso! ✅' as status;
SELECT 'Tabelas criadas:', count(*) FROM information_schema.tables 
WHERE table_schema = 'public' AND table_name IN (
    'consultation_types', 'consultations', 'consultation_details', 
    'user_credits', 'credit_transactions', 'daily_analytics'
);
