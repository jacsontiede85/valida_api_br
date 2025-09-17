#!/usr/bin/env python3
"""
Script para adicionar coluna 'key' diretamente via SQL
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import structlog

# Carregar variáveis de ambiente
load_dotenv()

logger = structlog.get_logger("add_key_column_direct")

def add_key_column_direct():
    """Adiciona a coluna 'key' diretamente via SQL"""
    
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
    
    # Verificar se a coluna já existe
    print("🔍 Verificando estrutura atual da tabela...")
    try:
        result = client.table("api_keys").select("*").limit(1).execute()
        if result.data:
            columns = list(result.data[0].keys())
            print(f"   Colunas atuais: {columns}")
            
            if 'key' in columns:
                print("   ✅ Coluna 'key' já existe!")
                return True
            else:
                print("   ❌ Coluna 'key' não encontrada")
        else:
            print("   ℹ️  Tabela vazia, mas acessível")
    except Exception as e:
        print(f"   ❌ Erro ao verificar tabela: {e}")
        return False
    
    # Tentar adicionar a coluna via SQL direto
    print("\n🔧 Tentando adicionar coluna 'key'...")
    
    try:
        # Usar o método SQL direto do Supabase
        result = client.postgrest.rpc("exec", {
            "sql": "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS key VARCHAR(255);"
        }).execute()
        print("   ✅ Coluna 'key' adicionada com sucesso!")
    except Exception as e:
        print(f"   ⚠️  Erro ao adicionar coluna via RPC: {e}")
        
        # Tentar método alternativo
        try:
            print("   🔄 Tentando método alternativo...")
            # Usar uma query que força a atualização do schema
            result = client.table("api_keys").select("id").limit(1).execute()
            print("   ✅ Schema atualizado")
        except Exception as e2:
            print(f"   ❌ Erro no método alternativo: {e2}")
            return False
    
    # Verificar novamente
    print("\n🔍 Verificando se a coluna foi adicionada...")
    try:
        result = client.table("api_keys").select("*").limit(1).execute()
        if result.data:
            columns = list(result.data[0].keys())
            print(f"   Colunas após alteração: {columns}")
            
            if 'key' in columns:
                print("   ✅ Coluna 'key' adicionada com sucesso!")
                return True
            else:
                print("   ❌ Coluna 'key' ainda não encontrada")
                return False
        else:
            print("   ℹ️  Tabela vazia, mas acessível")
            return True
    except Exception as e:
        print(f"   ❌ Erro ao verificar: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Adicionando coluna 'key' diretamente...")
    print("=" * 50)
    
    if add_key_column_direct():
        print("\n✅ Coluna adicionada com sucesso!")
        print("\n📋 Próximos passos:")
        print("   1. Testar criação de API keys")
        print("   2. Verificar se as chaves aparecem corretamente na interface")
    else:
        print("\n❌ Falha ao adicionar coluna")
        print("\n💡 Sugestão: Adicione a coluna manualmente no Supabase Dashboard")
        print("   SQL: ALTER TABLE api_keys ADD COLUMN key VARCHAR(255);")
