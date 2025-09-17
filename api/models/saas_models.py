"""
Modelos de dados para o SaaS Valida
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum

class SubscriptionPlan(str, Enum):
    """Planos de assinatura disponíveis"""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class SubscriptionStatus(str, Enum):
    """Status da assinatura"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"

class UserCreate(BaseModel):
    """Modelo para criação de usuário"""
    email: EmailStr
    password: str
    full_name: str
    company: Optional[str] = None

class UserResponse(BaseModel):
    """Modelo de resposta do usuário"""
    id: str
    email: str
    full_name: str
    company: Optional[str] = None
    created_at: datetime
    subscription_plan: SubscriptionPlan
    subscription_status: SubscriptionStatus

class APIKeyCreate(BaseModel):
    """Modelo para criação de API key"""
    name: str
    description: Optional[str] = None

class APIKeyResponse(BaseModel):
    """Modelo de resposta da API key"""
    id: str
    name: str
    description: Optional[str] = None
    key: str  # Só retornado na criação
    key_hash: str
    user_id: str
    created_at: datetime
    last_used: Optional[datetime] = None
    is_active: bool

class APIKeyList(BaseModel):
    """Modelo para listagem de API keys"""
    id: str
    name: str
    description: Optional[str] = None
    key: Optional[str] = None  # Chave original (só disponível na listagem)
    key_hash: str
    user_id: str
    created_at: datetime
    last_used: Optional[datetime] = None
    is_active: bool

class SubscriptionResponse(BaseModel):
    """Modelo de resposta da assinatura"""
    id: str
    user_id: str
    plan: SubscriptionPlan
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    trial_end: Optional[datetime] = None

class UsageStats(BaseModel):
    """Modelo para estatísticas de uso"""
    total_requests: int
    requests_this_month: int
    requests_today: int
    plan_limit: Optional[int] = None
    remaining_requests: Optional[int] = None

class DashboardStats(BaseModel):
    """Modelo para estatísticas do dashboard"""
    user: UserResponse
    subscription: SubscriptionResponse
    usage: UsageStats
    api_keys_count: int
    recent_requests: List[dict]

class InvoiceResponse(BaseModel):
    """Modelo de resposta da fatura"""
    id: str
    user_id: str
    amount: int  # Em centavos
    currency: str
    status: str
    created_at: datetime
    paid_at: Optional[datetime] = None
    invoice_url: Optional[str] = None

class ConsultationRequest(BaseModel):
    """Modelo para requisição de consulta expandida"""
    cnpj: str
    api_key: Optional[str] = None  # Para compatibilidade com API existente
    
    # Parâmetros de consulta (todos opcionais com defaults para backward compatibility)
    protestos: bool = True          # Manter compatibilidade - sempre true por default
    simples: bool = False           # CNPJa - Simples Nacional/MEI
    registrations: Optional[str] = None  # CNPJa - 'BR' para todos os estados
    geocoding: bool = False         # CNPJa - Geolocalização
    suframa: bool = False          # CNPJa - SUFRAMA
    strategy: str = "CACHE_IF_FRESH" # CNPJa - Estratégia de cache
    
    # Parâmetros de extração (controle fino do que extrair dos dados CNPJa)
    extract_basic: bool = True      # Dados básicos da empresa
    extract_address: bool = True    # Endereço
    extract_contact: bool = True    # Contatos
    extract_activities: bool = True # CNAEs
    extract_partners: bool = True   # Sócios

class ConsultationResponse(BaseModel):
    """Modelo de resposta da consulta expandida"""
    success: bool
    cnpj: str
    timestamp: datetime
    user_id: Optional[str] = None
    api_key_id: Optional[str] = None
    
    # Dados segmentados por tipo
    protestos: Optional[dict] = None      # Dados de protestos (estrutura atual)
    dados_receita: Optional[dict] = None  # Dados da Receita Federal via CNPJa
    error: Optional[str] = None
    
    # Metadados da consulta
    sources_consulted: List[str] = []     # ['protestos', 'cnpja']
    cache_used: bool = False              # Se usou cache CNPJa
    response_time_ms: Optional[int] = None
    
    # Estatísticas (para protestos)
    total_protests: Optional[int] = None
    has_protests: Optional[bool] = None
    
    # Campo data mantido para backward compatibility
    data: Optional[dict] = None

class ErrorResponse(BaseModel):
    """Modelo para respostas de erro"""
    error: str
    message: str
    details: Optional[dict] = None
