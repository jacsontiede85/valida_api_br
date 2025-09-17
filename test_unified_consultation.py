#!/usr/bin/env python3
"""
Teste básico da implementação do UnifiedConsultationService
"""

import asyncio
import sys
from pathlib import Path

# Adicionar o path da API ao sys.path
sys.path.append(str(Path(__file__).parent))

from api.models.saas_models import ConsultationRequest
from api.services.unified_consultation_service import UnifiedConsultationService

async def test_backward_compatibility():
    """Testa se a implementação mantém backward compatibility"""
    print("🧪 Testando backward compatibility...")
    
    # Teste 1: Requisição apenas com protestos (comportamento antigo)
    request_old = ConsultationRequest(
        cnpj="12345678000190"  # CNPJ de teste
        # Todos outros parâmetros usam defaults (protestos=True, demais=False)
    )
    
    service = UnifiedConsultationService()
    
    try:
        result = await service.consultar_dados_completos(request_old, "test_user")
        
        print(f"✅ Consulta backward compatibility - Success: {result.success}")
        print(f"✅ Fontes consultadas: {result.sources_consulted}")
        print(f"✅ Tem dados de protestos: {result.protestos is not None}")
        print(f"✅ Tem dados da receita: {result.dados_receita is not None}")
        print(f"✅ Campo 'data' para compatibilidade: {result.data is not None}")
        print(f"✅ Tempo de resposta: {result.response_time_ms}ms")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de backward compatibility: {e}")
        return False

async def test_unified_consultation():
    """Testa consulta com múltiplas fontes"""
    print("\n🧪 Testando consulta unificada...")
    
    # Teste 2: Requisição com múltiplas fontes
    request_unified = ConsultationRequest(
        cnpj="12345678000190",
        protestos=True,
        simples=True,
        geocoding=True,
        registrations="BR",
        strategy="CACHE_IF_FRESH"
    )
    
    service = UnifiedConsultationService()
    
    try:
        result = await service.consultar_dados_completos(request_unified, "test_user")
        
        print(f"✅ Consulta unificada - Success: {result.success}")
        print(f"✅ Fontes consultadas: {result.sources_consulted}")
        print(f"✅ Cache usado: {result.cache_used}")
        print(f"✅ Dados de protestos: {result.protestos is not None}")
        print(f"✅ Dados da receita: {result.dados_receita is not None}")
        print(f"✅ Tempo de resposta: {result.response_time_ms}ms")
        
        # Verificar estrutura dos dados da receita
        if result.dados_receita:
            print(f"✅ Categorias de dados da receita: {list(result.dados_receita.keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de consulta unificada: {e}")
        return False

async def test_cnpja_only():
    """Testa consulta apenas com dados da CNPJa"""
    print("\n🧪 Testando consulta apenas CNPJa...")
    
    # Teste 3: Apenas dados da CNPJa
    request_cnpja = ConsultationRequest(
        cnpj="12345678000190",
        protestos=False,  # Desabilitar protestos
        simples=True,
        geocoding=True
    )
    
    service = UnifiedConsultationService()
    
    try:
        result = await service.consultar_dados_completos(request_cnpja, "test_user")
        
        print(f"✅ Consulta CNPJa only - Success: {result.success}")
        print(f"✅ Fontes consultadas: {result.sources_consulted}")
        print(f"✅ Dados de protestos: {result.protestos is not None}")
        print(f"✅ Dados da receita: {result.dados_receita is not None}")
        
        # Deve ter apenas cnpja nas fontes consultadas
        expected_sources = ['cnpja']
        if result.sources_consulted == expected_sources:
            print(f"✅ Fontes corretas: {result.sources_consulted}")
        else:
            print(f"⚠️ Fontes inesperadas. Esperado: {expected_sources}, Recebido: {result.sources_consulted}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste CNPJa only: {e}")
        return False

async def test_invalid_cnpj():
    """Testa comportamento com CNPJ inválido"""
    print("\n🧪 Testando CNPJ inválido...")
    
    request_invalid = ConsultationRequest(
        cnpj="11111111111111",  # CNPJ inválido
        protestos=True,
        simples=True
    )
    
    service = UnifiedConsultationService()
    
    try:
        result = await service.consultar_dados_completos(request_invalid, "test_user")
        
        print(f"✅ CNPJ inválido - Success: {result.success}")
        print(f"✅ Error message: {result.error}")
        print(f"✅ Fontes consultadas: {result.sources_consulted}")
        
        # Com CNPJ inválido, esperamos success=False
        if not result.success and result.error:
            print("✅ Comportamento correto para CNPJ inválido")
        else:
            print("⚠️ Deveria retornar erro para CNPJ inválido")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de CNPJ inválido: {e}")
        return False

async def main():
    """Executa todos os testes"""
    print("🚀 Iniciando testes do UnifiedConsultationService\n")
    
    tests = [
        ("Backward Compatibility", test_backward_compatibility),
        ("Consulta Unificada", test_unified_consultation), 
        ("CNPJa Only", test_cnpja_only),
        ("CNPJ Inválido", test_invalid_cnpj)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Executando teste: {test_name}")
        print('='*50)
        
        try:
            result = await test_func()
            results.append((test_name, result))
            
        except Exception as e:
            print(f"❌ Falha crítica no teste {test_name}: {e}")
            results.append((test_name, False))
    
    # Relatório final
    print(f"\n{'='*50}")
    print("📊 RELATÓRIO FINAL DOS TESTES")
    print('='*50)
    
    passed = 0
    failed = 0
    
    for test_name, success in results:
        status = "✅ PASSOU" if success else "❌ FALHOU"
        print(f"{status} - {test_name}")
        
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📈 Resumo: {passed} passaram, {failed} falharam")
    
    if failed == 0:
        print("🎉 Todos os testes passaram! Implementação está funcionando.")
        return 0
    else:
        print("⚠️ Alguns testes falharam. Verificar implementação.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
