"""
Router de Gerenciamento de Sessão da API Resolve CenProt
"""

from fastapi import APIRouter, HTTPException
from ..models.api_models import SessionStatusResponse
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()

# Referência global para session_manager (será definida no main.py)
session_manager = None


def set_session_manager(manager):
    """Define o session manager para este router"""
    global session_manager
    session_manager = manager


@router.get("/status", response_model=SessionStatusResponse)
async def get_session_status():
    """
    Retorna status detalhado da sessão do navegador
    """
    try:
        if not session_manager:
            raise HTTPException(status_code=503, detail="Session manager não inicializado")
        
        status = session_manager.get_status()
        
        return SessionStatusResponse(
            active=status["active"],
            logged_in=status["logged_in"],
            last_activity=status["last_activity"],
            login_cnpj=status["login_cnpj"]
        )
        
    except Exception as e:
        logger.error("erro_get_session_status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Erro ao obter status da sessão: {str(e)}")


@router.post("/renew")
async def renew_session():
    """
    Force renewal da sessão (re-login)
    """
    try:
        if not session_manager:
            raise HTTPException(status_code=503, detail="Session manager não inicializado")
        
        logger.info("iniciando_renovacao_sessao")
        success = await session_manager.renew_session()
        
        if success:
            logger.info("sessao_renovada_com_sucesso")
            return {"message": "Sessão renovada com sucesso", "success": True}
        else:
            logger.error("falha_renovar_sessao")
            raise HTTPException(status_code=500, detail="Falha ao renovar sessão")
            
    except Exception as e:
        logger.error("erro_renovar_sessao", error=str(e))
        raise HTTPException(status_code=500, detail=f"Erro ao renovar sessão: {str(e)}")


@router.delete("/logout")
async def logout_session():
    """
    Encerra sessão atual (força novo login na próxima consulta)
    """
    try:
        if not session_manager:
            raise HTTPException(status_code=503, detail="Session manager não inicializado")
        
        logger.info("encerrando_sessao_atual")
        session_manager.is_logged_in = False
        session_manager.last_login = None
        
        return {"message": "Sessão encerrada", "success": True}
        
    except Exception as e:
        logger.error("erro_encerrar_sessao", error=str(e))
        raise HTTPException(status_code=500, detail=f"Erro ao encerrar sessão: {str(e)}")


@router.get("/health")
async def get_session_health():
    """
    Retorna informações de saúde da sessão incluindo pool de páginas
    """
    try:
        if not session_manager:
            raise HTTPException(status_code=503, detail="Session manager não inicializado")
        
        from ..services.scraping_service import ScrapingService
        scraping_service = ScrapingService(session_manager)
        health = await scraping_service.get_session_health()
        
        return health
        
    except Exception as e:
        logger.error("erro_get_session_health", error=str(e))
        raise HTTPException(status_code=500, detail=f"Erro ao obter saúde da sessão: {str(e)}")
