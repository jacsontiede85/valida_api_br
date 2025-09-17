-- Adicionar coluna status na tabela query_history
-- Execute este SQL no SQL Editor do Supabase

-- Adicionar coluna status
ALTER TABLE query_history 
ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'success';

-- Atualizar registros existentes para ter status baseado no response_status
UPDATE query_history 
SET status = CASE 
    WHEN response_status < 400 THEN 'success'
    ELSE 'error'
END
WHERE status IS NULL;

-- Criar índice para performance
CREATE INDEX IF NOT EXISTS idx_query_history_status ON query_history(status);
CREATE INDEX IF NOT EXISTS idx_query_history_user_status ON query_history(user_id, status);

-- Comentário da tabela
COMMENT ON COLUMN query_history.status IS 'Status da consulta: success ou error';
