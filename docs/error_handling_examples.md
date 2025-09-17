# Tratamento de Erros - API CNPJa

## Visão Geral

A API CNPJa agora possui tratamento robusto de erros, incluindo fallback automático quando serviços específicos estão offline (erro 503).

## Cenários de Erro Tratados

### 1. Serviço Simples Nacional Offline (503)

```python
from src.utils.cnpja_api import CNPJaAPI, CNPJaServerError

api = CNPJaAPI()

try:
    # Tentativa com todos os dados
    dados = api.get_all_company_info("12345678000190",
        simples=True,
        registrations='BR',
        geocoding=True,
        suframa=True
    )
    print("Dados completos obtidos:", list(dados.keys()))
    
except CNPJaServerError as e:
    if "offline" in str(e).lower():
        print("Alguns serviços estão offline. Tentando consulta básica...")
        # Fallback automático - a API tentará sem o serviço problemático
        dados = api.get_all_company_info("12345678000190",
            simples=False,  # Desabilitar serviço offline
            registrations='BR',
            geocoding=True,
            suframa=True
        )
        print("Dados parciais obtidos:", list(dados.keys()))
    else:
        print(f"Erro do servidor: {e}")
```

### 2. Tratamento de Erros por Categoria

```python
def consultar_cnpj_com_fallback(cnpj: str):
    """Consulta CNPJ com fallback automático para serviços offline."""
    
    api = CNPJaAPI()
    
    # Parâmetros desejados
    params = {
        'simples': True,
        'registrations': 'BR',
        'geocoding': True,
        'suframa': True
    }
    
    try:
        # Primeira tentativa: todos os dados
        dados = api.get_all_company_info(cnpj, **params)
        print("✅ Todos os dados obtidos com sucesso")
        return dados
        
    except CNPJaServerError as e:
        if "simples service is offline" in str(e):
            print("⚠️ Serviço Simples Nacional offline. Tentando sem ele...")
            params['simples'] = False
            
        elif "suframa service is offline" in str(e):
            print("⚠️ Serviço SUFRAMA offline. Tentando sem ele...")
            params['suframa'] = False
            
        elif "registrations service is offline" in str(e):
            print("⚠️ Serviço de registros offline. Tentando sem ele...")
            params['registrations'] = None
            
        # Segunda tentativa: sem o serviço problemático
        try:
            dados = api.get_all_company_info(cnpj, **params)
            print("✅ Dados parciais obtidos com sucesso")
            return dados
        except Exception as e2:
            print(f"❌ Erro mesmo com fallback: {e2}")
            raise
            
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        raise

# Exemplo de uso
dados = consultar_cnpj_com_fallback("12345678000190")
```

### 3. Verificação de Dados Disponíveis

```python
def verificar_dados_disponiveis(cnpj: str):
    """Verifica quais dados estão disponíveis para um CNPJ."""
    
    api = CNPJaAPI()
    
    # Parâmetros completos
    params = {
        'simples': True,
        'registrations': 'BR',
        'geocoding': True,
        'suframa': True
    }
    
    try:
        dados = api.get_all_company_info(cnpj, **params)
        
        # Verificar quais categorias foram obtidas
        categorias_obtidas = list(dados.keys())
        categorias_solicitadas = ['basico', 'endereco', 'contato', 'atividades', 
                                'socios', 'simples', 'registros_estaduais', 'suframa']
        
        print(f"📊 Dados disponíveis para CNPJ {cnpj}:")
        for categoria in categorias_solicitadas:
            if categoria in categorias_obtidas:
                print(f"  ✅ {categoria}")
            else:
                print(f"  ❌ {categoria} (serviço offline ou dados não disponíveis)")
        
        return dados
        
    except Exception as e:
        print(f"❌ Erro na consulta: {e}")
        return None

# Exemplo de uso
dados = verificar_dados_disponiveis("12345678000190")
```

### 4. Estratégia de Retry com Backoff

```python
import time
from src.utils.cnpja_api import CNPJaAPI, CNPJaServerError, CNPJaRateLimitError

def consultar_cnpj_com_retry(cnpj: str, max_tentativas: int = 3):
    """Consulta CNPJ com estratégia de retry e backoff exponencial."""
    
    api = CNPJaAPI()
    
    for tentativa in range(max_tentativas):
        try:
            dados = api.get_all_company_info(cnpj,
                simples=True,
                registrations='BR',
                geocoding=True,
                suframa=True
            )
            print(f"✅ Sucesso na tentativa {tentativa + 1}")
            return dados
            
        except CNPJaRateLimitError as e:
            wait_time = 2 ** tentativa  # Backoff exponencial
            print(f"⏳ Rate limit excedido. Aguardando {wait_time}s...")
            time.sleep(wait_time)
            
        except CNPJaServerError as e:
            if "offline" in str(e).lower():
                print(f"⚠️ Serviços offline na tentativa {tentativa + 1}")
                if tentativa < max_tentativas - 1:
                    time.sleep(2 ** tentativa)
                    continue
                else:
                    # Última tentativa: dados básicos apenas
                    print("🔄 Última tentativa: dados básicos apenas")
                    dados = api.get_all_company_info(cnpj, simples=False, 
                                                   registrations=None, 
                                                   geocoding=False, 
                                                   suframa=False)
                    return dados
            else:
                raise
                
        except Exception as e:
            print(f"❌ Erro na tentativa {tentativa + 1}: {e}")
            if tentativa == max_tentativas - 1:
                raise
            time.sleep(2 ** tentativa)
    
    raise Exception("Máximo de tentativas excedido")

# Exemplo de uso
dados = consultar_cnpj_com_retry("12345678000190")
```

## Logs de Monitoramento

A API agora gera logs informativos sobre o status dos serviços:

```
2024-01-15 10:30:15 - CNPJaAPI - WARNING - Serviço simples temporariamente offline. Tentando fallback...
2024-01-15 10:30:16 - CNPJaAPI - INFO - Tentando consulta sem dados do Simples Nacional...
2024-01-15 10:30:17 - CNPJaAPI - WARNING - Dados não disponíveis para CNPJ 12345678000190: simples (serviços podem estar offline)
```

## Estratégias de Fallback

### 1. Fallback Automático
- Detecta serviços offline (erro 503)
- Tenta automaticamente sem o serviço problemático
- Retorna dados parciais quando possível

### 2. Fallback Manual
- Permite controle granular sobre quais dados solicitar
- Útil para aplicações que precisam de dados específicos
- Evita dependência de serviços instáveis

### 3. Fallback Gradual
- Tenta primeiro com todos os dados
- Se falhar, tenta com dados essenciais
- Se falhar novamente, tenta apenas dados básicos

## Boas Práticas

### 1. Sempre Tratar Erros
```python
try:
    dados = api.get_all_company_info(cnpj, **params)
except CNPJaServerError as e:
    # Implementar fallback
    pass
```

### 2. Verificar Dados Obtidos
```python
dados = api.get_all_company_info(cnpj, **params)
if 'simples' not in dados:
    print("Aviso: Dados do Simples Nacional não disponíveis")
```

### 3. Usar Logs para Monitoramento
```python
import logging
logging.basicConfig(level=logging.INFO)
# Os logs da API mostrarão o status dos serviços
```

### 4. Implementar Cache Local
```python
# A API já possui cache automático
# Para cache personalizado, use:
api.clear_cache()  # Limpar cache
api.remove_from_cache(cnpj)  # Remover CNPJ específico
```

## Códigos de Erro Tratados

| Código | Erro | Tratamento |
|--------|------|------------|
| 200 | Sucesso | Dados retornados normalmente |
| 400 | Requisição inválida | Erro de validação |
| 401 | Não autorizado | Credenciais inválidas |
| 403 | Acesso negado | Permissões insuficientes |
| 404 | CNPJ não encontrado | CNPJ inexistente |
| 429 | Rate limit | Retry com backoff |
| 503 | Serviço offline | Fallback automático |
| 5xx | Erro do servidor | Tratamento genérico |

## Exemplo Completo de Uso

```python
from src.utils.cnpja_api import CNPJaAPI, CNPJaServerError, CNPJaNotFoundError

def consultar_empresa_robusto(cnpj: str):
    """Consulta empresa com tratamento robusto de erros."""
    
    api = CNPJaAPI()
    
    try:
        # Tentativa com todos os dados
        dados = api.get_all_company_info(cnpj,
            simples=True,
            registrations='BR',
            geocoding=True,
            suframa=True
        )
        
        return {
            'success': True,
            'data': dados,
            'message': 'Dados completos obtidos',
            'categories': list(dados.keys())
        }
        
    except CNPJaNotFoundError:
        return {
            'success': False,
            'data': None,
            'message': 'CNPJ não encontrado',
            'error': 'NOT_FOUND'
        }
        
    except CNPJaServerError as e:
        if "offline" in str(e).lower():
            # Fallback para dados básicos
            try:
                dados = api.get_all_company_info(cnpj)
                return {
                    'success': True,
                    'data': dados,
                    'message': 'Dados básicos obtidos (alguns serviços offline)',
                    'categories': list(dados.keys()),
                    'warning': 'Alguns dados não disponíveis'
                }
            except Exception as e2:
                return {
                    'success': False,
                    'data': None,
                    'message': f'Erro mesmo com fallback: {e2}',
                    'error': 'FALLBACK_FAILED'
                }
        else:
            return {
                'success': False,
                'data': None,
                'message': f'Erro do servidor: {e}',
                'error': 'SERVER_ERROR'
            }
            
    except Exception as e:
        return {
            'success': False,
            'data': None,
            'message': f'Erro inesperado: {e}',
            'error': 'UNKNOWN_ERROR'
        }

# Exemplo de uso
resultado = consultar_empresa_robusto("12345678000190")
print(f"Sucesso: {resultado['success']}")
print(f"Mensagem: {resultado['message']}")
if resultado['success']:
    print(f"Categorias: {resultado['categories']}")
```

Esta implementação garante que sua aplicação continue funcionando mesmo quando alguns serviços da API CNPJa estão temporariamente indisponíveis.
