#!/usr/bin/env python3
"""
Script alternativo para inspecionar tabelas do Supabase
Usa queries diretas nas tabelas ao invés de SQL raw
"""

import os
import json
from dotenv import load_dotenv
from supabase import create_client, Client

# Carregar variáveis de ambiente
load_dotenv()

def get_supabase_client():
    """Criar cliente Supabase"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("❌ SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY devem estar configuradas no .env")
        return None
    
    return create_client(url, key)

def inspect_tables(supabase: Client):
    """Inspecionar tabelas principais"""
    
    tables_info = {}
    
    # Lista de tabelas para inspecionar
    tables_to_check = [
        'users', 'subscriptions', 'subscription_plans', 
        'api_keys', 'credit_transactions', 'service_costs', 
        'stripe_webhook_logs'
    ]
    
    for table_name in tables_to_check:
        print(f"🔍 Inspecionando tabela: {table_name}")
        try:
            # Tentar fazer uma query simples para verificar se a tabela existe e obter estrutura
            result = supabase.table(table_name).select("*").limit(1).execute()
            
            if result.data:
                # Se temos dados, pegar as chaves para entender a estrutura
                sample_record = result.data[0]
                tables_info[table_name] = {
                    "exists": True,
                    "columns": list(sample_record.keys()),
                    "sample_data": sample_record,
                    "record_count": len(result.data)
                }
                print(f"  ✅ {table_name}: {len(sample_record.keys())} colunas")
            else:
                # Tabela existe mas está vazia
                tables_info[table_name] = {
                    "exists": True,
                    "columns": [],
                    "sample_data": None,
                    "record_count": 0
                }
                print(f"  ⚠️  {table_name}: existe mas está vazia")
                
        except Exception as e:
            print(f"  ❌ {table_name}: erro - {e}")
            tables_info[table_name] = {
                "exists": False,
                "error": str(e),
                "columns": [],
                "sample_data": None
            }
    
    return tables_info

def detailed_credit_transactions_check(supabase: Client):
    """Verificação detalhada da tabela credit_transactions"""
    
    print("\n🔍 ANÁLISE DETALHADA - CREDIT_TRANSACTIONS")
    
    try:
        # Tentar obter alguns registros
        result = supabase.table('credit_transactions').select("*").limit(3).execute()
        
        print(f"📊 Total de registros encontrados: {len(result.data)}")
        
        if result.data:
            # Analisar primeiro registro para ver estrutura
            first_record = result.data[0]
            print(f"\n📋 Estrutura detectada ({len(first_record.keys())} colunas):")
            
            for column, value in first_record.items():
                value_type = type(value).__name__
                print(f"  - {column}: {value_type} = {value}")
            
            return {
                "table_exists": True,
                "columns_detected": list(first_record.keys()),
                "sample_records": result.data,
                "structure_analysis": {col: type(val).__name__ for col, val in first_record.items()}
            }
        else:
            print("⚠️  Tabela existe mas está vazia")
            return {
                "table_exists": True,
                "is_empty": True,
                "columns_detected": [],
                "sample_records": []
            }
            
    except Exception as e:
        print(f"❌ Erro ao acessar credit_transactions: {e}")
        return {
            "table_exists": False,
            "error": str(e)
        }

def main():
    try:
        print("🚀 INSPEÇÃO DO BANCO DE DADOS SUPABASE")
        print("=" * 50)
        
        supabase = get_supabase_client()
        if not supabase:
            return
        
        # Inspecionar todas as tabelas
        print("\n1️⃣ INSPEÇÃO GERAL DAS TABELAS")
        tables_info = inspect_tables(supabase)
        
        # Análise específica da credit_transactions
        print("\n2️⃣ ANÁLISE ESPECÍFICA - CREDIT_TRANSACTIONS")
        credit_analysis = detailed_credit_transactions_check(supabase)
        
        # Compilar relatório final
        report = {
            "timestamp": "2025-09-22T13:35:00Z",
            "general_inspection": tables_info,
            "credit_transactions_analysis": credit_analysis
        }
        
        # Salvar relatório
        with open('supabase/database_inspection_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n✅ Relatório salvo em: supabase/database_inspection_report.json")
        
        # Mostrar resumo na tela
        print(f"\n📋 RESUMO EXECUTIVO:")
        print(f"{'=' * 30}")
        
        for table_name, info in tables_info.items():
            if info.get("exists"):
                columns = len(info.get("columns", []))
                print(f"✅ {table_name}: {columns} colunas")
            else:
                print(f"❌ {table_name}: não existe ou erro")
        
        # Informações críticas sobre credit_transactions
        if credit_analysis.get("table_exists"):
            columns = credit_analysis.get("columns_detected", [])
            print(f"\n🎯 CREDIT_TRANSACTIONS:")
            print(f"   Colunas detectadas: {', '.join(columns)}")
            
            # Verificar se tem as colunas problemáticas
            problem_columns = ["balance_after_cents", "amount_cents"]
            for col in problem_columns:
                if col in columns:
                    print(f"   ✅ {col}: EXISTE")
                else:
                    print(f"   ❌ {col}: NÃO EXISTE")
        
    except Exception as e:
        print(f"❌ Erro geral: {e}")

if __name__ == "__main__":
    main()
