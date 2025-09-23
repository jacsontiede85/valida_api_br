-- Adicionar campo provider à tabela consultation_types e atualizar dados existentes
-- Baseado nos dados atuais da tabela

-- 1. Adicionar a coluna provider
ALTER TABLE consultation_types 
ADD COLUMN provider VARCHAR(100) NULL COMMENT 'Provedor do serviço (resolve_cenprot, cnpja, etc)' 
AFTER cost_cents;

-- 2. Adicionar índice para o campo provider
ALTER TABLE consultation_types ADD KEY idx_provider (provider);

-- 3. Atualizar dados existentes com os valores corretos de provider
UPDATE consultation_types SET provider = 'cnpja' WHERE code = 'receita_federal';
UPDATE consultation_types SET provider = 'cnpja' WHERE code = 'simples_nacional';  
UPDATE consultation_types SET provider = 'cnpja' WHERE code = 'suframa';
UPDATE consultation_types SET provider = 'cnpja' WHERE code = 'geocodificacao';
UPDATE consultation_types SET provider = 'resolve_cenprot' WHERE code = 'protestos';
UPDATE consultation_types SET provider = 'cnpja' WHERE code = 'cadastro_contribuintes';

-- 4. Verificar se as atualizações funcionaram
SELECT code, name, cost_cents, provider 
FROM consultation_types 
ORDER BY code;

-- 5. Mostrar estatísticas
SELECT 
    provider,
    COUNT(*) as total_types,
    AVG(cost_cents) as avg_cost_cents,
    MIN(cost_cents) as min_cost_cents,
    MAX(cost_cents) as max_cost_cents
FROM consultation_types 
WHERE provider IS NOT NULL
GROUP BY provider;

-- 6. Verificar estrutura da tabela atualizada
DESCRIBE consultation_types;
