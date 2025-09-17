#!/usr/bin/env python3
"""
Script para testar consulta direta no banco de dados
"""
import os
from supabase import create_client, Client
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurar Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("❌ Variáveis de ambiente do Supabase não configuradas")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def test_query_history():
    """Testa busca de consultas no histórico"""
    user_id = "00000000-0000-0000-0000-000000000001"
    
    print(f"🔍 Buscando consultas para user_id: {user_id}")
    
    # Buscar todas as consultas do usuário
    result = supabase.table("query_history").select("*").eq("user_id", user_id).execute()
    
    print(f"📊 Total de consultas encontradas: {len(result.data)}")
    
    if result.data:
        print("📋 Últimas 5 consultas:")
        for i, query in enumerate(result.data[-5:], 1):
            print(f"  {i}. CNPJ: {query.get('cnpj', 'N/A')}")
            print(f"     Data: {query.get('created_at', 'N/A')}")
            print(f"     Status: {query.get('status', 'N/A')}")
            print(f"     Endpoint: {query.get('endpoint', 'N/A')}")
            print()
    else:
        print("❌ Nenhuma consulta encontrada")
    
    # Buscar analytics
    print("📈 Buscando analytics...")
    analytics = supabase.table("query_analytics").select("*").eq("user_id", user_id).execute()
    
    # Testar busca com período (como no dashboard)
    from datetime import datetime, timedelta
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    print(f"📅 Testando busca com período: {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')}")
    analytics_period = supabase.table("query_analytics").select("*").eq("user_id", user_id).gte("date", start_date.strftime("%Y-%m-%d")).lte("date", end_date.strftime("%Y-%m-%d")).execute()
    
    print(f"📊 Analytics no período: {len(analytics_period.data)}")
    if analytics_period.data:
        for analytic in analytics_period.data:
            print(f"  Data: {analytic.get('date', 'N/A')} - Queries: {analytic.get('total_queries', 0)}")
    
    print(f"📊 Total de analytics encontrados: {len(analytics.data)}")
    
    if analytics.data:
        print("📋 Analytics encontrados:")
        for analytic in analytics.data:
            print(f"  Data: {analytic.get('date', 'N/A')}")
            print(f"  Total queries: {analytic.get('total_queries', 0)}")
            print(f"  Successful: {analytic.get('successful_queries', 0)}")
            print(f"  Failed: {analytic.get('failed_queries', 0)}")
            print(f"  Credits used: {analytic.get('total_credits_used', 0)}")
            print()
        
        # Calcular totais
        total_queries = sum(a.get("total_queries", 0) for a in analytics.data)
        successful_queries = sum(a.get("successful_queries", 0) for a in analytics.data)
        failed_queries = sum(a.get("failed_queries", 0) for a in analytics.data)
        total_credits_used = sum(a.get("total_credits_used", 0) for a in analytics.data)
        
        print(f"📊 TOTAIS:")
        print(f"  Total queries: {total_queries}")
        print(f"  Successful: {successful_queries}")
        print(f"  Failed: {failed_queries}")
        print(f"  Credits used: {total_credits_used}")
    else:
        print("❌ Nenhum analytics encontrado")

if __name__ == "__main__":
    test_query_history()
