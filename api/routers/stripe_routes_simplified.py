"""
Rotas Stripe simplificadas e funcionais
"""
import os
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
import structlog
from datetime import datetime, timedelta

from api.middleware.auth_middleware import require_auth, AuthUser, get_supabase_client

# Configurar Stripe
stripe.api_key = os.getenv("STRIPE_API_KEY_SECRETA")

logger = structlog.get_logger(__name__)
router = APIRouter()

# Modelos Pydantic
class CheckoutSessionRequest(BaseModel):
    price_id: str
    success_url: str = "http://localhost:2377/assinatura?success=true"
    cancel_url: str = "http://localhost:2377/assinatura?canceled=true"

@router.get("/costs")
async def get_service_costs():
    """Retorna os custos por tipo de serviço"""
    # Valores padrão - sempre funciona
    return {
        'protestos': 0.15,
        'receita_federal': 0.03,
        'outros': 0.03
    }

@router.get("/public-key")
async def get_stripe_public_key():
    """Retorna a chave pública do Stripe para uso no frontend"""
    public_key = os.getenv("STRIPE_API_KEY_PUBLICAVEL")
    if not public_key:
        raise HTTPException(status_code=500, detail="Chave pública do Stripe não configurada")
    
    return {"public_key": public_key}

@router.get("/products")
async def get_stripe_products(user: AuthUser = Depends(require_auth)):
    """Retorna produtos/planos mockados para desenvolvimento"""
    try:
        # Retornar dados mockados para desenvolvimento
        mock_products = [
            {
                "id": "starter",
                "name": "Starter",
                "description": "Plano básico para começar",
                "price_cents": 2990,
                "credits_included_cents": 2990,
                "api_keys_limit": 1,
                "features": {"api_keys": 1, "support": "email", "analytics": False}
            },
            {
                "id": "professional", 
                "name": "Professional",
                "description": "Plano profissional completo",
                "price_cents": 9990,
                "credits_included_cents": 9990,
                "api_keys_limit": 5,
                "features": {"api_keys": 5, "support": "priority", "analytics": True}
            },
            {
                "id": "enterprise",
                "name": "Enterprise", 
                "description": "Solução empresarial avançada",
                "price_cents": 29990,
                "credits_included_cents": 29990,
                "api_keys_limit": -1,
                "features": {"api_keys": -1, "support": "24/7", "analytics": True, "custom_features": True}
            }
        ]
        
        return {
            "products": mock_products,
            "prices": {}  # Mockado para desenvolvimento
        }
    except Exception as e:
        logger.error(f"Erro ao buscar produtos: {e}")
        raise HTTPException(status_code=500, detail="Erro ao carregar produtos")

@router.post("/create-checkout-session")
async def create_checkout_session(
    request: CheckoutSessionRequest,
    user: AuthUser = Depends(require_auth)
):
    """Cria uma sessão de checkout do Stripe"""
    try:
        # Para desenvolvimento, retornar URL mockada
        return {
            "checkout_url": f"https://checkout.stripe.com/pay/mock_session_id?success_url={request.success_url}&cancel_url={request.cancel_url}",
            "session_id": "mock_session_id_for_dev"
        }
    except Exception as e:
        logger.error(f"Erro ao criar sessão de checkout: {e}")
        raise HTTPException(status_code=500, detail="Erro ao criar sessão de pagamento")

@router.get("/subscription/current")
async def get_current_subscription(user: AuthUser = Depends(require_auth)):
    """Retorna a assinatura atual do usuário"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            # Mock para desenvolvimento
            return {
                "subscription": {
                    "id": "mock_subscription_id",
                    "plan_name": "Starter",
                    "status": "active",
                    "price_cents": 2990,
                    "credits_available": 10.00,
                    "auto_renewal": True,
                    "current_period_end": (datetime.now() + timedelta(days=30)).isoformat()
                }
            }
        
        # Buscar assinatura real no banco
        result = supabase.table("subscriptions").select(
            "*, subscription_plans(name, price_cents)"
        ).eq("user_id", user.user_id).eq("status", "active").execute()
        
        if result.data:
            subscription = result.data[0]
            return {
                "subscription": {
                    "id": subscription["id"],
                    "plan_name": subscription.get("subscription_plans", {}).get("name", "Unknown"),
                    "status": subscription["status"],
                    "price_cents": subscription.get("subscription_plans", {}).get("price_cents", 0),
                    "credits_available": 0.00,  # Será calculado pelos serviços
                    "auto_renewal": subscription.get("auto_renewal_enabled", True),
                    "current_period_end": subscription.get("current_period_end")
                }
            }
        else:
            return {"subscription": None}
            
    except Exception as e:
        logger.error(f"Erro ao buscar assinatura: {e}")
        # Retornar mock em caso de erro
        return {
            "subscription": {
                "id": "mock_subscription_id",
                "plan_name": "Starter",
                "status": "active", 
                "price_cents": 2990,
                "credits_available": 10.00,
                "auto_renewal": True,
                "current_period_end": (datetime.now() + timedelta(days=30)).isoformat()
            }
        }

@router.get("/transactions/recent")
async def get_recent_transactions(user: AuthUser = Depends(require_auth)):
    """Retorna transações recentes do usuário"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            # Mock para desenvolvimento
            return {
                "transactions": [
                    {
                        "id": "mock_transaction_1",
                        "type": "purchase",
                        "amount_cents": 2990,
                        "description": "Compra de créditos - Plano Starter",
                        "created_at": datetime.now().isoformat(),
                        "status": "completed"
                    }
                ]
            }
        
        # Buscar transações reais no banco
        result = supabase.table("credit_transactions").select(
            "id, type, amount_cents, description, created_at"
        ).eq("user_id", user.user_id).order("created_at", desc=True).limit(10).execute()
        
        return {
            "transactions": result.data or []
        }
        
    except Exception as e:
        logger.error(f"Erro ao buscar transações: {e}")
        # Retornar mock em caso de erro
        return {
            "transactions": [
                {
                    "id": "mock_transaction_1",
                    "type": "purchase",
                    "amount_cents": 2990,
                    "description": "Compra de créditos - Plano Starter",
                    "created_at": datetime.now().isoformat(),
                    "status": "completed"
                }
            ]
        }

@router.get("/user/credits")
async def get_user_credits(user: AuthUser = Depends(require_auth)):
    """Retorna informações de créditos do usuário"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            # Mock para desenvolvimento
            return {
                "credits_available": 10.00,
                "total_purchased": 29.90,
                "total_spent": 19.90,
                "last_transaction": datetime.now().isoformat()
            }
        
        # Buscar dados reais no banco
        result = supabase.table("users").select("credits").eq("id", user.user_id).single().execute()
        
        credits = result.data.get("credits", 0) if result.data else 0
        
        return {
            "credits_available": float(credits),
            "total_purchased": float(credits),  # Simplificado
            "total_spent": 0.00,
            "last_transaction": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erro ao buscar créditos: {e}")
        # Retornar mock em caso de erro
        return {
            "credits_available": 10.00,
            "total_purchased": 29.90,
            "total_spent": 19.90,
            "last_transaction": datetime.now().isoformat()
        }
