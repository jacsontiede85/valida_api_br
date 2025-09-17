#!/usr/bin/env python3
"""
Script para testar criação de API keys com usuário válido
"""
import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client

# Carregar variáveis de ambiente
load_dotenv()

async def test_with_user():
    """Testa criação de API keys com usuário válido"""
    
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
        # 1. Criar usuário de teste
        print("👤 Criando usuário de teste...")
        test_user_id = "550e8400-e29b-41d4-a716-446655440000"
        
        try:
            # Verificar se usuário já existe
            existing_user = client.table("users").select("id").eq("id", test_user_id).execute()
            if existing_user.data:
                print("   ✅ Usuário de teste já existe")
            else:
                # Criar usuário de teste
                user_data = {
                    "id": test_user_id,
                    "email": "teste@valida.com.br",
                    "name": "Usuário de Teste"
                }
                client.table("users").insert(user_data).execute()
                print("   ✅ Usuário de teste criado")
        except Exception as e:
            print(f"   ⚠️  Erro ao criar usuário: {e}")
        
        # 2. Testar criação de API key
        print("\n🔑 Testando criação de API key...")
        from api.services.api_key_service import api_key_service
        from api.models.saas_models import APIKeyCreate
        
        key_data = APIKeyCreate(
            name="Teste Chave RCP",
            description="Chave de teste para verificar se está salvando corretamente"
        )
        
        try:
            api_key = await api_key_service.create_api_key(test_user_id, key_data)
            
            print(f"   ✅ API key criada com sucesso!")
            print(f"   ID: {api_key.id}")
            print(f"   Nome: {api_key.name}")
            print(f"   Chave: {api_key.key}")
            print(f"   Hash: {api_key.key_hash}")
            print(f"   Ativa: {api_key.is_active}")
            
            # Verificar se a chave começa com "rcp_"
            if api_key.key and api_key.key.startswith("rcp_"):
                print("   ✅ Chave começa com 'rcp_' corretamente!")
            else:
                print("   ❌ Chave NÃO começa com 'rcp_'")
            
            # Verificar no banco de dados
            print("\n🔍 Verificando no banco de dados...")
            result = client.table("api_keys").select("*").eq("id", api_key.id).execute()
            
            if result.data:
                db_key = result.data[0]
                print(f"   ✅ Encontrada no banco de dados")
                print(f"   Chave no DB: {db_key.get('key', 'NÃO ENCONTRADA')}")
                print(f"   Hash no DB: {db_key.get('key_hash', 'NÃO ENCONTRADO')}")
                
                if db_key.get('key') and db_key.get('key').startswith("rcp_"):
                    print("   ✅ Chave no banco começa com 'rcp_'!")
                else:
                    print("   ❌ Chave no banco NÃO começa com 'rcp_'")
            else:
                print("   ❌ API key não encontrada no banco de dados")
            
            # Testar listagem de API keys
            print("\n📋 Testando listagem de API keys...")
            api_keys = await api_key_service.get_user_api_keys(test_user_id)
            
            print(f"   Total de API keys: {len(api_keys)}")
            for i, key in enumerate(api_keys, 1):
                print(f"   {i}. {key.name} - {key.key[:20] if key.key else 'N/A'}...")
                if key.key and key.key.startswith("rcp_"):
                    print(f"      ✅ Começa com 'rcp_'")
                else:
                    print(f"      ❌ NÃO começa com 'rcp_'")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Erro ao criar API key: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"❌ Erro durante teste: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Testando criação de API keys com usuário válido...")
    print("=" * 60)
    
    asyncio.run(test_with_user())
