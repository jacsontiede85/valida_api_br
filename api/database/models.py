"""
Modelos de dados para integração com MariaDB (migração de Supabase)
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

class User(BaseModel):
    """Modelo do usuário"""
    id: str
    email: EmailStr
    name: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    password_hash: str
    last_login: Optional[datetime] = None
    is_active: bool = True
    stripe_customer_id: Optional[str] = None
    credits: Optional[Decimal] = Decimal('0.00')
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }

class Subscription(BaseModel):
    """Modelo de assinatura"""
    id: str
    user_id: str
    plan_id: str
    status: str
    stripe_subscription_id: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class SubscriptionPlan(BaseModel):
    """Modelo de plano de assinatura"""
    id: str
    code: str
    name: str
    description: str
    price_cents: int
    credits_included_cents: int
    api_keys_limit: int
    is_active: bool = True
    stripe_product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    features: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class CreditTransaction(BaseModel):
    """Modelo de transação de crédito"""
    id: str
    user_id: str
    type: str  # 'add', 'subtract', 'purchase', 'spend'
    amount_cents: int
    balance_after_cents: int
    description: str
    stripe_payment_intent_id: Optional[str] = None
    stripe_invoice_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ApiKey(BaseModel):
    """Modelo de chave da API"""
    id: str
    user_id: str
    key_visible: Optional[str] = None  # Chave visível (rcp_...) - removida após primeira visualização
    key_hash: str
    name: str
    description: Optional[str] = None
    is_active: bool = True
    last_used_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ConsultationType(BaseModel):
    """Modelo de tipo de consulta"""
    id: str
    code: str
    name: str
    description: Optional[str] = None
    cost_cents: int
    provider: Optional[str] = None  # Provedor do serviço (resolve_cenprot, cnpja, etc)
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class Consultation(BaseModel):
    """Modelo de consulta realizada"""
    id: str
    user_id: str
    api_key_id: Optional[str] = None
    cnpj: str
    status: str = "success"
    total_cost_cents: int = 0
    response_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    cache_used: bool = False
    client_ip: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ConsultationDetail(BaseModel):
    """Modelo de detalhe de consulta por tipo"""
    id: str
    consultation_id: str
    consultation_type_id: str
    cost_cents: int
    status: str = "success"
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# ✅ REMOVIDO: UserCredits - tabela descontinuada por redundância
# Sistema usa apenas credit_transactions (fonte verdade) + users.credits (cache)

# ✅ REMOVIDO: DailyAnalytics - tabela descontinuada por redundância
# Analytics podem ser calculados on-demand via consultations quando necessário
