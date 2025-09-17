"""
Scraper principal de protestos do Resolve CenProt
Usa apenas Playwright para extração completa - sem dependências externas
"""

from playwright.async_api import Page
from typing import Dict, Any, List, Optional
import asyncio
import re
from datetime import datetime
import structlog
from bs4 import BeautifulSoup

from ..models.protest_models import ConsultaCNPJResult, CartorioProtesto, ProtestoDetalhado
from ..config.selectors import ResolveSelectors
from ..config.settings import settings
from ..utils.data_formatter import DataFormatter

logger = structlog.get_logger(__name__)

class ProtestScraper:
    """Scraper principal para extração de dados de protestos usando apenas Playwright"""
    
    def __init__(self, page: Page):
        self.page = page
        self.selectors = ResolveSelectors()
        self.formatter = DataFormatter()
        self.current_cnpj: Optional[str] = None
        
    async def consultar_cnpj(self, cnpj: str) -> ConsultaCNPJResult:
        """
        Realiza consulta completa de um CNPJ seguindo os passos documentados
        
        Args:
            cnpj: CNPJ para consultar (com ou sem formatação)
            
        Returns:
            ConsultaCNPJResult: Resultado completo da consulta
        """
        # Armazenar CNPJ atual para uso nas funções internas
        self.current_cnpj = cnpj
        logger.info("iniciando_consulta_cnpj", cnpj=cnpj[:8] + "****")
        
        try:
            # Navegar para página de consulta
            if not await self._navigate_to_search_page():
                raise Exception("Falha ao navegar para página de consulta")
            
            # Realizar consulta
            if not await self._perform_search(cnpj):
                raise Exception("Falha ao executar consulta")
            
            return await self._complete_consultation(cnpj)
            
        except Exception as e:
            logger.error("erro_consulta_cnpj", cnpj=cnpj[:8] + "****", error=str(e))
            raise
    
    async def consultar_cnpj_direct(self, cnpj: str) -> ConsultaCNPJResult:
        """
        Realiza consulta direta de CNPJ em página já logada e na tela de consulta
        
        Args:
            cnpj: CNPJ para consultar (com ou sem formatação)
            
        Returns:
            ConsultaCNPJResult: Resultado completo da consulta
        """
        # Armazenar CNPJ atual para uso nas funções internas
        self.current_cnpj = cnpj
        logger.info("iniciando_consulta_cnpj_direct", cnpj=cnpj[:8] + "****")
        
        try:
            # Página já está logada e na URL correta, apenas fazer consulta
            if not await self._perform_search(cnpj):
                raise Exception("Falha ao executar consulta")
                
            return await self._complete_consultation(cnpj)
            
        except Exception as e:
            logger.error("erro_consulta_cnpj_direct", cnpj=cnpj[:8] + "****", error=str(e))
            raise
    
    async def _complete_consultation(self, cnpj: str) -> ConsultaCNPJResult:
        """🔧 CORREÇÃO: Completa consulta com timeout global anti-travamento"""
        
        # ⏱️ TIMEOUT GLOBAL para evitar consultas de 5+ minutos
        timeout_global = 180  # 3 minutos máximo total por consulta
        
        try:
            logger.info("iniciando_complete_consultation_com_timeout", 
                       cnpj=cnpj[:8] + "****",
                       timeout_global=timeout_global)
            
            # Executar toda a lógica com timeout global
            return await asyncio.wait_for(
                self._complete_consultation_internal(cnpj),
                timeout=timeout_global
            )
            
        except asyncio.TimeoutError:
            logger.error("timeout_global_consulta_cnpj", 
                       cnpj=cnpj[:8] + "****",
                       timeout=timeout_global)
            
            # Retornar resultado básico sem detalhes em caso de timeout
            return ConsultaCNPJResult(
                cnpj=cnpj,
                cenprotProtestos={"TIMEOUT": []},  # Indicar que houve timeout
                dataHora=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                link_pdf="/Consulta interrompida por timeout"
            )
            
        except Exception as e:
            logger.error("erro_complete_consultation", 
                       cnpj=cnpj[:8] + "****", 
                       error=str(e))
            raise

    async def _complete_consultation_internal(self, cnpj: str) -> ConsultaCNPJResult:
        """🔧 ATUALIZADO: Lógica interna com tratamento de erros técnicos do site"""
        
        try:
            # Aguardar resultados carregarem - OTIMIZADO
            await self._wait_for_results_fast()
            
            # 🚨 EXTRAÇÃO COM VALIDAÇÃO COMBINADA (pode lançar exceção se erro técnico)
            consultation_data = await self._extract_consultation_data_playwright()
            
            # Extrair status já processado pela validação combinada
            tem_protestos_text = consultation_data.get('tem_protestos', '').lower()
            tem_protestos = consultation_data.get('tem_protestos_bool', False)
            
            logger.info("status_consulta_extraido_com_validacao", 
                       cnpj=cnpj[:8] + "****", 
                       tem_protestos=tem_protestos,
                       status_text=tem_protestos_text[:50] + "..." if len(tem_protestos_text) > 50 else tem_protestos_text)
            
            if not tem_protestos:
                return self._create_empty_result(cnpj)
            
            # Se tem protestos, extrair detalhes de cada cartório
            logger.info("iniciando_extracao_cartorios_com_limite", cnpj=cnpj[:8] + "****")
            
            cartorios_por_estado = await self._extract_cartorios_details_with_limit(consultation_data)
            
            result = ConsultaCNPJResult(
                cnpj=cnpj,
                cenprotProtestos=cartorios_por_estado,
                dataHora=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                link_pdf="/Download de PDF desabilitado"
            )
            
            # DEBUG: Verificar dados antes do retorno
            total_protestos_calculado = result.get_total_protests_count()
            
            logger.info("consulta_cnpj_finalizada_com_timeout_control", 
                       cnpj=cnpj[:8] + "****",
                       estados_count=len(cartorios_por_estado),
                       total_protestos=total_protestos_calculado)
            
            return result
            
        except Exception as e:
            # 🚨 TRATAMENTO ESPECÍFICO PARA ERRO TÉCNICO DO SITE
            if "falha técnica do site" in str(e).lower():
                logger.error("erro_tecnico_site_durante_consulta", 
                           cnpj=cnpj[:8] + "****", 
                           error=str(e))
                
                # Retornar resultado específico indicando erro técnico
                return ConsultaCNPJResult(
                    cnpj=cnpj,
                    cenprotProtestos={"ERRO_TECNICO": []},  # Indicar erro técnico
                    dataHora=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                    link_pdf="/Erro técnico do site detectado - consulta inválida"
                )
            else:
                # Re-raise outros erros
                logger.error("erro_geral_consulta_interna", 
                           cnpj=cnpj[:8] + "****", 
                           error=str(e))
                raise
    
    async def _navigate_to_search_page(self) -> bool:
        """Navega para página de consulta pública"""
        try:
            logger.info("navegando_para_pagina_consulta")
            
            search_url = f"{settings.RESOLVE_CENPROT_URL}/app/dashboard/search/public-search"
            await self.page.goto(search_url)
            await self.page.wait_for_load_state("networkidle", timeout=15000)
            
            # Verificar se chegou na página correta
            current_url = self.page.url
            if "/public-search" not in current_url:
                logger.warning("url_consulta_diferente_esperado", current_url=current_url)
                # Tentar continuar mesmo assim
            
            # Aguardar campo de consulta aparecer
            await self.page.wait_for_selector(self.selectors.SEARCH_INPUT, timeout=10000)
            
            logger.info("pagina_consulta_carregada")
            return True
            
        except Exception as e:
            logger.error("erro_navegar_consulta", error=str(e))
            return False
    
    async def _perform_search(self, cnpj: str) -> bool:
        """Executa a consulta preenchendo CNPJ e clicando em consultar"""
        try:
            logger.info("executando_consulta", cnpj=cnpj[:8] + "****")
            
            # Limpar campo antes de preencher
            await self.page.fill(self.selectors.SEARCH_INPUT, "")
            await asyncio.sleep(0.5)
            
            # Preencher CNPJ
            await self.page.fill(self.selectors.SEARCH_INPUT, cnpj)
            
            # Verificar se foi preenchido
            field_value = await self.page.input_value(self.selectors.SEARCH_INPUT)
            if not field_value:
                logger.error("campo_consulta_nao_preenchido")
                return False
            
            # Clicar botão consultar
            await self.page.click(self.selectors.SEARCH_BTN)
            
            logger.info("consulta_executada", cnpj=cnpj[:8] + "****")
            return True
            
        except Exception as e:
            logger.error("erro_executar_consulta", error=str(e))
            return False
    
    async def _wait_for_results(self, timeout: int = 3000):
        """Aguarda resultados da consulta carregarem - VERSÃO ULTRA OTIMIZADA"""
        try:
            logger.info("aguardando_resultados_consulta_otimizado")
            
            # Tentar detectar resultados rapidamente - seletores individuais
            result_selectors = [
                self.selectors.RESULT_STATUS,  # Mais provável de existir
                self.selectors.PROTESTS_FOUND,
                self.selectors.NO_PROTESTS
            ]
            
            encontrou_resultado = False
            for i, selector in enumerate(result_selectors):
                try:
                    # Timeout muito baixo para cada seletor
                    await self.page.wait_for_selector(selector, timeout=1000)  # 1s cada
                    logger.info("resultado_encontrado_rapido", selector_index=i, selector=selector[:50])
                    encontrou_resultado = True
                    break
                except Exception:
                    continue
            
            if not encontrou_resultado:
                logger.info("seletores_nao_encontrados_assumindo_resultados_prontos")
                # Se não encontrou seletores, assumir que resultados já estão prontos
                # A extração posterior vai validar
            
            # Tempo mínimo para garantir renderização completa
            await asyncio.sleep(1)  # Reduzido de 3s para 1s
            
            logger.info("resultados_consulta_prontos_para_extracao")
            
        except Exception as e:
            logger.warning("erro_aguardar_resultados_continuando_assim_mesmo", error=str(e))
            await asyncio.sleep(0.5)  # Mínimo possível
    
    async def _wait_for_results_fast(self):
        """
        Versão ULTRA RÁPIDA com validação inteligente:
        Tenta extrair dados rapidamente ao invés de aguardar seletores específicos
        """
        logger.info("aguardando_resultados_ultra_fast_com_validacao")
        
        # Aguardar tempo mínimo inicial
        await asyncio.sleep(1)
        
        # Tentar validar se resultados estão prontos verificando se há conteúdo na página
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Tentar encontrar qualquer indicação de resultado
                page_text = await self.page.inner_text('body')
                
                # Verificar indicadores de que a consulta foi processada
                resultado_indicators = [
                    'protestos encontrados',
                    'protestos não encontrados', 
                    'não foram encontrados protestos',
                    'consulta realizada'
                ]
                
                page_text_lower = page_text.lower()
                tem_resultado = any(indicator in page_text_lower for indicator in resultado_indicators)
                
                if tem_resultado:
                    logger.info("resultados_detectados_via_texto", attempt=attempt+1)
                    break
                    
                logger.info("tentando_novamente_detectar_resultados", attempt=attempt+1)
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.warning("erro_validacao_resultados", attempt=attempt+1, error=str(e))
                await asyncio.sleep(1)
        
        logger.info("resultados_assumidos_prontos_ultra_fast")
    
    async def _extract_cartorios_details(self, consultation_data: Dict[str, Any]) -> Dict[str, List[CartorioProtesto]]:
        """
        Extrai detalhes de cada cartório clicando nos botões 'Detalhes'
        
        Args:
            consultation_data: Dados extraídos da página de consulta
            
        Returns:
            Dict com cartórios organizados por estado
        """
        logger.info("extraindo_detalhes_cartorios")
        cartorios_por_estado = {}
        
        estados_data = consultation_data.get('estados', [])
        if not estados_data:
            logger.warning("nenhum_estado_encontrado_na_consulta")
            return cartorios_por_estado
        
        for estado_data in estados_data:
            estado_nome_raw = estado_data.get('estado_nome', '')
            estado_nome = self._extract_estado_from_text(estado_nome_raw)
            
            logger.info("debug_processando_estado", 
                       estado_raw=estado_nome_raw,
                       estado_extraido=estado_nome)
            
            if not estado_nome:
                logger.warning("estado_nao_reconhecido_pulando", estado_raw=estado_nome_raw)
                continue
                
            logger.info("processando_estado", estado=estado_nome)
            cartorios_estado = []
            
            cartorios_data = estado_data.get('cartorios', [])
            
            for i, cartorio_data in enumerate(cartorios_data):
                try:
                    logger.debug("processando_cartorio", 
                               estado=estado_nome, 
                               cartorio_index=i, 
                               cartorio=cartorio_data.get('nome_cartorio', '')[:50])
                    
                    # NOVA VERSÃO: Clicar no modal para extrair valores REAIS
                    cartorio_details = await self._extract_single_cartorio_details(i, cartorio_data, estado_nome)
                    
                    if cartorio_details:
                        cartorios_estado.append(cartorio_details)
                        
                except Exception as e:
                    logger.warning("erro_extrair_cartorio_detalhes", 
                                 estado=estado_nome,
                                 cartorio_index=i,
                                 cartorio=cartorio_data.get('nome_cartorio', 'unknown'),
                                 error=str(e))
                    continue
            
            if cartorios_estado:
                cartorios_por_estado[estado_nome] = cartorios_estado
                logger.info("estado_processado", estado=estado_nome, cartorios_count=len(cartorios_estado))
        
        total_cartorios = sum(len(cartorios) for cartorios in cartorios_por_estado.values())
        logger.info("extracao_cartorios_finalizada", 
                   estados_count=len(cartorios_por_estado),
                   total_cartorios=total_cartorios)
        
        return cartorios_por_estado

    async def _extract_cartorios_details_with_limit(self, consultation_data: Dict[str, Any]) -> Dict[str, List[CartorioProtesto]]:
        """🔧 NOVO: Extrai detalhes com limite para evitar travamento"""
        logger.info("extraindo_detalhes_cartorios_com_limite")
        cartorios_por_estado = {}
        
        estados_data = consultation_data.get('estados', [])
        if not estados_data:
            logger.warning("nenhum_estado_encontrado_na_consulta_com_limite")
            return cartorios_por_estado

        # Limite global para evitar travamento
        max_cartorios_total = 20  # Máximo 20 cartórios processados por consulta
        cartorios_processados = 0
        
        for estado_data in estados_data:
            if cartorios_processados >= max_cartorios_total:
                logger.warning("limite_cartorios_atingido", 
                             processados=cartorios_processados, 
                             limite=max_cartorios_total)
                break
                
            estado_nome_raw = estado_data.get('estado_nome', '')
            estado_nome = self._extract_estado_from_text(estado_nome_raw)
            
            if not estado_nome:
                logger.warning("estado_nao_reconhecido_pulando_com_limite", estado_raw=estado_nome_raw)
                continue
                
            logger.info("processando_estado_com_limite", 
                       estado=estado_nome,
                       cartorios_restantes=max_cartorios_total - cartorios_processados)
            
            cartorios_estado = []
            cartorios_data = estado_data.get('cartorios', [])
            
            # Limite por estado também
            max_cartorios_por_estado = min(10, len(cartorios_data))  # Máximo 10 por estado
            
            for i, cartorio_data in enumerate(cartorios_data[:max_cartorios_por_estado]):
                if cartorios_processados >= max_cartorios_total:
                    break
                    
                try:
                    logger.debug("processando_cartorio_com_limite", 
                               estado=estado_nome, 
                               cartorio_index=i,
                               total_processados=cartorios_processados,
                               cartorio=cartorio_data.get('nome_cartorio', '')[:50])
                    
                    # Usar método com timeout já implementado
                    cartorio_details = await self._extract_single_cartorio_details(i, cartorio_data, estado_nome)
                    
                    if cartorio_details:
                        cartorios_estado.append(cartorio_details)
                        
                    cartorios_processados += 1
                    
                    # Log de progresso
                    logger.info("cartorio_processado_com_limite", 
                               estado=estado_nome,
                               cartorio_index=i,
                               total_processados=cartorios_processados,
                               limite=max_cartorios_total)
                        
                except Exception as e:
                    logger.warning("erro_extrair_cartorio_detalhes_com_limite", 
                                 estado=estado_nome,
                                 cartorio_index=i,
                                 cartorio=cartorio_data.get('nome_cartorio', 'unknown'),
                                 error=str(e))
                    cartorios_processados += 1  # Contar mesmo com erro
                    continue
            
            if cartorios_estado:
                cartorios_por_estado[estado_nome] = cartorios_estado
                logger.info("estado_processado_com_limite", 
                           estado=estado_nome, 
                           cartorios_count=len(cartorios_estado),
                           total_processados=cartorios_processados)

        total_cartorios = sum(len(cartorios) for cartorios in cartorios_por_estado.values())
        logger.info("extracao_cartorios_finalizada_com_limite", 
                   estados_count=len(cartorios_por_estado),
                   total_cartorios=total_cartorios,
                   limite_aplicado=max_cartorios_total,
                   processados=cartorios_processados)
        
        return cartorios_por_estado
    
    async def _extract_single_cartorio_details(self, cartorio_index: int, cartorio_data: Dict, estado_nome: str) -> Optional[CartorioProtesto]:
        """🔧 CORREÇÃO: Extrai detalhes com timeouts agressivos para evitar travamento"""
        cartorio_nome = cartorio_data.get('nome_cartorio', '').strip()
        
        # Timeout total para evitar travamento de 5+ minutos
        timeout_total = 30  # 30 segundos máximo por cartório
        
        try:
            logger.info("iniciando_extracao_com_timeout", 
                       index=cartorio_index, 
                       cartorio=cartorio_nome[:50],
                       timeout=timeout_total)
            
            # Usar asyncio.wait_for para timeout agressivo
            return await asyncio.wait_for(
                self._extract_single_cartorio_with_timeout(cartorio_index, cartorio_data, estado_nome),
                timeout=timeout_total
            )
            
        except asyncio.TimeoutError:
            logger.error("timeout_extracao_cartorio", 
                       cartorio_index=cartorio_index,
                       cartorio=cartorio_nome[:50],
                       timeout=timeout_total)
            
            # Tentar fechar modal que pode ter ficado aberto
            try:
                await asyncio.wait_for(self._emergency_close_modal(), timeout=5)
            except:
                pass
                
            return self._create_cartorio_without_details(cartorio_data)
            
        except Exception as e:
            logger.error("erro_geral_extracao_cartorio", 
                       cartorio_index=cartorio_index,
                       cartorio=cartorio_nome[:50],
                       error=str(e))
            
            return self._create_cartorio_without_details(cartorio_data)

    async def _extract_single_cartorio_with_timeout(self, cartorio_index: int, cartorio_data: Dict, estado_nome: str) -> Optional[CartorioProtesto]:
        """Método interno com lógica de extração"""
        cartorio_nome = cartorio_data.get('nome_cartorio', '').strip()
        
        try:
            # PASSO 1: Buscar botões com timeout curto
            primary_selector = "button:has-text('Detalhes')"
            
            buttons = await asyncio.wait_for(
                self.page.query_selector_all(primary_selector),
                timeout=5  # 5s para encontrar botões
            )
            
            if cartorio_index >= len(buttons):
                logger.warning("botao_detalhes_nao_encontrado_no_indice", 
                             cartorio_index=cartorio_index, total_buttons=len(buttons))
                return self._create_cartorio_without_details(cartorio_data)
            
            button_found = buttons[cartorio_index]
            logger.info("botao_encontrado_rapido", 
                       total_buttons=len(buttons), 
                       cartorio_index=cartorio_index)
            
            # PASSO 2: Clique com timeout
            logger.info("clicando_botao_com_timeout", cartorio_index=cartorio_index)
            
            await asyncio.wait_for(button_found.click(), timeout=3)
            logger.info("clique_executado_sucesso")
            
            # PASSO 3: Aguardo mínimo para modal
            await asyncio.sleep(0.8)  # 800ms para modal abrir
            
            # PASSO 4: Extrair dados com timeout
            logger.info("extraindo_dados_modal_com_timeout")
            
            modal_details = await asyncio.wait_for(
                self._extract_modal_details_fast(),
                timeout=10  # 10s para extrair dados
            )
            
            # PASSO 5: Criar objeto cartório
            cartorio = CartorioProtesto(
                cartorio=cartorio_nome,
                obterDetalhes=None,
                cidade=cartorio_data.get('cidade', '').strip(),
                quantidadeTitulos=self._parse_quantidade_titulos(cartorio_data.get('quantidade_titulos', '0')),
                endereco=modal_details.get('endereco', ''),
                telefone=modal_details.get('telefone', ''),
                protestos=modal_details.get('protestos', [])
            )
            
            logger.info("cartorio_extraido_com_sucesso", 
                       cartorio=cartorio_nome[:50],
                       endereco_ok=bool(cartorio.endereco),
                       telefone_ok=bool(cartorio.telefone),
                       protestos_count=len(cartorio.protestos))
            
            # PASSO 6: Fechar modal com timeout
            try:
                await asyncio.wait_for(self._close_modal_fast(), timeout=5)
                logger.info("modal_fechado_com_sucesso")
            except Exception as e:
                logger.warning("erro_fechar_modal", error=str(e))
            
            return cartorio
            
        except Exception as e:
            logger.error("erro_extracao_cartorio_timeout", 
                       cartorio_index=cartorio_index,
                       cartorio=cartorio_nome[:50],
                       error=str(e))
            
            # Tentar fechar modal em caso de erro
            try:
                await asyncio.wait_for(self._emergency_close_modal(), timeout=3)
            except:
                pass
            
            return self._create_cartorio_without_details(cartorio_data)
    
    def _create_cartorio_without_details(self, cartorio_data: Dict) -> CartorioProtesto:
        """Cria objeto cartório sem detalhes quando extração falha"""
        return CartorioProtesto(
            cartorio=cartorio_data.get('nome_cartorio', '').strip(),
            obterDetalhes=None,
            cidade=cartorio_data.get('cidade', '').strip(),
            quantidadeTitulos=self._parse_quantidade_titulos(cartorio_data.get('quantidade_titulos', '0')),
            endereco="",
            telefone="",
            protestos=[]
        )
    
    def _parse_quantidade_titulos(self, qtde_str: str) -> int:
        """Converte string de quantidade para inteiro"""
        try:
            # Extrair apenas números
            numbers = re.findall(r'\d+', qtde_str)
            if numbers:
                return int(numbers[0])
            return 0
        except:
            return 0
    
    async def _create_cartorio_from_basic_data(self, cartorio_data: Dict[str, Any], estado_nome: str) -> Optional[CartorioProtesto]:
        """
        VERSÃO DE PRODUÇÃO: Cria cartório usando dados básicos já extraídos
        (sem necessidade de clique nos modals que estão com problemas)
        """
        try:
            nome_cartorio = cartorio_data.get('nome_cartorio', '').strip()
            cidade = cartorio_data.get('cidade', '').strip()  
            qtd_titulos = cartorio_data.get('quantidade_titulos', '0')
            
            # Converter quantidade para int
            try:
                qtd_num = int(qtd_titulos)
            except:
                qtd_num = 1
                
            # Tentar extrair valores da tabela principal
            valores_extraidos = cartorio_data.get('valores_protestos', [])
            
            # Criar protestos com valores reais se disponíveis
            protestos = []
            for i in range(qtd_num):
                # Usar valor específico se disponível, senão usar valor estimado
                valor_protesto = "Não informado"
                if i < len(valores_extraidos):
                    valor_protesto = valores_extraidos[i]
                elif len(valores_extraidos) == 1:
                    # Se há apenas 1 valor para múltiplos protestos, usar o mesmo
                    valor_protesto = valores_extraidos[0]
                
                protesto = ProtestoDetalhado(
                    cpfCnpj=getattr(self, 'current_cnpj', ''),
                    data=None,
                    dataProtesto=None, 
                    dataVencimento="",
                    autorizacaoCancelamento=False,
                    custasCancelamento="",
                    valor=valor_protesto
                )
                protestos.append(protesto)
            
            cartorio = CartorioProtesto(
                cartorio=nome_cartorio,
                obterDetalhes=None,
                cidade=cidade,
                quantidadeTitulos=qtd_num,
                endereco="",  # Seria extraído do modal
                telefone="",  # Seria extraído do modal
                protestos=protestos
            )
            
            logger.info("cartorio_criado_dados_basicos", 
                       cartorio=nome_cartorio[:30], 
                       cidade=cidade,
                       qtd_titulos=qtd_num)
            
            return cartorio
            
        except Exception as e:
            logger.error("erro_criar_cartorio_dados_basicos", error=str(e))
            return None
    
    def _convert_to_protesto_detalhado(self, titulos_data: List[Dict]) -> List[ProtestoDetalhado]:
        """
        Converte dados brutos dos títulos para modelo ProtestoDetalhado
        
        Args:
            titulos_data: Lista de títulos extraídos do modal
            
        Returns:
            Lista de ProtestoDetalhado
        """
        protestos = []
        
        for titulo in titulos_data:
            try:
                # Extrair e limpar valor monetário
                valor_raw = titulo.get('valor_titulo', '')
                valor_limpo = self.formatter.normalize_monetary_value(valor_raw)
                
                # Determinar autorização de cancelamento baseado em custas
                custas_raw = titulo.get('custas_cancelamento', '')
                custas_limpo = self.formatter.normalize_monetary_value(custas_raw)
                autoriza_cancelamento = bool(custas_raw and custas_raw.strip())
                
                protesto = ProtestoDetalhado(
                    cpfCnpj=self.current_cnpj,
                    data=titulo.get('data_protesto'),
                    dataProtesto=titulo.get('data_protesto'),
                    dataVencimento=titulo.get('data_vencimento', ''),
                    autorizacaoCancelamento=autoriza_cancelamento,
                    custasCancelamento=custas_limpo,
                    valor=valor_limpo
                )
                
                protestos.append(protesto)
                
            except Exception as e:
                logger.warning("erro_converter_titulo_protesto", titulo=titulo, error=str(e))
                continue
        
        return protestos
    
    def _extract_estado_from_text(self, title_text: str) -> Optional[str]:
        """Extrai sigla do estado do texto do título"""
        if not title_text:
            return None
            
        # CORREÇÃO: Aceitar "BRASIL" como estado válido para parsing básico
        if title_text.upper() == "BRASIL":
            return "BRASIL"
            
        # Patterns para identificar estados
        patterns = [
            r'\b([A-Z]{2})\b',  # Sigla de 2 letras
            r'Estado\s+de\s+([A-Z]{2})',
            r'Protestos.*?([A-Z]{2})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title_text.upper())
            if match:
                state = match.group(1)
                if len(state) == 2 and state.isalpha():
                    return state
        
        # Se não encontrou sigla, tentar estados por extenso
        state_map = {
            'BAHIA': 'BA', 'SÃO PAULO': 'SP', 'RIO DE JANEIRO': 'RJ',
            'MINAS GERAIS': 'MG', 'PARANÁ': 'PR', 'RIO GRANDE DO SUL': 'RS',
            'ESPÍRITO SANTO': 'ES', 'SANTA CATARINA': 'SC', 'GOIÁS': 'GO',
            'DISTRITO FEDERAL': 'DF', 'MATO GROSSO': 'MT', 'MATO GROSSO DO SUL': 'MS',
            'PARÁ': 'PA', 'AMAZONAS': 'AM', 'ACRE': 'AC', 'RONDÔNIA': 'RO',
            'RORAIMA': 'RR', 'AMAPÁ': 'AP', 'TOCANTINS': 'TO', 'MARANHÃO': 'MA',
            'PIAUÍ': 'PI', 'CEARÁ': 'CE', 'RIO GRANDE DO NORTE': 'RN',
            'PARAÍBA': 'PB', 'PERNAMBUCO': 'PE', 'ALAGOAS': 'AL', 'SERGIPE': 'SE'
        }
        
        for full_name, sigla in state_map.items():
            if full_name in title_text.upper():
                return sigla
        
        logger.debug("estado_nao_identificado", title_text=title_text)
        return None
    
    def _has_protests_smart_detection(self, status_text: str) -> bool:
        """
        🔧 CORREÇÃO: Detecção inteligente com validação combinada para evitar falsos negativos
        
        PROBLEMA CRÍTICO IDENTIFICADO:
        - Site retorna "Protestos não encontrados" em 2 situações:
          1. SEM protestos legítimo: "Protestos não encontrados" + texto explicativo completo
          2. ERRO técnico: "Protestos não encontrados" SEM texto explicativo
        
        Args:
            status_text: Texto do status extraído da página (já em lowercase)
            
        Returns:
            bool: True se tem protestos, False se não tem
            
        Raises:
            Exception: Se detectar possível falha técnica do site
        """
        if not status_text or not isinstance(status_text, str):
            return False
        
        # Remover espaços extras e normalizar
        texto = status_text.strip().lower()
        
        # 🚨 VALIDAÇÃO CRÍTICA - Detectar possível erro técnico do site
        if self._is_possible_technical_error(texto):
            error_msg = "Possível falha técnica do site: 'Protestos não encontrados' sem confirmação completa"
            logger.error("erro_tecnico_site_detectado", 
                        texto_original=status_text[:100],
                        motivo="falta_texto_explicativo")
            raise Exception(error_msg)
        
        # ✅ VALIDAÇÃO COMBINADA - SEM PROTESTOS LEGÍTIMO
        if self._is_legitimate_no_protests(texto):
            logger.info("sem_protestos_legitimamente_confirmado", 
                       texto_original=status_text[:100],
                       validacao="combinada_aprovada")
            return False
        
        # ✅ INDICADORES DE COM PROTESTOS
        if self._has_positive_protests_indicators(texto):
            logger.info("com_protestos_detectado_positivo", texto_original=status_text[:60])
            return True
        
        # 🔍 ANÁLISE CONTEXTUAL - última tentativa
        if ('encontrado' in texto or 'encontrados' in texto):
            palavras_negativas = ['não', 'nao', 'nenhum', 'zero', 'sem']
            tem_negacao = any(negativa in texto for negativa in palavras_negativas)
            
            if tem_negacao:
                logger.info("sem_protestos_por_contexto_negativo", texto_original=status_text[:60])
                return False
            else:
                logger.info("com_protestos_por_contexto_positivo", texto_original=status_text[:60]) 
                return True
        
        # 🤷 CASO AMBÍGUO - assumir sem protestos por segurança
        logger.warning("deteccao_ambigua_assumindo_sem_protestos", texto_original=status_text[:60])
        return False
    
    def _is_possible_technical_error(self, texto: str) -> bool:
        """
        🚨 DETECTA ERRO TÉCNICO DO SITE - Versão MELHORADA
        
        Identifica quando o site tem falha e retorna resposta incompleta/incorreta
        """
        # 1️⃣ INDICADORES DE ERRO TÉCNICO DIRETOS
        erro_direto_indicators = [
            'erro interno',
            'erro no servidor',
            'tente novamente',
            'sistema indisponível',
            'falha na consulta',
            'erro temporário'
        ]
        
        if any(indicator in texto for indicator in erro_direto_indicators):
            logger.warning("erro_tecnico_indicador_direto", indicador_encontrado=texto[:100])
            return True
        
        # 2️⃣ RESPOSTA MUITO CURTA/INCOMPLETA (suspeita de erro)
        if len(texto.strip()) < 20 and 'protestos' in texto:
            logger.warning("erro_tecnico_resposta_muito_curta", texto_completo=texto)
            return True
        
        # 3️⃣ ANÁLISE COMBINADA ORIGINAL (melhorada)
        tem_titulo_nao_encontrados = any(indicador in texto for indicador in [
            'protestos não encontrados',
            'protestos nao encontrados',
            'não encontrados protestos',
            'nao encontrados protestos',
            'nenhum protesto encontrado',
            'sem protestos encontrados'
        ])
        
        if not tem_titulo_nao_encontrados:
            return False
        
        # ✅ TEXTOS EXPLICATIVOS QUE CONFIRMAM LEGITIMIDADE
        textos_explicativos_obrigatorios = [
            # Frases completas específicas
            'não foram encontrados protestos para esse cpf/cnpj consultado',
            'nao foram encontrados protestos para esse cpf/cnpj consultado',
            'não foram encontrados protestos para esse',
            'nao foram encontrados protestos para esse',
            'não foram encontrados protestos para',
            'nao foram encontrados protestos para',
            # Frases sobre validade legal
            'as informações referem-se a pesquisa',
            'as informacoes referem-se a pesquisa',
            'não valendo como certidão',
            'nao valendo como certidao',
            'certidão no tabelionato indicado',
            'certidao no tabelionato indicado',
            'confirmação por certidão',
            'confirmacao por certidao',
            # Data da consulta (outro indicador de resposta completa)
            'consulta realizada em:',
            'consultado em:',
            # Horário específico
            'às '
        ]
        
        tem_texto_explicativo = any(explicativo in texto for explicativo in textos_explicativos_obrigatorios)
        
        # 4️⃣ LÓGICA PRINCIPAL: Título sem explicação = ERRO TÉCNICO
        if tem_titulo_nao_encontrados and not tem_texto_explicativo:
            logger.warning("erro_tecnico_titulo_sem_explicacao", 
                         titulo_encontrado=True,
                         tem_explicacao=False,
                         texto_preview=texto[:150])
            return True
        
        # 5️⃣ VERIFICAÇÃO ADICIONAL: Se tem data/hora mas resposta muito curta
        if ('consulta realizada' in texto or 'consultado em' in texto) and len(texto.strip()) < 80:
            logger.warning("erro_tecnico_resposta_com_data_mas_incompleta", tamanho=len(texto))
            return True
            
        return False
    
    def _is_legitimate_no_protests(self, texto: str) -> bool:
        """
        ✅ NOVA: Valida se é um "sem protestos" legítimo com validação combinada
        
        Exige AMBOS:
        1. Título "Protestos não encontrados"  
        2. Texto explicativo confirmatório
        """
        # Verificar título
        tem_titulo = any(titulo in texto for titulo in [
            'protestos não encontrados',
            'protestos nao encontrados',
            'não encontrados protestos',
            'nao encontrados protestos'
        ])
        
        # Verificar texto explicativo (pelo menos um)
        textos_explicativos = [
            'não foram encontrados protestos para esse cpf/cnpj consultado',
            'nao foram encontrados protestos para esse cpf/cnpj consultado',
            'não foram encontrados protestos para',
            'nao foram encontrados protestos para',
            'as informações referem-se a pesquisa',
            'as informacoes referem-se a pesquisa'
        ]
        
        tem_explicacao = any(explicacao in texto for explicacao in textos_explicativos)
        
        # ✅ VALIDAÇÃO COMBINADA: Precisa ter AMBOS
        return tem_titulo and tem_explicacao
    
    def _has_positive_protests_indicators(self, texto: str) -> bool:
        """✅ Verifica indicadores positivos de protestos"""
        com_protestos_indicadores = [
            'protestos encontrados',
            'protesto encontrado', 
            'encontrados protestos',
            'encontrado protesto',
            'foram encontrados protestos',
            'foi encontrado protesto',
            'existem protestos',
            'há protestos',
            'ha protestos'
        ]
        
        return any(indicador in texto for indicador in com_protestos_indicadores)

    def _create_empty_result(self, cnpj: str) -> ConsultaCNPJResult:
        """Cria resultado vazio para CNPJs sem protestos"""
        return ConsultaCNPJResult(
            cnpj=cnpj,
            cenprotProtestos={},
            dataHora=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            link_pdf="/Download de PDF desabilitado"
        )
    
    async def _take_error_screenshot(self, filename: str):
        """Captura screenshot em caso de erro"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = settings.LOGS_DIR / "screenshots" / f"{filename}_{timestamp}.png"
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info("screenshot_erro_capturado", path=str(screenshot_path))
            
        except Exception as e:
            logger.debug("erro_capturar_screenshot", error=str(e))
    
    async def validate_search_page_loaded(self) -> bool:
        """Valida se a página de consulta carregou corretamente"""
        try:
            # Verificar se elementos essenciais estão presentes
            search_input = await self.page.query_selector(self.selectors.SEARCH_INPUT)
            search_btn = await self.page.query_selector(self.selectors.SEARCH_BTN)
            
            if not search_input or not search_btn:
                return False
            
            # Verificar se estão visíveis
            input_visible = await search_input.is_visible()
            btn_visible = await search_btn.is_visible()
            
            return input_visible and btn_visible
            
        except Exception as e:
            logger.debug("erro_validar_pagina_consulta", error=str(e))
            return False
    
    async def _extract_consultation_data_playwright(self) -> Dict[str, Any]:
        """
        🔧 ATUALIZADO: Extrai dados completos da consulta incluindo validação combinada
        
        Returns:
            Dict com tem_protestos, data_consulta e lista de estados/cartórios
        """
        logger.info("extraindo_dados_consulta_playwright_puro_com_validacao_combinada")
        
        try:
            # Verificar se tem protestos com VALIDAÇÃO COMBINADA
            tem_protestos = False
            status_text = ""
            
            # 🔧 CORREÇÃO: Extrair texto da área de resultados (não formulário)
            try:
                status_text_completo = ""
                
                # ESTRATÉGIA 1: Buscar seletor específico de resultados primeiro  
                try:
                    # Aguardar área de resultados aparecer (timeout menor para detectar falhas rápidas)
                    try:
                        await self.page.wait_for_selector("text=Protestos", timeout=3000)
                        logger.info("area_resultados_detectada_rapidamente")
                    except Exception:
                        # Se não apareceu rápido, pode ser erro técnico - fazer busca mais ampla
                        logger.warning("area_resultados_nao_detectada_rapidamente_buscando_alternativas")
                    
                    # Buscar especificamente por containers com "Protestos" (resultados)
                    result_selectors_prioritarios = [
                        # Containers que definitivamente contêm resultados
                        "div:has-text('Protestos encontrados')",
                        "div:has-text('Protestos não encontrados')", 
                        # Container pai dos resultados
                        ".border:has-text('Protestos')",
                        # Seletor original (mais confiável)
                        self.selectors.RESULT_STATUS,
                        # 🚨 NOVO: Seletor mais amplo para capturar erros técnicos
                        "*:has-text('Protestos')",
                        "div:contains('Protestos')"
                    ]
                    
                    for selector in result_selectors_prioritarios:
                        try:
                            element = await self.page.query_selector(selector)
                            if element:
                                text_content = (await element.inner_text()).strip()
                                # 🔧 NOVA VALIDAÇÃO: Aceitar qualquer conteúdo com "protestos"
                                if 'protestos' in text_content.lower():
                                    # Se for muito curto, pode ser erro técnico - ainda assim capturar
                                    if 'consultar' not in text_content.lower() or len(text_content) < 50:
                                        status_text_completo = text_content
                                        logger.info("resultado_encontrado_possivelmente_incompleto", 
                                                   selector=selector[:40],
                                                   tamanho_texto=len(text_content),
                                                   texto_preview=text_content[:100])
                                        break
                        except Exception:
                            continue
                            
                except Exception:
                    logger.warning("erro_estrategia_1_busca_especifica")
                    pass
                
                # ESTRATÉGIA 2: Se não encontrou resultado específico, buscar área mais ampla
                if not status_text_completo:
                    try:
                        # Buscar container mais amplo, mas filtrar conteúdo
                        broader_selectors = [
                            ".border.border-\\[\\#D0DFEA\\].bg-white.text-slate-950",
                            ".border.bg-white"
                        ]
                        
                        for selector in broader_selectors:
                            try:
                                container = await self.page.query_selector(selector)
                                if container:
                                    full_text = (await container.inner_text()).strip()
                                    # 🔍 FILTRAR: Só aceitar se contém "protestos" E NÃO é apenas formulário
                                    if ('protestos' in full_text.lower() and 
                                        'consultado' in full_text.lower() and  # Indica resultado
                                        len(full_text) > 50):  # Texto substancial
                                        
                                        status_text_completo = full_text
                                        logger.info("container_resultado_filtrado_encontrado", 
                                                   selector=selector[:30],
                                                   texto_preview=full_text[:100])
                                        break
                            except Exception:
                                continue
                    except Exception:
                        pass
                
                # ESTRATÉGIA 3: Fallback para seletor original simples
                if not status_text_completo:
                    try:
                        status_element = await self.page.query_selector(self.selectors.RESULT_STATUS)
                        if status_element:
                            status_text_completo = (await status_element.inner_text()).strip()
                            logger.info("usando_seletor_original_fallback", 
                                       texto_preview=status_text_completo[:100])
                    except Exception:
                        pass
                
                # 🚨 ESTRATÉGIA 4: ANÁLISE DE HTML BRUTO para casos críticos
                if not status_text_completo:
                    try:
                        logger.warning("todas_estrategias_falharam_analisando_html_bruto")
                        page_content = await self.page.content()
                        
                        # Buscar por "protestos" no HTML usando regex simples
                        import re
                        
                        # Extrair texto ao redor de "protestos"
                        protestos_matches = re.finditer(
                            r'.{0,200}protestos.{0,200}', 
                            page_content, 
                            re.IGNORECASE | re.DOTALL
                        )
                        
                        for match in protestos_matches:
                            # Limpar HTML tags básicas
                            texto_limpo = re.sub(r'<[^>]+>', ' ', match.group())
                            texto_limpo = re.sub(r'\s+', ' ', texto_limpo).strip()
                            
                            # Se encontrou texto substancial com "protestos"
                            if len(texto_limpo) > 10 and 'protestos' in texto_limpo.lower():
                                status_text_completo = texto_limpo
                                logger.warning("texto_recuperado_via_html_bruto", 
                                             texto_preview=texto_limpo[:150])
                                break
                                
                    except Exception as e:
                        logger.error("erro_analise_html_bruto", error=str(e))
                
                # Usar texto encontrado para validação
                status_text = status_text_completo.lower()
                
                if status_text and 'protestos' in status_text:
                    # 🚨 VALIDAÇÃO COMBINADA com possibilidade de erro técnico
                    tem_protestos = self._has_protests_smart_detection(status_text)
                    logger.info("status_extraido_com_validacao_combinada", 
                               status_preview=status_text[:100], 
                               tem_protestos=tem_protestos)
                elif status_text:
                    # Se tem texto mas não contém "protestos", é provavelmente formulário
                    logger.warning("texto_encontrado_mas_sem_protestos_possivelmente_formulario", 
                                 texto=status_text[:100])
                    tem_protestos = False
                else:
                    logger.warning("nenhum_texto_status_encontrado_com_protestos")
                    
            except Exception as e:
                # Se _has_protests_smart_detection lançar exceção (erro técnico)
                if "falha técnica do site" in str(e).lower():
                    logger.error("erro_tecnico_detectado_durante_extracao", error=str(e))
                    # Re-raise para que seja tratado no nível superior
                    raise
                else:
                    logger.warning("erro_extrair_status_combinado", error=str(e))
            
            # Extrair data da consulta
            data_consulta = ""
            try:
                date_element = await self.page.query_selector(self.selectors.CONSULTATION_DATE)
                if date_element:
                    data_consulta = (await date_element.inner_text()).strip()
            except Exception as e:
                logger.warning("erro_extrair_data_consulta", error=str(e))
            
            # Se não tem protestos, retornar dados básicos
            if not tem_protestos:
                return {
                    "tem_protestos": status_text or "sem protestos",
                    "tem_protestos_bool": False,  # 🔧 NOVO: boolean processado
                    "data_consulta": data_consulta,
                    "estados": []
                }
            
            # Extrair dados dos cartórios por estado
            estados = await self._extract_estados_cartorios_playwright()
            
            logger.info("extracao_consulta_playwright_finalizada",
                       tem_protestos=tem_protestos,
                       total_estados=len(estados))
            
            return {
                "tem_protestos": status_text,
                "tem_protestos_bool": tem_protestos,  # 🔧 NOVO: boolean processado
                "data_consulta": data_consulta,
                "estados": estados
            }
            
        except Exception as e:
            logger.error("erro_extracao_consulta_playwright", error=str(e))
            return {
                "tem_protestos": "erro",
                "data_consulta": "",
                "estados": []
            }
    
    async def _extract_estados_cartorios_playwright(self) -> List[Dict[str, Any]]:
        """
        Extrai dados de estados e cartórios usando Playwright puro
        
        Returns:
            Lista de estados com seus cartórios
        """
        estados = []
        
        try:
            # Buscar seções de estados
            state_sections = await self.page.query_selector_all(self.selectors.STATE_SECTIONS)
            
            for section in state_sections:
                try:
                    # Extrair nome do estado
                    state_name_elem = await section.query_selector(self.selectors.STATE_NAME)
                    if not state_name_elem:
                        continue
                        
                    estado_nome = await state_name_elem.inner_text()
                    estado_nome = estado_nome.strip()
                    
                    # Extrair cartórios da tabela
                    cartorios = []
                    cartorio_rows = await section.query_selector_all(self.selectors.CARTORIOS_TABLE)
                    
                    for row in cartorio_rows:
                        try:
                            cells = await row.query_selector_all("td")
                            if len(cells) >= 3:
                                # Extrair dados das células
                                nome_cartorio = await cells[0].inner_text() if cells[0] else ""
                                cidade = await cells[1].inner_text() if len(cells) > 1 and cells[1] else ""
                                qtd_titulos = await cells[2].inner_text() if len(cells) > 2 and cells[2] else "0"
                                
                                # Limpar dados
                                nome_cartorio = nome_cartorio.strip()
                                cidade = cidade.strip()
                                qtd_titulos = qtd_titulos.strip()
                                
                                if nome_cartorio and cidade:  # Só adiciona se tem dados válidos
                                    cartorios.append({
                                        "nome_cartorio": nome_cartorio,
                                        "cidade": cidade,
                                        "quantidade_titulos": qtd_titulos
                                    })
                                    
                        except Exception as e:
                            logger.warning("erro_extrair_cartorio_row", error=str(e))
                            continue
                    
                    if cartorios:  # Só adiciona estado se tem cartórios
                        estados.append({
                            "estado_nome": estado_nome,
                            "cartorios": cartorios
                        })
                        
                        logger.debug("estado_extraido", estado=estado_nome, cartorios_count=len(cartorios))
                        
                except Exception as e:
                    logger.warning("erro_extrair_estado", error=str(e))
                    continue
            
            logger.info("estados_extraidos_playwright", total_estados=len(estados))
            return estados
            
        except Exception as e:
            logger.error("erro_extrair_estados_playwright", error=str(e))
            return []
    
    async def _extract_modal_details_playwright(self) -> Dict[str, Any]:
        """
        Extrai detalhes do modal usando apenas Playwright
        
        Returns:
            Dict com endereco, telefone e lista de protestos detalhados
        """
        logger.info("extraindo_modal_details_playwright")
        
        try:
            # Extrair endereço
            endereco = ""
            try:
                endereco_selectors = [
                    self.selectors.MODAL_ENDERECO,
                    "p:has-text('Endereço') + p",
                    "p:has-text('Endereço:') span",
                    "text=/Endereço[:\s]+([^\\n]+)/i"
                ]
                
                for selector in endereco_selectors:
                    endereco_elem = await self.page.query_selector(selector)
                    if endereco_elem:
                        endereco = (await endereco_elem.inner_text()).strip()
                        if endereco:
                            break
                            
            except Exception as e:
                logger.warning("erro_extrair_endereco_modal", error=str(e))
            
            # Extrair telefone
            telefone = ""
            try:
                telefone_selectors = [
                    self.selectors.MODAL_TELEFONE,
                    "p:has-text('Telefone') + p", 
                    "p:has-text('Telefone:') span",
                    "text=/Telefone[:\s]+([^\\n]+)/i"
                ]
                
                for selector in telefone_selectors:
                    telefone_elem = await self.page.query_selector(selector)
                    if telefone_elem:
                        telefone = (await telefone_elem.inner_text()).strip()
                        if telefone:
                            break
                            
            except Exception as e:
                logger.warning("erro_extrair_telefone_modal", error=str(e))
            
            # Extrair protestos detalhados
            protestos = await self._extract_protestos_from_modal()
            
            logger.info("modal_details_extraidos_playwright",
                       tem_endereco=bool(endereco),
                       tem_telefone=bool(telefone),
                       protestos_count=len(protestos))
            
            return {
                "endereco": endereco,
                "telefone": telefone,
                "protestos": protestos
            }
            
        except Exception as e:
            logger.error("erro_extrair_modal_details_playwright", error=str(e))
            return {
                "endereco": "",
                "telefone": "",
                "protestos": []
            }
    
    async def _extract_protestos_from_modal(self) -> List[ProtestoDetalhado]:
        """
        Extrai protestos individuais do modal usando Playwright
        
        Returns:
            Lista de protestos detalhados com valores REAIS
        """
        protestos = []
        
        try:
            # Buscar containers de títulos no modal
            titulo_containers = await self.page.query_selector_all(self.selectors.TITULOS_CONTAINER)
            
            if not titulo_containers:
                # Fallback: buscar qualquer div ou section que contenha dados de protesto
                titulo_containers = await self.page.query_selector_all("div:has-text('Código'), section:has-text('Código'), .protesto, [data-protesto]")
            
            for container in titulo_containers:
                try:
                    # Extrair código
                    codigo = ""
                    try:
                        codigo_elem = await container.query_selector(self.selectors.TITULO_CODIGO)
                        if not codigo_elem:
                            # Fallback: buscar texto que contenha "Código:"
                            codigo_elem = await container.query_selector("text=/Código[:\s]+([^\\n]+)/i")
                        if codigo_elem:
                            codigo_text = await codigo_elem.inner_text()
                            # Extrair só o código (remover "Código:" se existir)
                            codigo = re.sub(r'^.*?código[:\s]*', '', codigo_text, flags=re.IGNORECASE).strip()
                    except:
                        pass
                    
                    # Extrair documento
                    documento = ""
                    try:
                        doc_elem = await container.query_selector(self.selectors.TITULO_DOCUMENTO)
                        if not doc_elem:
                            # Fallback: buscar texto que contenha "Documento:"
                            doc_elem = await container.query_selector("text=/Documento[:\s]+([^\\n]+)/i")
                        if doc_elem:
                            documento_text = await doc_elem.inner_text()
                            # Extrair só o documento (remover "Documento:" se existir)
                            documento = re.sub(r'^.*?documento[:\s]*', '', documento_text, flags=re.IGNORECASE).strip()
                    except:
                        pass
                    
                    # Extrair valor (mais importante!)
                    valor = await self._extract_valor_from_container(container)
                    
                    # Criar protesto se encontrou pelo menos um valor
                    if valor and valor != "0,00":
                        protesto = ProtestoDetalhado(
                            cpfCnpj=self.current_cnpj or "",
                            data=None,
                            dataProtesto=None,
                            dataVencimento="",
                            autorizacaoCancelamento=False,  # TODO: extrair se disponível
                            custasCancelamento="",  # TODO: extrair se disponível
                            valor=valor
                        )
                        
                        protestos.append(protesto)
                        
                        logger.debug("protesto_extraido_playwright",
                                   codigo=codigo[:10] if codigo else "",
                                   documento=documento[:20] if documento else "",
                                   valor=valor)
                    
                except Exception as e:
                    logger.warning("erro_extrair_protesto_container", error=str(e))
                    continue
            
            # Se não encontrou protestos nos containers específicos, buscar valores monetários em geral
            if not protestos:
                protestos = await self._extract_valores_fallback_modal()
            
            logger.info("protestos_extraidos_modal", total=len(protestos))
            return protestos
            
        except Exception as e:
            logger.error("erro_extrair_protestos_modal", error=str(e))
            return []
    
    async def _extract_valor_from_container(self, container) -> str:
        """
        Extrai valor monetário de um container específico
        
        Args:
            container: Elemento do modal que contém dados do protesto
            
        Returns:
            Valor monetário formatado
        """
        try:
            # Tentar seletor específico do valor (fundo verde)
            valor_elem = await container.query_selector(self.selectors.TITULO_VALOR)
            
            if not valor_elem:
                # Fallback: buscar qualquer elemento com classe de valor ou fundo colorido
                fallback_selectors = [
                    ".valor, .value",
                    "[class*='bg-green']",
                    "[class*='bg-']",
                    "span:has-text('R$')",
                    "p:has-text('R$')",
                    "div:has-text('R$')"
                ]
                
                for selector in fallback_selectors:
                    valor_elem = await container.query_selector(selector)
                    if valor_elem:
                        break
            
            if valor_elem:
                valor_text = await valor_elem.inner_text()
                return self._clean_monetary_value(valor_text)
            
            # Se ainda não encontrou, buscar por texto que contenha valor monetário
            container_text = await container.inner_text()
            return self._extract_monetary_from_text(container_text)
            
        except Exception as e:
            logger.warning("erro_extrair_valor_container", error=str(e))
            return "0,00"
    
    async def _extract_valores_fallback_modal(self) -> List[ProtestoDetalhado]:
        """
        Extração de fallback quando não consegue encontrar containers específicos
        Busca qualquer valor monetário no modal
        
        Returns:
            Lista de protestos com valores encontrados
        """
        protestos = []
        
        try:
            # Buscar todos os elementos que podem conter valores
            value_selectors = [
                "text=/R\\$[\\s]*[\\d.,]+/",
                "[class*='valor']",
                "[class*='value']", 
                "[class*='bg-green']",
                "span:has-text('R$'), p:has-text('R$'), div:has-text('R$')"
            ]
            
            valores_encontrados = set()  # Evitar duplicatas
            
            for selector in value_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    for elem in elements:
                        text = await elem.inner_text()
                        valor_limpo = self._extract_monetary_from_text(text)
                        if valor_limpo and valor_limpo != "0,00" and valor_limpo not in valores_encontrados:
                            valores_encontrados.add(valor_limpo)
                            
                            protesto = ProtestoDetalhado(
                                cpfCnpj=self.current_cnpj or "",
                                data=None,
                                dataProtesto=None,
                                dataVencimento="",
                                autorizacaoCancelamento=False,
                                custasCancelamento="",
                                valor=valor_limpo
                            )
                            
                            protestos.append(protesto)
                            logger.debug("valor_extraido_fallback", valor=valor_limpo)
                            
                except Exception as e:
                    logger.warning("erro_fallback_selector", selector=selector, error=str(e))
                    continue
            
            return protestos
            
        except Exception as e:
            logger.error("erro_extract_valores_fallback", error=str(e))
            return []
    
    def _extract_monetary_from_text(self, text: str) -> str:
        """
        Extrai valor monetário de qualquer texto usando regex
        
        Args:
            text: Texto que pode conter valor monetário
            
        Returns:
            Valor monetário limpo e formatado
        """
        if not text:
            return "0,00"
        
        # Padrões para valores monetários brasileiros
        patterns = [
            r'R\$\s*([\d.,]+)',  # R$ 123,45
            r'([\d.,]+)\s*reais?',  # 123,45 reais
            r'Valor:?\s*R?\$?\s*([\d.,]+)',  # Valor: R$ 123,45
            r'([\d]{1,3}(?:[.,]\d{3})*[.,]\d{2})',  # 1.234,56
            r'([\d]+[.,]\d{2})',  # 123,45
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                found_value = match.group(1)
                return self._clean_monetary_value(found_value)
        
        return "0,00"
    
    def _clean_monetary_value(self, raw_value: str) -> str:
        """
        Limpa e padroniza valor monetário
        
        Args:
            raw_value: Valor bruto extraído
            
        Returns:
            Valor limpo no formato brasileiro (1.234,56)
        """
        if not raw_value:
            return "0,00"
        
        # Remover caracteres não numéricos exceto vírgula e ponto
        cleaned = re.sub(r'[^\d.,]', '', raw_value.strip())
        
        if not cleaned:
            return "0,00"
        
        # Se tem vírgula E ponto, assumir formato brasileiro (1.234,56)
        if ',' in cleaned and '.' in cleaned:
            # Verificar se vírgula está depois do ponto (formato brasileiro correto)
            if cleaned.rfind(',') > cleaned.rfind('.'):
                return cleaned  # Já está correto
            else:
                # Formato americano (1,234.56) -> converter para brasileiro
                cleaned = cleaned.replace(',', 'X').replace('.', ',').replace('X', '.')
        
        # Se tem apenas vírgula, assumir que é decimal brasileiro
        elif ',' in cleaned and '.' not in cleaned:
            return cleaned
        
        # Se tem apenas ponto, pode ser decimal americano -> converter
        elif '.' in cleaned and ',' not in cleaned:
            # Se o ponto está nas últimas 2 posições, é decimal
            if len(cleaned) - cleaned.rfind('.') <= 3:
                return cleaned.replace('.', ',')
            else:
                # Ponto é separador de milhares, adicionar ,00
                return cleaned + ',00'
        
        # Só números, adicionar ,00
        else:
            return cleaned + ',00'
    
    async def _extract_modal_details_robust(self) -> Dict[str, Any]:
        """
        Extrai detalhes do modal usando múltiplas estratégias robustas
        baseado na estrutura HTML real da documentação
        
        Returns:
            Dict com endereco, telefone e lista de protestos detalhados
        """
        logger.info("extraindo_modal_details_robust")
        
        try:
            # Estratégia 1: Extrair endereço com múltiplas abordagens
            endereco = ""
            endereco_selectors = [
                "p:has-text('Endereço:') span",
                "span:has-text('Endereço:')",
                "p:contains('Endereço:')",
                "*[class*='text-[#323739]']:has-text('Endereço:')"
            ]
            
            for selector in endereco_selectors:
                try:
                    elementos = await self.page.query_selector_all(selector)
                    for elem in elementos:
                        text = await elem.inner_text()
                        # Extrair endereço (após "Endereço: ")
                        if "Endereço:" in text:
                            endereco = text.replace("Endereço:", "").strip()
                            if endereco:
                                logger.debug("endereco_extraido", endereco=endereco[:50])
                                break
                    if endereco:
                        break
                except Exception as e:
                    logger.debug("erro_extrair_endereco", selector=selector, error=str(e))
                    continue
            
            # Estratégia 2: Extrair telefone
            telefone = ""
            telefone_selectors = [
                "p:has-text('Telefone:') span",
                "span:has-text('Telefone:')",
                "p:contains('Telefone:')",
                "*[class*='text-[#323739]']:has-text('Telefone:')"
            ]
            
            for selector in telefone_selectors:
                try:
                    elementos = await self.page.query_selector_all(selector)
                    for elem in elementos:
                        text = await elem.inner_text()
                        # Extrair telefone (após "Telefone: ")
                        if "Telefone:" in text:
                            telefone = text.replace("Telefone:", "").strip()
                            if telefone:
                                logger.debug("telefone_extraido", telefone=telefone)
                                break
                    if telefone:
                        break
                except Exception as e:
                    logger.debug("erro_extrair_telefone", selector=selector, error=str(e))
                    continue
            
            # Estratégia 3: Extrair protestos individuais com valores reais
            protestos = await self._extract_protestos_robust_from_modal()
            
            logger.info("modal_details_extraidos_robust",
                       tem_endereco=bool(endereco),
                       tem_telefone=bool(telefone),
                       protestos_count=len(protestos))
            
            return {
                "endereco": endereco,
                "telefone": telefone,
                "protestos": protestos
            }
            
        except Exception as e:
            logger.error("erro_extrair_modal_details_robust", error=str(e))
            return {
                "endereco": "",
                "telefone": "",
                "protestos": []
            }
    
    async def _extract_protestos_robust_from_modal(self) -> List[ProtestoDetalhado]:
        """
        Extrai protestos individuais do modal com valores reais - TODOS OS PROTESTOS
        baseado na estrutura HTML da documentação
        
        Returns:
            Lista de protestos detalhados com valores REAIS (TODOS - valores iguais são legítimos)
        """
        protestos = []
        # REMOVIDA deduplicação - protestos diferentes podem ter valores iguais legitimamente
        
        try:
            # ESTRATÉGIA 1: Usar seletor mais específico (da documentação HTML real)
            # Baseado na estrutura real: div.flex.flex-col que contém código E tem elemento irmão com valor
            protesto_selectors = [
                "div.flex.flex-col:has(p:contains('Código:'))",  # Mais específico da documentação
                ".grid.md\\:grid-cols-2 .flex.flex-col"  # Fallback original 
            ]
            
            protesto_elements = []
            for selector in protesto_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    if elements:
                        protesto_elements = elements
                        logger.info("protestos_elementos_encontrados_sem_duplicata", 
                                   selector=selector, 
                                   count=len(elements))
                        break
                except Exception as e:
                    logger.debug("erro_selector_protestos", selector=selector, error=str(e))
                    continue
            
            # Se não encontrou com seletores específicos, usar fallback
            if not protesto_elements:
                logger.info("usando_fallback_busca_valores_r$_sem_duplicata")
                return await self._extract_protestos_fallback_robust()
            
            for i, element in enumerate(protesto_elements):
                try:
                    # Extrair dados de cada protesto
                    codigo = ""
                    documento = ""
                    valor = ""
                    
                    # Buscar código no elemento
                    try:
                        codigo_text = await element.inner_text()
                        # Extrair código usando regex (da documentação: *******************0714)
                        import re
                        codigo_match = re.search(r'Código:\s*([*0-9]+)', codigo_text)
                        if codigo_match:
                            codigo = codigo_match.group(1).strip()
                    except:
                        pass
                    
                    # Buscar documento no elemento
                    try:
                        doc_match = re.search(r'Documento:\s*([0-9./\-]+)', codigo_text)
                        if doc_match:
                            documento = doc_match.group(1).strip()
                    except:
                        pass
                    
                    # Buscar valor (mais importante!) - pode estar em elemento irmão
                    try:
                        # Estratégia 1: Buscar valor no próprio elemento
                        valor_match = re.search(r'Valor:\s*R\$([0-9.,]+)', codigo_text)
                        if valor_match:
                            valor = f"R${valor_match.group(1).strip()}"
                        else:
                            # Estratégia 2: Buscar em elemento irmão (estrutura da documentação)
                            parent = await element.query_selector("..")
                            if parent:
                                # Buscar div com fundo verde (bg-[#A1F5A7])
                                valor_element = await parent.query_selector(".bg-\\[\\#A1F5A7\\] p, [class*='bg-[#A1F5A7]'] p")
                                if valor_element:
                                    valor_text = await valor_element.inner_text()
                                    # Extrair valor (formato: "Valor: R$8.180,75")
                                    valor_match = re.search(r'R\$([0-9.,]+)', valor_text)
                                    if valor_match:
                                        valor = f"R${valor_match.group(1).strip()}"
                                    else:
                                        valor = valor_text.strip()
                    except:
                        pass
                    
                    # Criar protesto se encontrou valor válido
                    if valor and valor != "R$" and "R$" in valor:
                        valor_limpo = self._clean_monetary_value_simple(valor)
                        
                        # ADICIONAR TODOS OS PROTESTOS - valores iguais são legítimos
                        protesto = ProtestoDetalhado(
                            cpfCnpj=self.current_cnpj or "",
                            data=None,
                            dataProtesto=None,
                            dataVencimento="",
                            autorizacaoCancelamento=False,
                            custasCancelamento="",
                            valor=valor_limpo
                        )
                        
                        protestos.append(protesto)
                        
                        logger.debug("protesto_extraido_mantendo_todos",
                                   elemento_index=i,
                                   codigo=codigo[:15] if codigo else "",
                                   documento=documento[:20] if documento else "",
                                   valor=valor_limpo)
                    
                except Exception as e:
                    logger.warning("erro_extrair_protesto_individual", error=str(e))
                    continue
            
            logger.info("protestos_extraidos_todos_mantidos", 
                       total_elementos=len(protesto_elements),
                       total_protestos=len(protestos))
            return protestos
            
        except Exception as e:
            logger.error("erro_extrair_protestos_robust", error=str(e))
            return []
    
    async def _extract_protestos_fallback_robust(self) -> List[ProtestoDetalhado]:
        """
        Fallback robusto: busca qualquer elemento com valor monetário - SEM DUPLICATAS
        """
        protestos = []
        
        try:
            # Buscar todos os elementos que contenham R$ com números - OTIMIZADO
            value_selectors = [
                "[class*='bg-[#A1F5A7]'] p",  # Fundo verde da documentação - PRIMEIRO
                "p:contains('R$')",
                "*:has-text('R$')"
            ]
            
            valores_encontrados = set()
            
            for selector in value_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    for elem in elements:
                        text = await elem.inner_text()
                        
                        # Buscar padrão de valor (R$123,45)
                        import re
                        valor_matches = re.findall(r'R\$[\s]*([0-9.,]+)', text)
                        
                        for match in valor_matches:
                            valor_limpo = f"R${match.strip()}"
                            
                            # Evitar duplicatas e valores inválidos
                            if (valor_limpo not in valores_encontrados and 
                                len(match.replace(',', '').replace('.', '')) >= 2):  # Valor mínimo
                                
                                valores_encontrados.add(valor_limpo)
                                
                                protesto = ProtestoDetalhado(
                                    cpfCnpj=self.current_cnpj or "",
                                    data=None,
                                    dataProtesto=None,
                                    dataVencimento="",
                                    autorizacaoCancelamento=False,
                                    custasCancelamento="",
                                    valor=self._clean_monetary_value_simple(valor_limpo)
                                )
                                
                                protestos.append(protesto)
                                logger.debug("valor_extraido_fallback_sem_duplicata", 
                                           valor=valor_limpo, 
                                           selector=selector)
                                
                except Exception as e:
                    logger.debug("erro_fallback_selector", selector=selector, error=str(e))
                    continue
            
            logger.info("fallback_finalizado", 
                       total_protestos=len(protestos),
                       valores_encontrados=len(valores_encontrados))
            return protestos
            
        except Exception as e:
            logger.error("erro_fallback_robust", error=str(e))
            return []
    
    def _clean_monetary_value_simple(self, value: str) -> str:
        """
        Limpeza simples de valor monetário
        """
        if not value:
            return "0,00"
        
        # Remover R$ e espaços
        cleaned = value.replace('R$', '').strip()
        
        # Se já está no formato brasileiro, retornar
        if re.match(r'^[0-9.,]+$', cleaned):
            return cleaned
        
        return "0,00"
    
    async def _close_modal_robust(self):
        """
        Fecha o modal de detalhes usando múltiplas estratégias
        """
        try:
            # Estratégia 1: Botão X específico da documentação  
            close_selectors = [
                "button:has(svg[viewBox='0 0 32 32'])",  # SVG X da documentação
                "button[class*='bg-white']:has(svg)",  # Botão branco com SVG
                "[role='dialog'] button:has(svg)",  # Qualquer botão com SVG no modal
                "button[aria-label*='lose'], button[aria-label*='fechar']",  # Aria labels
                "button:has-text('×')",  # Símbolo X
                ".modal-close, [data-close]"  # Classes genéricas
            ]
            
            modal_fechado = False
            for selector in close_selectors:
                try:
                    close_button = await self.page.query_selector(selector)
                    if close_button:
                        await close_button.click()
                        logger.info("modal_fechado_com_selector", selector=selector)
                        await asyncio.sleep(1)
                        modal_fechado = True
                        break
                except Exception as e:
                    logger.debug("erro_fechar_modal_selector", selector=selector, error=str(e))
                    continue
            
            # Estratégia 2: Usar ESC se nenhum botão funcionou
            if not modal_fechado:
                await self.page.keyboard.press('Escape')
                logger.info("modal_fechado_via_escape")
                await asyncio.sleep(1)
            
        except Exception as e:
            logger.warning("erro_fechar_modal_robust", error=str(e))
    
    async def _close_modal_fast(self):
        """
        Fecha o modal de forma otimizada - baseado no seletor que funcionou nos logs
        """
        try:
            logger.info("fechando_modal_fast")
            
            # Usar o seletor que funcionou nos logs primeiro
            close_selectors = [
                "[role='dialog'] button:has(svg)",  # Funcionou nos logs
                "button:has(svg[viewBox='0 0 32 32'])",  # SVG X da documentação
                "button[class*='bg-white']:has(svg)"  # Botão branco com SVG
            ]
            
            modal_fechado = False
            for selector in close_selectors:
                try:
                    close_button = await self.page.query_selector(selector)
                    if close_button and await close_button.is_visible():
                        await close_button.click()
                        logger.info("modal_fechado_fast", selector=selector)
                        await asyncio.sleep(0.2)  # Tempo mínimo reduzido
                        modal_fechado = True
                        break
                except Exception as e:
                    logger.debug("erro_selector_fast", selector=selector, error=str(e))
                    continue
            
            # Se não funcionou, usar ESC imediatamente
            if not modal_fechado:
                logger.info("usando_escape_direto")
                await self.page.keyboard.press('Escape')
                await asyncio.sleep(0.2)  # Tempo reduzido
                logger.info("modal_fechado_via_escape_fast")
            
        except Exception as e:
            logger.warning("erro_fechar_modal_fast", error=str(e))
            # Fallback final - ESC
            try:
                await self.page.keyboard.press('Escape')
            except:
                pass
    
    async def _extract_modal_details_fast(self) -> Dict[str, Any]:
        """🔧 NOVO: Extração rápida de dados do modal com timeout agressivo"""
        try:
            logger.info("extraindo_modal_details_fast")
            
            # Obter HTML completo da página com timeout
            page_html = await asyncio.wait_for(self.page.content(), timeout=5)
            
            import re
            
            # Verificar se modal existe no HTML
            if 'role="dialog"' not in page_html and 'relative z-10' not in page_html:
                logger.warning("modal_nao_encontrado_fast")
                return {"endereco": "", "telefone": "", "protestos": []}
            
            logger.info("modal_encontrado_extraindo_fast")
            
            # Extrair endereço usando regex (com timeout implícito via processamento rápido)
            endereco = ""
            try:
                endereco_match = re.search(r'Endereço:\s*</span>([^<]+)', page_html, re.IGNORECASE)
                if endereco_match:
                    endereco = endereco_match.group(1).strip()
            except Exception:
                pass
            
            # Extrair telefone usando regex
            telefone = ""
            try:
                telefone_match = re.search(r'Telefone:\s*</span>([^<]+)', page_html, re.IGNORECASE)
                if telefone_match:
                    telefone = telefone_match.group(1).strip()
            except Exception:
                pass
            
            # Extrair valores monetários - estratégia otimizada
            protestos = []
            
            try:
                # Buscar valores R$ com regex simples
                valor_matches = re.findall(r'R\$\s*([0-9.,]+)', page_html)
                
                for valor_match in valor_matches[:10]:  # Limite 10 valores para performance
                    try:
                        # Validação rápida
                        valor_numerico = re.sub(r'[^\d]', '', valor_match)
                        if len(valor_numerico) >= 3:  # Pelo menos 3 dígitos
                            valor_float = float(valor_match.replace('.', '').replace(',', '.'))
                            if valor_float > 1:  # Maior que R$ 1,00
                                protesto = ProtestoDetalhado(
                                    cpfCnpj=self.current_cnpj or "",
                                    data=None,
                                    dataProtesto=None, 
                                    dataVencimento="",
                                    autorizacaoCancelamento=False,
                                    custasCancelamento="",
                                    valor=f"R${valor_match}"
                                )
                                protestos.append(protesto)
                    except:
                        continue
                        
            except Exception as e:
                logger.warning("erro_extrair_valores_fast", error=str(e))
            
            resultado = {
                "endereco": endereco,
                "telefone": telefone,  
                "protestos": protestos
            }
            
            logger.info("modal_extraido_fast", 
                       endereco_ok=bool(endereco),
                       telefone_ok=bool(telefone),
                       protestos_count=len(protestos))
            
            return resultado
            
        except Exception as e:
            logger.error("erro_extract_modal_fast", error=str(e))
            return {"endereco": "", "telefone": "", "protestos": []}

    async def _emergency_close_modal(self):
        """🆘 NOVO: Fechamento de emergência do modal para evitar travamento"""
        try:
            logger.info("tentativa_emergency_close_modal")
            
            # Estratégias de fechamento em ordem de prioridade
            close_strategies = [
                # Estratégia 1: Botão X específico
                "button:has(svg[viewBox='0 0 32 32'])",
                
                # Estratégia 2: Qualquer botão com SVG no modal
                "[role='dialog'] button:has(svg)",
                
                # Estratégia 3: Pressionar ESC
                None  # Indica pressionar ESC
            ]
            
            for i, selector in enumerate(close_strategies):
                try:
                    if selector:
                        # Tentar clicar no botão
                        close_button = await asyncio.wait_for(
                            self.page.query_selector(selector),
                            timeout=2
                        )
                        
                        if close_button:
                            await asyncio.wait_for(close_button.click(), timeout=2)
                            logger.info("modal_fechado_emergency", strategy=i+1, selector=selector[:30])
                            return
                    else:
                        # Pressionar ESC
                        await asyncio.wait_for(self.page.keyboard.press('Escape'), timeout=2)
                        logger.info("modal_fechado_emergency_esc")
                        return
                        
                except Exception:
                    continue
            
            logger.warning("emergency_close_todas_estrategias_falharam")
            
        except Exception as e:
            logger.error("erro_emergency_close_modal", error=str(e))

    async def _extract_modal_details_from_html(self) -> Dict[str, Any]:
        """
        Extrai detalhes do modal diretamente do HTML da página
        usando BeautifulSoup para parsing preciso
        """
        try:
            logger.info("extraindo_modal_details_via_html")
            
            # Obter HTML completo da página
            page_html = await self.page.content()
            
            # Usar regex para parsing direto do HTML (mais simples e rápido)
            import re
            
            # Verificar se modal existe no HTML
            if 'role="dialog"' not in page_html and 'relative z-10' not in page_html:
                logger.warning("modal_nao_encontrado_no_html")
                return {"endereco": "", "telefone": "", "protestos": []}
            
            logger.info("modal_encontrado_no_html_extraindo_dados")
            
            # Extrair endereço usando regex
            endereco = ""
            endereco_match = re.search(r'Endereço:\s*</span>([^<]+)', page_html)
            if endereco_match:
                endereco = endereco_match.group(1).strip()
            
            # Extrair telefone usando regex
            telefone = ""
            telefone_match = re.search(r'Telefone:\s*</span>([^<]+)', page_html)
            if telefone_match:
                telefone = telefone_match.group(1).strip()
            
            # Extrair valores monetários - múltiplas estratégias
            protestos = []
            
            # Estratégia 1: Buscar valores diretos no HTML
            valor_matches = re.findall(r'R\$\s*([0-9.,]+)', page_html)
            
            for valor_match in valor_matches:
                try:
                    # Validar valor (mínimo 3 dígitos, valor > 1 real)
                    valor_numerico = valor_match.replace(',', '').replace('.', '')
                    if len(valor_numerico) >= 3:
                        # Converter para float para validação (formato brasileiro)
                        valor_float = float(valor_match.replace('.', '').replace(',', '.'))
                        if valor_float > 1:  # Maior que R$ 1,00
                            protesto = ProtestoDetalhado(
                                cpfCnpj=self.current_cnpj or "",
                                data=None,
                                dataProtesto=None,
                                dataVencimento="",
                                autorizacaoCancelamento=False,
                                custasCancelamento="",
                                valor=self._clean_monetary_value_simple(f"R${valor_match}")
                            )
                            protestos.append(protesto)
                            logger.info("protesto_extraido_via_html_regex", valor=f"R${valor_match}")
                except (ValueError, AttributeError):
                    continue
            
            # MANTER TODOS OS PROTESTOS - valores iguais são legítimos
            logger.info("modal_extraido_via_html",
                       endereco_ok=bool(endereco),
                       telefone_ok=bool(telefone),
                       protestos_total=len(protestos),
                       protestos_mantidos=len(protestos))
            
            return {
                "endereco": endereco,
                "telefone": telefone,
                "protestos": protestos
            }
            
        except Exception as e:
            logger.error("erro_extrair_modal_via_html", error=str(e))
            return {"endereco": "", "telefone": "", "protestos": []}
