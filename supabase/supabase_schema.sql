-- Schema SQL para o SaaS Valida API
-- Execute este SQL no SQL Editor do Supabase

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
    key VARCHAR(255) UNIQUE,  -- Chave original (rcp_...)
    key_hash VARCHAR(255) UNIQUE NOT NULL,  -- Hash da chave para validação
    name VARCHAR(100) NOT NULL,
    description TEXT,  -- Descrição opcional da chave
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

-- Inserir planos padrão
INSERT INTO subscription_plans (name, description, price_cents, queries_limit, api_keys_limit) VALUES
('Starter', 'Plano básico para começar', 2990, 100, 1),
('Professional', 'Plano profissional', 9990, 1000, 5),
('Enterprise', 'Plano empresarial', 29990, NULL, NULL)
ON CONFLICT DO NOTHING;

-- Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_query_history_user_id ON query_history(user_id);
CREATE INDEX IF NOT EXISTS idx_query_history_created_at ON query_history(created_at);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_query_analytics_user_date ON query_analytics(user_id, date);

-- Habilitar Row Level Security (RLS)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE query_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE query_analytics ENABLE ROW LEVEL SECURITY;

-- Políticas RLS para users
CREATE POLICY "Users can view own data" ON users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own data" ON users
    FOR UPDATE USING (auth.uid() = id);

-- Políticas RLS para subscriptions
CREATE POLICY "Users can view own subscriptions" ON subscriptions
    FOR SELECT USING (auth.uid() = user_id);

-- Políticas RLS para api_keys
CREATE POLICY "Users can view own api_keys" ON api_keys
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own api_keys" ON api_keys
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own api_keys" ON api_keys
    FOR UPDATE USING (auth.uid() = user_id);

-- Políticas RLS para query_history
CREATE POLICY "Users can view own query_history" ON query_history
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own query_history" ON query_history
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Políticas RLS para query_analytics
CREATE POLICY "Users can view own query_analytics" ON query_analytics
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own query_analytics" ON query_analytics
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Políticas RLS para subscription_plans (público para leitura)
CREATE POLICY "Anyone can view subscription_plans" ON subscription_plans
    FOR SELECT USING (true);
