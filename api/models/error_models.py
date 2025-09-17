"""
Modelos de Erro da API Resolve CenProt
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class APIError(BaseModel):
    """Modelo padrão de erro da API"""
    error: str = Field(description="Tipo do erro")
    message: str = Field(description="Mensagem do erro")
    detail: Optional[Dict[str, Any]] = Field(default=None, description="Detalhes adicionais")
    timestamp: datetime = Field(default_factory=datetime.now)


class ValidationError(APIError):
    """Erro de validação"""
    error: str = "validation_error"


class SessionError(APIError):
    """Erro relacionado à sessão"""
    error: str = "session_error"


class ScrapingError(APIError):
    """Erro durante scraping"""
    error: str = "scraping_error"


class PoolTimeoutError(APIError):
    """Erro de timeout do pool de páginas"""
    error: str = "pool_timeout_error"
