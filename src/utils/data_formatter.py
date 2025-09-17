"""
Utilitários para formatação e normalização de dados extraídos
"""

import re
from typing import Optional, Any, Dict
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)

class DataFormatter:
    """Formatador e normalizador de dados para o sistema RPA"""
    
    @staticmethod
    def normalize_monetary_value(value: str) -> str:
        """
        Normaliza valores monetários para formato padrão brasileiro
        
        Args:
            value: Valor em string (ex: "R$ 1.234,56", "1234.56", etc.)
            
        Returns:
            str: Valor normalizado no formato "1234,56"
        """
        if not value or not isinstance(value, str):
            return "0,00"
        
        # Remove símbolos e espaços
        clean_value = re.sub(r'[R$\s\xa0]', '', value.strip())
        
        if not clean_value:
            return "0,00"
        
        # Se tem vírgula e ponto, assume formato brasileiro (1.234.567,89)
        if ',' in clean_value and '.' in clean_value:
            # Remove pontos de milhares e mantém vírgula decimal
            clean_value = re.sub(r'\.(?=\d{3})', '', clean_value)
        elif '.' in clean_value and not ',' in clean_value:
            # Se só tem ponto, pode ser separador decimal americano
            parts = clean_value.split('.')
            if len(parts) == 2 and len(parts[1]) == 2:
                # 1234.56 -> 1234,56
                clean_value = clean_value.replace('.', ',')
            elif len(parts) > 2:
                # 1.234.567 -> 1234567,00
                clean_value = ''.join(parts[:-1]) + ',' + parts[-1] if len(parts[-1]) <= 2 else ''.join(parts) + ',00'
        
        # Garantir que tem casa decimal
        if ',' not in clean_value:
            clean_value += ',00'
        else:
            # Garantir 2 casas decimais
            parts = clean_value.split(',')
            if len(parts[1]) == 1:
                clean_value += '0'
            elif len(parts[1]) > 2:
                clean_value = parts[0] + ',' + parts[1][:2]
        
        # Validar formato final
        if re.match(r'^\d+,\d{2}$', clean_value):
            return clean_value
        
        logger.warning("valor_monetario_nao_normalizavel", original=value, result=clean_value)
        return "0,00"
    
    @staticmethod
    def normalize_cnpj(cnpj: str) -> str:
        """
        Normaliza CNPJ removendo formatação
        
        Args:
            cnpj: CNPJ com ou sem formatação
            
        Returns:
            str: CNPJ apenas com dígitos
        """
        if not cnpj:
            return ""
        
        # Remove tudo que não é dígito
        digits_only = re.sub(r'[^\d]', '', cnpj)
        return digits_only
    
    @staticmethod
    def format_cnpj(cnpj: str) -> str:
        """
        Formata CNPJ no padrão XX.XXX.XXX/XXXX-XX
        
        Args:
            cnpj: CNPJ apenas com dígitos
            
        Returns:
            str: CNPJ formatado
        """
        digits = DataFormatter.normalize_cnpj(cnpj)
        
        if len(digits) != 14:
            return cnpj  # Retorna original se não tem 14 dígitos
        
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """
        Normaliza telefone removendo formatação
        
        Args:
            phone: Telefone com ou sem formatação
            
        Returns:
            str: Telefone apenas com dígitos
        """
        if not phone:
            return ""
        
        return re.sub(r'[^\d]', '', phone)
    
    @staticmethod
    def format_phone(phone: str) -> str:
        """
        Formata telefone no padrão brasileiro
        
        Args:
            phone: Telefone apenas com dígitos
            
        Returns:
            str: Telefone formatado
        """
        digits = DataFormatter.normalize_phone(phone)
        
        if len(digits) == 11:  # Celular: (11) 99999-9999
            return f"({digits[:2]}) {digits[2:7]}-{digits[7:11]}"
        elif len(digits) == 10:  # Fixo: (11) 9999-9999
            return f"({digits[:2]}) {digits[2:6]}-{digits[6:10]}"
        elif len(digits) >= 8:  # Sem DDD
            return f"{digits[:-4]}-{digits[-4:]}"
        
        return phone  # Retorna original se não conseguir formatar
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        Limpa texto removendo espaços extras e caracteres especiais
        
        Args:
            text: Texto para limpar
            
        Returns:
            str: Texto limpo
        """
        if not text:
            return ""
        
        # Remove quebras de linha e espaços extras
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Remove caracteres de controle
        cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
        
        return cleaned
    
    @staticmethod
    def extract_numeric_value(text: str) -> Optional[float]:
        """
        Extrai valor numérico de um texto
        
        Args:
            text: Texto contendo número
            
        Returns:
            Optional[float]: Valor extraído ou None
        """
        if not text:
            return None
        
        # Remove tudo exceto dígitos, vírgula e ponto
        clean_text = re.sub(r'[^\d,.]', '', text)
        
        if not clean_text:
            return None
        
        try:
            # Se tem vírgula, assume formato brasileiro
            if ',' in clean_text:
                clean_text = clean_text.replace('.', '').replace(',', '.')
            
            return float(clean_text)
        except ValueError:
            return None
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Valida formato de email
        
        Args:
            email: Email para validar
            
        Returns:
            bool: True se válido
        """
        if not email:
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def normalize_address(address: str) -> str:
        """
        Normaliza endereço removendo formatação inconsistente
        
        Args:
            address: Endereço para normalizar
            
        Returns:
            str: Endereço normalizado
        """
        if not address:
            return ""
        
        # Limpar texto básico
        normalized = DataFormatter.clean_text(address)
        
        # Normalizar abreviações comuns
        replacements = {
            r'\bR\.\s*': 'RUA ',
            r'\bAV\.\s*': 'AVENIDA ',
            r'\bAL\.\s*': 'ALAMEDA ',
            r'\bPÇ\.\s*': 'PRAÇA ',
            r'\bTRAV\.\s*': 'TRAVESSA ',
            r'\bROD\.\s*': 'RODOVIA ',
            r'\bEST\.\s*': 'ESTRADA ',
            r'\bLT\.\s*': 'LOTE ',
            r'\bQD\.\s*': 'QUADRA ',
            r'\bBL\.\s*': 'BLOCO ',
            r'\bAPT\.\s*': 'APARTAMENTO ',
            r'\bCJ\.\s*': 'CONJUNTO ',
        }
        
        for pattern, replacement in replacements.items():
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
        return normalized.strip()
    
    @staticmethod
    def parse_date(date_str: str) -> Optional[str]:
        """
        Tenta parsear data de diferentes formatos para formato ISO
        
        Args:
            date_str: String de data
            
        Returns:
            Optional[str]: Data no formato YYYY-MM-DD ou None
        """
        if not date_str:
            return None
        
        # Patterns de data comuns no Brasil
        patterns = [
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', lambda m: f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"),
            (r'(\d{1,2})-(\d{1,2})-(\d{4})', lambda m: f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"),
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
        ]
        
        for pattern, formatter in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    return formatter(match)
                except:
                    continue
        
        return None
    
    @staticmethod
    def format_data_for_json(data: Any) -> Any:
        """
        Formata dados para serialização JSON - agora com suporte para datetime
        
        Args:
            data: Dados para formatar
            
        Returns:
            Any: Dados formatados
        """
        if isinstance(data, dict):
            return {key: DataFormatter.format_data_for_json(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [DataFormatter.format_data_for_json(item) for item in data]
        elif isinstance(data, datetime):
            # Formatar datetime para string ISO com timezone local
            return data.strftime("%Y-%m-%d %H:%M:%S.%f")
        elif isinstance(data, str):
            return DataFormatter.clean_text(data)
        else:
            return data
    
    @staticmethod
    def create_safe_filename(filename: str) -> str:
        """
        Cria nome de arquivo seguro removendo caracteres inválidos
        
        Args:
            filename: Nome do arquivo
            
        Returns:
            str: Nome seguro
        """
        if not filename:
            return "unnamed"
        
        # Remove caracteres inválidos para nomes de arquivo
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Remove espaços no início/fim e múltiplos espaços
        safe_name = re.sub(r'\s+', '_', safe_name.strip())
        
        # Limita tamanho
        if len(safe_name) > 100:
            safe_name = safe_name[:100]
        
        return safe_name or "unnamed"
