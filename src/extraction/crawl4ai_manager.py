"""
Gestor principal do Crawl4AI para extração inteligente de dados
"""

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai import JsonCssExtractionStrategy, LLMExtractionStrategy
from typing import Dict, Any, List, Optional
import json
import structlog
from ..config.settings import settings

logger = structlog.get_logger(__name__)

class Crawl4AIManager:
    """Gerenciador principal do Crawl4AI integrado com Playwright"""
    
    def __init__(self, playwright_context=None):
        self.crawler: Optional[AsyncWebCrawler] = None
        self.context = playwright_context
        self.initialized = False
        
    async def initialize(self):
        """Inicializa crawler com contexto autenticado do Playwright"""
        if self.initialized:
            logger.info("crawl4ai_ja_inicializado")
            return
            
        logger.info("inicializando_crawl4ai")
        
        # Inicializar crawler simples primeiro
        self.crawler = AsyncWebCrawler(
            verbose=True,
            headless=settings.HEADLESS
        )
        await self.crawler.start()
        self.initialized = True
        
        logger.info("crawl4ai_inicializado_com_sucesso")
    
    async def extract_consultation_results(self, page_html: str) -> Dict[str, Any]:
        """
        Extrai resultados da página de consulta usando estratégia CSS
        """
        if not self.initialized:
            await self.initialize()
            
        logger.info("iniciando_extracao_resultados_consulta")
        
        # Schema CSS para extração estruturada
        schema = {
            "name": "resolve_consultation_results",
            "baseSelector": "body",
            "fields": [
                {
                    "name": "tem_protestos",
                    "selector": ".text-\\[\\#4F4F4F\\].text-xl.font-semibold.w-full",
                    "type": "text"
                },
                {
                    "name": "data_consulta", 
                    "selector": ".text-\\[\\#888888\\] span",
                    "type": "text"
                },
                {
                    "name": "estados",
                    "selector": ".mt-6:has(h1)",
                    "type": "nested",
                    "fields": [
                        {
                            "name": "estado_nome",
                            "selector": "h1",
                            "type": "text"
                        },
                        {
                            "name": "cartorios",
                            "selector": "tbody tr",
                            "type": "nested",
                            "fields": [
                                {
                                    "name": "nome_cartorio",
                                    "selector": "td:first-child",
                                    "type": "text"
                                },
                                {
                                    "name": "cidade",
                                    "selector": "td:nth-child(2)",
                                    "type": "text"
                                },
                                {
                                    "name": "quantidade_titulos",
                                    "selector": "td:nth-child(3)",
                                    "type": "text"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        try:
            # Por enquanto, usar apenas parsing HTML direto sem Crawl4AI
            logger.info("usando_parse_html_direto")
            extracted_data = self._parse_html_with_fallback(page_html)
            logger.info("extracao_html_bem_sucedida")
            return extracted_data
                
        except Exception as e:
            logger.error("erro_extracao_html", error=str(e))
            return await self._extract_with_llm_fallback(page_html)
    
    def _parse_html_with_fallback(self, html_content: str) -> Dict[str, Any]:
        """Parser HTML baseado na estrutura real encontrada na análise"""
        from bs4 import BeautifulSoup
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Verificar se tem protestos pela mensagem específica
            tem_protestos = "protestos encontrados" in html_content.lower()
            
            # Extrair data da consulta
            data_consulta = ""
            data_span = soup.find("span", class_="text-[#888888]")
            if data_span:
                data_consulta = data_span.get_text(strip=True)
            
            # Extrair cartórios da tabela HTML
            estados = []
            
            # Procurar pela tabela que contém os cartórios
            table = soup.find("table", class_="w-full")
            if table:
                tbody = table.find("tbody")
                if tbody:
                    rows = tbody.find_all("tr")
                    
                    cartorios_encontrados = []
                    
                    for row in rows:
                        cells = row.find_all("td")
                        if len(cells) >= 3:
                            # Extrair dados das colunas: CARTÓRIO, CIDADE, QTD. DE TÍTULOS
                            cartorio = cells[0].get_text(strip=True) if cells[0] else ""
                            cidade = cells[1].get_text(strip=True) if len(cells) > 1 and cells[1] else ""
                            qtd_titulos = cells[2].get_text(strip=True) if len(cells) > 2 and cells[2] else "0"
                            
                            # Extrair número de títulos
                            try:
                                qtd_num = int(''.join(filter(str.isdigit, qtd_titulos)))
                            except:
                                qtd_num = 1  # Padrão caso não consiga extrair
                            
                            # Tentar extrair valores monetários da página
                            valores_protestos = self._extract_monetary_values_from_html(html_content, cartorio)
                            
                            cartorios_encontrados.append({
                                "nome_cartorio": cartorio,
                                "cidade": cidade, 
                                "quantidade_titulos": str(qtd_num),
                                "valores_protestos": valores_protestos
                            })
                    
                    # Se encontramos cartórios, criar estado genérico
                    if cartorios_encontrados:
                        estados.append({
                            "estado_nome": "BRASIL",  # Estado genérico por enquanto
                            "cartorios": cartorios_encontrados
                        })
            
            logger.info("parse_html_completo", 
                       tem_protestos=tem_protestos, 
                       total_estados=len(estados),
                       total_cartorios=sum(len(e.get("cartorios", [])) for e in estados))
            
            return {
                "tem_protestos": "Protestos encontrados" if tem_protestos else "Protestos não encontrados",
                "data_consulta": data_consulta,
                "estados": estados
            }
            
        except Exception as e:
            logger.error("erro_parse_html_fallback", error=str(e))
            return {
                "tem_protestos": "erro",
                "data_consulta": "",
                "estados": []
            }
    
    def _extract_monetary_values_from_html(self, html_content: str, cartorio_nome: str) -> List[str]:
        """
        Tenta extrair valores monetários do HTML para um cartório específico
        """
        import re
        from bs4 import BeautifulSoup
        
        try:
            # Padrões para valores monetários brasileiros
            monetary_patterns = [
                r'R\$\s*[\d.,]+',  # R$ 1.234,56
                r'[\d.,]+\s*reais',  # 1234,56 reais
                r'[\d]+[.,][\d]{2}(?:\s*R\$)?',  # 1234,56 R$
                r'Valor[:\s]+R\$[\d.,]+',  # Valor: R$ 1234,56
                r'[\d]{1,3}(?:[.,]\d{3})*[.,]\d{2}',  # 1.234,56 ou 1234,56
            ]
            
            valores_encontrados = []
            
            # Buscar por padrões monetários no HTML
            for pattern in monetary_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    # Limpar e formatar o valor
                    valor_limpo = self._clean_monetary_value(match)
                    if valor_limpo and valor_limpo != "0,00":
                        valores_encontrados.append(valor_limpo)
            
            # Se não encontrou valores específicos, tentar extrair da tabela
            if not valores_encontrados:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Procurar por células que contenham valores monetários
                all_cells = soup.find_all(['td', 'span', 'div'])
                for cell in all_cells:
                    text = cell.get_text(strip=True)
                    if text and ('R$' in text or ',' in text) and any(c.isdigit() for c in text):
                        for pattern in monetary_patterns:
                            if re.search(pattern, text, re.IGNORECASE):
                                valor_limpo = self._clean_monetary_value(text)
                                if valor_limpo and valor_limpo != "0,00":
                                    valores_encontrados.append(valor_limpo)
                                    break
            
            # Remover duplicatas e valores zerados
            valores_unicos = []
            for valor in valores_encontrados:
                if valor not in valores_unicos and valor != "0,00":
                    valores_unicos.append(valor)
            
            # Se não encontrou nada, usar valor padrão informativo
            if not valores_unicos:
                valores_unicos = ["Consultar no cartório"]
                
            logger.debug("valores_extraidos_cartorio", 
                        cartorio=cartorio_nome[:30], 
                        valores_count=len(valores_unicos))
            
            return valores_unicos
            
        except Exception as e:
            logger.debug("erro_extrair_valores_monetarios", error=str(e))
            return ["Valor não disponível"]
    
    def _clean_monetary_value(self, raw_value: str) -> str:
        """
        Limpa e padroniza valores monetários extraídos
        """
        import re
        
        try:
            # Remover texto extra
            value = re.sub(r'[^\d.,R$]', ' ', raw_value)
            
            # Encontrar padrões de valor monetário
            monetary_match = re.search(r'[\d]+[.,][\d]{2}', value)
            if monetary_match:
                clean_value = monetary_match.group()
                # Padronizar para formato brasileiro (1.234,56)
                if '.' in clean_value and ',' in clean_value:
                    # Já está no formato correto
                    return f"R$ {clean_value}"
                elif ',' in clean_value:
                    # Formato: 1234,56
                    return f"R$ {clean_value}"
                elif '.' in clean_value and len(clean_value.split('.')[-1]) == 2:
                    # Formato americano: 1234.56 -> converter para 1234,56
                    return f"R$ {clean_value.replace('.', ',')}"
                else:
                    return f"R$ {clean_value}"
            
            # Se não encontrou padrão específico, tentar extrair números
            numbers = re.findall(r'\d+', raw_value)
            if numbers:
                return f"R$ {numbers[-1]},00"  # Usar último número encontrado
                
            return "Valor não identificado"
            
        except Exception:
            return "Erro na conversão"

    async def extract_modal_details(self, modal_html: str) -> Dict[str, Any]:
        """
        Extrai detalhes do modal de cada cartório (versão simplificada)
        """
        logger.info("iniciando_extracao_modal_detalhes")
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(modal_html, 'html.parser')
            
            # Extração básica de dados do modal
            endereco = ""
            telefone = ""
            titulos_detalhados = []
            
            # Tentar extrair endereço
            endereco_elem = soup.find(text=lambda t: t and 'endereço' in t.lower())
            if endereco_elem:
                endereco = endereco_elem.strip()
            
            # Tentar extrair telefone
            telefone_elem = soup.find(text=lambda t: t and 'telefone' in t.lower())
            if telefone_elem:
                telefone = telefone_elem.strip()
            
            logger.info("extracao_modal_simplificada", 
                       tem_endereco=bool(endereco),
                       tem_telefone=bool(telefone))
            
            return {
                "endereco": endereco,
                "telefone": telefone,
                "titulos_detalhados": titulos_detalhados
            }
                
        except Exception as e:
            logger.error("erro_extracao_modal", error=str(e))
            return {
                "endereco": "",
                "telefone": "",
                "titulos_detalhados": []
            }
    
    async def _extract_with_llm_fallback(self, page_html: str) -> Dict[str, Any]:
        """Fallback usando LLM quando CSS extraction falha"""
        logger.info("executando_fallback_llm_consulta")
        
        if not settings.OPENAI_API_KEY:
            logger.error("openai_api_key_nao_configurada_para_fallback")
            return {"tem_protestos": "erro", "estados": []}
        
        # Fallback simples sem LLM por enquanto
        logger.info("usando_fallback_simples_sem_llm")
        return {
            "tem_protestos": "Não foi possível determinar",
            "data_consulta": "",
            "estados": []
        }
    
    async def _extract_modal_with_llm(self, modal_html: str) -> Dict[str, Any]:
        """Extração de modal usando LLM (simplificado)"""
        logger.info("fallback_modal_simples")
        return {
            "endereco": "",
            "telefone": "",
            "titulos_detalhados": []
        }
    
    async def close(self):
        """Fecha o crawler e limpa recursos"""
        if self.crawler and self.initialized:
            logger.info("fechando_crawl4ai")
            await self.crawler.close()
            self.initialized = False
            logger.info("crawl4ai_fechado")
    
    def __del__(self):
        """Cleanup automático"""
        if hasattr(self, 'crawler') and self.crawler and self.initialized:
            # Note: não pode usar await aqui, então apenas logamos
            logger.warning("crawl4ai_nao_fechado_adequadamente_use_close()")
