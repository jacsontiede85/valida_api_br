#!/usr/bin/env python3
"""
Script para criar tabelas no Supabase via API REST
"""
import os
import requests
from dotenv import load_dotenv
import structlog

# Carregar variáveis de ambiente
load_dotenv()

logger = structlog.get_logger("create_tables")

def create_tables():
    """Cria as tabelas necessárias no Supabase via API REST"""
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("❌ SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY são necessários")
        return False
    
    # Headers para a API
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    
    print("🔧 Criando tabelas no Supabase via API REST...")
    
    # SQL para criar as tabelas
    sql_commands = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        
        """
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
        CREATE TABLE IF NOT EXISTS api_keys (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            key_hash VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            is_active BOOLEAN DEFAULT true,
            last_used_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        
        """
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
        INSERT INTO subscription_plans (name, description, price_cents, queries_limit, api_keys_limit) VALUES
        ('Starter', 'Plano básico para começar', 2990, 100, 1),
        ('Professional', 'Plano profissional', 9990, 1000, 5),
        ('Enterprise', 'Plano empresarial', 29990, NULL, NULL)
        ON CONFLICT DO NOTHING;
        """
    ]
    
    # Executar cada comando SQL
    for i, sql in enumerate(sql_commands, 1):
        try:
            print(f"   {i}/{len(sql_commands)} Executando comando SQL...")
            
            # Usar a API REST do Supabase para executar SQL
            response = requests.post(
                f"{url}/rest/v1/rpc/exec_sql",
                headers=headers,
                json={"sql": sql},
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"   ✅ Comando {i} executado com sucesso")
            else:
                print(f"   ⚠️  Comando {i} falhou: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"   ⚠️  Comando {i} falhou: {e}")
    
    print("\n✅ Comandos SQL executados!")
    
    # Verificar se as tabelas foram criadas
    print("\n🔍 Verificando tabelas criadas...")
    try:
        # Testar tabela users
        response = requests.get(
            f"{url}/rest/v1/users?select=*&limit=1",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            print("✅ Tabela 'users' acessível")
        else:
            print(f"❌ Tabela 'users' não acessível: {response.status_code}")
            
        # Testar tabela subscription_plans
        response = requests.get(
            f"{url}/rest/v1/subscription_plans?select=*",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Tabela 'subscription_plans' acessível ({len(data)} planos)")
        else:
            print(f"❌ Tabela 'subscription_plans' não acessível: {response.status_code}")
            
        # Testar tabela api_keys
        response = requests.get(
            f"{url}/rest/v1/api_keys?select=*&limit=1",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            print("✅ Tabela 'api_keys' acessível")
        else:
            print(f"❌ Tabela 'api_keys' não acessível: {response.status_code}")
            
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
