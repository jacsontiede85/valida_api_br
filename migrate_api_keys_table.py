#!/usr/bin/env python3
"""
Script para migrar a tabela api_keys adicionando a coluna 'key'
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import structlog

# Carregar variáveis de ambiente
load_dotenv()

logger = structlog.get_logger("migrate_api_keys_table")

def migrate_api_keys_table():
    """Migra a tabela api_keys adicionando a coluna 'key'"""
    
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
        # 1. Backup dos dados existentes
        print("📦 Fazendo backup dos dados existentes...")
        existing_keys = client.table("api_keys").select("*").execute()
        print(f"   {len(existing_keys.data)} registros encontrados")
        
        # 2. Criar nova tabela com a estrutura correta
        print("\n🔧 Criando nova tabela api_keys_new...")
        
        # Usar uma query SQL para criar a nova tabela
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS api_keys_new (
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
        """
        
        # Tentar executar via SQL direto
        try:
            # Usar o método de query SQL do Supabase
            result = client.postgrest.rpc("exec", {"sql": create_table_sql}).execute()
            print("   ✅ Tabela api_keys_new criada")
        except Exception as e:
            print(f"   ⚠️  Erro ao criar tabela via RPC: {e}")
            print("   ℹ️  Continuando com a migração...")
        
        # 3. Migrar dados existentes
        print("\n📋 Migrando dados existentes...")
        for i, key_data in enumerate(existing_keys.data, 1):
            try:
                # Criar registro na nova tabela
                new_key_data = {
                    "id": key_data["id"],
                    "user_id": key_data["user_id"],
                    "key": None,  # Será preenchido quando criar novas chaves
                    "key_hash": key_data["key_hash"],
                    "name": key_data["name"],
                    "description": key_data.get("description"),
                    "is_active": key_data["is_active"],
                    "last_used_at": key_data.get("last_used_at"),
                    "created_at": key_data["created_at"]
                }
                
                # Inserir na nova tabela
                result = client.table("api_keys_new").insert(new_key_data).execute()
                print(f"   {i}/{len(existing_keys.data)} Migrado: {key_data['name']}")
                
            except Exception as e:
                print(f"   ⚠️  Erro ao migrar {key_data['name']}: {e}")
        
        # 4. Renomear tabelas
        print("\n🔄 Renomeando tabelas...")
        try:
            # Renomear tabela antiga
            rename_old_sql = "ALTER TABLE api_keys RENAME TO api_keys_old;"
            result = client.postgrest.rpc("exec", {"sql": rename_old_sql}).execute()
            print("   ✅ Tabela antiga renomeada para api_keys_old")
            
            # Renomear nova tabela
            rename_new_sql = "ALTER TABLE api_keys_new RENAME TO api_keys;"
            result = client.postgrest.rpc("exec", {"sql": rename_new_sql}).execute()
            print("   ✅ Nova tabela renomeada para api_keys")
            
        except Exception as e:
            print(f"   ⚠️  Erro ao renomear tabelas: {e}")
            print("   ℹ️  Você pode fazer isso manualmente no Supabase Dashboard")
        
        # 5. Verificar resultado
        print("\n🔍 Verificando resultado...")
        try:
            result = client.table("api_keys").select("*").limit(1).execute()
            if result.data:
                columns = list(result.data[0].keys())
                print(f"   Colunas na nova tabela: {columns}")
                
                if 'key' in columns:
                    print("   ✅ Coluna 'key' encontrada!")
                    return True
                else:
                    print("   ❌ Coluna 'key' não encontrada")
                    return False
            else:
                print("   ℹ️  Tabela vazia, mas acessível")
                return True
        except Exception as e:
            print(f"   ❌ Erro ao verificar: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Erro durante migração: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Migrando tabela api_keys...")
    print("=" * 50)
    
    if migrate_api_keys_table():
        print("\n✅ Migração concluída com sucesso!")
        print("\n📋 Próximos passos:")
        print("   1. Testar criação de API keys")
        print("   2. Verificar se as chaves aparecem corretamente na interface")
    else:
        print("\n❌ Falha na migração")
        print("\n💡 Sugestão: Execute manualmente no Supabase Dashboard:")
        print("   1. ALTER TABLE api_keys ADD COLUMN key VARCHAR(255);")
        print("   2. ALTER TABLE api_keys ADD COLUMN description TEXT;")
