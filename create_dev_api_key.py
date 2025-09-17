#!/usr/bin/env python3
"""
Script para criar uma API key de desenvolvimento válida no banco
"""
import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client

# Carregar variáveis de ambiente
load_dotenv()

async def create_dev_api_key():
    """Cria uma API key de desenvolvimento válida no banco"""
    
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
    
    try:
        # 1. Buscar ou criar usuário de desenvolvimento
        print("👤 Configurando usuário de desenvolvimento...")
        dev_user_id = "00000000-0000-0000-0000-000000000001"
        
        # Verificar se usuário existe
        user_result = client.table("users").select("id").eq("id", dev_user_id).execute()
        if not user_result.data:
            # Criar usuário de desenvolvimento
            user_data = {
                "id": dev_user_id,
                "email": "dev@valida.com.br",
                "name": "Usuário Desenvolvimento"
            }
            client.table("users").insert(user_data).execute()
            print("   ✅ Usuário de desenvolvimento criado")
        else:
            print("   ✅ Usuário de desenvolvimento já existe")
        
        # 2. Criar API key de desenvolvimento
        print("\n🔑 Criando API key de desenvolvimento...")
        
        # Chave que o JavaScript está usando
        dev_api_key = "rcp_dev-key-2"
        
        # Calcular hash da chave
        import hashlib
        key_hash = hashlib.sha256(dev_api_key.encode()).hexdigest()
        
        print(f"   Chave: {dev_api_key}")
        print(f"   Hash: {key_hash}")
        
        # Verificar se já existe
        existing_key = client.table("api_keys").select("id").eq("key_hash", key_hash).execute()
        if existing_key.data:
            print("   ✅ API key de desenvolvimento já existe")
            return True
        
        # Criar API key no banco
        api_key_data = {
            "user_id": dev_user_id,
            "key": dev_api_key,  # Chave original
            "key_hash": key_hash,  # Hash da chave
            "name": "Chave de Desenvolvimento",
            "description": "API key para desenvolvimento e testes",
            "is_active": True
        }
        
        result = client.table("api_keys").insert(api_key_data).execute()
        
        if result.data:
            print("   ✅ API key de desenvolvimento criada com sucesso!")
            print(f"   ID: {result.data[0]['id']}")
            print(f"   Chave: {dev_api_key}")
            print(f"   Hash: {key_hash}")
            return True
        else:
            print("   ❌ Falha ao criar API key de desenvolvimento")
            return False
            
    except Exception as e:
        print(f"❌ Erro durante criação: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Criando API key de desenvolvimento...")
    print("=" * 50)
    
    asyncio.run(create_dev_api_key())
