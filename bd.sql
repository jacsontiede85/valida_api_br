-- =====================================================
-- SCHEMA MARIADB PARA VALIDA SAAS API
-- =====================================================
-- Migração de Supabase PostgreSQL para MariaDB Local
-- Criado em: 22/09/2025
-- Versão: 1.0
-- 
-- INSTRUÇÕES DE USO:
-- 1. Criar banco de dados: CREATE DATABASE valida_saas; -- CRIADO COM SUCESSO
-- 2. Usar banco: USE valida_saas; -- CRIADO COM SUCESSO
-- 3. Executar este script completo -- CRIADO COM SUCESSO
-- =====================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- =====================================================
-- 1. TABELA DE USUÁRIOS - PRINCIPAL
-- =====================================================

CREATE TABLE IF NOT EXISTS users (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NULL,
    last_login DATETIME NULL,
    is_active BOOLEAN DEFAULT TRUE,
    stripe_customer_id VARCHAR(255) NULL COMMENT 'ID do cliente no Stripe',
    credits DECIMAL(10,2) DEFAULT 0.00 COMMENT 'Saldo atual de créditos em reais',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    UNIQUE KEY unique_email (email),
    KEY idx_stripe_customer (stripe_customer_id),
    KEY idx_email (email),
    KEY idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Tabela principal de usuários do sistema SaaS';

-- =====================================================
-- 2. PLANOS DE ASSINATURA
-- =====================================================

CREATE TABLE IF NOT EXISTS subscription_plans (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    code VARCHAR(50) NOT NULL COMMENT 'Código único do plano (starter, pro, enterprise)',
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price_cents INTEGER NOT NULL COMMENT 'Preço em centavos (ex: 2990 = R$ 29,90)',
    credits_included_cents INTEGER NOT NULL DEFAULT 0 COMMENT 'Créditos inclusos em centavos',
    api_keys_limit INTEGER DEFAULT 1,
    queries_limit INTEGER NULL COMMENT 'Limite de consultas por mês (NULL = ilimitado)',
    is_active BOOLEAN DEFAULT TRUE,
    stripe_product_id VARCHAR(255) NULL,
    stripe_price_id VARCHAR(255) NULL,
    features JSON NULL COMMENT 'Recursos específicos do plano',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    UNIQUE KEY unique_code (code),
    KEY idx_active (is_active),
    KEY idx_price_cents (price_cents)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Planos de assinatura disponíveis no sistema';

-- =====================================================
-- 3. ASSINATURAS DOS USUÁRIOS
-- =====================================================

CREATE TABLE IF NOT EXISTS subscriptions (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    user_id CHAR(36) NOT NULL,
    plan_id CHAR(36) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    stripe_subscription_id VARCHAR(255) NULL,
    stripe_price_id VARCHAR(255) NULL,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    current_period_start DATETIME NULL,
    current_period_end DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    KEY idx_user_id (user_id),
    KEY idx_plan_id (plan_id),
    KEY idx_status (status),
    KEY idx_period_end (current_period_end),
    
    CONSTRAINT fk_subscriptions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_subscriptions_plan FOREIGN KEY (plan_id) REFERENCES subscription_plans(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Assinaturas ativas dos usuários';

-- =====================================================
-- 4. CHAVES DE API
-- =====================================================

CREATE TABLE IF NOT EXISTS api_keys (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    user_id CHAR(36) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT NULL,
    key_visible VARCHAR(255) NULL COMMENT 'Chave visível (rcp_...) - NULL após primeira visualização',
    key_hash VARCHAR(255) NOT NULL COMMENT 'Hash SHA256 da chave rcp_...',
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    UNIQUE KEY unique_key_hash (key_hash),
    KEY idx_user_id (user_id),
    KEY idx_active (is_active),
    KEY idx_last_used (last_used_at),
    
    CONSTRAINT fk_api_keys_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Chaves de API dos usuários para integração externa';

-- =====================================================
-- 5. TIPOS DE CONSULTA E CUSTOS
-- =====================================================

CREATE TABLE IF NOT EXISTS consultation_types (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    code VARCHAR(50) NOT NULL COMMENT 'Código único (protestos, receita_federal, etc)',
    name VARCHAR(100) NOT NULL,
    description TEXT,
    cost_cents INTEGER NOT NULL COMMENT 'Custo por consulta em centavos',
    provider VARCHAR(100) NULL COMMENT 'Provedor do serviço (resolve_cenprot, cnpja, etc)',
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    UNIQUE KEY unique_code (code),
    KEY idx_active (is_active),
    KEY idx_cost (cost_cents),
    KEY idx_provider (provider)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Tipos de consulta disponíveis e seus custos';

-- =====================================================
-- 6. HISTÓRICO DE CONSULTAS
-- =====================================================

CREATE TABLE IF NOT EXISTS consultations (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    user_id CHAR(36) NOT NULL,
    api_key_id CHAR(36) NULL,
    cnpj VARCHAR(18) NOT NULL,
    status VARCHAR(20) DEFAULT 'success',
    total_cost_cents INTEGER NOT NULL DEFAULT 0,
    response_time_ms INTEGER NULL,
    error_message TEXT NULL,
    cache_used BOOLEAN DEFAULT FALSE,
    client_ip VARCHAR(45) NULL COMMENT 'IP do cliente (IPv4 ou IPv6)',
    response_data JSON NULL COMMENT 'JSON completo retornado pela rota /api/v1/cnpj/consult',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    KEY idx_user_id (user_id),
    KEY idx_api_key_id (api_key_id),
    KEY idx_cnpj (cnpj),
    KEY idx_status (status),
    KEY idx_created_at (created_at),
    KEY idx_user_created (user_id, created_at),
    
    CONSTRAINT fk_consultations_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_consultations_api_key FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Histórico de consultas realizadas pelos usuários';

-- =====================================================
-- 7. DETALHES DAS CONSULTAS POR TIPO
-- =====================================================

CREATE TABLE IF NOT EXISTS consultation_details (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    consultation_id CHAR(36) NOT NULL,
    consultation_type_id CHAR(36) NOT NULL,
    cost_cents INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'success',
    response_data JSON NULL COMMENT 'Dados da resposta (se necessário)',
    error_message TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    KEY idx_consultation_id (consultation_id),
    KEY idx_type_id (consultation_type_id),
    KEY idx_status (status),
    
    CONSTRAINT fk_consultation_details_consultation FOREIGN KEY (consultation_id) REFERENCES consultations(id) ON DELETE CASCADE,
    CONSTRAINT fk_consultation_details_type FOREIGN KEY (consultation_type_id) REFERENCES consultation_types(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Detalhes específicos de cada tipo de consulta realizada';

-- =====================================================
-- 8. TRANSAÇÕES DE CRÉDITO (TABELA CRÍTICA)
-- =====================================================

CREATE TABLE IF NOT EXISTS credit_transactions (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    user_id CHAR(36) NOT NULL,
    consultation_id CHAR(36) NULL,
    type VARCHAR(20) NOT NULL COMMENT 'add, subtract, purchase, spend',
    amount_cents INTEGER NOT NULL COMMENT 'Valor da transação em centavos',
    balance_after_cents INTEGER NOT NULL COMMENT 'Saldo após a transação em centavos',
    description TEXT NOT NULL,
    stripe_payment_intent_id VARCHAR(255) NULL,
    stripe_invoice_id VARCHAR(255) NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    KEY idx_user_id (user_id),
    KEY idx_consultation_id (consultation_id),
    KEY idx_type (type),
    KEY idx_created_at (created_at),
    KEY idx_user_created (user_id, created_at),
    
    CONSTRAINT fk_credit_transactions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_credit_transactions_consultation FOREIGN KEY (consultation_id) REFERENCES consultations(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Histórico completo de transações de crédito';

-- =====================================================
-- 9. CRÉDITOS DOS USUÁRIOS (CONTROLE DE SALDO)
-- =====================================================

-- table user_credits descontinuada (drop realizado)

-- =====================================================
-- 10. ANALYTICS DIÁRIO - DESCONTINUADO
-- =====================================================
-- 
-- ✅ REMOVIDO: daily_analytics - tabela descontinuada por redundância
-- ✅ BENEFÍCIO: -1 INSERT por consulta (melhor performance)
-- ✅ ALTERNATIVA: Analytics on-demand via consultations quando necessário
--

-- =====================================================
-- 11. CUSTOS DOS SERVIÇOS
-- =====================================================
-- a table service_costs foi excluída, deve-se usar somente a table consultation_types
-- =====================================================
-- 12. LOGS DE WEBHOOKS STRIPE
-- =====================================================

CREATE TABLE IF NOT EXISTS stripe_webhook_logs (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    event_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    error_message TEXT NULL,
    webhook_data JSON NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_at DATETIME NULL,
    
    PRIMARY KEY (id),
    UNIQUE KEY unique_event_id (event_id),
    KEY idx_event_type (event_type),
    KEY idx_processed (processed),
    KEY idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Log de eventos recebidos via webhooks do Stripe';

-- =====================================================
-- 13. TRIGGERS PARA ATUALIZAÇÃO DE CRÉDITOS
-- =====================================================

DELIMITER $$

-- Trigger para atualizar saldo após inserir transação de crédito
CREATE TRIGGER trigger_update_user_credits
BEFORE INSERT ON credit_transactions
FOR EACH ROW
BEGIN
    DECLARE current_balance INT DEFAULT 0;
    
    SELECT COALESCE(SUM(
        CASE 
            WHEN type IN ('add', 'purchase') THEN amount_cents
            WHEN type IN ('subtract', 'spend', 'usage') THEN amount_cents
            ELSE 0
        END
    ), 0) INTO current_balance
    FROM credit_transactions 
    WHERE user_id = NEW.user_id;
    
    SET current_balance = current_balance + NEW.amount_cents;
    SET NEW.balance_after_cents = current_balance;
    
    UPDATE users 
    SET credits = current_balance / 100.0
    WHERE id = NEW.user_id;
END$$

DELIMITER ;

-- =====================================================
-- 14. VIEWS PARA RELATÓRIOS E CONSULTAS
-- =====================================================

-- View de resumo de créditos dos usuários
CREATE OR REPLACE VIEW user_credits_summary AS
SELECT 
    u.id,
    u.email,
    u.name,
    u.credits as current_credits,
    COALESCE(ct.total_purchased, 0) as total_purchased,
    COALESCE(ct.total_spent, 0) as total_spent,
    COALESCE(ct.transaction_count, 0) as transaction_count,
    u.created_at as user_created_at,
    COALESCE(ct.last_transaction, u.created_at) as last_transaction
FROM users u
LEFT JOIN (
    SELECT 
        user_id,
        SUM(CASE WHEN type IN ('add', 'purchase') THEN amount_cents ELSE 0 END) / 100.0 as total_purchased,
        SUM(CASE WHEN type IN ('subtract', 'spend') THEN amount_cents ELSE 0 END) / 100.0 as total_spent,
        COUNT(*) as transaction_count,
        MAX(created_at) as last_transaction
    FROM credit_transactions 
    GROUP BY user_id
) ct ON u.id = ct.user_id;

-- View de assinaturas ativas com detalhes dos planos
CREATE OR REPLACE VIEW active_subscriptions AS
SELECT 
    s.*,
    u.email,
    u.name as user_name,
    sp.name as plan_name,
    sp.code as plan_code,
    sp.price_cents,
    sp.credits_included_cents,
    sp.queries_limit,
    sp.api_keys_limit,
    sp.stripe_product_id,
    sp.stripe_price_id as plan_stripe_price_id
FROM subscriptions s
JOIN users u ON s.user_id = u.id
JOIN subscription_plans sp ON s.plan_id = sp.id
WHERE s.status = 'active';

-- ✅ REMOVIDO: monthly_user_analytics - view descontinuada junto com daily_analytics
-- Analytics mensais podem ser calculados on-demand via consultations quando necessário

-- =====================================================
-- 15. DADOS INICIAIS (SEED DATA)
-- =====================================================

-- Planos de assinatura padrão
INSERT INTO subscription_plans (code, name, description, price_cents, credits_included_cents, api_keys_limit, queries_limit) VALUES
('starter', 'Starter', 'Plano básico para começar', 2990, 1000, 1, 100),
('professional', 'Professional', 'Plano profissional', 9990, 5000, 5, 1000),
('enterprise', 'Enterprise', 'Plano empresarial', 29990, 15000, NULL, NULL)
ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;

-- Tipos de consulta padrão
INSERT INTO consultation_types (code, name, description, cost_cents, provider) VALUES
('protestos', 'Consulta de Protestos', 'Consulta de protestos no Resolve CenProt', 15, 'resolve_cenprot'),
('receita_federal', 'Receita Federal', 'Dados básicos da Receita Federal', 5, 'cnpja'),
('simples_nacional', 'Simples Nacional', 'Consulta situação no Simples Nacional', 3, 'cnpja'),
('cnae', 'CNAE', 'Consulta de atividades econômicas', 2, 'cnpja'),
('socios', 'Quadro Societário', 'Informações dos sócios', 5, 'cnpja'),
('endereco', 'Endereço Completo', 'Endereço detalhado da empresa', 2, 'cnpja')
ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;


-- =====================================================
-- 16. ÍNDICES ADICIONAIS PARA PERFORMANCE
-- =====================================================

-- Índices compostos otimizados
CREATE INDEX IF NOT EXISTS idx_consultations_user_date ON consultations(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_balance ON credit_transactions(user_id, balance_after_cents);
-- ✅ REMOVIDO: idx_daily_analytics_date_range - índice da daily_analytics descontinuada

-- Índices para queries de dashboard
CREATE INDEX IF NOT EXISTS idx_consultations_status_date ON consultations(status, created_at);
CREATE INDEX IF NOT EXISTS idx_consultations_cnpj_user ON consultations(cnpj, user_id);

-- =====================================================
-- 17. CONFIGURAÇÕES DE PERFORMANCE
-- =====================================================

-- Configurações recomendadas para o banco
SET GLOBAL innodb_buffer_pool_size = 1073741824;  -- 1GB
SET GLOBAL innodb_log_file_size = 268435456;      -- 256MB
SET GLOBAL innodb_flush_log_at_trx_commit = 1;
SET GLOBAL max_connections = 200;
SET GLOBAL query_cache_size = 67108864;           -- 64MB

-- =====================================================
-- 18. VERIFICAÇÕES E VALIDAÇÕES
-- =====================================================

-- Verificar se todas as tabelas foram criadas
SELECT 
    TABLE_NAME as 'Tabela',
    TABLE_ROWS as 'Registros',
    ROUND(((DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024), 2) as 'Tamanho (MB)'
FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME;

-- Verificar foreign keys
SELECT 
    TABLE_NAME,
    COLUMN_NAME,
    CONSTRAINT_NAME,
    REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE REFERENCED_TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME, COLUMN_NAME;

SET FOREIGN_KEY_CHECKS = 1;

-- =====================================================
-- FIM DO SCRIPT
-- =====================================================

SELECT '✅ SCHEMA MARIADB PARA VALIDA SAAS CRIADO COM SUCESSO!' as 'STATUS',
       NOW() as 'EXECUTADO_EM',
       DATABASE() as 'BANCO_DE_DADOS',
       VERSION() as 'VERSAO_MARIADB';

-- =====================================================
-- INFORMAÇÕES IMPORTANTES:
-- 
-- 1. Este schema é compatível com MariaDB 10.4+
-- 2. Usa UUIDs nativos do MariaDB (função UUID())
-- 3. Triggers implementados em MySQL/MariaDB syntax
-- 4. Views otimizadas para consultas de dashboard
-- 5. Índices criados para máxima performance
-- 6. Dados iniciais incluídos (seed data)
-- 
-- PRÓXIMOS PASSOS:
-- 1. Adaptar api/database/connection.py para PyMySQL
-- 2. Migrar dados do Supabase usando scripts Python
-- 3. Testar todas as funcionalidades
-- =====================================================

-- ✅ SCHEMA MARIADB PARA VALIDA SAAS CRIADO COM SUCESSO!   2025-09-22 22:00:56 valida_saas 10.9.7-MariaDB

-- Variavéis de ambiente no .env do projeto
-- MARIADB_HOST = 10.0.20.2
-- MARIADB_PORT = 7706
-- MARIADB_USER = 
-- MARIADB_PASS = 