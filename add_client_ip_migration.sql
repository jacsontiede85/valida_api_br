-- =====================================================
-- MIGRAÇÃO: Adicionar campo client_ip na tabela consultations
-- =====================================================
-- Adiciona campo para armazenar IP do cliente nas consultas
-- Execute este SQL no SQL Editor do Supabase

-- 1. Adicionar campo client_ip na tabela consultations
ALTER TABLE consultations 
ADD COLUMN IF NOT EXISTS client_ip VARCHAR(45);  -- VARCHAR(45) suporta IPv4 e IPv6

-- 2. Adicionar comentário explicativo
COMMENT ON COLUMN consultations.client_ip IS 'Endereço IP do cliente que fez a requisição (IPv4 ou IPv6)';

-- 3. Criar índice para consultas por IP (opcional, para análises)
CREATE INDEX IF NOT EXISTS idx_consultations_client_ip 
ON consultations (client_ip) 
WHERE client_ip IS NOT NULL;

-- 4. Criar índice composto para consultas de auditoria
CREATE INDEX IF NOT EXISTS idx_consultations_user_ip_date 
ON consultations (user_id, client_ip, created_at) 
WHERE client_ip IS NOT NULL;

-- =====================================================
-- VERIFICAÇÕES
-- =====================================================

-- 5. Verificar se a coluna foi criada
SELECT 
    column_name, 
    data_type, 
    character_maximum_length, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'consultations' 
  AND column_name = 'client_ip';

-- 6. Verificar comentário da coluna (PostgreSQL específico)
SELECT 
    c.column_name,
    pgd.description as column_comment
FROM information_schema.columns c
LEFT JOIN pg_class pgc ON pgc.relname = c.table_name
LEFT JOIN pg_description pgd ON pgd.objoid = pgc.oid 
    AND pgd.objsubid = c.ordinal_position
WHERE c.table_name = 'consultations' 
  AND c.column_name = 'client_ip';

-- 7. Exibir estrutura completa da tabela
SELECT 
    column_name,
    data_type,
    character_maximum_length,
    is_nullable,
    column_default,
    ordinal_position
FROM information_schema.columns 
WHERE table_name = 'consultations' 
ORDER BY ordinal_position;

-- 8. Verificar índices criados
SELECT 
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'consultations' 
  AND (indexname LIKE '%client_ip%' OR indexname LIKE '%user_ip_date%');

-- =====================================================
-- TESTE DE FUNCIONALIDADE
-- =====================================================

-- 9. Consultar últimas 5 consultas com IP (após implementação)
SELECT 
    cnpj,
    client_ip,
    user_id,
    total_cost_cents,
    created_at,
    status
FROM consultations 
WHERE client_ip IS NOT NULL
ORDER BY created_at DESC 
LIMIT 5;

-- 10. Estatísticas de IPs únicos
SELECT 
    client_ip,
    COUNT(*) as total_consultas,
    MIN(created_at) as primeira_consulta,
    MAX(created_at) as ultima_consulta
FROM consultations 
WHERE client_ip IS NOT NULL
GROUP BY client_ip
ORDER BY total_consultas DESC
LIMIT 10;

-- =====================================================
-- MIGRAÇÃO COMPLETA!
-- =====================================================
-- Execute este script completo no SQL Editor do Supabase
-- Todas as verificações são incluídas para confirmar sucesso
