"""
Service Layer para Operações de Scraping com Suporte a Pool de Páginas
Agora integrado com API oficial do Resolve CenProt
"""

import sys
from pathlib import Path
from typing import Dict, Any
import structlog

# Adicionar src ao path para reutilizar código existente
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from src.scraping.protest_scraper import ProtestScraper
from src.models.protest_models import ConsultaCNPJResult
from src.services.consultation_service import ConsultationService
from .session_manager import SessionManager

logger = structlog.get_logger(__name__)


class ScrapingService:
    """Service layer para operações de scraping com suporte a múltiplas requisições"""
    
    def __init__(self, session_manager: SessionManager = None, api_oficial_only: bool = False):
        self.session_manager = session_manager
        self.api_oficial_only = api_oficial_only
        
        # Inicializar ConsultationService baseado no modo
        if api_oficial_only:
            # Modo API oficial apenas - não inicializar RPA
            self.consultation_service = ConsultationService(scraping_service=None)
            logger.info("scraping_service_inicializado_api_oficial_apenas", 
                       provider=self.consultation_service.active_provider.provider_type)
        else:
            # Modo completo (RPA + API oficial)
            self.consultation_service = ConsultationService(scraping_service=self)
            logger.info("scraping_service_inicializado_modo_completo", 
                       provider=self.consultation_service.active_provider.provider_type)
    
    async def consultar_cnpj(self, cnpj: str) -> ConsultaCNPJResult:
        """
        Realiza consulta de um CNPJ usando o provider configurado (RPA ou API oficial)
        
        Args:
            cnpj: CNPJ para consultar
            
        Returns:
            ConsultaCNPJResult: Resultado da consulta
        """
        logger.info("consulta_cnpj_iniciada", cnpj=cnpj[:8] + "****")
        
        # Usar ConsultationService que escolhe automaticamente o provider
        return await self.consultation_service.consultar_cnpj(cnpj)
    
    async def consultar_cnpj_rpa_direto(self, cnpj: str) -> ConsultaCNPJResult:
        """
        Realiza consulta de um CNPJ usando RPA diretamente (método original)
        Mantido para compatibilidade e casos especiais
        """
        # Verificar se está em modo API oficial apenas
        if self.api_oficial_only or not self.session_manager:
            raise Exception("RPA não está disponível no modo API oficial apenas")
            
        page_info = None
        try:
            # Verificar se sessão está ativa
            if not await self.session_manager.ensure_logged_in():
                raise Exception("Não foi possível estabelecer sessão logada")
            
            # Obter página exclusiva do pool
            page_info = await self.session_manager.get_page_from_pool()
            page = page_info["page"]
            
            logger.info("iniciando_consulta_com_pagina_pool", 
                       cnpj=cnpj, 
                       page_id=page_info["id"],
                       url_atual=page.url)
            
            # VALIDAR SESSÃO: Fazer refresh e verificar se ainda está logado
            session_valida = await self.session_manager.validate_page_session(page)
            
            if not session_valida:
                logger.warning("sessao_expirada_detectada", page_id=page_info["id"])
                
                # Tentar re-login automático
                relogin_success = await self.session_manager.perform_relogin_on_page(page)
                
                if not relogin_success:
                    raise Exception(f"Falha no re-login automático para página {page_info['id']}")
                
                logger.info("relogin_automatico_realizado", page_id=page_info["id"])
            
            # Garantir que está na página de consulta após validação/re-login
            if "public-search" not in page.url:
                await page.goto("https://resolve.cenprot.org.br/app/dashboard/search/public-search")
                await page.wait_for_load_state("networkidle", timeout=10000)
            
            # Criar scraper com página dedicada e já logada
            scraper = ProtestScraper(page)
            scraper.current_cnpj = cnpj
            
            # Realizar consulta (página já está logada e na tela de consulta)
            result = await scraper.consultar_cnpj_direct(cnpj)
            
            logger.info("consulta_finalizada_sucesso_pool", 
                       cnpj=cnpj, 
                       page_id=page_info["id"],
                       tem_protestos=bool(result.cenprotProtestos))
            
            return result
            
        except Exception as e:
            logger.error("erro_scraping_service_consultar_pool", 
                        cnpj=cnpj, 
                        page_id=page_info["id"] if page_info else "none",
                        error=str(e))
            raise
        finally:
            # SEMPRE retornar página ao pool
            if page_info:
                await self.session_manager.return_page_to_pool(page_info)
    
    async def get_session_health(self) -> Dict[str, Any]:
        """Verifica saúde da sessão incluindo status do pool e providers"""
        try:
            if self.api_oficial_only or not self.session_manager:
                # Modo API oficial apenas
                health = {
                    "mode": "API_OFICIAL_ONLY",
                    "can_scrape": True,  # API oficial sempre pode consultar
                    "active": True,
                    "logged_in": True,  # API oficial gerencia própria auth
                    "pool_size": 0,
                    "available_pages": 0,
                    "active_pages": 0,
                    "concurrent_capacity": "unlimited",  # API oficial não tem limite de pool
                    "current_load": 0
                }
            else:
                # Modo RPA completo
                status = self.session_manager.get_status()
                pool_status = await self.session_manager.get_pool_status()
                
                health = {
                    "mode": "RPA_FULL",
                    **status,
                    **pool_status,
                    "can_scrape": status["active"] and status["logged_in"],
                    "needs_renewal": not self.session_manager._is_session_valid(),
                    "concurrent_capacity": self.session_manager.pool_size,
                    "current_load": len(self.session_manager.active_pages)
                }
            
            # REMOVIDO: consultation_service status para evitar recursão
            # consultation_status = self.consultation_service.get_status()
            # health["consultation_service"] = consultation_status
            
            return health
            
        except Exception as e:
            logger.error("erro_get_session_health", error=str(e))
            return {"error": str(e)}
