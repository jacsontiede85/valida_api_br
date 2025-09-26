-- Adicionar campo para limite de alerta de créditos na tabela users
ALTER TABLE users 
ADD COLUMN credit_alert_threshold_cents INT DEFAULT 500 COMMENT 'Limite de alerta de créditos em centavos (padrão: R$ 5,00)';

-- Atualizar usuários existentes com valor padrão
UPDATE users 
SET credit_alert_threshold_cents = 500 
WHERE credit_alert_threshold_cents IS NULL;
