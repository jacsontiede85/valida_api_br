-- =====================================================
-- INVESTIGAÇÃO ESPECÍFICA - CREDIT_TRANSACTIONS
-- =====================================================
-- Execute no SQL Editor do Supabase para descobrir a estrutura real

-- 1. ESTRUTURA COMPLETA DA TABELA
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default,
    character_maximum_length,
    numeric_precision,
    numeric_scale,
    ordinal_position
FROM information_schema.columns 
WHERE table_schema = 'public'
AND table_name = 'credit_transactions'
ORDER BY ordinal_position;

-- 2. CONSTRAINTS NOT NULL
SELECT 
    column_name,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public'
AND table_name = 'credit_transactions'
AND is_nullable = 'NO'
ORDER BY ordinal_position;

-- 3. VER DADOS EXISTENTES (se houver)
-- SELECT * FROM credit_transactions LIMIT 5;

-- 4. VERIFICAR SE EXISTE balance_after_cents
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public'
AND table_name = 'credit_transactions'
AND column_name LIKE '%balance%'
ORDER BY column_name;

-- 5. VERIFICAR TODAS AS COLUNAS COM "cents"
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public'
AND table_name = 'credit_transactions'
AND column_name LIKE '%cents%'
ORDER BY column_name;
