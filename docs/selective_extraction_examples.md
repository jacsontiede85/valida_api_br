# Exemplos de Extração Seletiva - API CNPJa

## Visão Geral

A função `get_all_company_info` agora suporta extração seletiva de dados, permitindo que você solicite apenas as informações necessárias para sua aplicação, otimizando performance e reduzindo o uso de recursos.

## Exemplos Práticos

### 1. Consulta Mínima (Apenas Dados Básicos)

```python
from src.utils.cnpja_api import CNPJaAPI

api = CNPJaAPI()

# Consulta apenas dados básicos da empresa
dados = api.get_all_company_info("12345678000190")

print("Categorias incluídas:", list(dados.keys()))
# Output: ['basico']

print("Dados básicos:", dados['basico']['razao_social'])
# Output: Nome da empresa
```

### 2. Consulta para Validação de Endereço

```python
# Consulta apenas dados básicos + endereço para validação
dados = api.get_all_company_info("12345678000190", 
    address=True
)

print("Categorias:", list(dados.keys()))
# Output: ['basico', 'endereco']

print("Endereço completo:", dados['endereco']['logradouro'])
```

### 3. Consulta para Análise de Sócios

```python
# Consulta dados básicos + sócios para análise societária
dados = api.get_all_company_info("12345678000190", 
    partners=True
)

print("Categorias:", list(dados.keys()))
# Output: ['basico', 'socios']

print("Número de sócios:", len(dados['socios']))
for socio in dados['socios']:
    print(f"- {socio['nome']} ({socio['qualificacao']})")
```

### 4. Consulta para Verificação de SUFRAMA

```python
# Consulta apenas dados básicos + SUFRAMA para verificação de incentivos
dados = api.get_all_company_info("04337168000148", 
    suframa=True
)

print("Categorias:", list(dados.keys()))
# Output: ['basico', 'suframa']

if dados['suframa']:
    print("Empresa possui registros SUFRAMA:")
    for registro in dados['suframa']:
        print(f"- Número: {registro['numero']}")
        print(f"- Status: {registro['status']['texto']}")
        print(f"- Incentivos: {len(registro['incentivos'])}")
else:
    print("Empresa não possui registros SUFRAMA")
```

### 5. Consulta para Análise Fiscal Completa

```python
# Consulta dados básicos + Simples Nacional + Registros Estaduais
dados = api.get_all_company_info("12345678000190",
    simples=True,
    registrations='BR'
)

print("Categorias:", list(dados.keys()))
# Output: ['basico', 'simples', 'registros_estaduais']

# Verificar se está no Simples Nacional
if dados['simples']['optante']:
    print("Empresa é optante do Simples Nacional")
    print(f"Data de opção: {dados['simples']['data_opcao']}")
else:
    print("Empresa não é optante do Simples Nacional")

# Listar registros estaduais
print(f"Registros estaduais: {len(dados['registros_estaduais'])}")
for registro in dados['registros_estaduais']:
    print(f"- {registro['estado']}: {registro['inscricao']}")
```

### 6. Consulta para Dashboard Executivo

```python
# Consulta dados essenciais para dashboard
dados = api.get_all_company_info("12345678000190",
    address=True,
    contact=True,
    activities=True
)

print("Categorias:", list(dados.keys()))
# Output: ['basico', 'endereco', 'contato', 'atividades']

# Dados para dashboard
dashboard_data = {
    'empresa': dados['basico']['razao_social'],
    'cnpj': dados['basico']['cnpj'],
    'situacao': dados['basico']['situacao'],
    'endereco': f"{dados['endereco']['logradouro']}, {dados['endereco']['cidade']}",
    'telefone': dados['contato'].get('telefone', 'N/A'),
    'atividade_principal': dados['atividades']['principal']['texto']
}

print("Dados do dashboard:", dashboard_data)
```

### 7. Consulta Completa (Todos os Dados)

```python
# Consulta todos os dados disponíveis
dados = api.get_all_company_info("12345678000190",
    simples=True,
    registrations='BR',
    geocoding=True,
    suframa=True,
    partners=True,
    activities=True,
    contact=True,
    address=True
)

print("Categorias completas:", list(dados.keys()))
# Output: ['basico', 'endereco', 'contato', 'atividades', 'socios', 
#          'simples', 'registros_estaduais', 'suframa']

print("Total de categorias:", len(dados))
```

## Integração com Sistema SaaS

### Exemplo de Endpoint com Parâmetros Opcionais

```python
from fastapi import FastAPI, Query
from typing import Optional

app = FastAPI()

@app.post("/cnpj/consulta")
async def consultar_cnpj(
    cnpj: str,
    incluir_simples: bool = Query(False, description="Incluir dados do Simples Nacional"),
    incluir_suframa: bool = Query(False, description="Incluir dados de SUFRAMA"),
    incluir_registros: Optional[str] = Query(None, description="Incluir registros estaduais (ex: 'BR')"),
    incluir_geocoding: bool = Query(False, description="Incluir dados de geolocalização"),
    incluir_socios: bool = Query(True, description="Incluir dados de sócios"),
    incluir_atividades: bool = Query(True, description="Incluir atividades econômicas"),
    incluir_contato: bool = Query(True, description="Incluir dados de contato"),
    incluir_endereco: bool = Query(True, description="Incluir dados de endereço")
):
    """Consulta CNPJ com parâmetros seletivos."""
    
    api = CNPJaAPI()
    
    # Montar parâmetros baseado na query
    params = {
        'simples': incluir_simples,
        'suframa': incluir_suframa,
        'registrations': incluir_registros,
        'geocoding': incluir_geocoding,
        'partners': incluir_socios,
        'activities': incluir_atividades,
        'contact': incluir_contato,
        'address': incluir_endereco
    }
    
    # Consultar dados
    dados = api.get_all_company_info(cnpj, save_to_db=False, **params)
    
    return {
        "success": True,
        "cnpj": cnpj,
        "categorias_incluidas": list(dados.keys()),
        "total_categorias": len(dados),
        "dados": dados
    }
```

### Exemplo de Uso da API

```bash
# Consulta básica
curl -X POST "http://localhost:8000/cnpj/consulta?cnpj=12345678000190"

# Consulta com SUFRAMA
curl -X POST "http://localhost:8000/cnpj/consulta?cnpj=12345678000190&incluir_suframa=true"

# Consulta completa
curl -X POST "http://localhost:8000/cnpj/consulta?cnpj=12345678000190&incluir_simples=true&incluir_suframa=true&incluir_registros=BR&incluir_geocoding=true"
```

## Benefícios da Extração Seletiva

### 1. Performance
- **Menos dados transferidos**: Reduz o tamanho da resposta
- **Processamento mais rápido**: Menos dados para processar
- **Cache mais eficiente**: Dados específicos podem ser cacheados separadamente

### 2. Flexibilidade
- **Casos de uso específicos**: Cada endpoint pode solicitar apenas o necessário
- **Planos diferenciados**: Diferentes níveis de acesso podem ter diferentes dados
- **Integração gradual**: Pode ser implementado gradualmente

### 3. Economia de Recursos
- **Menos uso de API**: Solicita apenas dados necessários
- **Menos armazenamento**: Dados desnecessários não são salvos
- **Menos processamento**: Reduz carga no servidor

### 4. Experiência do Usuário
- **Respostas mais rápidas**: Menos dados = resposta mais rápida
- **Dados relevantes**: Usuário recebe apenas o que precisa
- **Interface mais limpa**: Dados organizados por categoria

## Casos de Uso Recomendados

| Cenário | Parâmetros Recomendados | Justificativa |
|---------|------------------------|---------------|
| Validação básica | `address=True` | Apenas dados essenciais |
| Análise societária | `partners=True` | Foco em sócios |
| Verificação fiscal | `simples=True, registrations='BR'` | Dados fiscais completos |
| Análise de incentivos | `suframa=True` | Foco em SUFRAMA |
| Dashboard executivo | `address=True, contact=True, activities=True` | Visão geral |
| Consulta completa | Todos os parâmetros | Análise detalhada |

## Considerações Técnicas

### 1. Parâmetros Padrão
- `basic`: Sempre incluído (dados essenciais)
- `address`, `contact`, `activities`, `partners`: `True` por padrão
- `simples`, `suframa`, `geocoding`: `False` por padrão
- `registrations`: `None` por padrão

### 2. Compatibilidade
- Mantém compatibilidade com código existente
- Parâmetros não especificados usam valores padrão
- API CNPJa recebe apenas parâmetros válidos

### 3. Tratamento de Erros
- Parâmetros inválidos são ignorados silenciosamente
- Dados básicos sempre incluídos mesmo com erros
- Logs detalhados para debugging
