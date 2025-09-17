-- =====================================================
-- CONFIGURAÇÃO COMPLETA DO BANCO DE DADOS - SAAS VALIDA API
-- =====================================================
-- Execute este SQL no SQL Editor do Supabase
-- Painel: https://supabase.com/dashboard > SQL Editor

-- =====================================================
-- 1. CRIAÇÃO DAS TABELAS
-- =====================================================

-- Tabela de usuários
CREATE TABLE IF NOT EXISTS users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de planos de assinatura
CREATE TABLE IF NOT EXISTS subscription_plans (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price_cents INTEGER NOT NULL,
    queries_limit INTEGER,
    api_keys_limit INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de assinaturas
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    plan_id UUID REFERENCES subscription_plans(id),
    status VARCHAR(50) DEFAULT 'active',
    stripe_subscription_id VARCHAR(255),
    current_period_start TIMESTAMP WITH TIME ZONE,
    current_period_end TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de API keys
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de histórico de consultas
CREATE TABLE IF NOT EXISTS query_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    cnpj VARCHAR(18) NOT NULL,
    endpoint VARCHAR(100) NOT NULL,
    response_status INTEGER NOT NULL,
    credits_used INTEGER DEFAULT 1,
    response_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de analytics de consultas
CREATE TABLE IF NOT EXISTS query_analytics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    total_queries INTEGER DEFAULT 0,
    successful_queries INTEGER DEFAULT 0,
    failed_queries INTEGER DEFAULT 0,
    total_credits_used INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, date)
);

-- =====================================================
-- 2. ÍNDICES PARA PERFORMANCE
-- =====================================================

-- Índices para api_keys
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active);

-- Índices para query_history
CREATE INDEX IF NOT EXISTS idx_query_history_user_id ON query_history(user_id);
CREATE INDEX IF NOT EXISTS idx_query_history_created_at ON query_history(created_at);
CREATE INDEX IF NOT EXISTS idx_query_history_cnpj ON query_history(cnpj);
CREATE INDEX IF NOT EXISTS idx_query_history_api_key_id ON query_history(api_key_id);

-- Índices para subscriptions
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_plan_id ON subscriptions(plan_id);

-- Índices para query_analytics
CREATE INDEX IF NOT EXISTS idx_query_analytics_user_date ON query_analytics(user_id, date);
CREATE INDEX IF NOT EXISTS idx_query_analytics_date ON query_analytics(date);

-- =====================================================
-- 3. DADOS INICIAIS
-- =====================================================

-- Inserir planos de assinatura padrão
INSERT INTO subscription_plans (name, description, price_cents, queries_limit, api_keys_limit) VALUES
('Starter', 'Plano básico para começar', 2990, 100, 1),
('Professional', 'Plano profissional com mais recursos', 9990, 1000, 5),
('Enterprise', 'Plano empresarial com recursos ilimitados', 29990, NULL, NULL)
ON CONFLICT DO NOTHING;

-- =====================================================
-- 4. ROW LEVEL SECURITY (RLS)
-- =====================================================

-- Habilitar RLS em todas as tabelas
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE query_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE query_analytics ENABLE ROW LEVEL SECURITY;

-- subscription_plans é público para leitura
ALTER TABLE subscription_plans ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- 5. POLÍTICAS RLS
-- =====================================================

-- Políticas para users
CREATE POLICY "Users can view own data" ON users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own data" ON users
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can insert own data" ON users
    FOR INSERT WITH CHECK (auth.uid() = id);

-- Políticas para subscriptions
CREATE POLICY "Users can view own subscriptions" ON subscriptions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own subscriptions" ON subscriptions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own subscriptions" ON subscriptions
    FOR UPDATE USING (auth.uid() = user_id);

-- Políticas para api_keys
CREATE POLICY "Users can view own api_keys" ON api_keys
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own api_keys" ON api_keys
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own api_keys" ON api_keys
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own api_keys" ON api_keys
    FOR DELETE USING (auth.uid() = user_id);

-- Políticas para query_history
CREATE POLICY "Users can view own query_history" ON query_history
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own query_history" ON query_history
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Políticas para query_analytics
CREATE POLICY "Users can view own query_analytics" ON query_analytics
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own query_analytics" ON query_analytics
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own query_analytics" ON query_analytics
    FOR UPDATE USING (auth.uid() = user_id);

-- Políticas para subscription_plans (público para leitura)
CREATE POLICY "Anyone can view subscription_plans" ON subscription_plans
    FOR SELECT USING (true);

-- =====================================================
-- 6. FUNÇÕES AUXILIARES
-- =====================================================

-- Função para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para updated_at
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_subscriptions_updated_at 
    BEFORE UPDATE ON subscriptions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Função para registrar uso de API key
CREATE OR REPLACE FUNCTION register_api_usage(
    p_user_id UUID,
    p_api_key_id UUID,
    p_cnpj VARCHAR(18),
    p_endpoint VARCHAR(100),
    p_response_status INTEGER,
    p_credits_used INTEGER DEFAULT 1,
    p_response_time_ms INTEGER DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    -- Inserir no histórico
    INSERT INTO query_history (
        user_id, api_key_id, cnpj, endpoint, 
        response_status, credits_used, response_time_ms
    ) VALUES (
        p_user_id, p_api_key_id, p_cnpj, p_endpoint,
        p_response_status, p_credits_used, p_response_time_ms
    );
    
    -- Atualizar analytics do dia
    INSERT INTO query_analytics (
        user_id, date, total_queries, successful_queries, 
        failed_queries, total_credits_used
    ) VALUES (
        p_user_id, CURRENT_DATE, 1, 
        CASE WHEN p_response_status < 400 THEN 1 ELSE 0 END,
        CASE WHEN p_response_status >= 400 THEN 1 ELSE 0 END,
        p_credits_used
    )
    ON CONFLICT (user_id, date) DO UPDATE SET
        total_queries = query_analytics.total_queries + 1,
        successful_queries = query_analytics.successful_queries + 
            CASE WHEN p_response_status < 400 THEN 1 ELSE 0 END,
        failed_queries = query_analytics.failed_queries + 
            CASE WHEN p_response_status >= 400 THEN 1 ELSE 0 END,
        total_credits_used = query_analytics.total_credits_used + p_credits_used;
    
    -- Atualizar last_used_at da API key
    UPDATE api_keys 
    SET last_used_at = NOW() 
    WHERE id = p_api_key_id;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 7. DADOS DE TESTE (OPCIONAL)
-- =====================================================

-- Inserir usuário de teste (opcional - remover em produção)
INSERT INTO users (id, email, name) VALUES 
('00000000-0000-0000-0000-000000000001', 'teste@valida.com.br', 'Usuário Teste')
ON CONFLICT (id) DO NOTHING;

-- Inserir assinatura de teste
INSERT INTO subscriptions (user_id, plan_id, status) 
SELECT 
    '00000000-0000-0000-0000-000000000001',
    id,
    'active'
FROM subscription_plans 
WHERE name = 'Starter'
ON CONFLICT DO NOTHING;

-- =====================================================
-- 8. VERIFICAÇÃO FINAL
-- =====================================================

-- Verificar se as tabelas foram criadas
SELECT 
    table_name,
    CASE 
        WHEN table_name IN ('users', 'subscription_plans', 'subscriptions', 'api_keys', 'query_history', 'query_analytics') 
        THEN '✅' 
        ELSE '❌' 
    END as status
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('users', 'subscription_plans', 'subscriptions', 'api_keys', 'query_history', 'query_analytics')
ORDER BY table_name;

-- Verificar planos inseridos
SELECT 'Planos de assinatura:' as info;
SELECT name, description, price_cents, queries_limit, api_keys_limit 
FROM subscription_plans 
ORDER BY price_cents;

-- =====================================================
-- FIM DA CONFIGURAÇÃO
-- =====================================================

-- Após executar este SQL:
-- 1. Execute: python test_and_setup.py
-- 2. Execute: python test_connection.py  
-- 3. Reinicie o servidor: python run.py
-- 4. Acesse: http://localhost:2377/dashboard
