#!/usr/bin/env python3
"""
Script para testar e configurar o banco de dados
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import structlog

# Carregar variáveis de ambiente
load_dotenv()

logger = structlog.get_logger("test_setup")

def test_and_setup():
    """Testa e configura o banco de dados"""
    
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
    
    print("🔍 Testando tabelas...")
    
    # Testar cada tabela
    tables = [
        "users",
        "subscription_plans", 
        "subscriptions",
        "api_keys",
        "query_history",
        "query_analytics"
    ]
    
    existing_tables = []
    
    for table in tables:
        try:
            result = client.table(table).select('*').limit(1).execute()
            print(f"✅ Tabela '{table}' existe")
            existing_tables.append(table)
        except Exception as e:
            print(f"❌ Tabela '{table}' não existe: {e}")
    
    if len(existing_tables) == len(tables):
        print("\n✅ Todas as tabelas existem!")
        
        # Verificar se há planos de assinatura
        try:
            plans = client.table('subscription_plans').select('*').execute()
            if len(plans.data) == 0:
                print("📝 Inserindo planos de assinatura...")
                plans_data = [
                    {
                        "name": "Starter",
                        "description": "Plano básico para começar",
                        "price_cents": 2990,
                        "queries_limit": 100,
                        "api_keys_limit": 1
                    },
                    {
                        "name": "Professional", 
                        "description": "Plano profissional",
                        "price_cents": 9990,
                        "queries_limit": 1000,
                        "api_keys_limit": 5
                    },
                    {
                        "name": "Enterprise",
                        "description": "Plano empresarial", 
                        "price_cents": 29990,
                        "queries_limit": None,
                        "api_keys_limit": None
                    }
                ]
                
                for plan in plans_data:
                    client.table('subscription_plans').insert(plan).execute()
                
                print("✅ Planos de assinatura inseridos!")
            else:
                print(f"✅ Planos de assinatura já existem ({len(plans.data)} planos)")
                
        except Exception as e:
            print(f"⚠️  Erro ao verificar/inserir planos: {e}")
        
        return True
    else:
        print(f"\n❌ Apenas {len(existing_tables)} de {len(tables)} tabelas existem")
        print("\n📋 Para criar as tabelas:")
        print("   1. Acesse o painel do Supabase: https://supabase.com/dashboard")
        print("   2. Vá em SQL Editor")
        print("   3. Execute o arquivo: supabase_schema.sql")
        print("   4. Execute novamente: python test_and_setup.py")
        return False

if __name__ == "__main__":
    print("🚀 Testando e configurando banco de dados...")
    print("=" * 50)
    
    if test_and_setup():
        print("\n✅ Banco de dados configurado com sucesso!")
        print("\n📋 Próximos passos:")
        print("   1. Execute: python test_connection.py")
        print("   2. Reinicie o servidor: python run.py")
        print("   3. Acesse: http://localhost:2377/dashboard")
    else:
        print("\n❌ Falha na configuração")
        print("\n📋 Instruções:")
        print("   1. Execute o SQL no painel do Supabase")
        print("   2. Execute novamente: python test_and_setup.py")
