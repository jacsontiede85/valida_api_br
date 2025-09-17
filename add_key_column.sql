-- SQL para adicionar coluna 'key' na tabela api_keys
-- Execute este SQL no SQL Editor do Supabase Dashboard

-- 1. Adicionar coluna 'key' na tabela api_keys
ALTER TABLE api_keys 
ADD COLUMN IF NOT EXISTS key VARCHAR(255);

-- 2. Adicionar coluna 'description' se não existir (já existe, mas por segurança)
ALTER TABLE api_keys 
ADD COLUMN IF NOT EXISTS description TEXT;

-- 3. Criar índice para a coluna 'key' para melhor performance
CREATE INDEX IF NOT EXISTS idx_api_keys_key ON api_keys(key);

-- 4. Verificar se as colunas foram adicionadas
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'api_keys' 
ORDER BY ordinal_position;

-- 5. Verificar estrutura atual da tabela
SELECT * FROM api_keys LIMIT 1;
