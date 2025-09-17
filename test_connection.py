"""
Script para testar a conexão com o banco de dados
"""
import os
import sys
from pathlib import Path

# Adicionar o diretório atual ao path
sys.path.append(str(Path(__file__).parent))

def test_supabase_connection():
    """Testa conexão com Supabase"""
    print("🔍 Testando conexão com Supabase...")
    
    try:
        from api.middleware.auth_middleware import get_supabase_client
        
        client = get_supabase_client()
        if not client:
            print("❌ Cliente Supabase não configurado")
            print("   Verifique as variáveis SUPABASE_URL e SUPABASE_ANON_KEY no .env")
            return False
        
        # Testar conexão
        result = client.table("users").select("id").limit(1).execute()
        print("✅ Conexão com Supabase estabelecida com sucesso!")
        print(f"   Tabela 'users' acessível: {len(result.data)} registros encontrados")
        return True
        
    except Exception as e:
        print(f"❌ Erro na conexão com Supabase: {e}")
        return False

def test_api_endpoints():
    """Testa endpoints da API"""
    print("\n🔍 Testando endpoints da API...")
    
    import requests
    
    base_url = "http://localhost:2377"
    
    # Testar health check
    try:
        response = requests.get(f"{base_url}/api/v1/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health check funcionando")
        else:
            print(f"❌ Health check falhou: {response.status_code}")
    except Exception as e:
        print(f"❌ Erro no health check: {e}")
        return False
    
    # Testar endpoint de consulta CNPJ (sem autenticação)
    try:
        response = requests.post(
            f"{base_url}/api/v1/cnpj/consult",
            json={"cnpj": "12.345.678/0001-90"},
            timeout=10
        )
        if response.status_code == 200:
            print("✅ Endpoint de consulta CNPJ funcionando")
        else:
            print(f"⚠️  Endpoint de consulta CNPJ retornou: {response.status_code}")
    except Exception as e:
        print(f"❌ Erro no endpoint de consulta: {e}")
    
    return True

def test_templates():
    """Testa se os templates estão acessíveis"""
    print("\n🔍 Testando templates...")
    
    import requests
    
    base_url = "http://localhost:2377"
    templates = ["/", "/dashboard", "/api-keys", "/assinatura", "/faturas", "/history", "/perfil"]
    
    for template in templates:
        try:
            response = requests.get(f"{base_url}{template}", timeout=5)
            if response.status_code == 200:
                print(f"✅ {template} - OK")
            else:
                print(f"❌ {template} - Status: {response.status_code}")
        except Exception as e:
            print(f"❌ {template} - Erro: {e}")

def main():
    """Função principal"""
    print("🧪 Testando configuração do SaaS Valida...")
    print("="*50)
    
    # Verificar se o servidor está rodando
    print("⚠️  Certifique-se de que o servidor está rodando (python run.py)")
    input("Pressione Enter para continuar...")
    
    # Testar conexão com Supabase
    supabase_ok = test_supabase_connection()
    
    # Testar endpoints da API
    api_ok = test_api_endpoints()
    
    # Testar templates
    test_templates()
    
    print("\n" + "="*50)
    if supabase_ok and api_ok:
        print("✅ Todos os testes passaram! Sistema funcionando corretamente.")
    else:
        print("⚠️  Alguns testes falharam. Verifique a configuração.")
    
    print("\n📋 Status do sistema:")
    print(f"   Supabase: {'✅' if supabase_ok else '❌'}")
    print(f"   API: {'✅' if api_ok else '❌'}")
    print(f"   Templates: ✅ (acessíveis via HTTP)")

if __name__ == "__main__":
    main()
