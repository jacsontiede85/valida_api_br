"""
Serviço Unificado de Consulta
Combina consultas de protestos (ScrapingService) e dados CNPJa
"""

import time
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
import structlog

# Adicionar src ao path para importar CNPJaAPI
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from api.models.saas_models import ConsultationRequest, ConsultationResponse
from api.services.scraping_service import ScrapingService
from src.utils.cnpja_api import CNPJaAPI, CNPJaAPIError, CNPJaInvalidCNPJError, CNPJaNotFoundError

logger = structlog.get_logger(__name__)


class UnifiedConsultationService:
    """Serviço que combina consultas de protestos e dados CNPJa"""
    
    def __init__(self):
        """Inicializa o serviço unificado"""
        self.scraping_service = None  # Será inicializado sob demanda
        self.cnpja_api = None        # Será inicializado sob demanda
        
    def _get_scraping_service(self) -> ScrapingService:
        """Lazy initialization do ScrapingService"""
        if self.scraping_service is None:
            self.scraping_service = ScrapingService()
            logger.info("scraping_service_inicializado")
        return self.scraping_service
    
    def _get_cnpja_api(self) -> CNPJaAPI:
        """Lazy initialization da CNPJa API"""
        if self.cnpja_api is None:
            self.cnpja_api = CNPJaAPI()
            logger.info("cnpja_api_inicializada")
        return self.cnpja_api
    
    async def consultar_dados_completos(self, request: ConsultationRequest, user_id: Optional[str] = None) -> ConsultationResponse:
        """
        Consulta dados completos baseado nos parâmetros solicitados
        
        Args:
            request: Requisição com parâmetros de consulta
            user_id: ID do usuário para logging
            
        Returns:
            ConsultationResponse: Resposta com dados segmentados
        """
        start_time = time.time()
        protestos_data = None
        cnpja_data = None
        cache_used = False
        error_messages = []
        
        logger.info("iniciando_consulta_unificada", 
                   cnpj=request.cnpj[:8] + "****",
                   user_id=user_id,
                   protestos=request.protestos,
                   simples=request.simples,
                   registrations=bool(request.registrations),
                   geocoding=request.geocoding,
                   suframa=request.suframa)
        
        # 1. Consultar protestos se solicitado
        if request.protestos:
            try:
                scraping_service = self._get_scraping_service()
                logger.info("consultando_protestos", cnpj=request.cnpj[:8] + "****")
                
                protestos_result = await scraping_service.consultar_cnpj(request.cnpj)
                protestos_data = self._format_protestos_data(protestos_result)
                
                logger.info("consulta_protestos_sucesso", 
                           cnpj=request.cnpj[:8] + "****",
                           tem_protestos=bool(protestos_data.get('cenprotProtestos')))
                
            except Exception as e:
                error_msg = f"Erro na consulta de protestos: {str(e)}"
                error_messages.append(error_msg)
                logger.error("erro_consulta_protestos", 
                           cnpj=request.cnpj[:8] + "****", 
                           error=str(e),
                           error_type=type(e).__name__)
        
        # 2. Consultar dados CNPJa se algum parâmetro foi solicitado
        # Considerar CNPJa solicitada se há parâmetros específicos OU parâmetros de extração habilitados
        cnpja_requested = any([
            request.simples, 
            request.registrations, 
            request.geocoding, 
            request.suframa,
            # Ou se os parâmetros de extração básicos estão habilitados (indicando que usuário quer dados da Receita Federal)
            request.extract_basic,
            request.extract_address,
            request.extract_contact,
            request.extract_activities,
            request.extract_partners
        ])
        
        if cnpja_requested:
            try:
                cnpja_api = self._get_cnpja_api()
                cnpja_params = self._build_cnpja_params(request)
                
                logger.info("consultando_cnpja", 
                           cnpj=request.cnpj[:8] + "****",
                           params=cnpja_params)
                
                cnpja_result = cnpja_api.get_all_company_info(request.cnpj, **cnpja_params)
                cnpja_data = cnpja_result
                
                # Cache usado baseado na estratégia solicitada
                cache_used = request.strategy == 'CACHE_IF_FRESH'
                
                logger.info("consulta_cnpja_sucesso", 
                           cnpj=request.cnpj[:8] + "****",
                           cache_usado=cache_used,
                           categorias_retornadas=list(cnpja_result.keys()) if cnpja_result else [])
                
            except CNPJaInvalidCNPJError as e:
                error_msg = f"CNPJ inválido: {str(e)}"
                error_messages.append(error_msg)
                logger.warning("cnpj_invalido_cnpja", 
                              cnpj=request.cnpj[:8] + "****", 
                              error=str(e))
                
            except CNPJaNotFoundError as e:
                error_msg = f"CNPJ não encontrado na base da Receita: {str(e)}"
                error_messages.append(error_msg)
                logger.warning("cnpj_nao_encontrado_cnpja", 
                              cnpj=request.cnpj[:8] + "****", 
                              error=str(e))
                
            except CNPJaAPIError as e:
                error_msg = f"Erro na API CNPJa: {str(e)}"
                error_messages.append(error_msg)
                logger.error("erro_consulta_cnpja", 
                           cnpj=request.cnpj[:8] + "****", 
                           error=str(e),
                           error_type=type(e).__name__)
                
            except Exception as e:
                error_msg = f"Erro inesperado na consulta CNPJa: {str(e)}"
                error_messages.append(error_msg)
                logger.error("erro_inesperado_cnpja", 
                           cnpj=request.cnpj[:8] + "****", 
                           error=str(e),
                           error_type=type(e).__name__)
        
        # 3. Calcular estatísticas de protestos
        total_protests, has_protests = self._calculate_protest_stats(protestos_data)
        response_time = int((time.time() - start_time) * 1000)
        
        # 4. Determinar sucesso geral
        # Consulta é considerada bem-sucedida se pelo menos uma fonte retornou dados
        # ou se nenhuma fonte foi solicitada (caso edge)
        success = (
            (request.protestos and protestos_data is not None) or
            (cnpja_requested and cnpja_data is not None) or
            (not request.protestos and not cnpja_requested)
        )
        
        # 5. O campo 'data' agora será automaticamente preenchido com a data/hora da consulta
        
        # 6. Preparar mensagem de erro final
        final_error = None
        if not success:
            if error_messages:
                final_error = " | ".join(error_messages)
            else:
                final_error = "Nenhuma fonte de dados retornou resultados"
        
        logger.info("consulta_unificada_finalizada",
                   cnpj=request.cnpj[:8] + "****",
                   user_id=user_id,
                   success=success,
                   response_time_ms=response_time,
                   cache_usado=cache_used,
                   total_protestos=total_protests)
        
        return ConsultationResponse(
            success=success,
            cnpj=request.cnpj,
            timestamp=datetime.now(),
            protestos=protestos_data,
            dados_receita=cnpja_data,
            error=final_error,
            cache_used=cache_used,
            response_time_ms=response_time,
            total_protests=total_protests,
            has_protests=has_protests
            # Campo 'data' será preenchido automaticamente com datetime.now()
        )
    
    def _format_protestos_data(self, protestos_result) -> Optional[dict]:
        """
        Formata dados de protestos para estrutura consistente
        
        Args:
            protestos_result: Resultado do scraping service
            
        Returns:
            dict: Dados formatados ou None
        """
        if not protestos_result:
            return None
        
        try:
            # Converter para dict usando model_dump (Pydantic V2) com segurança
            if hasattr(protestos_result, 'model_dump'):
                result_dict = protestos_result.model_dump()
            elif hasattr(protestos_result, 'dict'):
                # Fallback para Pydantic V1
                result_dict = protestos_result.dict()
            else:
                # Fallback para dict nativo
                result_dict = dict(protestos_result)
            
            # Remover link_pdf do resultado
            if 'link_pdf' in result_dict:
                del result_dict['link_pdf']
            
            return result_dict
            
        except Exception as e:
            logger.error("erro_formatar_protestos", 
                       error=str(e),
                       result_type=type(protestos_result).__name__)
            
            # Fallback seguro - retornar estrutura básica
            return {
                "cnpj": getattr(protestos_result, 'cnpj', 'unknown'),
                "cenprotProtestos": {},
                "dataHora": datetime.now().isoformat()
            }
    
    def _build_cnpja_params(self, request: ConsultationRequest) -> dict:
        """
        Converte parâmetros do request para formato CNPJa API
        
        Args:
            request: Request com parâmetros
            
        Returns:
            dict: Parâmetros formatados para CNPJa API
        """
        params = {
            'strategy': request.strategy,
            'simples': request.simples,
            'geocoding': request.geocoding,
            'suframa': request.suframa,
            # Parâmetros de extração
            'basic': request.extract_basic,
            'address': request.extract_address,
            'contact': request.extract_contact,
            'activities': request.extract_activities,
            'partners': request.extract_partners
        }
        
        # Adicionar registrations se especificado
        if request.registrations:
            params['registrations'] = request.registrations
        
        # Filtrar parâmetros None e False desnecessários
        # IMPORTANTE: Sempre manter pelo menos um parâmetro para garantir que a CNPJa retorne dados básicos
        filtered_params = {}
        for key, value in params.items():
            if value is not None and value is not False:
                filtered_params[key] = value
        
        # Se nenhum parâmetro específico foi incluído, garantir que pelo menos 'basic' e 'strategy' estejam presentes
        if not any(k in filtered_params for k in ['simples', 'registrations', 'geocoding', 'suframa']):
            if 'basic' not in filtered_params:
                filtered_params['basic'] = True
            if 'strategy' not in filtered_params:
                filtered_params['strategy'] = 'CACHE_IF_FRESH'
        
        logger.debug("parametros_cnpja_construidos", params=filtered_params)
        return filtered_params
    
    def _calculate_protest_stats(self, protestos_data: Optional[dict]) -> tuple[Optional[int], Optional[bool]]:
        """
        Calcula estatísticas dos dados de protestos
        
        Args:
            protestos_data: Dados de protestos formatados
            
        Returns:
            tuple: (total_protests, has_protests)
        """
        if not protestos_data:
            return None, None
        
        try:
            # Usar a mesma lógica existente de verificação de protestos
            from api.routers.cnpj import verificar_existencia_protestos
            
            has_protests = verificar_existencia_protestos(protestos_data)
            
            # Contar total de protestos
            total_protests = 0
            cenprot_protestos = protestos_data.get('cenprotProtestos', {})
            
            if isinstance(cenprot_protestos, dict) and has_protests:
                for uf, protestos_uf in cenprot_protestos.items():
                    if isinstance(protestos_uf, list):
                        for protesto_info in protestos_uf:
                            if isinstance(protesto_info, dict):
                                # Contar pelos protestos individuais se disponível
                                protestos_list = protesto_info.get('protestos', [])
                                if isinstance(protestos_list, list):
                                    total_protests += len(protestos_list)
                                else:
                                    # Fallback: usar quantidade de títulos
                                    qtd_titulos = protesto_info.get('quantidadeTitulos', 0)
                                    total_protests += qtd_titulos
            
            return total_protests, has_protests
            
        except Exception as e:
            logger.error("erro_calcular_estatisticas_protestos", 
                        error=str(e),
                        protestos_data_type=type(protestos_data).__name__)
            return None, None
