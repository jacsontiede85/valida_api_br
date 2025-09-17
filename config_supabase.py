#!/usr/bin/env python3
"""
Script para configurar as variáveis do Supabase
"""
import os
from pathlib import Path

def create_env_file():
    """Cria arquivo .env com as variáveis do Supabase"""
    
    print("🔧 Configuração do Supabase para SaaS Valida")
    print("=" * 50)
    
    # Verificar se já existe .env
    env_file = Path(".env")
    if env_file.exists():
        print("⚠️  Arquivo .env já existe!")
        response = input("Deseja sobrescrever? (s/N): ").lower()
        if response != 's':
            print("❌ Operação cancelada")
            return
    
    print("\n📝 Por favor, forneça as informações do seu projeto Supabase:")
    print("   (Você pode encontrar essas informações no painel do Supabase)")
    
    # Coletar informações
    supabase_url = input("\n🌐 SUPABASE_URL: ").strip()
    if not supabase_url:
        print("❌ URL do Supabase é obrigatória")
        return
    
    supabase_anon_key = input("🔑 SUPABASE_ANON_KEY: ").strip()
    if not supabase_anon_key:
        print("❌ Chave anônima é obrigatória")
        return
    
    supabase_service_key = input("🔐 SUPABASE_SERVICE_ROLE_KEY: ").strip()
    if not supabase_service_key:
        print("⚠️  Chave de serviço não fornecida (opcional)")
    
    # Configurações adicionais
    stripe_secret = input("💳 STRIPE_SECRET_KEY (opcional): ").strip()
    stripe_webhook = input("🔔 STRIPE_WEBHOOK_SECRET (opcional): ").strip()
    
    # Criar conteúdo do .env
    env_content = f"""# Configurações do Supabase
SUPABASE_URL={supabase_url}
SUPABASE_ANON_KEY={supabase_anon_key}
SUPABASE_SERVICE_ROLE_KEY={supabase_service_key}

# URL de conexão direta do PostgreSQL (opcional)
DATABASE_URL=postgresql://postgres.your-project:your-password@db.your-project.supabase.co:5432/postgres

# Configurações JWT (não necessárias com Supabase Auth)
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production

# Configurações Stripe
STRIPE_SECRET_KEY={stripe_secret or 'sk_test_your_stripe_secret_key'}
STRIPE_WEBHOOK_SECRET={stripe_webhook or 'whsec_your_webhook_secret'}

# Configurações do Servidor
SAAS_PORT=2377

# Configurações do Frontend
NEXT_PUBLIC_API_URL=http://localhost:2377/api/v1
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key
NEXT_PUBLIC_SUPABASE_URL={supabase_url}
NEXT_PUBLIC_SUPABASE_ANON_KEY={supabase_anon_key}
"""
    
    # Salvar arquivo
    try:
        with open(".env", "w", encoding="utf-8") as f:
            f.write(env_content)
        
        print("\n✅ Arquivo .env criado com sucesso!")
        print("📁 Localização: .env")
        
        # Testar configuração
        print("\n🧪 Testando configuração...")
        os.environ["SUPABASE_URL"] = supabase_url
        os.environ["SUPABASE_ANON_KEY"] = supabase_anon_key
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = supabase_service_key
        
        # Importar e testar
        try:
            from sistema.saas.database.supabase_client import supabase_client
            if supabase_client.test_connection():
                print("✅ Conexão com Supabase OK!")
            else:
                print("❌ Erro na conexão com Supabase")
        except Exception as e:
            print(f"❌ Erro ao testar conexão: {e}")
        
        print("\n🚀 Próximos passos:")
        print("   1. Execute: python setup_database.py")
        print("   2. Execute: python test_connection.py")
        print("   3. Reinicie o servidor: python run.py")
        
    except Exception as e:
        print(f"❌ Erro ao criar arquivo .env: {e}")

if __name__ == "__main__":
    create_env_file()
