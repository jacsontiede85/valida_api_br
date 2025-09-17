"""
Script para configurar o banco de dados do SaaS
"""
import os
import sys
import subprocess
from pathlib import Path

def create_env_file():
    """Cria arquivo .env com configurações padrão"""
    env_content = """# Configurações do Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
SUPABASE_DB_PASSWORD=your-database-password

# URL de conexão direta do PostgreSQL (opcional)
DATABASE_URL=postgresql://postgres.your-project:your-password@db.your-project.supabase.co:5432/postgres

# Configurações JWT (não necessárias com Supabase Auth)
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production

# Configurações Stripe
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Configurações do Servidor
SAAS_PORT=2377

# Configurações do Frontend
NEXT_PUBLIC_API_URL=http://localhost:2377/api/v1
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
"""
    
    env_path = Path(".env")
    if not env_path.exists():
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)
        print("✅ Arquivo .env criado com configurações padrão")
        print("⚠️  Configure as credenciais do Supabase no arquivo .env")
    else:
        print("✅ Arquivo .env já existe")

def install_dependencies():
    """Instala dependências necessárias"""
    print("📦 Instalando dependências...")
    
    # Instalar Prisma
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "prisma"], check=True)
        print("✅ Prisma instalado")
    except subprocess.CalledProcessError:
        print("❌ Erro ao instalar Prisma")
        return False
    
    return True

def setup_prisma():
    """Configura e executa migrações do Prisma"""
    print("🔧 Configurando Prisma...")
    
    # Navegar para o diretório do sistema
    sistema_path = Path("sistema")
    if not sistema_path.exists():
        print("❌ Diretório 'sistema' não encontrado")
        return False
    
    os.chdir(sistema_path)
    
    try:
        # Gerar cliente Prisma
        print("📝 Gerando cliente Prisma...")
        subprocess.run(["prisma", "generate"], check=True)
        print("✅ Cliente Prisma gerado")
        
        # Executar migrações (apenas se DATABASE_URL estiver configurado)
        database_url = os.getenv("DATABASE_URL")
        if database_url and not database_url.startswith("postgresql://postgres.your-project"):
            print("🚀 Executando migrações...")
            subprocess.run(["prisma", "db", "push"], check=True)
            print("✅ Migrações executadas com sucesso")
        else:
            print("⚠️  DATABASE_URL não configurado, pulando migrações")
            print("   Configure as credenciais do Supabase no arquivo .env")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao configurar Prisma: {e}")
        return False
    except FileNotFoundError:
        print("❌ Prisma CLI não encontrado. Instale com: pip install prisma")
        return False
    finally:
        # Voltar para o diretório raiz
        os.chdir("..")

def create_supabase_tables():
    """Cria tabelas diretamente no Supabase usando SQL"""
    print("🗄️  Criando tabelas no Supabase...")
    
    # SQL para criar as tabelas
    sql_script = """
-- Tabela de usuários
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    company VARCHAR(255),
    subscription_plan VARCHAR(50) DEFAULT 'free',
    subscription_status VARCHAR(50) DEFAULT 'inactive',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de API keys
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used TIMESTAMP WITH TIME ZONE,
    revoked_at TIMESTAMP WITH TIME ZONE
);

-- Tabela de assinaturas
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    plan VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'inactive',
    current_period_start TIMESTAMP WITH TIME ZONE,
    current_period_end TIMESTAMP WITH TIME ZONE,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de histórico de consultas
CREATE TABLE IF NOT EXISTS api_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    api_key_id UUID REFERENCES api_keys(id),
    cnpj VARCHAR(18) NOT NULL,
    success BOOLEAN NOT NULL,
    has_protests BOOLEAN DEFAULT FALSE,
    total_protests INTEGER DEFAULT 0,
    response_time_ms INTEGER,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de faturas
CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL, -- em centavos
    currency VARCHAR(3) DEFAULT 'BRL',
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    paid_at TIMESTAMP WITH TIME ZONE,
    invoice_url TEXT
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_api_requests_user_id ON api_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_api_requests_created_at ON api_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_api_requests_cnpj ON api_requests(cnpj);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
"""
    
    print("📋 SQL script preparado para execução no Supabase")
    print("   Execute este script no SQL Editor do Supabase:")
    print("   https://supabase.com/dashboard/project/[seu-projeto]/sql")
    print("\n" + "="*50)
    print(sql_script)
    print("="*50)
    
    return True

def main():
    """Função principal"""
    print("🚀 Configurando banco de dados do SaaS Valida...")
    print("="*50)
    
    # 1. Criar arquivo .env
    create_env_file()
    
    # 2. Instalar dependências
    if not install_dependencies():
        print("❌ Falha na instalação de dependências")
        return False
    
    # 3. Configurar Prisma
    if not setup_prisma():
        print("❌ Falha na configuração do Prisma")
        return False
    
    # 4. Criar tabelas no Supabase
    create_supabase_tables()
    
    print("\n" + "="*50)
    print("✅ Configuração do banco de dados concluída!")
    print("\n📋 Próximos passos:")
    print("1. Configure as credenciais do Supabase no arquivo .env")
    print("2. Execute o SQL script no Supabase Dashboard")
    print("3. Teste a conexão com: python test_connection.py")
    print("4. Execute o servidor: python run.py")
    
    return True

if __name__ == "__main__":
    main()
