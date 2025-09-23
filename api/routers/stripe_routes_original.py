"""
Router para integração com Stripe
Gerencia produtos, preços, assinaturas e webhooks
"""

import os
import stripe
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
import structlog
from datetime import datetime, timedelta

from api.middleware.auth_middleware import require_auth, AuthUser, get_supabase_client

# Configurar Stripe
stripe.api_key = os.getenv("STRIPE_API_KEY_SECRETA")

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/costs")
async def get_service_costs():
    """Retorna os custos por tipo de serviço"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            # Retornar valores padrão se Supabase não estiver disponível
            return {
                'protestos': 0.15,
                'receita_federal': 0.03,
                'outros': 0.03
            }
        
        result = supabase.table("service_costs").select("service_name, cost_per_request").eq("is_active", True).order("service_name").execute()
        
        costs = {}
        for cost in result.data:
            costs[cost['service_name']] = float(cost['cost_per_request'])
        
        # Valores padrão se não encontrar no banco
        if not costs:
            costs = {
                'protestos': 0.15,
                'receita_federal': 0.03,
                'outros': 0.03
            }
        
        return costs
        
    except Exception as e:
        logger.error("error_loading_costs", error=str(e))
        # Retornar valores padrão em caso de erro
        return {
            'protestos': 0.15,
            'receita_federal': 0.03,
            'outros': 0.03
        }


# Novo endpoint para créditos do usuário
@router.get("/user/credits")
async def get_user_credits(user: AuthUser = Depends(require_auth)):
    """Retorna informações de créditos do usuário"""
    try:
        async with get_db_connection() as conn:
            # Buscar créditos atuais do usuário
            credits_data = await conn.fetchrow("""
                SELECT 
                    credits,
                    (SELECT COALESCE(SUM(
                        CASE WHEN type IN ('add', 'purchase') THEN amount ELSE 0 END
                    ), 0) FROM credit_transactions WHERE user_id = $1) as total_purchased,
                    (SELECT COALESCE(SUM(
                        CASE WHEN type IN ('subtract', 'spend') THEN amount ELSE 0 END
                    ), 0) FROM credit_transactions WHERE user_id = $1) as total_used
                FROM users 
                WHERE id = $1
            """, user.id)
        
        if credits_data:
            return {
                "available": float(credits_data['credits'] or 0),
                "total": float(credits_data['total_purchased'] or 0),
                "used": float(credits_data['total_used'] or 0)
            }
        else:
            return {
                "available": 0.0,
                "total": 0.0,
                "used": 0.0
            }
        
    except Exception as e:
        logger.error("error_loading_user_credits", 
                    user_id=user.id, 
                    error=str(e))
        return {
            "available": 0.0,
            "total": 0.0,
            "used": 0.0
        }


class CheckoutSessionRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str


class AutoRenewalRequest(BaseModel):
    enabled: bool


class WebhookEvent(BaseModel):
    id: str
    object: str
    type: str
    data: Dict[str, Any]


@router.get("/public-key")
async def get_stripe_public_key():
    """Retorna a chave pública do Stripe para uso no frontend"""
    public_key = os.getenv("STRIPE_API_KEY_PUBLICAVEL")
    if not public_key:
        raise HTTPException(status_code=500, detail="Chave pública do Stripe não configurada")
    
    return {"public_key": public_key}


@router.get("/products")
async def get_stripe_products(user: AuthUser = Depends(require_auth)):
    """Retorna todos os produtos/planos disponíveis do Stripe"""
    try:
        # Buscar produtos ativos
        products = stripe.Product.list(active=True, expand=["data.default_price"])
        
        # Buscar todos os preços
        prices = stripe.Price.list(active=True)
        prices_dict = {price.id: price for price in prices.data}
        
        logger.info("stripe_products_loaded", 
                   user_id=user.id, 
                   products_count=len(products.data))
        
        return {
            "products": [product.to_dict() for product in products.data],
            "prices": {price_id: price.to_dict() for price_id, price in prices_dict.items()}
        }
        
    except stripe.error.StripeError as e:
        logger.error("stripe_error_loading_products", 
                    user_id=user.id, 
                    error=str(e))
        raise HTTPException(status_code=400, detail=f"Erro do Stripe: {str(e)}")
    except Exception as e:
        logger.error("error_loading_products", 
                    user_id=user.id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


@router.post("/create-checkout-session")
async def create_checkout_session(
    request: CheckoutSessionRequest,
    user: AuthUser = Depends(require_auth)
):
    """Cria uma sessão de checkout do Stripe"""
    try:
        # Verificar se o usuário já tem customer no Stripe
        customer_id = await get_or_create_stripe_customer(user)
        
        # Criar sessão de checkout
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': request.price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            metadata={
                'user_id': str(user.id),
            }
        )
        
        logger.info("checkout_session_created", 
                   user_id=user.id, 
                   session_id=session.id,
                   price_id=request.price_id)
        
        return {"session_id": session.id}
        
    except stripe.error.StripeError as e:
        logger.error("stripe_error_creating_checkout", 
                    user_id=user.id, 
                    error=str(e))
        raise HTTPException(status_code=400, detail=f"Erro do Stripe: {str(e)}")
    except Exception as e:
        logger.error("error_creating_checkout", 
                    user_id=user.id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


@router.get("/checkout-session/{session_id}")
async def get_checkout_session(
    session_id: str,
    user: AuthUser = Depends(require_auth)
):
    """Verifica o status de uma sessão de checkout"""
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        
        # Verificar se a sessão pertence ao usuário
        if session.metadata.get('user_id') != str(user.id):
            raise HTTPException(status_code=403, detail="Acesso negado")
        
        return session.to_dict()
        
    except stripe.error.StripeError as e:
        logger.error("stripe_error_retrieving_session", 
                    user_id=user.id, 
                    session_id=session_id,
                    error=str(e))
        raise HTTPException(status_code=400, detail=f"Erro do Stripe: {str(e)}")
    except Exception as e:
        logger.error("error_retrieving_session", 
                    user_id=user.id, 
                    session_id=session_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


@router.get("/subscription/current")
async def get_current_subscription(user: AuthUser = Depends(require_auth)):
    """Retorna a assinatura atual do usuário"""
    try:
        # Buscar customer no Stripe
        customer = await get_stripe_customer(user)
        if not customer:
            return {"subscription": None}
        
        # Buscar assinaturas ativas
        subscriptions = stripe.Subscription.list(
            customer=customer.id,
            status='all',
            limit=1
        )
        
        if subscriptions.data:
            subscription = subscriptions.data[0]
            logger.info("subscription_retrieved", 
                       user_id=user.id, 
                       subscription_id=subscription.id,
                       status=subscription.status)
            
            return {"subscription": subscription.to_dict()}
        else:
            return {"subscription": None}
            
    except stripe.error.StripeError as e:
        logger.error("stripe_error_getting_subscription", 
                    user_id=user.id, 
                    error=str(e))
        raise HTTPException(status_code=400, detail=f"Erro do Stripe: {str(e)}")
    except Exception as e:
        logger.error("error_getting_subscription", 
                    user_id=user.id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


@router.post("/subscription/auto-renewal")
async def toggle_auto_renewal(
    request: AutoRenewalRequest,
    user: AuthUser = Depends(require_auth)
):
    """Ativa/desativa renovação automática da assinatura"""
    try:
        # Buscar customer e assinatura atual
        customer = await get_stripe_customer(user)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer não encontrado")
        
        subscriptions = stripe.Subscription.list(
            customer=customer.id,
            status='active',
            limit=1
        )
        
        if not subscriptions.data:
            raise HTTPException(status_code=404, detail="Assinatura ativa não encontrada")
        
        subscription = subscriptions.data[0]
        
        # Atualizar renovação automática
        updated_subscription = stripe.Subscription.modify(
            subscription.id,
            cancel_at_period_end=not request.enabled
        )
        
        action = "ativada" if request.enabled else "desativada"
        logger.info("auto_renewal_updated", 
                   user_id=user.id, 
                   subscription_id=subscription.id,
                   enabled=request.enabled)
        
        return {
            "message": f"Renovação automática {action} com sucesso",
            "subscription": updated_subscription.to_dict()
        }
        
    except stripe.error.StripeError as e:
        logger.error("stripe_error_updating_auto_renewal", 
                    user_id=user.id, 
                    error=str(e))
        raise HTTPException(status_code=400, detail=f"Erro do Stripe: {str(e)}")
    except Exception as e:
        logger.error("error_updating_auto_renewal", 
                    user_id=user.id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


@router.get("/transactions/recent")
async def get_recent_transactions(user: AuthUser = Depends(require_auth)):
    """Retorna transações recentes do usuário"""
    try:
        # Buscar customer no Stripe
        customer = await get_stripe_customer(user)
        if not customer:
            return {"transactions": []}
        
        # Buscar invoices recentes (últimos 30 dias)
        thirty_days_ago = int((datetime.now() - timedelta(days=30)).timestamp())
        
        invoices = stripe.Invoice.list(
            customer=customer.id,
            created={'gte': thirty_days_ago},
            limit=10
        )
        
        transactions = []
        for invoice in invoices.data:
            if invoice.charge:
                charge = stripe.Charge.retrieve(invoice.charge)
                transactions.append({
                    'id': charge.id,
                    'amount': charge.amount,
                    'currency': charge.currency,
                    'status': charge.status,
                    'description': charge.description or f"Fatura {invoice.number}",
                    'created': charge.created
                })
        
        logger.info("recent_transactions_retrieved", 
                   user_id=user.id, 
                   transactions_count=len(transactions))
        
        return {"transactions": transactions}
        
    except stripe.error.StripeError as e:
        logger.error("stripe_error_getting_transactions", 
                    user_id=user.id, 
                    error=str(e))
        raise HTTPException(status_code=400, detail=f"Erro do Stripe: {str(e)}")
    except Exception as e:
        logger.error("error_getting_transactions", 
                    user_id=user.id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Webhook do Stripe para processar eventos"""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    if not endpoint_secret:
        logger.error("stripe_webhook_secret_missing")
        raise HTTPException(status_code=500, detail="Webhook secret não configurado")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        logger.error("stripe_webhook_invalid_payload", error=str(e))
        raise HTTPException(status_code=400, detail="Payload inválido")
    except stripe.error.SignatureVerificationError as e:
        logger.error("stripe_webhook_invalid_signature", error=str(e))
        raise HTTPException(status_code=400, detail="Assinatura inválida")
    
    # Processar evento
    await handle_stripe_event(event)
    
    return {"status": "success"}


async def handle_stripe_event(event: Dict[str, Any]):
    """Processa eventos do webhook do Stripe"""
    event_type = event['type']
    
    logger.info("stripe_webhook_event_received", 
               event_type=event_type, 
               event_id=event['id'])
    
    try:
        if event_type == 'customer.subscription.created':
            await handle_subscription_created(event['data']['object'])
        elif event_type == 'customer.subscription.updated':
            await handle_subscription_updated(event['data']['object'])
        elif event_type == 'customer.subscription.deleted':
            await handle_subscription_deleted(event['data']['object'])
        elif event_type == 'invoice.payment_succeeded':
            await handle_payment_succeeded(event['data']['object'])
        elif event_type == 'invoice.payment_failed':
            await handle_payment_failed(event['data']['object'])
        else:
            logger.info("stripe_webhook_unhandled_event", event_type=event_type)
            
    except Exception as e:
        logger.error("stripe_webhook_processing_error", 
                    event_type=event_type, 
                    event_id=event['id'],
                    error=str(e))
        raise


async def handle_subscription_created(subscription: Dict[str, Any]):
    """Processa criação de assinatura"""
    customer_id = subscription['customer']
    user = await get_user_by_stripe_customer(customer_id)
    
    if user:
        # Adicionar créditos baseados no valor da assinatura
        amount = subscription['items']['data'][0]['price']['unit_amount']
        credits = amount / 100  # Converter centavos para reais
        
        await add_user_credits(user.id, credits)
        
        logger.info("subscription_created_processed", 
                   user_id=user.id, 
                   customer_id=customer_id,
                   credits_added=credits)


async def handle_subscription_updated(subscription: Dict[str, Any]):
    """Processa atualização de assinatura"""
    customer_id = subscription['customer']
    user = await get_user_by_stripe_customer(customer_id)
    
    if user:
        logger.info("subscription_updated_processed", 
                   user_id=user.id, 
                   customer_id=customer_id,
                   status=subscription['status'])


async def handle_subscription_deleted(subscription: Dict[str, Any]):
    """Processa cancelamento de assinatura"""
    customer_id = subscription['customer']
    user = await get_user_by_stripe_customer(customer_id)
    
    if user:
        logger.info("subscription_deleted_processed", 
                   user_id=user.id, 
                   customer_id=customer_id)


async def handle_payment_succeeded(invoice: Dict[str, Any]):
    """Processa pagamento bem-sucedido"""
    customer_id = invoice['customer']
    user = await get_user_by_stripe_customer(customer_id)
    
    if user and invoice['billing_reason'] == 'subscription_cycle':
        # Adicionar créditos para renovação de assinatura
        amount = invoice['amount_paid']
        credits = amount / 100  # Converter centavos para reais
        
        await add_user_credits(user.id, credits)
        
        logger.info("payment_succeeded_processed", 
                   user_id=user.id, 
                   customer_id=customer_id,
                   credits_added=credits,
                   invoice_id=invoice['id'])


async def handle_payment_failed(invoice: Dict[str, Any]):
    """Processa pagamento falhado"""
    customer_id = invoice['customer']
    user = await get_user_by_stripe_customer(customer_id)
    
    if user:
        logger.warning("payment_failed_processed", 
                      user_id=user.id, 
                      customer_id=customer_id,
                      invoice_id=invoice['id'])


async def get_or_create_stripe_customer(user: AuthUser) -> str:
    """Obtém ou cria um customer no Stripe para o usuário"""
    # Primeiro, tentar buscar customer existente
    customer = await get_stripe_customer(user)
    
    if customer:
        return customer.id
    
    # Criar novo customer
    try:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.nome,
            metadata={
                'user_id': str(user.id)
            }
        )
        
        # Salvar customer_id no banco de dados
        await save_stripe_customer_id(user.id, customer.id)
        
        logger.info("stripe_customer_created", 
                   user_id=user.id, 
                   customer_id=customer.id)
        
        return customer.id
        
    except stripe.error.StripeError as e:
        logger.error("error_creating_stripe_customer", 
                    user_id=user.id, 
                    error=str(e))
        raise


async def get_stripe_customer(user: AuthUser) -> Optional[stripe.Customer]:
    """Busca customer do Stripe para o usuário"""
    try:
        # Buscar por customer_id salvo no banco
        customer_id = await get_stripe_customer_id(user.id)
        
        if customer_id:
            return stripe.Customer.retrieve(customer_id)
        
        # Buscar por email como fallback
        customers = stripe.Customer.list(email=user.email, limit=1)
        
        if customers.data:
            customer = customers.data[0]
            # Salvar customer_id para próximas consultas
            await save_stripe_customer_id(user.id, customer.id)
            return customer
        
        return None
        
    except stripe.error.StripeError as e:
        logger.error("error_getting_stripe_customer", 
                    user_id=user.id, 
                    error=str(e))
        return None


# Funções auxiliares para banco de dados
async def save_stripe_customer_id(user_id: int, customer_id: str):
    """Salva customer_id do Stripe no banco de dados"""
    async with get_db_connection() as conn:
        await conn.execute("""
            UPDATE users 
            SET stripe_customer_id = $1, updated_at = NOW()
            WHERE id = $2
        """, customer_id, user_id)


async def get_stripe_customer_id(user_id: int) -> Optional[str]:
    """Recupera customer_id do Stripe do banco de dados"""
    async with get_db_connection() as conn:
        result = await conn.fetchval("""
            SELECT stripe_customer_id 
            FROM users 
            WHERE id = $1
        """, user_id)
        return result


async def get_user_by_stripe_customer(customer_id: str) -> Optional[User]:
    """Busca usuário pelo customer_id do Stripe"""
    async with get_db_connection() as conn:
        result = await conn.fetchrow("""
            SELECT id, email, nome, stripe_customer_id, credits
            FROM users 
            WHERE stripe_customer_id = $1
        """, customer_id)
        
        if result:
            return User(**dict(result))
        return None


async def add_user_credits(user_id: int, credits: float):
    """Adiciona créditos à conta do usuário"""
    async with get_db_connection() as conn:
        await conn.execute("""
            UPDATE users 
            SET credits = COALESCE(credits, 0) + $1,
                updated_at = NOW()
            WHERE id = $2
        """, credits, user_id)
        
        logger.info("user_credits_added", 
                   user_id=user_id, 
                   credits_added=credits)
