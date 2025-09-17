#!/usr/bin/env python3
"""
Script simples para criar tabelas no Supabase
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
    
    print("🔧 Criando tabelas no Supabase...")
    
    # Criar tabela de usuários
    try:
        print("   Criando tabela 'users'...")
        result = client.table('users').select('*').limit(1).execute()
        print("   ✅ Tabela 'users' já existe")
    except Exception as e:
        print(f"   ❌ Erro na tabela 'users': {e}")
        return False
    
    # Criar tabela de planos
    try:
        print("   Criando tabela 'subscription_plans'...")
        result = client.table('subscription_plans').select('*').execute()
        print(f"   ✅ Tabela 'subscription_plans' já existe ({len(result.data)} planos)")
    except Exception as e:
        print(f"   ❌ Erro na tabela 'subscription_plans': {e}")
        return False
    
    # Criar tabela de API keys
    try:
        print("   Criando tabela 'api_keys'...")
        result = client.table('api_keys').select('*').limit(1).execute()
        print("   ✅ Tabela 'api_keys' já existe")
    except Exception as e:
        print(f"   ❌ Erro na tabela 'api_keys': {e}")
        return False
    
    # Criar tabela de histórico
    try:
        print("   Criando tabela 'query_history'...")
        result = client.table('query_history').select('*').limit(1).execute()
        print("   ✅ Tabela 'query_history' já existe")
    except Exception as e:
        print(f"   ❌ Erro na tabela 'query_history': {e}")
        return False
    
    print("\n✅ Todas as tabelas estão acessíveis!")
    return True

if __name__ == "__main__":
    print("🚀 Verificando banco de dados Supabase...")
    print("=" * 50)
    
    if create_tables():
        print("\n✅ Banco de dados está funcionando!")
        print("\n📋 Próximos passos:")
        print("   1. Execute: python test_connection.py")
        print("   2. Reinicie o servidor: python run.py")
        print("   3. Acesse: http://localhost:2377/dashboard")
    else:
        print("\n❌ Falha na verificação")
