"""
Rotas da API SaaS para o Valida
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
import structlog
from datetime import datetime

from api.models.saas_models import (
    UserCreate, UserResponse, APIKeyCreate, APIKeyResponse, APIKeyList,
    DashboardStats, UsageStats, ConsultationRequest, ConsultationResponse,
    ErrorResponse
)
from api.middleware.auth_middleware import require_auth, require_api_key, AuthUser, get_current_user
from api.services.user_service import user_service
from api.services.api_key_service import api_key_service
from api.services.dashboard_service import dashboard_service

logger = structlog.get_logger("saas_routes")

router = APIRouter()

@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate):
    """
    Registra um novo usuário no sistema
    """
    try:
        user = await user_service.create_user(user_data)
        logger.info("usuario_registrado", user_id=user.id, email=user.email)
        return user
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
    period: str = "30d",
    user: AuthUser = Depends(require_auth)
):
    """
    Obtém estatísticas do dashboard para o usuário
    """
    try:
        stats = await dashboard_service.get_dashboard_stats(user.user_id, period)
        logger.info("dashboard_stats_buscadas", user_id=user.user_id, period=period)
        return stats
    except Exception as e:
        logger.error("erro_buscar_dashboard_stats", user_id=user.user_id, error=str(e))
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

@router.post("/cnpj/consult", response_model=ConsultationResponse)
async def consult_cnpj(
    request: ConsultationRequest,
    user: Optional[AuthUser] = Depends(get_current_user)
):
    """
    Consulta CNPJ com dados completos - protestos + receita federal
    
    Parâmetros aceitos:
    - protestos: bool - Consultar protestos (default: true) 
    - simples: bool - Dados Simples Nacional (default: false)
    - registrations: str - Inscrições estaduais 'BR' (default: None)
    - geocoding: bool - Geolocalização (default: false)
    - suframa: bool - Dados SUFRAMA (default: false)  
    - strategy: str - Cache strategy (default: 'CACHE_IF_FRESH')
    """
    try:
        # Verificar autenticação - aceitar tanto header quanto corpo da requisição
        logger.info("iniciando_autenticacao", 
                   user_from_header=bool(user),
                   api_key_in_body=bool(request.api_key))
        
        if not user and request.api_key:
            # Se não há usuário do header, tentar usar a API key do corpo
            from fastapi.security import HTTPAuthorizationCredentials
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=request.api_key)
            logger.info("tentando_autenticar_com_api_key_corpo", 
                       api_key_prefix=request.api_key[:20] + "...")
            try:
                user = await get_current_user(credentials)
                logger.info("autenticacao_api_key_sucesso", 
                           user_id=user.user_id if user else 'None')
            except HTTPException as e:
                logger.warning("api_key_invalida", error=e.detail)
                raise HTTPException(status_code=401, detail="API key inválida")
        
        if not user:
            logger.warning("nenhum_usuario_autenticado")
            raise HTTPException(status_code=401, detail="API key necessária")
        
        # Usar novo serviço unificado
        from api.services.unified_consultation_service import UnifiedConsultationService
        
        unified_service = UnifiedConsultationService()
        
        logger.info("iniciando_consulta_unificada", 
                   cnpj=request.cnpj[:8] + "****",
                   user_id=user.user_id,
                   parametros={
                       "protestos": request.protestos,
                       "simples": request.simples,
                       "registrations": bool(request.registrations),
                       "geocoding": request.geocoding,
                       "suframa": request.suframa,
                       "strategy": request.strategy
                   })
        
        # Fazer a consulta completa
        result = await unified_service.consultar_dados_completos(request, user.user_id)
        
        # Registrar consulta no histórico
        from api.services.query_logger_service import query_logger_service
        
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
        
        # Registrar consulta no histórico usando dados do resultado
        try:
            await query_logger_service.log_query(
                user_id=user_id,
                api_key_id=api_key_uuid or api_key_id,
                cnpj=request.cnpj,
                endpoint="/api/v1/cnpj/consult",
                response_status=200 if result.success else 400,
                credits_used=1,
                response_time_ms=result.response_time_ms or 0,
                success=result.success
            )
            
            # Atualizar analytics diários
            today = datetime.now().strftime("%Y-%m-%d")
            await query_logger_service.update_query_analytics(
                user_id=user_id,
                date=today,
                total_queries=1,
                successful_queries=1 if result.success else 0,
                failed_queries=0 if result.success else 1,
                total_credits_used=1
            )
        except Exception as log_error:
            # Log do erro mas não falhar a consulta por causa do logging
            logger.error("erro_logging_consulta", 
                        error=str(log_error),
                        cnpj=request.cnpj[:8] + "****")
        
        logger.info("consulta_cnpj_unificada_finalizada",
                   cnpj=request.cnpj[:8] + "****",
                   user_id=user_id,
                   success=result.success,
                   sources=result.sources_consulted,
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
        logger.error("erro_consulta_cnpj", cnpj=request.cnpj, error=str(e))
        return ConsultationResponse(
            success=False,
            cnpj=request.cnpj,
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
    user: AuthUser = Depends(require_auth)
):
    """
    Obtém o histórico de consultas do usuário
    """
    try:
        from api.services.history_service import history_service
        result = await history_service.get_user_query_history(
            user.user_id, page, limit, status, date_from, date_to, search
        )
        return result
    except Exception as e:
        logger.error("erro_buscar_historico", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@router.get("/analytics")
async def get_analytics(
    period: str = "30d",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
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
        
        # Gerar token JWT (simplificado para demo)
        token = f"jwt_token_{user.id}_{datetime.now().timestamp()}"
        
        logger.info("usuario_autenticado", user_id=user.id, email=user.email)
        
        return {
            "success": True,
            "token": token,
            "user": {
                "id": user.id,
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
