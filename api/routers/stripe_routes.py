"""
Rotas Stripe simplificadas e funcionais
"""
import os
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
import structlog
from datetime import datetime, timedelta

from api.middleware.auth_middleware import require_auth, AuthUser
from api.database.connection import execute_sql

logger = structlog.get_logger(__name__)

# Configurar Stripe
stripe_secret_key = os.getenv("STRIPE_API_KEY_SECRETA")
if not stripe_secret_key:
    logger.warning("⚠️ STRIPE_API_KEY_SECRETA não configurada no .env")
    # Usar chave de teste padrão para desenvolvimento (opcional)
    # stripe.api_key = "sk_test_..."
else:
    stripe.api_key = stripe_secret_key
    logger.info("✅ Stripe API configurada com sucesso")
router = APIRouter()

# Modelos Pydantic
class CheckoutSessionRequest(BaseModel):
    price_id: str
    success_url: str = "http://localhost:2377/assinatura?success=true"
    cancel_url: str = "http://localhost:2377/assinatura?canceled=true"

class CustomPlanRequest(BaseModel):
    amount: float  # Valor em reais (ex: 150.00)
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

@router.get("/consultation-types")
async def get_consultation_types():
    """Retorna todos os tipos de consulta disponíveis com preços para tabela de transparência"""
    try:
        sql = """
        SELECT code, name, description, cost_cents, provider, is_active
        FROM consultation_types 
        WHERE is_active = 1
        ORDER BY cost_cents DESC
        """
        
        result = await execute_sql(sql, (), "all")
        
        if result["error"]:
            logger.error(f"❌ Erro SQL ao buscar tipos de consulta: {result['error']}")
            raise Exception("Erro na consulta ao banco")
        
        consultation_types = []
        if result["data"]:
            for item in result["data"]:
                cost_cents = float(item["cost_cents"]) if item["cost_cents"] else 0.0
                consultation_types.append({
                    "code": item["code"],
                    "name": item["name"],
                    "description": item["description"],
                    "cost_reais": cost_cents / 100.0,  # Converter para reais
                    "cost_cents": int(cost_cents),
                    "provider": item["provider"],
                    "is_active": bool(item["is_active"])
                })
        
        return {
            "success": True,
            "consultation_types": consultation_types
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar tipos de consulta: {e}")
        # Retornar dados mockados em caso de erro
        return {
            "success": False,
            "consultation_types": [
                {
                    "code": "protestos",
                    "name": "Consulta de Protestos",
                    "description": "Consulta de protestos no Resolve CenProt",
                    "cost_reais": 0.15,
                    "cost_cents": 15,
                    "provider": "resolve_cenprot",
                    "is_active": True
                },
                {
                    "code": "receita_federal",
                    "name": "Receita Federal",
                    "description": "Dados básicos da Receita Federal",
                    "cost_reais": 0.05,
                    "cost_cents": 5,
                    "provider": "cnpja",
                    "is_active": True
                }
            ]
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
    """
    Retorna produtos da tabela local subscription_plans (OTIMIZADO)
    Dados sincronizados do Stripe para carregamento ultrarrápido
    ✅ IMPLEMENTAÇÃO: Isolamento de planos customizados por usuário
    """
    try:
        # Buscar produtos da tabela local com filtro por usuário
        sql = """
        SELECT 
            id, code, name, description, price_cents, credits_included_cents,
            stripe_product_id, stripe_price_id, is_active, features, user_id
        FROM subscription_plans 
        WHERE is_active = 1 
        AND (user_id IS NULL OR user_id = %s)
        ORDER BY price_cents ASC
        """
        
        result = await execute_sql(sql, (user.user_id,), "all")
        
        if result["error"]:
            logger.error(f"❌ Erro ao buscar planos do MariaDB: {result['error']}")
            return await get_stripe_products_online()
        
        products_data = []
        prices_data = {}
        
        if result["data"]:
            for plan in result["data"]:
                # Converter para formato compatível com frontend
                product_data = {
                    "id": plan["stripe_product_id"] or plan["id"],
                    "name": plan["name"],
                    "description": plan["description"],
                    "code": plan["code"],
                    "default_price": plan["stripe_price_id"] or f"price_{plan['code']}",
                    "price_cents": plan["price_cents"],
                    "credits_included_cents": plan["credits_included_cents"],
                    "is_active": plan["is_active"],
                    "features": plan.get("features", {}),
                    "is_custom": plan["user_id"] is not None,  # Indica se é plano customizado
                    "metadata": {
                        "plan_code": plan["code"],
                        "local_plan_id": plan["id"],
                        "is_custom_plan": plan["user_id"] is not None
                    }
                }
                products_data.append(product_data)
                
                # Construir prices_data
                price_id = product_data["default_price"]
                if price_id and price_id.startswith("price_"):
                    prices_data[price_id] = {
                        "id": price_id,
                        "unit_amount": plan["price_cents"],
                        "currency": "brl",
                        "recurring": {"interval": "month"},
                        "product": product_data["id"]
                    }
        
        logger.info(f"🚀 {len(products_data)} produtos carregados do MariaDB (ultrarrápido)")
        logger.info(f"👤 Filtrados para usuário: {user.email}")
        
        return {
            "products": products_data,
            "prices": prices_data,
            "source": "local_database",
            "optimized": True,
            "user_filtered": True
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar produtos do MariaDB: {e}")
        
        # Fallback para busca online do Stripe (modo original - mais lento)
        logger.warning("⚠️ Fallback para busca online do Stripe")
        return await get_stripe_products_online()


async def get_stripe_products_online():
    """
    Método original - busca produtos diretamente do Stripe (LENTO)
    Usado apenas como fallback
    """
    try:
        # IDs dos produtos criados no Stripe Dashboard
        product_ids = [
            "prod_T6ANMZkdf6gzQE",  # R$ 100,00
            "prod_T6w1fA20Y5N0Mp",  # R$ 200,00  
            "prod_T6w2idmnU4IBif"   # R$ 300,00
        ]
        
        # Buscar produtos reais do Stripe (ONLINE)
        products_data = []
        prices_data = {}
        
        for product_id in product_ids:
            try:
                # Buscar produto
                product = stripe.Product.retrieve(product_id)
                
                # Buscar preços do produto
                prices = stripe.Price.list(product=product_id, active=True)
                
                if prices.data:
                    price = prices.data[0]  # Pegar o primeiro preço ativo
                    price_amount = price.unit_amount / 100  # Converter de centavos para reais
                    
                    # Mapear produto com informações necessárias
                    product_data = {
                        "id": product.id,
                        "name": product.name,
                        "description": product.description or f"Plano de R$ {price_amount:.2f} em créditos mensais",
                        "default_price": price.id,
                        "price_cents": price.unit_amount,
                        "credits_included_cents": price.unit_amount,  # 1:1 - cada R$ pago vira R$ em créditos
                        "metadata": product.metadata or {}
                    }
                    
                    products_data.append(product_data)
                    prices_data[price.id] = {
                        "id": price.id,
                        "unit_amount": price.unit_amount,
                        "currency": price.currency,
                        "recurring": price.recurring,
                        "product": product.id
                    }
                    
            except stripe.error.StripeError as e:
                logger.error(f"Erro ao buscar produto {product_id}: {e}")
                continue
        
        # Ordenar por preço (menor para maior)
        products_data.sort(key=lambda x: x["price_cents"])
        
        logger.info(f"⚠️ {len(products_data)} produtos carregados do Stripe (ONLINE - lento)")
        
        return {
            "products": products_data,
            "prices": prices_data,
            "source": "stripe_online",
            "optimized": False
        }
        
    except Exception as e:
        logger.error(f"❌ Erro geral ao buscar produtos online: {e}")
        
        # Fallback final para dados estáticos
        fallback_products = [
            {
                "id": "prod_T6ANMZkdf6gzQE",
                "name": "Créditos R$ 100,00",
                "description": "R$ 100,00 em créditos mensais",
                "price_cents": 10000,
                "credits_included_cents": 10000,
                "default_price": "price_fallback_100"
            },
            {
                "id": "prod_T6w1fA20Y5N0Mp", 
                "name": "Créditos R$ 200,00",
                "description": "R$ 200,00 em créditos mensais",
                "price_cents": 20000,
                "credits_included_cents": 20000,
                "default_price": "price_fallback_200"
            },
            {
                "id": "prod_T6w2idmnU4IBif",
                "name": "Créditos R$ 300,00",
                "description": "R$ 300,00 em créditos mensais", 
                "price_cents": 30000,
                "credits_included_cents": 30000,
                "default_price": "price_fallback_300"
            }
        ]
        
        return {
            "products": fallback_products,
            "prices": {},
            "source": "fallback_static",
            "optimized": False
        }

@router.post("/sync-products")
async def sync_stripe_products(user: AuthUser = Depends(require_auth)):
    """
    Força sincronização dos produtos Stripe com MariaDB
    Endpoint administrativo para atualizar dados quando necessário
    """
    try:
        # Importar serviço de sincronização
        from api.services.stripe_sync_service import stripe_sync_service
        
        logger.info(f"🔄 Usuário {user.email} solicitou sincronização de produtos")
        
        # Executar sincronização
        sync_result = await stripe_sync_service.force_sync()
        
        if sync_result["success"]:
            message = f"Sincronização concluída: {sync_result['updated']} atualizados, {sync_result['created']} criados"
            logger.info(f"✅ {message}")
            
            return {
                "success": True,
                "message": message,
                "updated": sync_result["updated"],
                "created": sync_result["created"],
                "errors": sync_result.get("errors", [])
            }
        else:
            error_message = sync_result.get("message", "Erro desconhecido")
            logger.error(f"❌ Falha na sincronização: {error_message}")
            
            return {
                "success": False,
                "message": error_message,
                "updated": 0,
                "created": 0,
                "errors": sync_result.get("errors", [])
            }
        
    except Exception as e:
        logger.error(f"❌ Erro ao sincronizar produtos: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro na sincronização: {str(e)}"
        )

@router.get("/sync-status")
async def get_sync_status(user: AuthUser = Depends(require_auth)):
    """
    Retorna status da sincronização dos produtos
    """
    try:
        from api.services.stripe_sync_service import get_last_sync_info
        
        sync_info = await get_last_sync_info()
        
        # Contar produtos sincronizados
        count_sql = "SELECT COUNT(*) as total FROM subscription_plans WHERE stripe_product_id IS NOT NULL"
        count_result = await execute_sql(count_sql, (), "one")
        
        synced_count = count_result["data"]["total"] if count_result["data"] else 0
        
        return {
            "last_sync": sync_info.get("last_sync"),
            "has_stripe_data": sync_info.get("has_stripe_data", False),
            "synced_products_count": synced_count,
            "stripe_configured": bool(stripe.api_key and stripe.api_key != "sk_test_dummy"),
            "recommended_action": "sync_needed" if not sync_info.get("has_stripe_data") else "up_to_date"
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar status de sincronização: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao verificar status: {str(e)}"
        )

@router.post("/create-checkout-session")
async def create_checkout_session(
    request: CheckoutSessionRequest,
    user: AuthUser = Depends(require_auth)
):
    """Cria uma sessão de checkout real do Stripe"""
    try:
        logger.info(f"🛒 Criando checkout session para user {user.user_id}, price_id: {request.price_id}")
        
        # Verificar se Stripe está configurado
        if not stripe.api_key:
            raise HTTPException(
                status_code=500, 
                detail="Stripe não configurado - STRIPE_API_KEY_SECRETA não encontrada"
            )
        
        # Buscar ou criar cliente no Stripe
        customer_id = await get_or_create_stripe_customer(user)
        
        # Criar sessão de checkout do Stripe
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{
                'price': request.price_id,
                'quantity': 1,
            }],
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            metadata={
                'user_id': user.user_id,
                'user_email': user.email
            },
            # Configurações para assinatura
            subscription_data={
                'metadata': {
                    'user_id': user.user_id,
                    'user_email': user.email
                }
            }
        )
        
        logger.info(f"✅ Checkout session criada: {session.id}")
        
        return {
            "checkout_url": session.url,
            "session_id": session.id
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"❌ Erro Stripe ao criar checkout: {e}")
        raise HTTPException(
            status_code=400, 
            detail=f"Erro do Stripe: {str(e)}"
        )
    except Exception as e:
        logger.error(f"❌ Erro geral ao criar checkout: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao criar sessão de pagamento"
        )


async def get_or_create_stripe_customer(user: AuthUser) -> str:
    """Busca ou cria um cliente no Stripe - migrado para MariaDB"""
    try:
        # Verificar se usuário já tem stripe_customer_id no MariaDB
        sql = "SELECT stripe_customer_id FROM users WHERE id = %s"
        result = await execute_sql(sql, (user.user_id,), "one")
        
        if result and result.get("data") and result["data"] and result["data"].get("stripe_customer_id"):
            stripe_customer_id = result["data"]["stripe_customer_id"]
            logger.info(f"✅ Cliente Stripe existente: {stripe_customer_id}")
            return stripe_customer_id
        
        # Verificar se Stripe está configurado
        if not stripe.api_key:
            raise HTTPException(
                status_code=500, 
                detail="Stripe não configurado - STRIPE_API_KEY_SECRETA não encontrada"
            )
        
        # Criar novo cliente no Stripe
        customer = stripe.Customer.create(
            email=user.email,
            name=getattr(user, 'name', user.email),
            metadata={
                'user_id': user.user_id,
                'internal_user_email': user.email
            }
        )
        
        if not customer:
            raise HTTPException(status_code=500, detail="Falha ao criar customer no Stripe")
        
        # Salvar stripe_customer_id no MariaDB
        update_sql = "UPDATE users SET stripe_customer_id = %s WHERE id = %s"
        update_result = await execute_sql(update_sql, (customer.id, user.user_id), "none")
        
        if update_result["error"]:
            logger.error(f"❌ Erro ao salvar stripe_customer_id no MariaDB: {update_result['error']}")
        else:
            logger.info(f"✅ Stripe customer ID salvo no MariaDB: {customer.id}")
        
        logger.info(f"✅ Novo cliente Stripe criado: {customer.id}")
        return customer.id
        
    except stripe.error.StripeError as e:
        logger.error(f"❌ Erro do Stripe ao criar/buscar cliente: {e}")
        raise HTTPException(status_code=400, detail=f"Erro do Stripe: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Erro geral ao gerenciar cliente Stripe: {e}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")

@router.get("/subscription/current")
async def get_current_subscription(user: AuthUser = Depends(require_auth)):
    """Retorna a assinatura atual do usuário - migrado para MariaDB"""
    try:
        # Buscar assinatura ativa no MariaDB
        sql = """
        SELECT 
            s.id, s.status, s.current_period_end, s.cancel_at_period_end,
            s.stripe_subscription_id, s.stripe_price_id,
            sp.name as plan_name, sp.price_cents, sp.code as plan_code,
            sp.description as plan_description
        FROM subscriptions s
        JOIN subscription_plans sp ON s.plan_id = sp.id
        WHERE s.user_id = %s AND s.status = 'active'
        ORDER BY s.created_at DESC
        LIMIT 1
        """
        
        result = await execute_sql(sql, (user.user_id,), "one")
        
        if result["data"]:
            subscription = result["data"]
            
            # Calcular próximo período de cobrança
            current_period_end = subscription.get("current_period_end")
            next_billing_date = None
            if current_period_end:
                next_billing_date = current_period_end.isoformat()
            
            return {
                "subscription": {
                    "id": subscription["id"],
                    "stripe_subscription_id": subscription.get("stripe_subscription_id"),
                    "plan_name": subscription.get("plan_name", "Unknown"),
                    "plan_code": subscription.get("plan_code", "unknown"),
                    "plan_description": subscription.get("plan_description", ""),
                    "status": subscription["status"],
                    "price_cents": subscription.get("price_cents", 0),
                    "price_reais": subscription.get("price_cents", 0) / 100.0,
                    "credits_available": 0.00,  # Será calculado pelos serviços
                    "auto_renewal": not subscription.get("cancel_at_period_end", False),
                    "current_period_end": next_billing_date,
                    "cancel_at_period_end": subscription.get("cancel_at_period_end", False),
                    "is_recurring": True,  # Sempre é recorrente
                    "billing_interval": "monthly"  # Sempre mensal
                }
            }
        else:
            return {"subscription": None}
            
    except Exception as e:
        logger.error(f"❌ Erro ao buscar assinatura no MariaDB: {e}")
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

@router.post("/subscription/auto-renewal")
async def toggle_auto_renewal(
    request: dict, 
    user: AuthUser = Depends(require_auth)
):
    """Ativar ou desativar renovação automática da assinatura"""
    try:
        enabled = request.get("enabled", True)
        
        # Buscar assinatura atual do usuário
        sql_subscription = """
        SELECT stripe_subscription_id 
        FROM subscriptions 
        WHERE user_id = %s AND status = 'active'
        LIMIT 1
        """
        
        result = await execute_sql(sql_subscription, (user.user_id,), "one")
        
        if result["error"] or not result["data"]:
            logger.warning(f"Nenhuma assinatura ativa encontrada para user {user.user_id}")
            return {
                "success": False,
                "message": "Nenhuma assinatura ativa encontrada"
            }
        
        stripe_subscription_id = result["data"]["stripe_subscription_id"]
        
        if stripe_subscription_id:
            # Alterar no Stripe
            try:
                stripe_subscription = stripe.Subscription.modify(
                    stripe_subscription_id,
                    cancel_at_period_end=not enabled  # Se enabled=True, cancel_at_period_end=False
                )
                logger.info(f"✅ Renovação automática {'ativada' if enabled else 'desativada'} no Stripe")
            except Exception as stripe_error:
                logger.warning(f"⚠️ Erro no Stripe (não crítico): {stripe_error}")
        
        # Atualizar no banco local
        sql_update = """
        UPDATE subscriptions 
        SET cancel_at_period_end = %s
        WHERE user_id = %s AND status = 'active'
        """
        
        update_result = await execute_sql(sql_update, (not enabled, user.user_id))
        
        if update_result["error"]:
            logger.error(f"❌ Erro ao atualizar renovação automática no banco: {update_result['error']}")
            raise Exception("Erro ao atualizar configuração")
        
        status_message = "ativada" if enabled else "desativada"
        logger.info(f"✅ Renovação automática {status_message} para usuário {user.user_id}")
        
        return {
            "success": True,
            "auto_renewal": enabled,
            "message": f"Renovação automática {status_message} com sucesso"
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao alterar renovação automática: {e}")
        raise HTTPException(status_code=500, detail="Erro ao alterar renovação automática")

@router.get("/transactions/recent")
async def get_recent_transactions(user: AuthUser = Depends(require_auth)):
    """Retorna transações recentes de COMPRAS de créditos (não consumos) - migrado para MariaDB"""
    try:
        # Buscar apenas transações de compra/adição de créditos no MariaDB
        sql = """
        SELECT id, type, amount_cents, description, created_at
        FROM credit_transactions 
        WHERE user_id = %s 
        AND type IN ('add', 'purchase')
        ORDER BY created_at DESC 
        LIMIT 10
        """
        
        result = await execute_sql(sql, (user.user_id,), "all")
        
        if result["error"]:
            logger.error(f"❌ Erro SQL ao buscar transações: {result['error']}")
            raise Exception("Erro na consulta ao banco")
        
        transactions = []
        if result["data"]:
            for transaction in result["data"]:
                # Converter Decimal para float se necessário
                amount_cents = float(transaction["amount_cents"]) if transaction["amount_cents"] else 0.0
                transactions.append({
                    "id": transaction["id"],
                    "type": transaction["type"],
                    "amount": abs(amount_cents) / 100.0,  # Converter para reais
                    "amount_cents": abs(int(amount_cents)),
                    "description": transaction["description"],
                    "created": transaction["created_at"].isoformat() if transaction["created_at"] else None,
                    "status": "completed"  # Por enquanto todas são completed
                })
        
        return {
            "transactions": transactions
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar transações no MariaDB: {e}")
        # Retornar mock em caso de erro
        return {
            "transactions": [
                {
                    "id": "mock_transaction_1",
                    "type": "purchase",
                    "amount": 29.90,
                    "amount_cents": 2990,
                    "description": "Compra de créditos - Plano Starter",
                    "created": datetime.now().isoformat(),
                    "status": "completed"
                }
            ]
        }

@router.get("/user/credits")
async def get_user_credits_endpoint(user: AuthUser = Depends(require_auth)):
    """Retorna informações completas de créditos do usuário"""
    try:
        # Importar serviço de créditos
        from api.services.credit_service import get_user_credit_summary
        
        # Buscar resumo completo dos créditos
        credit_summary = await get_user_credit_summary(user.user_id)
        
        return {
            "available": float(credit_summary["available"]),  # Garantir que é float
            "total": float(credit_summary["total_purchased"]), 
            "used": float(credit_summary["total_spent"]),
            "transaction_count": credit_summary["transaction_count"]
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar créditos do usuário: {e}")
        
        # Fallback para desenvolvimento
        return {
            "available": 10.00,
            "total": 29.90,
            "used": 19.90,
            "transaction_count": 3
        }


@router.get("/checkout-session/{session_id}")
async def get_checkout_session(
    session_id: str,
    user: AuthUser = Depends(require_auth)
):
    """
    Verifica o status de uma sessão de checkout do Stripe
    Processa assinatura manualmente se necessário (para quando webhooks não estão configurados)
    """
    try:
        # Verificar se Stripe está configurado
        if not stripe.api_key:
            raise HTTPException(
                status_code=500, 
                detail="Stripe não configurado"
            )
        
        # Buscar sessão no Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        
        logger.info(f"🔍 Checkout session recuperada: {session_id}")
        logger.info(f"   Status: {session.payment_status}")
        logger.info(f"   Customer: {session.customer}")
        logger.info(f"   Subscription: {session.subscription}")
        
        # Se pagamento foi bem-sucedido e há subscription, processar
        if (session.payment_status == 'paid' and 
            session.subscription and 
            session.customer):
            
            # Verificar se assinatura já foi processada
            check_sql = "SELECT id FROM subscriptions WHERE stripe_subscription_id = %s"
            check_result = await execute_sql(check_sql, (session.subscription,), "one")
            
            if not check_result.get("data"):
                # Processar assinatura manualmente
                await process_subscription_manually(session)
                logger.info(f"✅ Assinatura processada manualmente: {session.subscription}")
            else:
                logger.info(f"ℹ️ Assinatura já existe no banco: {session.subscription}")
        
            return {
            "session_id": session_id,
            "payment_status": session.payment_status,
            "customer_id": session.customer,
            "subscription_id": session.subscription,
            "amount_total": session.amount_total,
            "currency": session.currency,
            "metadata": session.metadata
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"❌ Erro Stripe ao buscar sessão: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Erro do Stripe: {str(e)}"
        )
    except Exception as e:
        logger.error(f"❌ Erro ao verificar checkout session: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao verificar sessão"
        )


async def cancel_previous_subscriptions(customer_id: str, current_subscription_id: str):
    """
    Cancela todas as assinaturas anteriores do mesmo cliente
    Mantém apenas a assinatura mais recente ativa
    """
    try:
        logger.info(f"🔄 Cancelando assinaturas anteriores para customer: {customer_id}")
        
        # Buscar usuário pelo stripe_customer_id
        user_sql = "SELECT id FROM users WHERE stripe_customer_id = %s"
        user_result = await execute_sql(user_sql, (customer_id,), "one")
        
        if not user_result.get("data"):
            logger.warning(f"⚠️ Usuário não encontrado para customer_id: {customer_id}")
            return
        
        user_id = user_result["data"]["id"]
        
        # Buscar assinaturas ativas do usuário (exceto a atual)
        subscriptions_sql = """
        SELECT stripe_subscription_id 
        FROM subscriptions 
        WHERE user_id = %s AND status = 'active' AND stripe_subscription_id != %s
        """
        
        subscriptions_result = await execute_sql(subscriptions_sql, (user_id, current_subscription_id), "all")
        
        if not subscriptions_result.get("data"):
            logger.info(f"ℹ️ Nenhuma assinatura anterior encontrada para cancelar")
            return
        
        # Cancelar cada assinatura anterior
        for sub in subscriptions_result["data"]:
            stripe_subscription_id = sub["stripe_subscription_id"]
            
            try:
                # Cancelar no Stripe
                stripe.Subscription.modify(
                    stripe_subscription_id,
                    cancel_at_period_end=True
                )
                
                # Atualizar status no banco local
                update_sql = """
                UPDATE subscriptions 
                SET status = 'canceled', cancel_at_period_end = 1, updated_at = %s
                WHERE stripe_subscription_id = %s
                """
                
                await execute_sql(update_sql, (datetime.now(), stripe_subscription_id), "none")
                
                logger.info(f"✅ Assinatura anterior cancelada: {stripe_subscription_id}")
                
            except Exception as e:
                logger.error(f"❌ Erro ao cancelar assinatura {stripe_subscription_id}: {e}")
                continue
        
        logger.info(f"✅ Processo de cancelamento de assinaturas anteriores concluído")
        
    except Exception as e:
        logger.error(f"❌ Erro ao cancelar assinaturas anteriores: {e}")


async def process_subscription_manually(session):
    """
    Processa assinatura manualmente quando webhooks não estão disponíveis
    IMPLEMENTAÇÃO: Sistema de upgrade/downgrade automático
    """
    try:
        # Buscar dados completos da subscription no Stripe
        subscription = stripe.Subscription.retrieve(session.subscription)
        customer = stripe.Customer.retrieve(session.customer)
        
        logger.info(f"📋 Processando assinatura manual:")
        logger.info(f"   Subscription ID: {subscription.id}")
        logger.info(f"   Customer: {customer.email}")
        logger.info(f"   Status: {subscription.status}")
        
        # ✅ NOVA LÓGICA: Cancelar assinaturas anteriores do mesmo usuário
        await cancel_previous_subscriptions(session.customer, subscription.id)
        # Acessar price via items list (Stripe v6.5.0)
        # Corrigir acesso aos items da subscription - múltiplas abordagens
        first_item = None
        price_amount_cents = 0
        
        try:
            # ✅ CORREÇÃO: Usar a API correta do Stripe para acessar items
            # Na versão atual do Stripe, items é um objeto que precisa ser listado
            items = stripe.SubscriptionItem.list(subscription=subscription.id)
            
            if not items.data or len(items.data) == 0:
                logger.error("❌ Nenhum item encontrado na subscription")
                return
            
            first_item = items.data[0]
            price_amount_cents = first_item.price.unit_amount
            logger.info(f"   Amount: {price_amount_cents}")
                
        except Exception as items_error:
            logger.error(f"❌ Erro ao acessar items da subscription: {items_error}")
            logger.error(f"❌ Tipo de subscription.items: {type(subscription.items)}")
            logger.error(f"❌ Atributos de subscription.items: {dir(subscription.items)}")
            return
        
        # Buscar usuário no MariaDB pelo stripe_customer_id
        user_sql = "SELECT id, email FROM users WHERE stripe_customer_id = %s"
        user_result = await execute_sql(user_sql, (session.customer,), "one")
        
        logger.info(f"🔍 Buscando usuário para customer_id: {session.customer}")
        logger.info(f"🔍 Resultado da busca: {user_result}")
        
        if not user_result.get("data"):
            logger.error(f"❌ Usuário não encontrado para customer_id: {session.customer}")
            return
        
        user = user_result["data"]
        user_id = user["id"]
        
        logger.info(f"✅ Usuário encontrado: {user['email']} (ID: {user_id})")
        
        # Determinar plano baseado no valor pago (já definido acima)
        
        # Mapear valores para planos existentes
        plan_mapping = {
            10000: "starter",      # R$ 100,00
            20000: "professional", # R$ 200,00  
            30000: "enterprise"    # R$ 300,00
        }
        
        plan_code = plan_mapping.get(price_amount_cents, "custom")
        
        logger.info(f"💰 Valor do plano: {price_amount_cents} centavos → código: {plan_code}")
        
        # Buscar plano correspondente ou criar personalizado
        plan_sql = "SELECT id FROM subscription_plans WHERE code = %s LIMIT 1"
        plan_result = await execute_sql(plan_sql, (plan_code,), "one")
        
        logger.info(f"🔍 Busca do plano '{plan_code}': {plan_result}")
        
        if not plan_result.get("data"):
            # Criar plano personalizado se não existir
            from api.database.connection import generate_uuid
            plan_id = generate_uuid()
            plan_name = f"Plano R$ {price_amount_cents/100:.2f}"
            
            # ✅ CORREÇÃO: Incluir stripe_product_id, stripe_price_id e user_id
            create_plan_sql = """
            INSERT INTO subscription_plans 
            (id, code, name, description, price_cents, credits_included_cents, 
             stripe_product_id, stripe_price_id, user_id, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
            """
            await execute_sql(create_plan_sql, (
                plan_id, 
                plan_code, 
                plan_name, 
                f"Plano personalizado de R$ {price_amount_cents/100:.2f} via Stripe", 
                price_amount_cents, 
                price_amount_cents,
                subscription.id,  # stripe_product_id
                first_item.price.id,  # stripe_price_id
                user_id  # user_id para isolamento
            ), "none")
            logger.info(f"✅ Plano '{plan_code}' criado: {plan_id}")
        else:
            plan_id = plan_result["data"]["id"]
            logger.info(f"✅ Usando plano existente '{plan_code}': {plan_id}")
            
            # ✅ CORREÇÃO: Atualizar stripe_product_id e stripe_price_id se não existirem
            update_plan_sql = """
            UPDATE subscription_plans 
            SET stripe_product_id = %s, stripe_price_id = %s, updated_at = %s
            WHERE id = %s AND (stripe_product_id IS NULL OR stripe_price_id IS NULL)
            """
            await execute_sql(update_plan_sql, (
                subscription.id,
                first_item.price.id,
                datetime.now(),
                plan_id
            ), "none")
            logger.info(f"✅ Plano '{plan_code}' atualizado com IDs do Stripe")
        
        # Registrar assinatura no MariaDB
        from api.database.connection import generate_uuid
        subscription_id = generate_uuid()
        
        insert_subscription_sql = """
        INSERT INTO subscriptions 
        (id, user_id, plan_id, status, stripe_subscription_id, stripe_price_id, 
         current_period_start, current_period_end, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        subscription_data = (
            subscription_id,
            user_id,
            plan_id,
            subscription.status,
            subscription.id,
            first_item.price.id,
            datetime.fromtimestamp(subscription.current_period_start),
            datetime.fromtimestamp(subscription.current_period_end),
            datetime.now()
        )
        
        subscription_result = await execute_sql(insert_subscription_sql, subscription_data, "none")
        
        if subscription_result["error"]:
            logger.error(f"❌ Erro ao inserir assinatura: {subscription_result['error']}")
            return
        
        logger.info(f"✅ Assinatura registrada no MariaDB: {subscription_id}")
        
        # Adicionar créditos equivalentes ao valor pago
        price_amount = first_item.price.unit_amount / 100.0
        description = f"Créditos da assinatura - R$ {price_amount:.2f}"
        
        from api.services.credit_service import add_user_credits
        
        credit_result = await add_user_credits(
            user_id=user_id,
            amount=price_amount,
            description=description,
            stripe_invoice_id=subscription.latest_invoice if subscription.latest_invoice else None
        )
        
        logger.info(f"✅ Créditos adicionados: R$ {price_amount:.2f} para {user['email']}")
        logger.info(f"💳 Novo saldo: R$ {credit_result['new_balance']:.2f}")
        
        return {
            "subscription_id": subscription_id,
            "stripe_subscription_id": subscription.id,
            "credits_added": price_amount,
            "new_balance": credit_result['new_balance']
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar assinatura manualmente: {e}")
        logger.error(f"❌ Tipo do erro: {type(e).__name__}")
        logger.error(f"❌ Detalhes do erro: {str(e)}")
        raise


@router.post("/create-custom-subscription")
async def create_custom_subscription(
    request: CustomPlanRequest,
    user: AuthUser = Depends(require_auth)
):
    """
    Cria uma assinatura personalizada com valor definido pelo usuário
    Cria produto e preço dinâmicos no Stripe
    """
    try:
        # Validar valor mínimo
        if request.amount < 10.0:
            raise HTTPException(
                status_code=400, 
                detail="Valor mínimo para plano personalizado: R$ 10,00"
            )
        
        if request.amount > 10000.0:
            raise HTTPException(
                status_code=400, 
                detail="Valor máximo para plano personalizado: R$ 10.000,00"
            )
        
        logger.info(f"🎨 Criando plano personalizado: R$ {request.amount:.2f} para {user.email}")
        
        # Buscar ou criar cliente no Stripe
        customer_id = await get_or_create_stripe_customer(user)
        
        # Criar produto personalizado no Stripe
        product_name = f"Créditos Personalizados R$ {request.amount:.2f}"
        product_description = f"Plano personalizado de R$ {request.amount:.2f} em créditos mensais"
        
        product = stripe.Product.create(
            name=product_name,
            description=product_description,
            metadata={
                "custom_plan": "true",
                "user_id": user.user_id,
                "user_email": user.email,
                "amount_brl": str(request.amount)
            }
        )
        
        # Criar preço recorrente para o produto
        price = stripe.Price.create(
            unit_amount=int(request.amount * 100),  # Converter para centavos
            currency='brl',
            recurring={'interval': 'month'},
            product=product.id,
            metadata={
                "custom_plan": "true",
                "user_id": user.user_id,
                "amount_brl": str(request.amount)
            }
        )
        
        logger.info(f"✅ Produto personalizado criado: {product.id}, Preço: {price.id}")
        
        # Criar sessão de checkout com o novo preço
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{
                'price': price.id,
                'quantity': 1,
            }],
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            metadata={
                'user_id': user.user_id,
                'user_email': user.email,
                'custom_plan': 'true',
                'amount_brl': str(request.amount)
            },
            subscription_data={
                'metadata': {
                    'user_id': user.user_id,
                    'user_email': user.email,
                    'custom_plan': 'true',
                    'amount_brl': str(request.amount)
                }
            }
        )
        
        logger.info(f"✅ Checkout personalizado criado: {session.id}")
        
        return {
            "checkout_url": session.url,
            "session_id": session.id,
            "product_id": product.id,
            "price_id": price.id,
            "amount": request.amount,
            "currency": "BRL"
        }
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except stripe.error.StripeError as e:
        logger.error(f"❌ Erro Stripe ao criar plano personalizado: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Erro do Stripe: {str(e)}"
        )
    except Exception as e:
        logger.error(f"❌ Erro geral ao criar plano personalizado: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao criar plano personalizado"
        )







@router.get("/check-active-subscriptions")
async def check_active_subscriptions():
    """
    Endpoint para verificar todas as assinaturas ativas (sem autenticação para debug)
    """
    try:
        # Buscar todas as assinaturas ativas no banco
        sql = """
        SELECT 
            s.id, s.status, s.stripe_subscription_id, s.current_period_end,
            sp.name as plan_name, sp.price_cents, sp.code
        FROM subscriptions s
        JOIN subscription_plans sp ON s.plan_id = sp.id
        WHERE s.status = 'active'
        ORDER BY s.created_at DESC
        """
        
        result = await execute_sql(sql, (), "all")
        
        if result["error"]:
            return {"success": False, "error": result["error"]}
        
        subscriptions = []
        total_monthly_cost = 0
        
        if result["data"]:
            for sub in result["data"]:
                price_reais = sub["price_cents"] / 100
                total_monthly_cost += price_reais
                
                subscriptions.append({
                    "id": sub["id"],
                    "stripe_subscription_id": sub["stripe_subscription_id"],
                    "plan_name": sub["plan_name"],
                    "plan_code": sub["code"],
                    "price_reais": price_reais,
                    "status": sub["status"],
                    "current_period_end": sub["current_period_end"].isoformat() if sub["current_period_end"] else None
                })
        
        return {
            "success": True,
            "active_subscriptions": subscriptions,
            "total_count": len(subscriptions),
            "total_monthly_cost": total_monthly_cost,
            "warning": f"Você será cobrado R$ {total_monthly_cost:.2f} por mês" if total_monthly_cost > 0 else "Nenhuma assinatura ativa"
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar assinaturas: {e}")
        return {"success": False, "error": str(e)}

@router.post("/create-dynamic-product")
async def create_dynamic_product(request: dict, user: AuthUser = Depends(require_auth)):
    """
    ✅ NOVO: Cria produto e preço automaticamente no Stripe para valor personalizado
    """
    try:
        amount = request.get("amount")
        success_url = request.get("success_url")
        cancel_url = request.get("cancel_url")
        
        if not amount or amount < 10 or amount > 10000:
            raise HTTPException(status_code=400, detail="Valor deve estar entre R$ 10,00 e R$ 10.000,00")
        
        logger.info(f"🎯 Criando produto dinâmico para usuário {user.email} - valor: R$ {amount:.2f}")
        
        # ✅ STEP 1: Criar produto no Stripe
        product_name = f"Plano R$ {amount:.2f}"
        product_description = f"Plano personalizado de R$ {amount:.2f} em créditos mensais"
        
        # Usar MCP para criar produto
        from api.main import app
        import stripe
        
        product = stripe.Product.create(
            name=product_name,
            description=product_description,
            type="service",
            metadata={
                "custom_plan": "true",
                "user_id": user.user_id,
                "user_email": user.email
            }
        )
        
        logger.info(f"✅ Produto criado: {product.id}")
        
        # ✅ STEP 2: Criar preço recorrente no Stripe
        price = stripe.Price.create(
            product=product.id,
            unit_amount=int(amount * 100),  # Converter para centavos
            currency="brl",
            recurring={"interval": "month"}
        )
        
        logger.info(f"✅ Preço criado: {price.id} (R$ {amount:.2f}/mês)")
        
        # ✅ STEP 2.5: Salvar plano no banco local com user_id
        from api.database.connection import generate_uuid
        plan_id = generate_uuid()
        
        save_plan_sql = """
        INSERT INTO subscription_plans 
        (id, code, name, description, price_cents, credits_included_cents, 
         stripe_product_id, stripe_price_id, user_id, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
        """
        
        await execute_sql(save_plan_sql, (
            plan_id,
            "custom",
            product_name,
            product_description,
            int(amount * 100),  # Converter para centavos
            int(amount * 100),  # 1:1 - cada R$ pago vira R$ em créditos
            product.id,
            price.id,
            user.user_id  # Isolamento por usuário
        ), "none")
        
        logger.info(f"✅ Plano salvo no banco local: {plan_id}")
        
        # ✅ STEP 3: Obter ou criar cliente Stripe
        stripe_customer_id = await get_or_create_stripe_customer(user)
        
        # ✅ STEP 4: Criar sessão de checkout
        checkout_session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price": price.id,
                "quantity": 1,
            }],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            allow_promotion_codes=True,
            billing_address_collection="required",
            metadata={
                "user_id": user.user_id,
                "plan_type": "dynamic_custom",
                "credit_amount": str(amount)
            }
        )
        
        logger.info(f"🛒 Checkout criado: {checkout_session.id}")
        
        return {
            "success": True,
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id,
            "product_id": product.id,
            "price_id": price.id,
            "amount": amount
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"❌ Erro Stripe ao criar produto dinâmico: {e}")
        raise HTTPException(status_code=400, detail=f"Erro do Stripe: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Erro geral ao criar produto dinâmico: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao criar produto dinâmico")
