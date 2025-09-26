from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from api.middleware.auth_middleware import validate_jwt_or_api_key, AuthUser
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documentation", tags=["documentation"])

@router.get("/", response_class=HTMLResponse)
async def documentation_page(request: Request):
    """
    Página principal de documentação da API
    """
    try:
        # Renderizar template de documentação
        from fastapi.templating import Jinja2Templates
        templates = Jinja2Templates(directory="templates")
        
        return templates.TemplateResponse("documentation.html", {
            "request": request,
            "user": None,  # Não precisa de usuário para visualizar documentação
            "api_base_url": str(request.base_url).rstrip('/')
        })
    except Exception as e:
        logger.error(f"Erro ao renderizar página de documentação: {str(e)}")
        raise

@router.get("/api-data")
async def get_api_documentation_data():
    """
    Endpoint para servir dados da documentação da API (sem autenticação)
    """
    try:
        documentation_data = {
            "endpoints": [
                {
                    "path": "/api/v1/cnpj/consult",
                    "method": "POST",
                    "description": "Consulta CNPJ com dados completos - protestos + receita federal",
                    "authentication": {
                        "frontend": "Use o token JWT da sessão (automatic via cookies)",
                        "external": "Use header `Authorization: Bearer rcp_sua_api_key_aqui`"
                    },
                    "parameters": {
                        "cnpj": {
                            "type": "string",
                            "required": True,
                            "description": "CNPJ para consulta (pode ser formatado ou não)",
                            "example": "12.345.678/0001-95"
                        },
                        "protestos": {
                            "type": "boolean",
                            "required": False,
                            "default": True,
                            "description": "Consultar protestos"
                        },
                        "receita_federal": {
                            "type": "boolean",
                            "required": False,
                            "default": False,
                            "description": "Consultar dados da Receita Federal"
                        },
                        "simples": {
                            "type": "boolean",
                            "required": False,
                            "default": False,
                            "description": "Dados Simples Nacional"
                        },
                        "registrations": {
                            "type": "boolean",
                            "required": False,
                            "default": False,
                            "description": "Buscar inscrições estaduais"
                        },
                        "geocoding": {
                            "type": "boolean",
                            "required": False,
                            "default": False,
                            "description": "Geolocalização"
                        },
                        "suframa": {
                            "type": "boolean",
                            "required": False,
                            "default": False,
                            "description": "Dados SUFRAMA"
                        },
                        "strategy": {
                            "type": "string",
                            "required": False,
                            "default": "CACHE_IF_FRESH",
                            "description": "Cache strategy",
                            "options": {
                                "CACHE_IF_FRESH": "Buscar dados do cache se estiver atualizado (<=20 dias)",
                                "ONLINE": "Buscar sempre online nas fontes e não usar cache (mais lento e maior custo)"
                            }
                        },
                        "extract_basic": {
                            "type": "boolean",
                            "required": False,
                            "default": True,
                            "description": "Dados básicos da empresa"
                        },
                        "extract_address": {
                            "type": "boolean",
                            "required": False,
                            "default": True,
                            "description": "Endereço"
                        },
                        "extract_contact": {
                            "type": "boolean",
                            "required": False,
                            "default": True,
                            "description": "Contatos"
                        },
                        "extract_activities": {
                            "type": "boolean",
                            "required": False,
                            "default": True,
                            "description": "CNAEs"
                        },
                        "extract_partners": {
                            "type": "boolean",
                            "required": False,
                            "default": True,
                            "description": "Sócios"
                        }
                    },
                    "response": {
                        "success": {
                            "type": "boolean",
                            "description": "Indica se a consulta foi bem-sucedida"
                        },
                        "cnpj": {
                            "type": "string",
                            "description": "CNPJ consultado"
                        },
                        "has_protests": {
                            "type": "boolean",
                            "description": "Indica se foram encontrados protestos"
                        },
                        "total_protests": {
                            "type": "integer",
                            "description": "Número total de protestos encontrados"
                        },
                        "protestos": {
                            "type": "array",
                            "description": "Lista de protestos encontrados"
                        },
                        "dados_receita": {
                            "type": "object",
                            "description": "Dados da Receita Federal"
                        },
                        "cache_used": {
                            "type": "boolean",
                            "description": "Indica se foi usado cache"
                        },
                        "response_time_ms": {
                            "type": "integer",
                            "description": "Tempo de resposta em milissegundos"
                        },
                        "timestamp": {
                            "type": "string",
                            "description": "Timestamp da consulta"
                        }
                    },
                    "examples": {
                        "javascript": {
                            "code": """const response = await fetch('/api/v1/cnpj/consult', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
    },
    body: JSON.stringify({
        cnpj: "12.345.678/0001-95",
        protestos: true,
        receita_federal: true
    })
});

const result = await response.json();
console.log(result);""",
                            "description": "Exemplo usando Fetch API no frontend"
                        },
                        "python": {
                            "code": """import requests

url = "http://localhost:2377/api/v1/cnpj/consult"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer rcp_sua_api_key_aqui"
}
data = {
    "cnpj": "12.345.678/0001-95",
    "protestos": True,
    "receita_federal": True,
    "simples": True,
    "registrations": True,
    "strategy": "CACHE_IF_FRESH"
}

response = requests.post(url, json=data, headers=headers, timeout=45)

if response.status_code == 200:
    result = response.json()
    print(f"Consulta realizada com sucesso!")
    print(f"CNPJ: {result['cnpj']}")
    print(f"Protestos encontrados: {result['has_protests']}")
else:
    print(f"Erro: {response.status_code}")
    print(response.json())""",
                            "description": "Exemplo usando Python requests"
                        },
                        "curl": {
                            "code": """curl -X POST "http://localhost:2377/api/v1/cnpj/consult" \\
     -H "Content-Type: application/json" \\
     -H "Authorization: Bearer rcp_sua_api_key_aqui" \\
     -d '{
       "cnpj": "12.345.678/0001-95",
       "protestos": true,
       "receita_federal": true,
       "simples": true,
       "registrations": true,
       "strategy": "CACHE_IF_FRESH"
     }'""",
                            "description": "Exemplo usando cURL"
                        }
                    }
                }
            ],
            "error_codes": {
                "400": {
                    "description": "Bad Request - Parâmetros inválidos",
                    "examples": [
                        "CNPJ deve ter 14 dígitos numéricos",
                        "Parâmetro obrigatório não fornecido"
                    ]
                },
                "401": {
                    "description": "Unauthorized - Token inválido ou expirado",
                    "examples": [
                        "Token JWT inválido",
                        "API Key inválida"
                    ]
                },
                "402": {
                    "description": "Payment Required - Limite de consultas excedido",
                    "examples": [
                        "Limite de consultas excedido",
                        "Créditos insuficientes"
                    ]
                },
                "403": {
                    "description": "Forbidden - Acesso negado",
                    "examples": [
                        "API Key inativa",
                        "Usuário sem permissão"
                    ]
                },
                "429": {
                    "description": "Too Many Requests - Rate limit excedido",
                    "examples": [
                        "Muitas requisições por minuto",
                        "Rate limit do plano excedido"
                    ]
                },
                "500": {
                    "description": "Internal Server Error - Erro interno do servidor",
                    "examples": [
                        "Erro na consulta aos serviços externos",
                        "Timeout na consulta"
                    ]
                }
            },
            "rate_limits": {
                "basic": "100 consultas/mês",
                "pro": "1.000 consultas/mês",
                "enterprise": "Consultas ilimitadas"
            },
            "user_api_keys": []  # Vazio para documentação pública
        }

        return documentation_data

    except Exception as e:
        logger.error(f"Erro ao buscar dados da documentação: {str(e)}")
        raise

@router.get("/api-data/authenticated")
async def get_authenticated_api_data(user: AuthUser = Depends(validate_jwt_or_api_key)):
    """
    Endpoint para servir dados da documentação da API para usuários autenticados
    """
    try:
        from api.services.api_key_service import api_key_service
        
        # Buscar API keys do usuário
        user_api_keys = await api_key_service.get_user_api_keys(user.user_id)
        active_keys = [k for k in user_api_keys if k.is_active]
        
        # Formatar API keys para o frontend
        formatted_keys = []
        for key in active_keys:
            formatted_keys.append({
                "key": key.key,
                "name": key.name or "API Key",
                "is_active": key.is_active,
                "created_at": key.created_at.isoformat() if key.created_at else None
            })
        
        documentation_data = {
            "endpoints": [
                {
                    "path": "/api/v1/cnpj/consult",
                    "method": "POST",
                    "description": "Consulta CNPJ com dados completos - protestos + receita federal",
                    "authentication": {
                        "frontend": "Use o token JWT da sessão (automatic via cookies)",
                        "external": "Use header `Authorization: Bearer rcp_sua_api_key_aqui`"
                    },
                    "parameters": {
                        "cnpj": {
                            "type": "string",
                            "required": True,
                            "description": "CNPJ para consulta (pode ser formatado ou não)",
                            "example": "12.345.678/0001-95"
                        },
                        "protestos": {
                            "type": "boolean",
                            "required": False,
                            "default": True,
                            "description": "Consultar protestos"
                        },
                        "receita_federal": {
                            "type": "boolean",
                            "required": False,
                            "default": False,
                            "description": "Consultar dados da Receita Federal"
                        },
                        "simples": {
                            "type": "boolean",
                            "required": False,
                            "default": False,
                            "description": "Dados Simples Nacional"
                        },
                        "registrations": {
                            "type": "boolean",
                            "required": False,
                            "default": False,
                            "description": "Buscar inscrições estaduais"
                        },
                        "geocoding": {
                            "type": "boolean",
                            "required": False,
                            "default": False,
                            "description": "Geolocalização"
                        },
                        "suframa": {
                            "type": "boolean",
                            "required": False,
                            "default": False,
                            "description": "Dados SUFRAMA"
                        },
                        "strategy": {
                            "type": "string",
                            "required": False,
                            "default": "CACHE_IF_FRESH",
                            "description": "Cache strategy",
                            "options": {
                                "CACHE_IF_FRESH": "Buscar dados do cache se estiver atualizado (<=20 dias)",
                                "ONLINE": "Buscar sempre online nas fontes e não usar cache (mais lento e maior custo)"
                            }
                        },
                        "extract_basic": {
                            "type": "boolean",
                            "required": False,
                            "default": True,
                            "description": "Dados básicos da empresa"
                        },
                        "extract_address": {
                            "type": "boolean",
                            "required": False,
                            "default": True,
                            "description": "Endereço"
                        },
                        "extract_contact": {
                            "type": "boolean",
                            "required": False,
                            "default": True,
                            "description": "Contatos"
                        },
                        "extract_activities": {
                            "type": "boolean",
                            "required": False,
                            "default": True,
                            "description": "CNAEs"
                        },
                        "extract_partners": {
                            "type": "boolean",
                            "required": False,
                            "default": True,
                            "description": "Sócios"
                        }
                    },
                    "response": {
                        "success": {
                            "type": "boolean",
                            "description": "Indica se a consulta foi bem-sucedida"
                        },
                        "cnpj": {
                            "type": "string",
                            "description": "CNPJ consultado"
                        },
                        "has_protests": {
                            "type": "boolean",
                            "description": "Indica se foram encontrados protestos"
                        },
                        "total_protests": {
                            "type": "integer",
                            "description": "Número total de protestos encontrados"
                        },
                        "protestos": {
                            "type": "array",
                            "description": "Lista de protestos encontrados"
                        },
                        "dados_receita": {
                            "type": "object",
                            "description": "Dados da Receita Federal"
                        },
                        "cache_used": {
                            "type": "boolean",
                            "description": "Indica se foi usado cache"
                        },
                        "response_time_ms": {
                            "type": "integer",
                            "description": "Tempo de resposta em milissegundos"
                        },
                        "timestamp": {
                            "type": "string",
                            "description": "Timestamp da consulta"
                        }
                    },
                    "examples": {
                        "javascript": {
                            "code": """const response = await fetch('/api/v1/cnpj/consult', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
    },
    body: JSON.stringify({
        cnpj: "12.345.678/0001-95",
        protestos: true,
        receita_federal: true
    })
});

const result = await response.json();
console.log(result);""",
                            "description": "Exemplo usando Fetch API no frontend"
                        },
                        "python": {
                            "code": """import requests

url = "http://localhost:2377/api/v1/cnpj/consult"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer rcp_sua_api_key_aqui"
}
data = {
    "cnpj": "12.345.678/0001-95",
    "protestos": True,
    "receita_federal": True,
    "simples": True,
    "registrations": True,
    "strategy": "CACHE_IF_FRESH"
}

response = requests.post(url, json=data, headers=headers, timeout=45)

if response.status_code == 200:
    result = response.json()
    print(f"Consulta realizada com sucesso!")
    print(f"CNPJ: {result['cnpj']}")
    print(f"Protestos encontrados: {result['has_protests']}")
else:
    print(f"Erro: {response.status_code}")
    print(response.json())""",
                            "description": "Exemplo usando Python requests"
                        },
                        "curl": {
                            "code": """curl -X POST "http://localhost:2377/api/v1/cnpj/consult" \\
     -H "Content-Type: application/json" \\
     -H "Authorization: Bearer rcp_sua_api_key_aqui" \\
     -d '{
       "cnpj": "12.345.678/0001-95",
       "protestos": true,
       "receita_federal": true,
       "simples": true,
       "registrations": true,
       "strategy": "CACHE_IF_FRESH"
     }'""",
                            "description": "Exemplo usando cURL"
                        }
                    }
                }
            ],
            "error_codes": {
                "400": {
                    "description": "Bad Request - Parâmetros inválidos",
                    "examples": [
                        "CNPJ deve ter 14 dígitos numéricos",
                        "Parâmetro obrigatório não fornecido"
                    ]
                },
                "401": {
                    "description": "Unauthorized - Token inválido ou expirado",
                    "examples": [
                        "Token JWT inválido",
                        "API Key inválida"
                    ]
                },
                "402": {
                    "description": "Payment Required - Limite de consultas excedido",
                    "examples": [
                        "Limite de consultas excedido",
                        "Créditos insuficientes"
                    ]
                },
                "403": {
                    "description": "Forbidden - Acesso negado",
                    "examples": [
                        "API Key inativa",
                        "Usuário sem permissão"
                    ]
                },
                "429": {
                    "description": "Too Many Requests - Rate limit excedido",
                    "examples": [
                        "Muitas requisições por minuto",
                        "Rate limit do plano excedido"
                    ]
                },
                "500": {
                    "description": "Internal Server Error - Erro interno do servidor",
                    "examples": [
                        "Erro na consulta aos serviços externos",
                        "Timeout na consulta"
                    ]
                }
            },
            "rate_limits": {
                "basic": "100 consultas/mês",
                "pro": "1.000 consultas/mês",
                "enterprise": "Consultas ilimitadas"
            },
            "user_api_keys": formatted_keys  # API keys do usuário autenticado
        }

        return documentation_data

    except Exception as e:
        logger.error(f"Erro ao buscar dados da documentação autenticada: {str(e)}")
        raise

@router.get("/test-auth")
async def test_auth(user: AuthUser = Depends(validate_jwt_or_api_key)):
    """
    Endpoint de teste para verificar se a autenticação está funcionando
    """
    return {
        "success": True,
        "user_id": user.user_id,
        "message": "Autenticação funcionando corretamente"
    }

@router.post("/playground/test")
async def test_api_endpoint(
    request_data: dict,
    user: AuthUser = Depends(validate_jwt_or_api_key)
):
    """
    Endpoint para testar a API via playground
    """
    try:
        # Validar dados de entrada
        if not request_data.get("cnpj"):
            raise ValueError("CNPJ é obrigatório")
        
        # Usar a API key fornecida ou a primeira ativa do usuário
        api_key = request_data.get("api_key")
        if not api_key:
            from api.services.api_key_service import api_key_service
            user_api_keys = await api_key_service.get_user_api_keys(user.user_id)
            active_keys = [k for k in user_api_keys if k.is_active]
            if not active_keys:
                raise ValueError("Nenhuma API key ativa encontrada")
            api_key = active_keys[0].key
        
        # Fazer a requisição para a API real
        import httpx
        import json
        
        # Preparar dados da requisição
        test_data = {
            "cnpj": request_data.get("cnpj"),
            "protestos": request_data.get("protestos", True),
            "receita_federal": request_data.get("receita_federal", False),
            "simples": request_data.get("simples", False),
            "registrations": request_data.get("registrations", False),
            "geocoding": request_data.get("geocoding", False),
            "suframa": request_data.get("suframa", False),
            "strategy": request_data.get("strategy", "CACHE_IF_FRESH"),
            "extract_basic": request_data.get("extract_basic", True),
            "extract_address": request_data.get("extract_address", True),
            "extract_contact": request_data.get("extract_contact", True),
            "extract_activities": request_data.get("extract_activities", True),
            "extract_partners": request_data.get("extract_partners", True)
        }
        
        # Fazer requisição interna para a API
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:2377/api/v1/cnpj/consult",
                json=test_data,
                headers=headers,
                timeout=45.0
            )
        
        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "response_data": response.json() if response.status_code == 200 else {"error": response.text},
            "request_data": test_data,
            "api_key_used": api_key[:8] + "****" + api_key[-4:]
        }
        
    except Exception as e:
        logger.error(f"Erro no playground: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "status_code": 500
        }
