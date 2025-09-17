"""
Extractors CSS específicos para elementos do Resolve CenProt
"""

import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger(__name__)

class CSSExtractors:
    """Extractors CSS customizados para elementos específicos do site"""
    
    @staticmethod
    def extract_consultation_status(html_content: str) -> Dict[str, Any]:
        """
        Extrai status da consulta (protestos encontrados ou não)
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Procurar indicadores de status
        status_selectors = [
            '.text-\\[\\#4F4F4F\\].text-xl.font-semibold.w-full',
            '.result-status',
            'h1:contains("Protestos")',
            'div:contains("Protestos encontrados")',
            'div:contains("Protestos não encontrados")'
        ]
        
        status_text = ""
        for selector in status_selectors:
            try:
                if ':contains(' in selector:
                    # BeautifulSoup não suporta :contains, usar find com texto
                    text_search = selector.split(':contains(')[1].split(')')[0].strip('"')
                    element = soup.find(text=re.compile(text_search, re.I))
                    if element:
                        status_text = element.get_text(strip=True)
                        break
                else:
                    # Selector CSS normal (limitado no BeautifulSoup)
                    element = soup.select_one(selector.replace('\\[', '[').replace('\\]', ']'))
                    if element:
                        status_text = element.get_text(strip=True)
                        break
            except Exception as e:
                logger.debug("erro_selector_status", selector=selector, error=str(e))
                continue
        
        has_protests = 'encontrados' in status_text.lower()
        
        return {
            "status_text": status_text,
            "has_protests": has_protests,
            "extracted_by": "css_extractor"
        }
    
    @staticmethod
    def extract_estados_cartorios(html_content: str) -> List[Dict[str, Any]]:
        """
        Extrai informações de estados e cartórios da página de resultados
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        estados = []
        
        # Procurar seções de estados
        state_sections = soup.find_all(['div', 'section'], class_=re.compile(r'mt-6|state-section'))
        
        for section in state_sections:
            # Procurar título do estado
            state_title = section.find(['h1', 'h2', 'h3'])
            if not state_title:
                continue
                
            state_name = CSSExtractors._extract_state_name(state_title.get_text(strip=True))
            if not state_name:
                continue
            
            # Procurar tabela de cartórios nesta seção
            table = section.find('table') or section.find_next('table')
            if not table:
                continue
            
            cartorios = CSSExtractors._extract_cartorios_from_table(table)
            
            if cartorios:
                estados.append({
                    "estado_nome": state_name,
                    "cartorios": cartorios
                })
        
        logger.info("estados_extraidos", count=len(estados))
        return estados
    
    @staticmethod
    def _extract_state_name(title_text: str) -> Optional[str]:
        """Extrai nome do estado do título"""
        # Patterns comuns: "Protestos no Estado de BA", "BA", "BAHIA"
        patterns = [
            r'Estado de ([A-Z]{2})',
            r'([A-Z]{2})(?:\s|$)',
            r'([A-Z]{2,})'  # Estados por extenso
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title_text.upper())
            if match:
                state = match.group(1)
                # Converter estados por extenso para sigla se necessário
                return CSSExtractors._normalize_state_name(state)
        
        return None
    
    @staticmethod
    def _normalize_state_name(state: str) -> str:
        """Normaliza nome do estado para sigla padrão"""
        state_map = {
            'ACRE': 'AC', 'ALAGOAS': 'AL', 'AMAPÁ': 'AP', 'AMAZONAS': 'AM',
            'BAHIA': 'BA', 'CEARÁ': 'CE', 'DISTRITO FEDERAL': 'DF',
            'ESPÍRITO SANTO': 'ES', 'GOIÁS': 'GO', 'MARANHÃO': 'MA',
            'MATO GROSSO': 'MT', 'MATO GROSSO DO SUL': 'MS', 'MINAS GERAIS': 'MG',
            'PARÁ': 'PA', 'PARAÍBA': 'PB', 'PARANÁ': 'PR', 'PERNAMBUCO': 'PE',
            'PIAUÍ': 'PI', 'RIO DE JANEIRO': 'RJ', 'RIO GRANDE DO NORTE': 'RN',
            'RIO GRANDE DO SUL': 'RS', 'RONDÔNIA': 'RO', 'RORAIMA': 'RR',
            'SANTA CATARINA': 'SC', 'SÃO PAULO': 'SP', 'SERGIPE': 'SE',
            'TOCANTINS': 'TO'
        }
        
        return state_map.get(state.upper(), state[:2].upper())
    
    @staticmethod
    def _extract_cartorios_from_table(table) -> List[Dict[str, Any]]:
        """Extrai dados dos cartórios da tabela"""
        cartorios = []
        
        rows = table.find_all('tr')[1:]  # Pular cabeçalho
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 3:
                nome_cartorio = cells[0].get_text(strip=True)
                cidade = cells[1].get_text(strip=True)
                quantidade_titulos = cells[2].get_text(strip=True)
                
                # Limpar e validar quantidade
                qtde_clean = re.sub(r'[^\d]', '', quantidade_titulos)
                qtde_int = int(qtde_clean) if qtde_clean.isdigit() else 0
                
                if nome_cartorio and cidade:
                    cartorios.append({
                        "nome_cartorio": nome_cartorio,
                        "cidade": cidade.upper(),
                        "quantidade_titulos": str(qtde_int)
                    })
        
        return cartorios
    
    @staticmethod
    def extract_modal_cartorio_details(modal_html: str) -> Dict[str, Any]:
        """
        Extrai detalhes específicos do modal do cartório
        """
        soup = BeautifulSoup(modal_html, 'html.parser')
        
        details = {
            "endereco": "",
            "telefone": "",
            "titulos_detalhados": []
        }
        
        # Extrair endereço
        endereco_patterns = [
            {'label': 'Endereço:', 'next_p': True},
            {'label': 'Endereço', 'next_p': True},
            {'class': 'endereco'},
        ]
        
        details["endereco"] = CSSExtractors._extract_field_by_patterns(soup, endereco_patterns)
        
        # Extrair telefone
        telefone_patterns = [
            {'label': 'Telefone:', 'next_p': True},
            {'label': 'Tel:', 'next_p': True},
            {'class': 'telefone'},
        ]
        
        details["telefone"] = CSSExtractors._extract_field_by_patterns(soup, telefone_patterns)
        
        # Extrair títulos detalhados
        titles_container = soup.find('div', class_=re.compile(r'grid.*md.*grid-cols-2'))
        if titles_container:
            title_items = titles_container.find_all('div', class_=re.compile(r'flex.*flex-col'))
            
            for item in title_items:
                titulo_details = CSSExtractors._extract_titulo_details(item)
                if titulo_details:
                    details["titulos_detalhados"].append(titulo_details)
        
        logger.info("modal_extraido", endereco=bool(details["endereco"]), 
                   telefone=bool(details["telefone"]), 
                   titulos_count=len(details["titulos_detalhados"]))
        
        return details
    
    @staticmethod
    def _extract_field_by_patterns(soup, patterns: List[Dict]) -> str:
        """Extrai campo usando vários padrões de busca"""
        for pattern in patterns:
            try:
                if 'label' in pattern:
                    # Buscar por label
                    label_elem = soup.find(text=re.compile(pattern['label'], re.I))
                    if label_elem:
                        parent = label_elem.find_parent()
                        if pattern.get('next_p'):
                            next_p = parent.find_next('p') if parent else None
                            if next_p:
                                return next_p.get_text(strip=True)
                        else:
                            return parent.get_text(strip=True) if parent else ""
                
                elif 'class' in pattern:
                    # Buscar por classe CSS
                    elem = soup.find(class_=re.compile(pattern['class'], re.I))
                    if elem:
                        return elem.get_text(strip=True)
            
            except Exception as e:
                logger.debug("erro_pattern_field", pattern=pattern, error=str(e))
                continue
        
        return ""
    
    @staticmethod
    def _extract_titulo_details(item_soup) -> Optional[Dict[str, Any]]:
        """Extrai detalhes de um título específico"""
        titulo = {}
        
        # Campos para extrair
        fields = {
            'codigo': ['Código:', 'Cod:'],
            'documento': ['Documento:', 'Doc:', 'CPF/CNPJ:'],
            'valor_titulo': ['Valor:', 'R$'],
            'data_protesto': ['Data do Protesto:', 'Data Protesto:'],
            'data_vencimento': ['Vencimento:', 'Data Venc:'],
            'custas_cancelamento': ['Custas:', 'Custo Cancel:']
        }
        
        for field_name, labels in fields.items():
            value = CSSExtractors._extract_field_from_item(item_soup, labels)
            titulo[field_name] = value
        
        # Verificar se pelo menos valor foi extraído
        if titulo.get('valor_titulo'):
            return titulo
        
        return None
    
    @staticmethod
    def _extract_field_from_item(item_soup, labels: List[str]) -> str:
        """Extrai um campo específico de um item de título"""
        for label in labels:
            try:
                # Procurar texto do label
                label_elem = item_soup.find(text=re.compile(label, re.I))
                if label_elem:
                    parent = label_elem.find_parent()
                    if parent:
                        # Tentar próximo elemento
                        next_elem = parent.find_next(['p', 'span', 'div'])
                        if next_elem and next_elem.get_text(strip=True):
                            return next_elem.get_text(strip=True)
                        
                        # Ou dentro do mesmo parent
                        text_after_label = parent.get_text().split(label, 1)
                        if len(text_after_label) > 1:
                            return text_after_label[1].strip()
            
            except Exception as e:
                logger.debug("erro_field_extraction", label=label, error=str(e))
                continue
        
        return ""

class ValidationUtils:
    """Utilitários para validação de dados extraídos"""
    
    @staticmethod
    def validate_cnpj_format(cnpj: str) -> bool:
        """Valida formato básico de CNPJ"""
        if not cnpj:
            return False
        digits = re.sub(r'[^\d]', '', cnpj)
        return len(digits) == 14
    
    @staticmethod
    def validate_monetary_value(value: str) -> bool:
        """Valida formato de valor monetário"""
        if not value:
            return False
        # Aceita: 1.234,56 | 1234,56 | 1234.56
        pattern = r'^\d{1,3}(\.\d{3})*,\d{2}$|^\d+[,\.]\d{2}$'
        return bool(re.match(pattern, value.strip()))
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normaliza número de telefone"""
        if not phone:
            return ""
        digits = re.sub(r'[^\d]', '', phone)
        return digits
    
    @staticmethod
    def normalize_monetary_value(value: str) -> str:
        """Normaliza valor monetário para formato padrão"""
        if not value:
            return "0,00"
        
        # Remove símbolos e espaços
        clean_value = re.sub(r'[R$\s]', '', value)
        
        # Se tem vírgula e ponto, assume formato brasileiro
        if ',' in clean_value and '.' in clean_value:
            # 1.234.567,89 -> 1234567,89
            clean_value = clean_value.replace('.', '')
        elif '.' in clean_value and not ',' in clean_value:
            # Se só tem ponto, pode ser separador decimal americano
            parts = clean_value.split('.')
            if len(parts) == 2 and len(parts[1]) == 2:
                # 1234.56 -> 1234,56
                clean_value = clean_value.replace('.', ',')
        
        return clean_value
