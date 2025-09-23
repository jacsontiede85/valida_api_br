-- =====================================================
-- SCRIPT PARA EXTRAIR ESTRUTURA DO BANCO SUPABASE
-- =====================================================
-- Execute este SQL no SQL Editor do Supabase para obter a estrutura atual
-- Copie os resultados para o arquivo current_structure.sql

-- =====================================================
-- 1. ESTRUTURA DAS TABELAS PRINCIPAIS
-- =====================================================

SELECT 
    '=== ESTRUTURA DAS TABELAS ===' as secao,
    '' as table_name,
    '' as column_name,
    '' as data_type,
    '' as is_nullable,
    '' as column_default
UNION ALL
SELECT 
    '📋 TABELA' as secao,
    table_name,
    column_name,
    data_type,
    is_nullable,
    COALESCE(column_default, 'NULL') as column_default
FROM information_schema.columns 
WHERE table_schema = 'public'
AND table_name IN (
    'users', 'subscriptions', 'subscription_plans', 
    'api_keys', 'credit_transactions', 'service_costs', 
    'stripe_webhook_logs'
)
ORDER BY 
    CASE WHEN secao = '=== ESTRUTURA DAS TABELAS ===' THEN 0 ELSE 1 END,
    table_name, 
    ordinal_position;

-- =====================================================
-- 2. CONSTRAINTS E CHAVES
-- =====================================================

SELECT 
    '=== CONSTRAINTS ===' as info,
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type,
    kcu.column_name,
    COALESCE(ccu.table_name, '') AS foreign_table,
    COALESCE(ccu.column_name, '') AS foreign_column
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
LEFT JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.table_schema = 'public'
AND tc.table_name IN (
    'users', 'subscriptions', 'subscription_plans', 
    'api_keys', 'credit_transactions', 'service_costs', 
    'stripe_webhook_logs'
)
ORDER BY tc.table_name, tc.constraint_name;

-- =====================================================
-- 3. ÍNDICES
-- =====================================================

SELECT 
    '=== ÍNDICES ===' as info,
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE schemaname = 'public'
AND tablename IN (
    'users', 'subscriptions', 'subscription_plans', 
    'api_keys', 'credit_transactions', 'service_costs', 
    'stripe_webhook_logs'
)
ORDER BY tablename, indexname;

-- =====================================================
-- 4. INFORMAÇÕES ESPECÍFICAS - CREDIT_TRANSACTIONS
-- =====================================================

SELECT 
    '=== CREDIT_TRANSACTIONS DETALHADA ===' as info,
    column_name,
    data_type,
    is_nullable,
    column_default,
    character_maximum_length,
    numeric_precision,
    numeric_scale
FROM information_schema.columns 
WHERE table_schema = 'public'
AND table_name = 'credit_transactions'
ORDER BY ordinal_position;

-- =====================================================
-- 5. VERIFICAR SE TABELAS EXISTEM
-- =====================================================

SELECT 
    '=== VERIFICAÇÃO DE TABELAS ===' as info,
    table_name,
    CASE 
        WHEN table_name IS NOT NULL THEN '✅ EXISTE' 
        ELSE '❌ NÃO EXISTE' 
    END as status
FROM information_schema.tables 
WHERE table_schema = 'public'
AND table_name IN (
    'users', 'subscriptions', 'subscription_plans', 
    'api_keys', 'credit_transactions', 'service_costs', 
    'stripe_webhook_logs'
);

-- =====================================================
-- 6. CONTAR REGISTROS
-- =====================================================

-- NOTA: Execute cada SELECT separadamente para evitar erros

-- SELECT 'users' as tabela, COUNT(*) as registros FROM users;
-- SELECT 'subscriptions' as tabela, COUNT(*) as registros FROM subscriptions;
-- SELECT 'subscription_plans' as tabela, COUNT(*) as registros FROM subscription_plans;
-- SELECT 'api_keys' as tabela, COUNT(*) as registros FROM api_keys;
-- SELECT 'credit_transactions' as tabela, COUNT(*) as registros FROM credit_transactions;
-- SELECT 'service_costs' as tabela, COUNT(*) as registros FROM service_costs;
-- SELECT 'stripe_webhook_logs' as tabela, COUNT(*) as registros FROM stripe_webhook_logs;

-- =====================================================
-- 7. DADOS DE EXEMPLO - CREDIT_TRANSACTIONS
-- =====================================================

SELECT 
    '=== EXEMPLO CREDIT_TRANSACTIONS ===' as info,
    id,
    user_id,
    type,
    amount_cents,
    description,
    created_at
FROM credit_transactions 
LIMIT 3;
