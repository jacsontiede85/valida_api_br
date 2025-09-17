"""
Script para popular o banco de dados Supabase com dados iniciais
"""
import os
import asyncio
import uuid
from datetime import datetime, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def get_supabase_client() -> Client:
    """
    Cria cliente Supabase
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        raise Exception("Variáveis SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY são obrigatórias")
    
    return create_client(url, key)

async def populate_database():
    """
    Popula o banco de dados com dados iniciais
    """
    print("🚀 Iniciando população do banco de dados...")
    
    try:
        supabase = get_supabase_client()
        
        # 1. Criar planos de assinatura
        print("📋 Criando planos de assinatura...")
        plans_data = [
            {
                "name": "Básico",
                "description": "Ideal para pequenas empresas",
                "price_cents": 2990,  # R$ 29,90
                "queries_limit": 100,
                "api_keys_limit": 1,
                "is_active": True
            },
            {
                "name": "Profissional",
                "description": "Para empresas em crescimento",
                "price_cents": 9990,  # R$ 99,90
                "queries_limit": 1000,
                "api_keys_limit": 5,
                "is_active": True
            },
            {
                "name": "Empresarial",
                "description": "Para grandes empresas",
                "price_cents": 29990,  # R$ 299,90
                "queries_limit": None,  # Ilimitado
                "api_keys_limit": None,  # Ilimitado
                "is_active": True
            }
        ]
        
        for plan in plans_data:
            result = supabase.table("subscription_plans").insert(plan).execute()
            print(f"✅ Plano '{plan['name']}' criado")
        
        # 2. Criar usuário de teste
        print("👤 Criando usuário de teste...")
        user_id = str(uuid.uuid4())
        user_data = {
            "id": user_id,
            "email": "dev@valida.com.br",
            "name": "Usuário Desenvolvimento",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        result = supabase.table("users").insert(user_data).execute()
        print("✅ Usuário de teste criado")
        
        # 3. Criar assinatura para o usuário
        print("💳 Criando assinatura...")
        subscription_data = {
            "user_id": user_id,
            "plan_id": result.data[0]["id"] if result.data else None,
            "status": "active",
            "current_period_start": datetime.now().isoformat(),
            "current_period_end": (datetime.now() + timedelta(days=30)).isoformat(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # Buscar ID do plano Profissional
        plans_result = supabase.table("subscription_plans").select("id").eq("name", "Profissional").execute()
        if plans_result.data:
            subscription_data["plan_id"] = plans_result.data[0]["id"]
        
        result = supabase.table("subscriptions").insert(subscription_data).execute()
        print("✅ Assinatura criada")
        
        # 4. Criar API keys para o usuário
        print("🔑 Criando API keys...")
        api_keys_data = [
            {
                "user_id": user_id,
                "key_hash": "rcp_dev-key-1",
                "name": "Chave de Desenvolvimento 1",
                "is_active": True,
                "created_at": datetime.now().isoformat()
            },
            {
                "user_id": user_id,
                "key_hash": "rcp_dev-key-2",
                "name": "Chave de Desenvolvimento 2",
                "is_active": True,
                "created_at": datetime.now().isoformat()
            }
        ]
        
        for api_key in api_keys_data:
            result = supabase.table("api_keys").insert(api_key).execute()
            print(f"✅ API key '{api_key['name']}' criada")
        
        # 5. Criar histórico de consultas de exemplo
        print("📊 Criando histórico de consultas...")
        cnpjs = [
            "12.345.678/0001-90",
            "98.765.432/0001-12",
            "11.222.333/0001-44",
            "55.666.777/0001-88",
            "99.888.777/0001-66"
        ]
        
        # Buscar ID da API key
        api_key_result = supabase.table("api_keys").select("id").eq("key_hash", "rcp_dev-key-1").execute()
        api_key_id = api_key_result.data[0]["id"] if api_key_result.data else None
        
        # Criar consultas dos últimos 30 dias
        for i in range(50):  # 50 consultas de exemplo
            query_time = datetime.now() - timedelta(hours=i*12, minutes=i*15)
            query_data = {
                "user_id": user_id,
                "api_key_id": api_key_id,
                "cnpj": cnpjs[i % len(cnpjs)],
                "endpoint": "/api/v1/cnpj/consult",
                "response_status": 200 if i % 10 != 0 else 400,
                "credits_used": 1,
                "response_time_ms": 1200 + (i % 5) * 300,
                "created_at": query_time.isoformat()
            }
            
            supabase.table("query_history").insert(query_data).execute()
        
        print("✅ Histórico de consultas criado")
        
        # 6. Criar analytics de exemplo
        print("📈 Criando analytics...")
        for i in range(30):  # Últimos 30 dias
            date = datetime.now() - timedelta(days=i)
            analytics_data = {
                "user_id": user_id,
                "date": date.strftime("%Y-%m-%d"),
                "total_queries": 10 + (i % 5) * 2,
                "successful_queries": 8 + (i % 3) * 2,
                "failed_queries": 2 + (i % 2),
                "total_credits_used": 10 + (i % 5) * 2,
                "created_at": datetime.now().isoformat()
            }
            
            supabase.table("query_analytics").insert(analytics_data).execute()
        
        print("✅ Analytics criados")
        
        print("🎉 Banco de dados populado com sucesso!")
        print("\n📋 Dados criados:")
        print("- 3 planos de assinatura")
        print("- 1 usuário de teste")
        print("- 1 assinatura ativa")
        print("- 2 API keys")
        print("- 50 consultas de exemplo")
        print("- 30 dias de analytics")
        
    except Exception as e:
        print(f"❌ Erro ao popular banco de dados: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(populate_database())
