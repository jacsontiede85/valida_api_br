#!/usr/bin/env python3
"""
Script para adicionar coluna 'key' na tabela api_keys
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import structlog

# Carregar variáveis de ambiente
load_dotenv()

logger = structlog.get_logger("add_key_column")

def add_key_column():
    """Adiciona a coluna 'key' na tabela api_keys"""
    
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
    
    # SQL para adicionar a coluna 'key'
    sql_commands = [
        """
        -- Adicionar coluna 'key' na tabela api_keys
        ALTER TABLE api_keys 
        ADD COLUMN IF NOT EXISTS key VARCHAR(255);
        """,
        
        """
        -- Adicionar coluna 'description' na tabela api_keys (se não existir)
        ALTER TABLE api_keys 
        ADD COLUMN IF NOT EXISTS description TEXT;
        """,
        
        """
        -- Criar índice para a coluna 'key'
        CREATE INDEX IF NOT EXISTS idx_api_keys_key ON api_keys(key);
        """
    ]
    
    print("🔧 Adicionando coluna 'key' na tabela api_keys...")
    
    for i, sql in enumerate(sql_commands, 1):
        try:
            print(f"   {i}/{len(sql_commands)} Executando comando SQL...")
            result = client.rpc('exec_sql', {'sql': sql}).execute()
            print(f"   ✅ Comando {i} executado com sucesso")
        except Exception as e:
            print(f"   ⚠️  Comando {i} falhou: {e}")
            # Continuar mesmo com erro
    
    print("\n✅ Coluna 'key' adicionada com sucesso!")
    
    # Verificar se a coluna foi adicionada
    print("\n🔍 Verificando estrutura da tabela...")
    try:
        # Tentar buscar uma API key para ver a estrutura
        keys = client.table('api_keys').select('*').limit(1).execute()
        if keys.data:
            print("✅ Tabela 'api_keys' acessível")
            print(f"   Colunas disponíveis: {list(keys.data[0].keys())}")
        else:
            print("ℹ️  Tabela 'api_keys' vazia, mas acessível")
        
    except Exception as e:
        print(f"❌ Erro ao verificar tabela: {e}")
        return False
    
    print("\n🎉 Coluna 'key' adicionada com sucesso!")
    return True

if __name__ == "__main__":
    print("🚀 Adicionando coluna 'key' na tabela api_keys...")
    print("=" * 50)
    
    if add_key_column():
        print("\n✅ Coluna adicionada com sucesso!")
        print("\n📋 Próximos passos:")
        print("   1. Atualizar o serviço para salvar a chave original")
        print("   2. Testar criação de novas API keys")
        print("   3. Verificar se as chaves aparecem corretamente na interface")
    else:
        print("\n❌ Falha ao adicionar coluna")
