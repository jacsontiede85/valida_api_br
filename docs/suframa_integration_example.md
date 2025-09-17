# Integração de Dados SUFRAMA - Exemplo de Uso

## Visão Geral

A funcionalidade de extração de dados SUFRAMA foi implementada na classe `CNPJaAPI` para permitir a consulta de informações sobre registros de incentivos fiscais da Superintendência da Zona Franca de Manaus (SUFRAMA).

## Como Usar

### 1. Consulta Básica com SUFRAMA

```python
from src.utils.cnpja_api import CNPJaAPI

# Inicializar cliente da API
api = CNPJaAPI()

# Parâmetros para incluir dados de SUFRAMA
params = {
    'suframa': True,  # Incluir dados de SUFRAMA
    'simples': True,
    'registrations': 'BR',
    'geocoding': True
}

# Consultar CNPJ com dados de SUFRAMA
dados = api.get_all_company_info("04337168000148", **params)

# Acessar dados de SUFRAMA
suframa_data = dados['suframa']
```

### 2. Extração Seletiva de Dados

A função `get_all_company_info` agora suporta extração seletiva baseada nos parâmetros habilitados:

```python
# Apenas dados básicos (sempre incluído)
dados_basicos = api.get_all_company_info("12345678000190")
# Retorna: {'basico': {...}}

# Dados básicos + endereço + contato
dados_contato = api.get_all_company_info("12345678000190", 
    address=True, 
    contact=True
)
# Retorna: {'basico': {...}, 'endereco': {...}, 'contato': {...}}

# Apenas SUFRAMA (sempre inclui básicos)
dados_suframa = api.get_all_company_info("12345678000190", 
    suframa=True
)
# Retorna: {'basico': {...}, 'suframa': [...]}

# Dados completos
dados_completos = api.get_all_company_info("12345678000190",
    simples=True,
    registrations='BR',
    geocoding=True,
    suframa=True,
    partners=True,
    activities=True,
    contact=True,
    address=True
)
# Retorna: {'basico': {...}, 'endereco': {...}, 'contato': {...}, 
#          'atividades': {...}, 'socios': [...], 'simples': {...}, 
#          'registros_estaduais': [...], 'suframa': [...]}
```

### 3. Parâmetros de Controle

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `basic` | `True` | Dados básicos (sempre incluído) |
| `address` | `True` | Dados de endereço |
| `contact` | `True` | Dados de contato |
| `activities` | `True` | Atividades econômicas |
| `partners` | `True` | Dados de sócios |
| `simples` | `False` | Dados do Simples Nacional |
| `registrations` | `None` | Registros estaduais (ex: 'BR') |
| `geocoding` | `False` | Dados de geolocalização |
| `suframa` | `False` | Dados de SUFRAMA |

### 2. Estrutura dos Dados SUFRAMA

```python
# Exemplo de estrutura retornada
{
    'suframa': [
        {
            'numero': '200106023',
            'data_inicio': '20/03/2018',
            'aprovado': True,
            'data_aprovacao': '18/12/2006',
            'status': {
                'id': 1,
                'texto': 'Ativa'
            },
            'incentivos': [
                {
                    'tributo': 'IPI',
                    'beneficio': 'Isenção',
                    'finalidade': 'Consumo Interno, Industrialização e Utilização',
                    'base_legal': 'Decreto 7.212 de 2010 (Art. 81)'
                },
                {
                    'tributo': 'ICMS',
                    'beneficio': 'Isenção',
                    'finalidade': 'Industrialização e Comercialização',
                    'base_legal': 'Convênio ICMS n° 65 de 1988'
                }
            ]
        }
    ]
}
```

### 3. Processamento dos Dados

```python
def processar_dados_suframa(dados_empresa):
    """Processa dados de SUFRAMA de uma empresa."""
    
    suframa_data = dados_empresa.get('suframa', [])
    
    if not suframa_data:
        print("Empresa não possui registros SUFRAMA")
        return
    
    print(f"Empresa possui {len(suframa_data)} registro(s) SUFRAMA")
    
    for i, registro in enumerate(suframa_data, 1):
        print(f"\n--- Registro SUFRAMA {i} ---")
        print(f"Número: {registro['numero']}")
        print(f"Status: {registro['status']['texto']}")
        print(f"Aprovado: {'Sim' if registro['aprovado'] else 'Não'}")
        print(f"Data Início: {registro['data_inicio']}")
        print(f"Data Aprovação: {registro['data_aprovacao']}")
        
        # Processar incentivos fiscais
        incentivos = registro.get('incentivos', [])
        if incentivos:
            print(f"\nIncentivos Fiscais ({len(incentivos)}):")
            for j, incentivo in enumerate(incentivos, 1):
                print(f"  {j}. {incentivo['tributo']} - {incentivo['beneficio']}")
                print(f"     Finalidade: {incentivo['finalidade']}")
                print(f"     Base Legal: {incentivo['base_legal']}")

# Exemplo de uso
api = CNPJaAPI()
dados = api.get_all_company_info("04337168000148", suframa=True)
processar_dados_suframa(dados)
```

### 4. Integração com Sistema SaaS

```python
# Exemplo de como integrar com o sistema de API keys
from api.services.api_key_service import APIKeyService
from api.middleware.auth_middleware import get_current_api_user

@router.post("/cnpj/consulta-completa")
async def consulta_completa_cnpj(
    request: CNPJRequest,
    user_api_key: tuple = Depends(get_current_api_user)
):
    """Consulta CNPJ com todos os dados incluindo SUFRAMA."""
    
    user, api_key = user_api_key
    
    # Verificar limites do usuário
    if not await check_user_limits(user.id):
        raise HTTPException(402, "Limite de consultas excedido")
    
    # Configurar parâmetros para dados completos
    params = {
        'suframa': True,
        'simples': True,
        'registrations': 'BR',
        'geocoding': True
    }
    
    # Consultar dados
    api_cnpja = CNPJaAPI()
    dados_completos = api_cnpja.get_all_company_info(
        request.cnpj, 
        save_to_db=True,
        **params
    )
    
    # Log da consulta
    await log_api_usage(user.id, api_key.id, "consulta_completa")
    
    return {
        "success": True,
        "data": dados_completos,
        "includes_suframa": len(dados_completos.get('suframa', [])) > 0
    }
```

## Campos Extraídos

### Informações Básicas do Registro
- `numero`: Número do registro SUFRAMA
- `data_inicio`: Data de início do registro
- `aprovado`: Se o registro foi aprovado (boolean)
- `data_aprovacao`: Data de aprovação do registro

### Status do Registro
- `status.id`: ID do status
- `status.texto`: Descrição do status (ex: "Ativa", "Inativa")

### Incentivos Fiscais
- `tributo`: Tipo de tributo (ex: "IPI", "ICMS")
- `beneficio`: Tipo de benefício (ex: "Isenção", "Redução")
- `finalidade`: Finalidade do incentivo
- `base_legal`: Base legal do incentivo

## Tratamento de Erros

A função `extract_suframa_info` retorna uma lista vazia `[]` quando:
- O CNPJ não possui registros SUFRAMA
- Os dados de SUFRAMA não estão disponíveis na API
- O parâmetro `suframa=True` não foi passado na consulta

## Performance

- A extração de dados SUFRAMA é feita localmente após receber a resposta da API
- Não há impacto significativo na performance da consulta
- Os dados são estruturados de forma consistente com o padrão das outras extrações

## Compatibilidade

- Compatível com a versão atual da API CNPJa
- Mantém compatibilidade com todas as funcionalidades existentes
- Integra-se perfeitamente com o sistema de cache e logging
