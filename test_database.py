"""
Script para testar a conexão com o banco de dados Supabase
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def test_database():
    """Testa a conexão com o banco de dados"""
    print("🔍 Testando conexão com Supabase...")
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("❌ Variáveis de ambiente não configuradas")
        return
    
    try:
        supabase = create_client(url, key)
        
        # Testar consulta de usuários
        print("👤 Testando consulta de usuários...")
        users = supabase.table("users").select("*").limit(5).execute()
        print(f"✅ {len(users.data)} usuários encontrados")
        
        # Testar consulta de API keys
        print("🔑 Testando consulta de API keys...")
        api_keys = supabase.table("api_keys").select("*").limit(5).execute()
        print(f"✅ {len(api_keys.data)} API keys encontradas")
        
        # Testar consulta específica de API key
        print("🔍 Testando busca por API key específica...")
        specific_key = supabase.table("api_keys").select(
            "id, user_id, name, is_active, users(id, email, name)"
        ).eq("key_hash", "rcp_dev-key-1").execute()
        
        if specific_key.data:
            print(f"✅ API key encontrada: {specific_key.data[0]}")
        else:
            print("❌ API key 'rcp_dev-key-1' não encontrada")
            
        # Listar todas as API keys
        print("📋 Listando todas as API keys:")
        for key in api_keys.data:
            print(f"  - {key['key_hash']} ({key['name']}) - Ativa: {key['is_active']}")
            
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    test_database()
