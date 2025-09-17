"""
Service Selector para escolher entre RPA e API oficial
Baseado na variável de ambiente USAR_RESOLVE_CENPROT_API_OFICIAL
"""

from typing import Dict, Any, Protocol
import structlog
from datetime import datetime

from ..config.settings import settings
from ..models.protest_models import ConsultaCNPJResult
from ..auth.api_oficial_client import ApiOficialClient

logger = structlog.get_logger(__name__)


class ConsultationProvider(Protocol):
    """Protocol para providers de consulta"""
    
    async def consultar_cnpj(self, cnpj: str) -> ConsultaCNPJResult:
        """Consulta um CNPJ"""
        ...
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status do provider"""
        ...


class RPAConsultationProvider:
    """Provider que usa RPA (sistema existente)"""
    
    def __init__(self, scraping_service):
        self.scraping_service = scraping_service
        self.provider_type = "RPA"
    
    async def consultar_cnpj(self, cnpj: str) -> ConsultaCNPJResult:
        """Consulta CNPJ via RPA"""
        logger.info("consultando_via_rpa", cnpj=cnpj[:8] + "****")
        # IMPORTANTE: Chamar método RPA direto para evitar loop infinito
        return await self.scraping_service.consultar_cnpj_rpa_direto(cnpj)
    
    def get_status(self) -> Dict[str, Any]:
        """Status do RPA"""
        try:
            # Verificar se scraping_service está disponível
            if not self.scraping_service:
                return {
                    "provider": "RPA",
                    "status": "unavailable",
                    "error": "scraping_service not initialized"
                }
                
            # Status básico sem await (evita problemas de recursão)
            session_manager = getattr(self.scraping_service, 'session_manager', None)
            if session_manager:
                basic_status = session_manager.get_status()
                return {
                    "provider": "RPA",
                    "status": "active" if basic_status.get("active", False) else "inactive",
                    "details": basic_status
                }
            else:
                return {
                    "provider": "RPA",
                    "status": "api_oficial_mode",
                    "details": {"mode": "API_OFICIAL_ONLY"}
                }
        except Exception as e:
            return {
                "provider": "RPA",
                "status": "error",
                "error": str(e)
            }


class ApiOficialConsultationProvider:
    """Provider que usa API oficial"""
    
    def __init__(self):
        self.client = ApiOficialClient()
        self.provider_type = "API_OFICIAL"
    
    async def consultar_cnpj(self, cnpj: str) -> ConsultaCNPJResult:
        """Consulta CNPJ via API oficial"""
        logger.info("consultando_via_api_oficial", cnpj=cnpj[:8] + "****")
        
        try:
            # Usar cliente diretamente sem context manager para evitar fechamento prematuro
            result = await self.client.consultar_cnpj(cnpj)
                
            # Adicionar metadado indicando que foi via API oficial
            result.link_pdf = f"/API Oficial - {result.link_pdf}"
            
            return result
            
        except Exception as e:
            logger.error("erro_consulta_api_oficial", 
                       cnpj=cnpj[:8] + "****", 
                       error=str(e))
            
            # Re-raise a exceção para que seja tratada pelo sistema de fallback
            # Não retornar resultado de erro que será salvo como "sem protestos"
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Status da API oficial"""
        try:
            # Usar client temporário apenas para status
            temp_client = ApiOficialClient()
            status = temp_client.get_status()
            
            return {
                "provider": "API_OFICIAL",
                "status": "active" if status["authenticated"] else "inactive",
                "details": status
            }
        except Exception as e:
            return {
                "provider": "API_OFICIAL", 
                "status": "error",
                "error": str(e)
            }


class ConsultationService:
    """
    Service principal que escolhe automaticamente entre RPA e API oficial
    baseado na configuração USAR_RESOLVE_CENPROT_API_OFICIAL
    """
    
    def __init__(self, scraping_service=None):
        self.scraping_service = scraping_service
        self.usar_api_oficial = settings.USAR_RESOLVE_CENPROT_API_OFICIAL
        
        # Verificar configuração inconsistente
        if not self.usar_api_oficial and not scraping_service:
            logger.error("configuracao_inconsistente", 
                        usar_api_oficial=False, 
                        scraping_service_disponivel=False)
            raise ValueError(
                "Configuração inconsistente: USAR_RESOLVE_CENPROT_API_OFICIAL=false "
                "mas scraping_service não foi inicializado. Reinicie a API com a "
                "configuração correta."
            )
        
        # Inicializar providers baseado na disponibilidade
        if scraping_service and not self.usar_api_oficial:
            # Modo RPA - inicializar RPA provider
            self.rpa_provider = RPAConsultationProvider(scraping_service)
            self.api_oficial_provider = None
            logger.info("consultation_service_modo_rpa_apenas")
        elif self.usar_api_oficial:
            # Modo API oficial - não inicializar RPA provider
            self.rpa_provider = None
            self.api_oficial_provider = ApiOficialConsultationProvider()
            logger.info("consultation_service_modo_api_oficial_apenas")
        else:
            # Modo híbrido ou fallback
            self.rpa_provider = RPAConsultationProvider(scraping_service) if scraping_service else None
            self.api_oficial_provider = ApiOficialConsultationProvider()
            logger.info("consultation_service_modo_hibrido")
        
        # Selecionar provider ativo
        self.active_provider = self._get_active_provider()
        
        logger.info("consultation_service_inicializado", 
                   provider_ativo=self.active_provider.provider_type,
                   usar_api_oficial=self.usar_api_oficial)
    
    def _get_active_provider(self) -> ConsultationProvider:
        """Retorna o provider ativo baseado na configuração"""
        if self.usar_api_oficial and self.api_oficial_provider:
            logger.info("selecionando_provider_api_oficial")
            return self.api_oficial_provider
        elif not self.usar_api_oficial and self.rpa_provider:
            logger.info("selecionando_provider_rpa")
            return self.rpa_provider
        else:
            # Fallback - usar o que estiver disponível
            if self.api_oficial_provider:
                logger.info("fallback_para_api_oficial")
                return self.api_oficial_provider
            elif self.rpa_provider:
                logger.info("fallback_para_rpa")
                return self.rpa_provider
            else:
                raise ValueError("Nenhum provider disponível - configuração inválida")
    
    async def consultar_cnpj(self, cnpj: str) -> ConsultaCNPJResult:
        """
        Consulta CNPJ usando o provider ativo
        
        Args:
            cnpj: CNPJ para consultar
            
        Returns:
            ConsultaCNPJResult: Resultado da consulta
        """
        logger.info("iniciando_consulta", 
                   cnpj=cnpj[:8] + "****", 
                   provider=self.active_provider.provider_type)
        
        try:
            result = await self.active_provider.consultar_cnpj(cnpj)
            
            logger.info("consulta_finalizada_sucesso", 
                       cnpj=cnpj[:8] + "****",
                       provider=self.active_provider.provider_type,
                       tem_protestos=bool(result.cenprotProtestos))
            
            return result
            
        except Exception as e:
            logger.error("erro_consulta_service", 
                       cnpj=cnpj[:8] + "****", 
                       provider=self.active_provider.provider_type,
                       error=str(e))
            
            # Se API oficial falhar, tentar fallback para RPA (apenas se disponível)
            if self.usar_api_oficial and self.rpa_provider:
                logger.warning("tentando_fallback_para_rpa", cnpj=cnpj[:8] + "****")
                
                try:
                    result = await self.rpa_provider.consultar_cnpj(cnpj)
                    result.link_pdf = f"/Fallback RPA após erro API - {result.link_pdf}"
                    
                    logger.info("fallback_rpa_sucesso", cnpj=cnpj[:8] + "****")
                    return result
                    
                except Exception as fallback_error:
                    logger.error("fallback_rpa_tambem_falhou", 
                               cnpj=cnpj[:8] + "****",
                               error=str(fallback_error))
            else:
                logger.info("fallback_rpa_nao_disponivel", 
                           usar_api_oficial=self.usar_api_oficial,
                           rpa_provider_exists=bool(self.rpa_provider))
            
            # Se chegou aqui, todos os métodos falharam
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status completo do service"""
        status = {
            "active_provider": self.active_provider.provider_type,
            "config": {
                "usar_api_oficial": self.usar_api_oficial,
                "api_base_url": settings.RESOLVE_CENPROT_API_BASE_URL,
                "login": settings.RESOLVE_CENPROT_LOGIN[:8] + "****"
            },
            "providers": {}
        }
        
        # Status do provider ativo
        status["providers"]["active"] = self.active_provider.get_status()
        
        # Status dos outros providers (se disponíveis)
        if self.rpa_provider and self.active_provider != self.rpa_provider:
            status["providers"]["rpa"] = self.rpa_provider.get_status()
            
        if self.api_oficial_provider and self.active_provider != self.api_oficial_provider:
            status["providers"]["api_oficial"] = self.api_oficial_provider.get_status()
        
        return status
    
    def switch_provider(self, use_api_oficial: bool = None):
        """
        Permite trocar o provider dinamicamente (para testes)
        
        Args:
            use_api_oficial: True para API oficial, False para RPA, None para usar config
        """
        if use_api_oficial is not None:
            self.usar_api_oficial = use_api_oficial
        else:
            self.usar_api_oficial = settings.USAR_RESOLVE_CENPROT_API_OFICIAL
            
        old_provider = self.active_provider.provider_type
        self.active_provider = self._get_active_provider()
        
        logger.info("provider_alterado", 
                   provider_anterior=old_provider,
                   provider_novo=self.active_provider.provider_type)

