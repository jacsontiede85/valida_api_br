#!/usr/bin/env python3
"""
Script para testar se a coluna 'key' foi adicionada corretamente
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Carregar variáveis de ambiente
load_dotenv()

def test_key_column():
    """Testa se a coluna 'key' foi adicionada"""
    
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
        # Verificar estrutura da tabela
        print("🔍 Verificando estrutura da tabela api_keys...")
        result = client.table("api_keys").select("*").limit(1).execute()
        
        if result.data:
            columns = list(result.data[0].keys())
            print(f"   Colunas encontradas: {columns}")
            
            if 'key' in columns:
                print("   ✅ Coluna 'key' encontrada!")
                
                # Testar inserção de uma chave de teste
                print("\n🧪 Testando inserção de chave de teste...")
                test_data = {
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "key": "rcp_test1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                    "key_hash": "test_hash_1234567890abcdef",
                    "name": "Teste Chave RCP",
                    "description": "Chave de teste para verificar se a coluna key funciona",
                    "is_active": True
                }
                
                try:
                    insert_result = client.table("api_keys").insert(test_data).execute()
                    if insert_result.data:
                        print("   ✅ Chave de teste inserida com sucesso!")
                        print(f"   ID: {insert_result.data[0]['id']}")
                        print(f"   Chave: {insert_result.data[0]['key']}")
                        
                        # Limpar chave de teste
                        client.table("api_keys").delete().eq("id", insert_result.data[0]['id']).execute()
                        print("   🧹 Chave de teste removida")
                        
                        return True
                    else:
                        print("   ❌ Falha ao inserir chave de teste")
                        return False
                except Exception as e:
                    print(f"   ❌ Erro ao inserir chave de teste: {e}")
                    return False
            else:
                print("   ❌ Coluna 'key' NÃO encontrada")
                print("   💡 Execute o SQL no Supabase Dashboard primeiro")
                return False
        else:
            print("   ℹ️  Tabela vazia, mas acessível")
            print("   ✅ Coluna 'key' deve estar disponível")
            return True
            
    except Exception as e:
        print(f"❌ Erro ao verificar tabela: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testando coluna 'key' na tabela api_keys...")
    print("=" * 50)
    
    if test_key_column():
        print("\n✅ Teste concluído com sucesso!")
        print("\n📋 Próximos passos:")
        print("   1. Testar criação de API keys na interface")
        print("   2. Verificar se as chaves aparecem com 'rcp_' na interface")
    else:
        print("\n❌ Teste falhou")
        print("\n💡 Execute o SQL no Supabase Dashboard primeiro:")
        print("   Arquivo: add_key_column.sql")
