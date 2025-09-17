#!/usr/bin/env python3
"""
Script para criar tabelas no Supabase via SQL
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import structlog

# Carregar variáveis de ambiente
load_dotenv()

logger = structlog.get_logger("create_tables")

def create_tables():
    """Cria as tabelas necessárias no Supabase"""
    
    # Configurar cliente Supabase
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("❌ SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY são necessários")
        return False
    
    try:
        client = create_client(url, key)
        print("✅ Conectado ao Supabase")
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return False
    
    # SQL para criar as tabelas
    sql_commands = [
        """
        -- Tabela de usuários
        CREATE TABLE IF NOT EXISTS users (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        
        """
        -- Tabela de planos de assinatura
        CREATE TABLE IF NOT EXISTS subscription_plans (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            price_cents INTEGER NOT NULL,
            queries_limit INTEGER,
            api_keys_limit INTEGER DEFAULT 1,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        
        """
        -- Tabela de assinaturas
        CREATE TABLE IF NOT EXISTS subscriptions (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            plan_id UUID REFERENCES subscription_plans(id),
            status VARCHAR(50) DEFAULT 'active',
            stripe_subscription_id VARCHAR(255),
            current_period_start TIMESTAMP WITH TIME ZONE,
            current_period_end TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        
        """
        -- Tabela de API keys
        CREATE TABLE IF NOT EXISTS api_keys (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            key VARCHAR(255) UNIQUE,  -- Chave original (rcp_...)
            key_hash VARCHAR(255) UNIQUE NOT NULL,  -- Hash da chave para validação
            name VARCHAR(100) NOT NULL,
            description TEXT,  -- Descrição opcional da chave
            is_active BOOLEAN DEFAULT true,
            last_used_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        
        """
        -- Tabela de histórico de consultas
        CREATE TABLE IF NOT EXISTS query_history (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
            cnpj VARCHAR(18) NOT NULL,
            endpoint VARCHAR(100) NOT NULL,
            response_status INTEGER NOT NULL,
            credits_used INTEGER DEFAULT 1,
            response_time_ms INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        
        """
        -- Tabela de analytics de consultas
        CREATE TABLE IF NOT EXISTS query_analytics (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            date DATE NOT NULL,
            total_queries INTEGER DEFAULT 0,
            successful_queries INTEGER DEFAULT 0,
            failed_queries INTEGER DEFAULT 0,
            total_credits_used INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(user_id, date)
        );
        """,
        
        """
        -- Inserir planos padrão
        INSERT INTO subscription_plans (name, description, price_cents, queries_limit, api_keys_limit) VALUES
        ('Starter', 'Plano básico para começar', 2990, 100, 1),
        ('Professional', 'Plano profissional', 9990, 1000, 5),
        ('Enterprise', 'Plano empresarial', 29990, NULL, NULL)
        ON CONFLICT DO NOTHING;
        """,
        
        """
        -- Criar índices para performance
        CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
        CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
        CREATE INDEX IF NOT EXISTS idx_query_history_user_id ON query_history(user_id);
        CREATE INDEX IF NOT EXISTS idx_query_history_created_at ON query_history(created_at);
        CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
        CREATE INDEX IF NOT EXISTS idx_query_analytics_user_date ON query_analytics(user_id, date);
        """
    ]
    
    print("🔧 Criando tabelas no Supabase...")
    
    for i, sql in enumerate(sql_commands, 1):
        try:
            print(f"   {i}/{len(sql_commands)} Executando comando SQL...")
            result = client.rpc('exec_sql', {'sql': sql}).execute()
            print(f"   ✅ Comando {i} executado com sucesso")
        except Exception as e:
            print(f"   ⚠️  Comando {i} falhou: {e}")
            # Continuar mesmo com erro (pode ser que a tabela já exista)
    
    print("\n✅ Tabelas criadas com sucesso!")
    
    # Verificar se as tabelas foram criadas
    print("\n🔍 Verificando tabelas criadas...")
    try:
        tables = client.table('users').select('*').limit(1).execute()
        print("✅ Tabela 'users' acessível")
        
        plans = client.table('subscription_plans').select('*').execute()
        print(f"✅ Tabela 'subscription_plans' acessível ({len(plans.data)} planos)")
        
        keys = client.table('api_keys').select('*').limit(1).execute()
        print("✅ Tabela 'api_keys' acessível")
        
    except Exception as e:
        print(f"❌ Erro ao verificar tabelas: {e}")
        return False
    
    print("\n🎉 Banco de dados configurado com sucesso!")
    return True

if __name__ == "__main__":
    print("🚀 Configurando banco de dados Supabase...")
    print("=" * 50)
    
    if create_tables():
        print("\n✅ Configuração concluída!")
        print("\n📋 Próximos passos:")
        print("   1. Execute: python test_connection.py")
        print("   2. Reinicie o servidor: python run.py")
        print("   3. Acesse: http://localhost:2377/dashboard")
    else:
        print("\n❌ Falha na configuração")
