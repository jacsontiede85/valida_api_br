-- Adicionar campo de senha na tabela users
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);

-- Adicionar campo para controle de sessão
ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;

-- Criar índice para melhorar performance de login
CREATE INDEX IF NOT EXISTS idx_users_email_password ON public.users(email, password_hash);

-- Adicionar comentários para documentação
COMMENT ON COLUMN public.users.password_hash IS 'Senha criptografada com bcrypt';
COMMENT ON COLUMN public.users.last_login IS 'Último login do usuário';
COMMENT ON COLUMN public.users.is_active IS 'Se a conta está ativa';
