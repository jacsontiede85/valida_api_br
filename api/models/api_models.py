"""
Modelos de Request/Response da API Resolve CenProt
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime
import re


class CNPJRequest(BaseModel):
    """Request para consulta de CNPJ"""
    cnpj: str = Field(..., description="CNPJ no formato XX.XXX.XXX/XXXX-XX ou apenas números")
    
    @validator('cnpj')
    def validate_cnpj(cls, v):
        # Remove formatação
        cnpj_numbers = re.sub(r'[^0-9]', '', v)
        
        if len(cnpj_numbers) != 14:
            raise ValueError('CNPJ deve conter 14 dígitos')
            
        # Formatar CNPJ
        return f"{cnpj_numbers[:2]}.{cnpj_numbers[2:5]}.{cnpj_numbers[5:8]}/{cnpj_numbers[8:12]}-{cnpj_numbers[12:]}"


class CNPJResponse(BaseModel):
    """Response da consulta de CNPJ"""
    success: bool = Field(description="Se a consulta foi bem-sucedida")
    existe_protestos: Optional[bool] = Field(default=None, description="Se foram encontrados protestos para o CNPJ")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Dados da consulta (formato atual)")
    message: str = Field(description="Mensagem de status")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp da consulta")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {}


class StatusResponse(BaseModel):
    """Response do status do serviço"""
    service: str = Field(default="Resolve CenProt API")
    status: str = Field(description="Status do serviço")
    version: str = Field(default="1.0.0")
    session_active: bool = Field(description="Se a sessão do navegador está ativa")
    last_login: Optional[datetime] = Field(default=None, description="Último login realizado")
    timestamp: datetime = Field(default_factory=datetime.now)


class SessionStatusResponse(BaseModel):
    """Response do status da sessão"""
    active: bool = Field(description="Se a sessão está ativa")
    logged_in: bool = Field(description="Se está logado no resolve.cenprot.org.br")
    last_activity: Optional[datetime] = Field(default=None, description="Última atividade")
    login_cnpj: Optional[str] = Field(default=None, description="CNPJ usado no login")


class PoolStatusResponse(BaseModel):
    """Response do status do pool de páginas"""
    pool_size: int = Field(description="Tamanho total do pool")
    available_pages: int = Field(description="Páginas disponíveis no pool")
    active_pages: int = Field(description="Páginas atualmente em uso")
    active_page_ids: list = Field(description="IDs das páginas ativas")
    concurrent_capacity: int = Field(description="Capacidade de requisições simultâneas")
    current_load: int = Field(description="Carga atual do sistema")
