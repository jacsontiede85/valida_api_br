"""
Router de Status da API Resolve CenProt
Agora com suporte a API oficial e RPA
"""

from fastapi import APIRouter, Query
from ..models.api_models import StatusResponse, PoolStatusResponse
import structlog

logger = structlog.get_logger(__name__)

# Router será inicializado com session_manager no main.py
router = APIRouter()

# Referência global para scraping_service (será definida no main.py)
scraping_service = None


def set_scraping_service(service):
    """Define o scraping service para este router"""
    global scraping_service
    scraping_service = service


def set_session_manager(manager):
    """Define o session manager para este router (mantido para compatibilidade)"""
    # Compatibilidade com código existente
    pass


@router.get("/status")
async def get_status():
    """
    Verifica status do serviço incluindo provider ativo (RPA ou API oficial)
    """
    try:
        if scraping_service:
            health = await scraping_service.get_session_health()
            
            # Obter provider ativo sem recursão
            provider_ativo = "API_OFICIAL" if scraping_service.api_oficial_only else "RPA"
            
            return {
                "status": "online" if health.get("can_scrape", False) else "offline",
                "provider_ativo": provider_ativo,
                "session_active": health.get("active", False),
                "last_login": health.get("last_login"),
                "mode": health.get("mode", "unknown"),
                "rpa_status": {
                    "can_scrape": health.get("can_scrape", False),
                    "pool_size": health.get("pool_size", 0),
                    "available_pages": health.get("available_pages", 0),
                    "active_pages": health.get("active_pages", 0),
                    "concurrent_capacity": health.get("concurrent_capacity", "unknown")
                }
            }
        else:
            return {
                "status": "initializing",
                "provider_ativo": "none",
                "session_active": False,
                "last_login": None
            }
        
    except Exception as e:
        logger.error("erro_get_status", error=str(e))
        return {
            "status": "error", 
            "provider_ativo": "error",
            "session_active": False,
            "last_login": None,
            "error": str(e)
        }


@router.get("/health")
async def health_check():
    """Health check simples para load balancers"""
    return {"status": "healthy"}


@router.get("/pool")
async def get_pool_status():
    """
    Retorna status detalhado do pool de páginas RPA
    """
    try:
        if not scraping_service:
            raise Exception("Scraping service não inicializado")
        
        health = await scraping_service.get_session_health()
        
        return {
            "pool_size": health.get("pool_size", 0),
            "available_pages": health.get("available_pages", 0),
            "active_pages": health.get("active_pages", 0),
            "active_page_ids": health.get("active_page_ids", []),
            "concurrent_capacity": health.get("concurrent_capacity", 0),
            "current_load": health.get("current_load", 0),
            "provider_ativo": health.get("consultation_service", {}).get("active_provider", "unknown")
        }
        
    except Exception as e:
        logger.error("erro_get_pool_status", error=str(e))
        return {
            "pool_size": 0,
            "available_pages": 0,
            "active_pages": 0,
            "active_page_ids": [],
            "concurrent_capacity": 0,
            "current_load": 0,
            "error": str(e)
        }


@router.post("/switch-provider")
async def switch_provider(use_api_oficial: bool = Query(description="True para API oficial, False para RPA")):
    """
    ATENÇÃO: Para alterar entre API oficial e RPA, é necessário reiniciar a API
    """
    return {
        "success": False,
        "message": "Para alternar entre API oficial e RPA, siga os passos:",
        "steps": [
            "1. Pare a API atual (Ctrl+C)",
            "2. Altere USAR_RESOLVE_CENPROT_API_OFICIAL no arquivo .env",
            "3. Reinicie a API: python -m api.main"
        ],
        "current_mode": "API_OFICIAL" if scraping_service and scraping_service.api_oficial_only else "RPA",
        "requested_mode": "API_OFICIAL" if use_api_oficial else "RPA",
        "reason": "A inicialização dos serviços (SessionManager/Playwright vs API Client) acontece no startup"
    }
