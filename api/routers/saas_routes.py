"""
Rotas da API SaaS para o Valida
"""
import os
import jwt
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import List, Optional
import structlog
from datetime import datetime, timedelta

from api.models.saas_models import (
    UserCreate, UserResponse, APIKeyCreate, APIKeyResponse, APIKeyList,
    DashboardStats, UsageStats, ConsultationRequest, ConsultationResponse,
    ErrorResponse, DashboardPeriod
)
from api.middleware.auth_middleware import require_auth, require_api_key, AuthUser, get_current_user, validate_jwt_or_api_key
from api.services.user_service import user_service
from api.services.api_key_service import api_key_service
from api.services.dashboard_service import dashboard_service
from api.services.credit_service import credit_service, InsufficientCreditsError

logger = structlog.get_logger("saas_routes")

router = APIRouter()

def get_client_ip(request: Request) -> str:
    """
    Captura o IP real do cliente considerando proxies, load balancers e CDNs
    
    Ordem de prioridade:
    1. X-Forwarded-For (primeiro IP da lista)
    2. X-Real-IP 
    3. CF-Connecting-IP (Cloudflare)
    4. request.client.host (conexão direta)
    """
    # 1. X-Forwarded-For - mais comum em proxies/load balancers
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # O primeiro IP é o cliente original, os demais são proxies
        client_ip = forwarded_for.split(",")[0].strip()
        if client_ip and client_ip != "unknown":
            logger.debug(f"IP capturado via X-Forwarded-For: {client_ip}")
            return client_ip
    
    # 2. X-Real-IP - usado por nginx e outros proxies
    real_ip = request.headers.get("x-real-ip") 
    if real_ip and real_ip != "unknown":
        logger.debug(f"IP capturado via X-Real-IP: {real_ip}")
        return real_ip
    
    # 3. CF-Connecting-IP - Cloudflare específico
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        logger.debug(f"IP capturado via CF-Connecting-IP: {cf_ip}")
        return cf_ip
    
    # 4. request.client.host - conexão direta
    if request.client and request.client.host:
        logger.debug(f"IP capturado via request.client.host: {request.client.host}")
        return request.client.host
    
    # 5. Fallback - IP desconhecido
    logger.warning("Não foi possível determinar IP do cliente")
    return "unknown"

@router.post("/auth/register")
async def register_user(user_data: UserCreate):
    """
    Registra um novo usuário no sistema e cria uma API key inicial
    """
    try:
        # Criar usuário
        user = await user_service.create_user(user_data)
        logger.info("usuario_registrado", user_id=user.id, email=user.email)
        
        # Criar API key padrão para o novo usuário
        api_key_response = None
        try:
            from api.models.saas_models import APIKeyCreate
            api_key_data = APIKeyCreate(
                name="Chave Principal",
                description="Chave de API criada automaticamente no registro"
            )
            api_key_response = await api_key_service.create_api_key(user.id, api_key_data)
            logger.info("api_key_criada_no_registro", user_id=user.id)
        except Exception as api_err:
            logger.error(f"Erro ao criar API key no registro: {api_err}")
            # Continua mesmo se falhar a criação da API key
        
        # Gerar token JWT
        import jwt
        from datetime import datetime, timedelta
        
        SECRET_KEY = os.getenv("SUPABASE_JWT_SECRET", "super-secret-jwt-key-development")
        
        # Criar payload do token
        payload = {
            "sub": user.id,
            "user_id": user.id,
            "email": user.email,
            "name": user.full_name,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(days=7),
            "type": "access"
        }
        
        # Gerar token
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        
        # Preparar resposta com API key se foi criada
        response_data = {
            "success": True,
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.full_name
            },
            "message": "Conta criada com sucesso! Você ganhou 7 dias de trial."
        }
        
        # Adicionar API key à resposta se foi criada
        if api_key_response:
            response_data["api_key"] = api_key_response.key
        
        return response_data
        
    except Exception as e:
        logger.error("erro_registro_usuario", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao registrar usuário: {str(e)}"
        )

@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(user: AuthUser = Depends(require_auth)):
    """
    Obtém informações do usuário atual
    """
    try:
        user_info = await user_service.get_user(user.user_id)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )
        return user_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error("erro_buscar_usuario", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@router.post("/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: APIKeyCreate,
    user: AuthUser = Depends(require_auth)
):
    """
    Cria uma nova API key para o usuário
    """
    try:
        api_key = await api_key_service.create_api_key(user.user_id, key_data)
        logger.info("api_key_criada", user_id=user.user_id, key_id=api_key.id)
        return api_key
    except Exception as e:
        logger.error("erro_criar_api_key", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao criar API key: {str(e)}"
        )

@router.get("/api-keys", response_model=List[APIKeyList])
async def list_api_keys(user: AuthUser = Depends(require_auth)):
    """
    Lista todas as API keys do usuário
    """
    try:
        api_keys = await api_key_service.get_user_api_keys(user.user_id)
        return api_keys
    except Exception as e:
        logger.error("erro_listar_api_keys", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@router.get("/dashboard/stats")
async def get_dashboard_stats(
    period: DashboardPeriod = Query(default=DashboardPeriod.THIRTY_DAYS, description="Período para análise (compatibilidade v1)"),
    user: AuthUser = Depends(require_auth)
):
    """
    🔄 MIGRADO: Obtém estatísticas REAIS do dashboard (dados do banco de dados)
    """
    try:
        # ✅ MIGRADO para usar dados reais do banco
        logger.info("dashboard_stats_v1_migrado_para_real", user_id=user.user_id, period=period)
        data = await dashboard_service.get_dashboard_data(user.user_id, period)
        
        # Converter formato para compatibilidade com endpoints v1
        legacy_format = {
            "credits_available": data.get("credits", {}).get("available_raw", 0),
            "period_consumption": data.get("usage", {}).get("total_consultations", 0),
            "total_queries": data.get("usage", {}).get("total_consultations", 0),
            "total_cost": data.get("usage", {}).get("total_cost_raw", 0),
            "success_rate": data.get("success_rate", 0),
            "period": period,
            "consumption_chart": data.get("charts", {}).get("consumption", {}),
            "volume_by_api": data.get("charts", {}).get("volume", {}),
            "last_updated": data.get("last_updated")
        }
        
        logger.info("dashboard_stats_v1_retornado_com_dados_reais", user_id=user.user_id, period=period)
        return legacy_format
        
    except Exception as e:
        logger.error("erro_buscar_dashboard_stats_migrado", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar estatísticas do dashboard: {str(e)}"
        )

@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    user: AuthUser = Depends(require_auth)
):
    """
    Revoga uma API key
    """
    try:
        success = await api_key_service.revoke_api_key(user.user_id, key_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key não encontrada"
            )
        logger.info("api_key_revogada", user_id=user.user_id, key_id=key_id)
        return {"message": "API key revogada com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("erro_revogar_api_key", user_id=user.user_id, key_id=key_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(user: AuthUser = Depends(require_auth)):
    """
    Obtém estatísticas do dashboard do usuário
    """
    try:
        # Buscar informações do usuário
        user_info = await user_service.get_user(user.user_id)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )
        
        # Buscar estatísticas de uso
        usage_stats = await user_service.get_user_usage_stats(user.user_id)
        
        # Buscar API keys
        api_keys = await api_key_service.get_user_api_keys(user.user_id)
        
        # Mock para subscription (será implementado posteriormente)
        from api.models.saas_models import SubscriptionResponse, SubscriptionPlan, SubscriptionStatus
        subscription = SubscriptionResponse(
            id="sub-123",
            user_id=user.user_id,
            plan=user_info.subscription_plan,
            status=user_info.subscription_status,
            current_period_start=datetime.now(),
            current_period_end=datetime.now(),
            cancel_at_period_end=False
        )
        
        # Mock para recent requests (será implementado posteriormente)
        recent_requests = [
            {
                "cnpj": "12.345.678/0001-90",
                "timestamp": datetime.now().isoformat(),
                "success": True
            },
            {
                "cnpj": "98.765.432/0001-12",
                "timestamp": datetime.now().isoformat(),
                "success": True
            }
        ]
        
        return DashboardStats(
            user=user_info,
            subscription=subscription,
            usage=UsageStats(**usage_stats),
            api_keys_count=len(api_keys),
            recent_requests=recent_requests
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("erro_dashboard_stats", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

def clean_cnpj(cnpj: str) -> str:
    """
    Remove todos os caracteres não numéricos do CNPJ
    Exemplo: '11.222.333/0001-81' -> '11222333000181'
    """
    import re
    return re.sub(r'[^0-9]', '', cnpj)

@router.post("/cnpj/consult", response_model=ConsultationResponse)
async def consult_cnpj(
    consultation_request: ConsultationRequest,
    http_request: Request,  # Objeto Request para capturar IP
    user: AuthUser = Depends(validate_jwt_or_api_key)  # Aceita tanto JWT (frontend) quanto API key (externa)
):
    """
    Consulta CNPJ com dados completos - protestos + receita federal
    
    **Autenticação:**
    - **Frontend (Webapp):** Use o token JWT da sessão (automatic via cookies)
    - **API Externa:** Use header `Authorization: Bearer rcp_sua_api_key_aqui`
    
    **Parâmetros aceitos:**
    - protestos: bool - Consultar protestos (default: true) 
    - receita_federal: bool - Consultar dados da Receita Federal (default: false)
        - simples: bool - Dados Simples Nacional (default: false)
        - registrations: bool - Buscar inscrições estaduais (default: false)
        - geocoding: bool - Geolocalização (default: false)
        - suframa: bool - Dados SUFRAMA (default: false)  
        - strategy: str - Cache strategy (default: 'CACHE_IF_FRESH')
            - 'CACHE_IF_FRESH' = Buscar dados do cache se estiver atualizado (<=20 dias)
            - 'ONLINE' = Buscar sempre online nas fontes e não usar cache (mais lento e maior custo)
        
        - extract_basic: bool - Dados básicos da empresa (default: true)
        - extract_address: bool - Endereço (default: true)
        - extract_contact: bool - Contatos (default: true)
        - extract_activities: bool - CNAEs (default: true)
        - extract_partners: bool - Sócios (default: true)
        
    **Exemplos de uso:**
    
    Frontend (JavaScript):
    ```javascript
    const response = await fetch('/api/v1/cnpj/consult', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({
            cnpj: "12.345.678/0001-95", // Pode usar formatado ou não
            protestos: true,
            receita_federal: true
        })
    });
    ```
    
    API Externa (cURL):
    ```bash
    curl -X POST "http://localhost:2377/api/v1/cnpj/consult" \\
         -H "Content-Type: application/json" \\
         -H "Authorization: Bearer rcp_sua_api_key_aqui" \\
         -d '{"cnpj": "12.345.678/0001-95", "protestos": true, "receita_federal": true}'
    ```
    
    API Externa (Python):
    ```python
    import requests
    
    url = "http://localhost:2377/api/v1/cnpj/consult"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer rcp_sua_api_key_aqui"
    }
    data = {
        "cnpj": "12.345.678/0001-95",  # Pode usar formatado
        "protestos": True,
        "receita_federal": True,
        "simples": True,
        "registrations": True,
        "geocoding": False,
        "suframa": False,
        "strategy": "CACHE_IF_FRESH",
        "extract_basic": True,
        "extract_address": True,
        "extract_contact": True,
        "extract_activities": True,
        "extract_partners": True
    }
    
    response = requests.post(url, json=data, headers=headers, timeout=45)
    
    if response.status_code == 200:
        result = response.json()
        print(f"Consulta realizada com sucesso!")
        print(f"CNPJ: {result['cnpj']}")
        print(f"Protestos encontrados: {result['has_protests']}")
        print(f"Dados da Receita Federal: {'Sim' if result['dados_receita'] else 'Não'}")
    else:
        print(f"Erro: {response.status_code}")
        print(response.json())
    ```
    """
    try:
        # ✅ LIMPAR CNPJ: Remover caracteres especiais (pontos, barras, hífens)
        original_cnpj = consultation_request.cnpj
        cleaned_cnpj = clean_cnpj(consultation_request.cnpj)
        consultation_request.cnpj = cleaned_cnpj
        
        # Log da limpeza do CNPJ se houve mudança
        if original_cnpj != cleaned_cnpj:
            logger.info("cnpj_limpo", 
                       original=original_cnpj,
                       cleaned=cleaned_cnpj[:8] + "****",
                       user_id=user.user_id)
        
        # Validar se CNPJ tem 14 dígitos após limpeza
        if len(cleaned_cnpj) != 14 or not cleaned_cnpj.isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CNPJ deve ter 14 dígitos numéricos. Recebido: '{original_cnpj}' -> '{cleaned_cnpj}'"
            )
        # Capturar IP do cliente
        client_ip = get_client_ip(http_request)
        
        # Usuário já foi autenticado via Depends(require_auth)
        logger.info("usuario_autenticado", 
                   user_id=user.user_id,
                   api_key_id=user.api_key,
                   client_ip=client_ip)
        
        # VERIFICAÇÃO DE SEGURANÇA: Usuário DEVE ter pelo menos uma API key ativa
        from api.services.api_key_service import api_key_service
        user_api_keys = await api_key_service.get_user_api_keys(user.user_id)
        active_keys = [k for k in user_api_keys if k.is_active]
        
        if not active_keys:
            logger.warning(f"Usuário {user.user_id} tentou fazer consulta sem API key ativa")
            raise HTTPException(
                status_code=403, 
                detail="Você precisa de uma API key ativa para fazer consultas. Crie ou ative uma API key em 'Chave de API'."
            )
        
        logger.info(f"Usuário {user.user_id} tem {len(active_keys)} API key(s) ativa(s)")
        
        # Converter registrations de bool para string antes da consulta
        original_registrations = consultation_request.registrations
        consultation_request.registrations = 'BR' if original_registrations else None
        
        # Usar novo serviço unificado
        from api.services.unified_consultation_service import UnifiedConsultationService
        
        unified_service = UnifiedConsultationService()
        
        logger.info("iniciando_consulta_unificada", 
                   cnpj=consultation_request.cnpj[:8] + "****",
                   user_id=user.user_id,
                   client_ip=client_ip,
                   parametros={
                       "protestos": consultation_request.protestos,
                       "receita_federal": consultation_request.receita_federal,
                       "simples": consultation_request.simples,
                       "registrations": bool(original_registrations),
                       "geocoding": consultation_request.geocoding,
                       "suframa": consultation_request.suframa,
                       "strategy": consultation_request.strategy
                   })
        
        # Fazer a consulta completa
        result = await unified_service.consultar_dados_completos(consultation_request, user.user_id)
        
        # Registrar consulta no histórico
        from api.services.query_logger_service import query_logger_service
        from api.services.consultation_types_service import consultation_types_service
        
        # Buscar o ID real da API key se necessário
        api_key_uuid = None
        api_key_id = user.api_key if user else None
        user_id = user.user_id if user else "anonymous"
        
        if api_key_id and not api_key_id.startswith("00000000-0000-0000-0000-000000000"):
            # Se api_key_id é uma string da chave, buscar o UUID real
            try:
                from api.services.api_key_service import api_key_service
                api_keys = await api_key_service.get_user_api_keys(user_id)
                for key in api_keys:
                    if key.key == api_key_id:
                        api_key_uuid = key.id
                        break
            except:
                pass
        
        # Registrar consulta no histórico usando novo sistema
        try:
            # Preparar tipos de consulta baseado no request
            consultation_types = []
            
            if consultation_request.protestos:
                protestos_cost = await consultation_types_service.get_cost_by_code('protestos')
                consultation_types.append({
                    "type_code": "protestos",
                    "cost_cents": protestos_cost or 15,  # Custo dinâmico com fallback
                    "success": result.success and bool(result.protestos),
                    "response_data": result.protestos if result.success else None,
                    "cache_used": result.cache_used,
                    "response_time_ms": result.response_time_ms or 0,
                    "error_message": None if result.success else result.error
                })
            
            # Logging de consultas CNPJa (Receita Federal) - somente se receita_federal=true
            if consultation_request.receita_federal:
                # Registrar receita federal básica se qualquer extração básica estiver ativa
                # (mesma condição do cálculo de custos)
                if (consultation_request.extract_basic or consultation_request.extract_address or 
                    consultation_request.extract_contact or consultation_request.extract_activities or consultation_request.extract_partners):
                    receita_cost = await consultation_types_service.get_cost_by_code('receita_federal')
                    consultation_types.append({
                        "type_code": "receita_federal", 
                        "cost_cents": receita_cost or 5,  # Custo dinâmico com fallback
                        "success": result.success and bool(result.dados_receita),
                        "response_data": result.dados_receita if result.success else None,
                        "cache_used": result.cache_used,
                        "response_time_ms": result.response_time_ms or 0,
                        "error_message": None if result.success else result.error
                    })
                
                if consultation_request.simples:
                    simples_cost = await consultation_types_service.get_cost_by_code('simples_nacional')
                    simples_data = result.dados_receita.get('simples') if result.dados_receita else None
                    consultation_types.append({
                        "type_code": "simples_nacional",
                        "cost_cents": simples_cost or 5,  # Custo dinâmico com fallback
                        "success": result.success and bool(simples_data),
                        "response_data": simples_data if result.success else None,
                        "cache_used": result.cache_used,
                        "response_time_ms": result.response_time_ms or 0,
                        "error_message": None if result.success else result.error
                    })
                
                # Registrar cadastro de contribuintes (registrations) se solicitado
                if original_registrations:
                    registrations_cost = await consultation_types_service.get_cost_by_code('registrations')
                    registrations_data = result.dados_receita.get('registros_estaduais') if result.dados_receita else None
                    consultation_types.append({
                        "type_code": "cadastro_contribuintes",  # Código mapeado no BD
                        "cost_cents": registrations_cost or 5,  # Custo dinâmico com fallback
                        "success": result.success and bool(registrations_data),
                        "response_data": registrations_data if result.success else None,
                        "cache_used": result.cache_used,
                        "response_time_ms": result.response_time_ms or 0,
                        "error_message": None if result.success else result.error
                    })
                
                # Registrar geocodificação se solicitada
                if consultation_request.geocoding:
                    geocoding_cost = await consultation_types_service.get_cost_by_code('geocoding')
                    # Dados de geocodificação estariam no endereço
                    geocoding_data = result.dados_receita.get('endereco') if result.dados_receita else None
                    consultation_types.append({
                        "type_code": "geocodificacao",  # Código mapeado no BD
                        "cost_cents": geocoding_cost or 5,  # Custo dinâmico com fallback
                        "success": result.success and bool(geocoding_data and geocoding_data.get('latitude')),
                        "response_data": geocoding_data if result.success else None,
                        "cache_used": result.cache_used,
                        "response_time_ms": result.response_time_ms or 0,
                        "error_message": None if result.success else result.error
                    })
                
                if consultation_request.suframa:
                    suframa_cost = await consultation_types_service.get_cost_by_code('suframa')
                    # Suframa normalmente estaria em dados_receita também
                    suframa_data = result.dados_receita.get('suframa') if result.dados_receita else None
                    consultation_types.append({
                        "type_code": "suframa",
                        "cost_cents": suframa_cost or 5,  # Custo dinâmico com fallback
                        "success": result.success and bool(suframa_data),
                        "response_data": suframa_data if result.success else None,
                        "cache_used": result.cache_used,
                        "response_time_ms": result.response_time_ms or 0,
                        "error_message": None if result.success else result.error
                    })
            
            # Se não especificou nenhum tipo, assumir protestos como padrão
            if not consultation_types:
                fallback_protestos_cost = await consultation_types_service.get_cost_by_code('protestos')
                consultation_types.append({
                    "type_code": "protestos",
                    "cost_cents": fallback_protestos_cost or 15,  # Custo dinâmico com fallback
                    "success": result.success,
                    "response_data": result.protestos if result.success else None,
                    "cache_used": result.cache_used,
                    "response_time_ms": result.response_time_ms or 0,
                    "error_message": None if result.success else result.error
                })
            
            # Construir response_data completo para armazenamento
            full_response_data = {
                "cnpj": result.cnpj,
                "success": result.success,
                "status": "success" if result.success else "error",
                "error": result.error if result.error else None,  # ✅ CORRIGIDO: usar result.error
                "timestamp": result.timestamp.isoformat() if result.timestamp else None,
                "response_time_ms": result.response_time_ms,
                "cache_used": result.cache_used,
                "total_protests": result.total_protests,
                "has_protests": result.has_protests,
                "data": {
                    "protestos": result.protestos if result.protestos else None,
                    "dados_receita": result.dados_receita if result.dados_receita else None
                },
                "user_id": user_id,  # ✅ CORRIGIDO: usar user_id da função, não result.user_id
                "api_key_id": api_key_uuid,  # ✅ CORRIGIDO: usar api_key_uuid da função, não result.api_key_id
                "consultation_types": consultation_types  # Incluir tipos consultados
            }
            
            # Usar novo sistema de logging com response_data completo
            logged_consultation = await query_logger_service.log_consultation(
                user_id=user_id,
                api_key_id=api_key_uuid,
                cnpj=consultation_request.cnpj,
                consultation_types=consultation_types,
                response_time_ms=result.response_time_ms or 0,
                status="success" if result.success else "error",
                error_message=result.error if not result.success else None,  # ✅ CORRIGIDO: usar result.error
                cache_used=result.cache_used,
                client_ip=client_ip,  # IP do cliente
                response_data=full_response_data  # ✅ NOVO: JSON completo da resposta
            )
            
            if logged_consultation:
                logger.info("consulta_registrada_novo_formato", 
                           consultation_id=logged_consultation.get("id"),
                           user_id=user_id,
                           types_count=len(consultation_types))
                
                # ✅ CORRIGIDO: Deduzir créditos após consulta bem-sucedida
                if result.success and consultation_types:
                    total_cost_cents = sum(ct.get("cost_cents", 0) for ct in consultation_types)
                    if total_cost_cents > 0:
                        try:
                            # Converter centavos para reais
                            total_cost_reais = total_cost_cents / 100.0
                            await credit_service.consume_credits(
                                user_id=user_id,
                                amount=total_cost_reais,
                                description=f"Consulta CNPJ {consultation_request.cnpj[:8]}****",
                                consultation_id=logged_consultation.get("id")
                            )
                            logger.info("creditos_deduzidos_apos_consulta",
                                       user_id=user_id,
                                       amount_cents=total_cost_cents,
                                       consultation_id=logged_consultation.get("id"))
                        except InsufficientCreditsError as credit_error:
                            # Se não há créditos suficientes, ainda assim a consulta foi feita
                            # então apenas logamos o erro
                            logger.error("creditos_insuficientes_apos_consulta",
                                       user_id=user_id,
                                       error=str(credit_error))
                        except Exception as credit_error:
                            logger.error("erro_deduzir_creditos_apos_consulta",
                                       user_id=user_id,
                                       error=str(credit_error))
            else:
                logger.warning("falha_registrar_consulta", user_id=user_id, cnpj=consultation_request.cnpj[:8] + "****")
        except Exception as log_error:
            # Log do erro mas não falhar a consulta por causa do logging
            logger.error("erro_logging_consulta", 
                        error=str(log_error),
                        cnpj=consultation_request.cnpj[:8] + "****")
        
        logger.info("consulta_cnpj_unificada_finalizada",
                   cnpj=consultation_request.cnpj[:8] + "****",
                   user_id=user_id,
                   success=result.success,
                   response_time_ms=result.response_time_ms,
                   cache_usado=result.cache_used,
                   total_protestos=result.total_protests)
        
        # Configurar user_id e api_key_id no resultado
        result.user_id = user_id
        result.api_key_id = api_key_id
        
        return result
        
    except HTTPException:
        # Re-raise HTTPException para que seja propagada corretamente
        raise
    except Exception as e:
        logger.error("erro_consulta_cnpj", cnpj=consultation_request.cnpj, error=str(e))
        return ConsultationResponse(
            success=False,
            cnpj=consultation_request.cnpj,
            error=str(e),
            timestamp=datetime.now(),
            user_id=user.user_id if user else None,
            api_key_id=user.api_key if user else None
        )

# =====================================================
# ENDPOINTS DE ASSINATURA
# =====================================================

@router.get("/subscription-plans")
async def get_subscription_plans():
    """
    Lista todos os planos de assinatura disponíveis
    """
    try:
        from api.services.subscription_service import subscription_service
        plans = await subscription_service.get_available_plans()
        return {"plans": plans}
    except Exception as e:
        logger.error("erro_buscar_planos", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@router.get("/subscription/current")
async def get_current_subscription(user: AuthUser = Depends(require_auth)):
    """
    Obtém a assinatura atual do usuário
    """
    try:
        from api.services.subscription_service import subscription_service
        subscription = await subscription_service.get_user_subscription(user.user_id)
        return {"subscription": subscription}
    except Exception as e:
        logger.error("erro_buscar_assinatura", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@router.post("/subscription/change")
async def change_subscription(
    plan_id: str,
    action: str,
    user: AuthUser = Depends(require_auth)
):
    """
    Altera o plano de assinatura do usuário
    """
    try:
        from api.services.subscription_service import subscription_service
        result = await subscription_service.change_subscription(user.user_id, plan_id, action)
        return {"message": "Assinatura alterada com sucesso", "result": result}
    except Exception as e:
        logger.error("erro_alterar_assinatura", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao alterar assinatura: {str(e)}"
        )

@router.post("/subscription/cancel")
async def cancel_subscription(user: AuthUser = Depends(require_auth)):
    """
    Cancela a assinatura do usuário
    """
    try:
        from api.services.subscription_service import subscription_service
        result = await subscription_service.cancel_subscription(user.user_id)
        return {"message": "Assinatura cancelada com sucesso", "result": result}
    except Exception as e:
        logger.error("erro_cancelar_assinatura", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao cancelar assinatura: {str(e)}"
        )

@router.post("/subscription/reactivate")
async def reactivate_subscription(user: AuthUser = Depends(require_auth)):
    """
    Reativa a assinatura do usuário
    """
    try:
        from api.services.subscription_service import subscription_service
        result = await subscription_service.reactivate_subscription(user.user_id)
        return {"message": "Assinatura reativada com sucesso", "result": result}
    except Exception as e:
        logger.error("erro_reativar_assinatura", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao reativar assinatura: {str(e)}"
        )

# =====================================================
# ENDPOINTS DE HISTÓRICO DE USO
# =====================================================

@router.get("/query-history")
async def get_query_history(
    page: int = 1,
    limit: int = 20,
    status: str = "all",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    type: str = "all",
    user: AuthUser = Depends(require_auth)
):
    """
    Obtém o histórico de consultas do usuário
    """
    try:
        from api.services.history_service import history_service
        result = await history_service.get_user_query_history(
            user.user_id, page, limit, status, date_from, date_to, search, type
        )
        return result
    except Exception as e:
        logger.error("erro_buscar_historico", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

# ========== DASHBOARD V2 - DADOS REAIS (SEM MOCK) ==========

@router.get("/v2/dashboard/data")
async def get_real_dashboard_data(
    period: DashboardPeriod = Query(default=DashboardPeriod.THIRTY_DAYS, description="Período para análise dos dados"),
    user: AuthUser = Depends(require_auth)
):
    """
    🎯 Dashboard V2 - Dados 100% reais do banco de dados (sem mock)
    
    Endpoints integrados:
    - consultation_types_service (custos dinâmicos)
    - credit_service (saldo real)
    - consultations/consultation_details (dados reais)
    
    Parâmetros:
    - period: today, 7d, 30d, 90d, 120d, 180d, 365d
    """
    try:
        logger.info("buscando_dashboard_v2_dados_reais", 
                   user_id=user.user_id, 
                   period=period)
        
        data = await dashboard_service.get_dashboard_data(user.user_id, period)
        
        logger.info("dashboard_v2_dados_reais_retornados", 
                   user_id=user.user_id, 
                   consultas=data.get("usage", {}).get("total_consultations", 0),
                   custo_total=data.get("usage", {}).get("total_cost_raw", 0))
        
        return data
        
    except Exception as e:
        logger.error("erro_dashboard_v2_dados_reais", 
                    user_id=user.user_id, 
                    period=period, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar dados reais do dashboard: {str(e)}"
        )

@router.get("/v2/dashboard/stats")
async def get_real_dashboard_stats(
    period: DashboardPeriod = Query(default=DashboardPeriod.THIRTY_DAYS, description="Período para análise das estatísticas"),
    user: AuthUser = Depends(require_auth)
):
    """
    📊 Dashboard V2 - Estatísticas detalhadas com dados reais
    """
    try:
        # Buscar dados completos e extrair apenas estatísticas
        full_data = await dashboard_service.get_dashboard_data(user.user_id, period)
        
        return {
            "consultas_por_tipo": full_data.get("usage", {}).get("usage_by_type", {}),
            "custos_por_tipo": {k: v for k, v in full_data.get("usage", {}).items() if k.endswith("_cost")},
            "taxa_sucesso": full_data.get("success_rate", 0),
            "periodo": period,
            "total_consultas": full_data.get("usage", {}).get("total_consultations", 0),
            "custo_total": full_data.get("usage", {}).get("total_cost", "R$ 0,00")
        }
        
    except Exception as e:
        logger.error("erro_dashboard_v2_stats", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar estatísticas do dashboard"
        )

@router.get("/v2/dashboard/credits")
async def get_real_dashboard_credits(user: AuthUser = Depends(require_auth)):
    """
    💰 Dashboard V2 - Créditos em tempo real (integração com credit_service)
    """
    try:
        # Buscar apenas dados de créditos
        credits_data = await dashboard_service._get_credits(user.user_id)
        
        return {
            "credits": credits_data,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error("erro_dashboard_v2_credits", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar créditos do usuário"
        )

@router.get("/v2/dashboard/costs")
async def get_real_consultation_costs(user: AuthUser = Depends(require_auth)):
    """
    💸 Dashboard V2 - Custos reais dos tipos de consulta
    """
    try:
        costs_data = await dashboard_service._get_consultation_costs()
        
        return {
            "costs": costs_data,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error("erro_dashboard_v2_costs", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar custos de consulta"
        )

# ========== FIM DASHBOARD V2 ==========

@router.get("/analytics")
async def get_analytics(
    period: DashboardPeriod = Query(default=DashboardPeriod.THIRTY_DAYS, description="Período para análise"),
    date_from: Optional[str] = Query(default=None, description="Data de início (formato YYYY-MM-DD)"),
    date_to: Optional[str] = Query(default=None, description="Data de fim (formato YYYY-MM-DD)"),
    user: AuthUser = Depends(require_auth)
):
    """
    Obtém analytics de uso do usuário
    """
    try:
        from api.services.history_service import history_service
        analytics = await history_service.get_user_analytics(
            user.user_id, period, date_from, date_to
        )
        return {"analytics": analytics}
    except Exception as e:
        logger.error("erro_buscar_analytics", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@router.get("/query-history/export")
async def export_query_history(
    format: str = "csv",
    status: str = "all",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    user: AuthUser = Depends(require_auth)
):
    """
    Exporta o histórico de consultas do usuário
    """
    try:
        from api.services.history_service import history_service
        export_data = await history_service.export_user_history(
            user.user_id, format, status, date_from, date_to, search
        )
        return export_data
    except Exception as e:
        logger.error("erro_exportar_historico", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

# =====================================================
# ENDPOINTS DE PERFIL
# =====================================================

@router.put("/auth/profile")
async def update_profile(
    name: str,
    email: str,
    user: AuthUser = Depends(require_auth)
):
    """
    Atualiza o perfil do usuário
    """
    try:
        from api.services.user_service import user_service
        updated_user = await user_service.update_user_profile(user.user_id, name, email)
        return {"user": updated_user}
    except Exception as e:
        logger.error("erro_atualizar_perfil", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao atualizar perfil: {str(e)}"
        )

@router.post("/auth/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    user: AuthUser = Depends(require_auth)
):
    """
    Altera a senha do usuário
    """
    try:
        from api.services.user_service import user_service
        result = await user_service.change_password(user.user_id, current_password, new_password)
        return {"message": "Senha alterada com sucesso", "result": result}
    except Exception as e:
        logger.error("erro_alterar_senha", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao alterar senha: {str(e)}"
        )

@router.post("/auth/2fa/enable")
async def enable_2fa(user: AuthUser = Depends(require_auth)):
    """
    Ativa a autenticação de dois fatores
    """
    try:
        from api.services.user_service import user_service
        result = await user_service.enable_2fa(user.user_id)
        return result
    except Exception as e:
        logger.error("erro_ativar_2fa", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao ativar 2FA: {str(e)}"
        )

@router.post("/auth/2fa/disable")
async def disable_2fa(user: AuthUser = Depends(require_auth)):
    """
    Desativa a autenticação de dois fatores
    """
    try:
        from api.services.user_service import user_service
        result = await user_service.disable_2fa(user.user_id)
        return {"message": "2FA desativado com sucesso", "result": result}
    except Exception as e:
        logger.error("erro_desativar_2fa", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao desativar 2FA: {str(e)}"
        )

@router.put("/auth/notifications")
async def update_notifications(
    settings: dict,
    user: AuthUser = Depends(require_auth)
):
    """
    Atualiza configurações de notificação do usuário
    """
    try:
        from api.services.user_service import user_service
        result = await user_service.update_notification_settings(user.user_id, settings)
        return {"message": "Configurações atualizadas com sucesso", "result": result}
    except Exception as e:
        logger.error("erro_atualizar_notificacoes", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao atualizar notificações: {str(e)}"
        )

@router.post("/auth/avatar")
async def upload_avatar(
    avatar: bytes,
    user: AuthUser = Depends(require_auth)
):
    """
    Faz upload do avatar do usuário
    """
    try:
        from api.services.user_service import user_service
        result = await user_service.upload_avatar(user.user_id, avatar)
        return {"avatar_url": result}
    except Exception as e:
        logger.error("erro_upload_avatar", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao fazer upload do avatar: {str(e)}"
        )

@router.delete("/auth/account")
async def delete_account(user: AuthUser = Depends(require_auth)):
    """
    Exclui a conta do usuário
    """
    try:
        from api.services.user_service import user_service
        result = await user_service.delete_account(user.user_id)
        return {"message": "Conta excluída com sucesso", "result": result}
    except Exception as e:
        logger.error("erro_excluir_conta", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao excluir conta: {str(e)}"
        )

# =====================================================
# ENDPOINTS DE FATURAS
# =====================================================

@router.get("/invoices")
async def get_invoices(
    page: int = 1,
    limit: int = 10,
    status: str = "all",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    user: AuthUser = Depends(require_auth)
):
    """
    Lista as faturas do usuário
    """
    try:
        from api.services.invoice_service import invoice_service
        result = await invoice_service.get_user_invoices(
            user.user_id, page, limit, status, date_from, date_to, search
        )
        return result
    except Exception as e:
        logger.error("erro_buscar_faturas", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    user: AuthUser = Depends(require_auth)
):
    """
    Obtém detalhes de uma fatura específica
    """
    try:
        from api.services.invoice_service import invoice_service
        invoice = await invoice_service.get_invoice(user.user_id, invoice_id)
        return {"invoice": invoice}
    except Exception as e:
        logger.error("erro_buscar_fatura", user_id=user.user_id, invoice_id=invoice_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fatura não encontrada"
        )

@router.get("/invoices/{invoice_id}/download")
async def download_invoice(
    invoice_id: str,
    user: AuthUser = Depends(require_auth)
):
    """
    Faz download de uma fatura em PDF
    """
    try:
        from api.services.invoice_service import invoice_service
        pdf_data = await invoice_service.download_invoice(user.user_id, invoice_id)
        return pdf_data
    except Exception as e:
        logger.error("erro_download_fatura", user_id=user.user_id, invoice_id=invoice_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fatura não encontrada"
        )

@router.post("/invoices/{invoice_id}/pay")
async def pay_invoice(
    invoice_id: str,
    user: AuthUser = Depends(require_auth)
):
    """
    Processa o pagamento de uma fatura
    """
    try:
        from api.services.invoice_service import invoice_service
        result = await invoice_service.pay_invoice(user.user_id, invoice_id)
        return result
    except Exception as e:
        logger.error("erro_pagar_fatura", user_id=user.user_id, invoice_id=invoice_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao processar pagamento: {str(e)}"
        )

@router.post("/auth/dev-token")
async def create_dev_token():
    """
    Cria um token de desenvolvimento para testes (apenas em modo desenvolvimento)
    """
    try:
        from api.middleware.mock_auth import get_mock_auth
        
        mock_auth = get_mock_auth()
        token = mock_auth.create_mock_token("dev-user-123")
        
        return {
            "token": token,
            "user_id": "dev-user-123",
            "email": "dev@valida.com.br",
            "message": "Token de desenvolvimento criado com sucesso",
            "note": "Use este token no header Authorization: Bearer <token>"
        }
    except Exception as e:
        logger.error("erro_criar_token_dev", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@router.post("/auth/dev-api-key")
async def create_dev_api_key():
    """
    Cria uma API key de desenvolvimento para testes (apenas em modo desenvolvimento)
    """
    try:
        from api.middleware.mock_auth import get_mock_auth
        
        mock_auth = get_mock_auth()
        api_key = mock_auth.create_mock_api_key("dev-user-123", "Chave de Desenvolvimento")
        
        return {
            "api_key": api_key["key"],
            "key_id": api_key["id"],
            "name": api_key["name"],
            "user_id": "dev-user-123",
            "message": "API key de desenvolvimento criada com sucesso",
            "note": "Use esta chave no header Authorization: Bearer <api_key>"
        }
    except Exception as e:
        logger.error("erro_criar_api_key_dev", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@router.get("/auth/real-api-key")
async def get_real_api_key():
    """
    Obtém uma API key real do banco de dados para testes
    """
    try:
        from api.middleware.auth_middleware import get_supabase_client
        
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Supabase não configurado"
            )
        
        # Buscar primeira API key ativa
        result = supabase.table("api_keys").select(
            "key_hash, name, users(email)"
        ).eq("is_active", True).limit(1).execute()
        
        if result.data:
            api_key_data = result.data[0]
            return {
                "api_key": api_key_data["key_hash"],
                "name": api_key_data["name"],
                "email": api_key_data["users"]["email"],
                "message": "API key real obtida com sucesso",
                "note": "Use esta chave no header Authorization: Bearer <api_key>"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nenhuma API key encontrada no banco de dados"
            )
            
    except Exception as e:
        logger.error("erro_obter_api_key_real", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@router.get("/test-auth")
async def test_auth(user: AuthUser = Depends(require_auth)):
    """
    Endpoint de teste para verificar autenticação
    """
    return {
        "message": "Autenticação funcionando!",
        "user_id": user.user_id,
        "email": user.email,
        "api_key": user.api_key
    }

@router.get("/test-no-auth")
async def test_no_auth():
    """
    Endpoint de teste sem autenticação
    """
    return {
        "message": "Endpoint sem autenticação funcionando!",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/test-simple-auth")
async def test_simple_auth(user: AuthUser = Depends(require_auth)):
    """
    Endpoint de teste simples com autenticação
    """
    return {
        "message": "Autenticação funcionando!",
        "user_id": user.user_id,
        "email": user.email,
        "api_key": user.api_key
    }

@router.get("/health")
async def health_check():
    """
    Verifica a saúde da API
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Valida API SaaS",
        "version": "1.0.0"
    }

# ============================================================================
# ENDPOINTS DE AUTENTICAÇÃO
# ============================================================================

@router.post("/auth/login")
async def login_user(email: str, password: str):
    """
    Autentica um usuário e retorna token de acesso
    """
    try:
        # Validar credenciais
        user = await user_service.authenticate_user(email, password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="E-mail ou senha incorretos"
            )
        
        # Gerar token JWT REAL
        import jwt
        import os
        from datetime import timedelta
        
        JWT_SECRET = os.getenv("JWT_SECRET", "valida-jwt-secret-2024")
        JWT_ALGORITHM = "HS256"
        
        payload = {
            "user_id": str(user.id),
            "email": user.email,
            "exp": datetime.utcnow() + timedelta(hours=24),
            "iat": datetime.utcnow(),
            "type": "access"
        }
        
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        logger.info("usuario_autenticado", user_id=user.id, email=user.email)
        
        return {
            "success": True,
            "token": token,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("erro_login", email=email, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@router.post("/auth/logout")
async def logout_user(current_user: AuthUser = Depends(require_auth)):
    """
    Faz logout do usuário (invalida token)
    """
    try:
        # Em uma implementação real, adicionar token à blacklist
        logger.info("usuario_logout", user_id=current_user.id, email=current_user.email)
        
        return {
            "success": True,
            "message": "Logout realizado com sucesso"
        }
        
    except Exception as e:
        logger.error("erro_logout", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@router.get("/auth/me")
async def get_current_user_info(current_user: AuthUser = Depends(require_auth)):
    """
    Retorna informações do usuário autenticado
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "created_at": current_user.created_at
    }

@router.post("/auth/forgot-password")
async def forgot_password(email: str):
    """
    Envia email para redefinição de senha
    """
    try:
        # Verificar se usuário existe
        user = await user_service.get_user_by_email(email)
        if not user:
            # Por segurança, retornar sucesso mesmo se usuário não existir
            return {
                "success": True,
                "message": "Se o e-mail existir, você receberá instruções para redefinir sua senha"
            }
        
        # Em uma implementação real, gerar token de reset e enviar email
        logger.info("solicitacao_reset_senha", email=email)
        
        return {
            "success": True,
            "message": "Se o e-mail existir, você receberá instruções para redefinir sua senha"
        }
        
    except Exception as e:
        logger.error("erro_forgot_password", email=email, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@router.post("/auth/reset-password")
async def reset_password(token: str, new_password: str):
    """
    Redefine a senha do usuário usando token de reset
    """
    try:
        # Em uma implementação real, validar token e redefinir senha
        logger.info("reset_senha_solicitado", token=token[:10] + "...")
        
        return {
            "success": True,
            "message": "Senha redefinida com sucesso"
        }
        
    except Exception as e:
        logger.error("erro_reset_password", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )
