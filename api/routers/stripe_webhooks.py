"""
Webhooks do Stripe para processar eventos de pagamento e assinaturas
Automatiza a adição de créditos quando pagamentos são processados
"""
import os
import stripe
from fastapi import APIRouter, Request, HTTPException
import structlog
from datetime import datetime

from api.services.credit_service import add_user_credits, get_user_balance
from api.database.connection import execute_sql

logger = structlog.get_logger(__name__)

# Configurar Stripe e webhook
stripe_secret_key = os.getenv("STRIPE_API_KEY_SECRETA")
if not stripe_secret_key:
    logger.warning("⚠️ STRIPE_API_KEY_SECRETA não configurada no .env")
else:
    stripe.api_key = stripe_secret_key
    logger.info("✅ Stripe API configurada para webhooks")

webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
router = APIRouter(prefix="/stripe", tags=["stripe-webhooks"])


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Endpoint para receber webhooks do Stripe
    Processa eventos de pagamento e assinaturas automaticamente
    """
    try:
        # Obter payload e assinatura
        payload = await request.body()
        sig_header = request.headers.get('Stripe-Signature')
        
        if not sig_header:
            logger.error("❌ Stripe-Signature header ausente")
            raise HTTPException(status_code=400, detail="Stripe-Signature header missing")
        
        # Verificar assinatura do webhook
        try:
            if webhook_secret:
                event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
            else:
                # Para desenvolvimento sem webhook secret configurado
                logger.warning("⚠️ STRIPE_WEBHOOK_SECRET não configurado - usando payload direto")
                import json
                event = json.loads(payload)
        except ValueError:
            logger.error("❌ Payload inválido do webhook")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError:
            logger.error("❌ Assinatura inválida do webhook")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Log do evento recebido
        event_type = event['type']
        event_id = event['id']
        logger.info(f"🔔 Webhook recebido: {event_type} (ID: {event_id})")
        
        # Registrar webhook no banco para auditoria
        await log_webhook_event(event_id, event_type, event)
        
        # Processar diferentes tipos de eventos
        if event_type == 'invoice.payment_succeeded':
            await handle_payment_succeeded(event['data']['object'])
        
        elif event_type == 'customer.subscription.created':
            await handle_subscription_created(event['data']['object'])
        
        elif event_type == 'customer.subscription.updated':
            await handle_subscription_updated(event['data']['object'])
        
        elif event_type == 'customer.subscription.deleted':
            await handle_subscription_canceled(event['data']['object'])
        
        elif event_type == 'invoice.payment_failed':
            await handle_payment_failed(event['data']['object'])
        
        else:
            logger.info(f"ℹ️ Evento não processado: {event_type}")
        
        # Marcar webhook como processado
        await mark_webhook_processed(event_id)
        
        return {"status": "success", "event_type": event_type}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro no webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook error: {str(e)}")


async def cancel_previous_subscriptions_webhook(customer_id: str, current_subscription_id: str):
    """
    Cancela todas as assinaturas anteriores do mesmo cliente (versão webhook)
    Mantém apenas a assinatura mais recente ativa
    """
    try:
        logger.info(f"🔄 [WEBHOOK] Cancelando assinaturas anteriores para customer: {customer_id}")
        
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
            logger.info(f"ℹ️ [WEBHOOK] Nenhuma assinatura anterior encontrada para cancelar")
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
                
                logger.info(f"✅ [WEBHOOK] Assinatura anterior cancelada: {stripe_subscription_id}")
                
            except Exception as e:
                logger.error(f"❌ [WEBHOOK] Erro ao cancelar assinatura {stripe_subscription_id}: {e}")
                continue
        
        logger.info(f"✅ [WEBHOOK] Processo de cancelamento de assinaturas anteriores concluído")
        
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Erro ao cancelar assinaturas anteriores: {e}")


async def handle_payment_succeeded(invoice):
    """
    Processa pagamentos bem-sucedidos
    Adiciona créditos equivalentes ao valor pago
    """
    try:
        customer_id = invoice['customer']
        amount_paid_cents = invoice['amount_paid']
        amount_paid = amount_paid_cents / 100.0  # Converter de centavos para reais
        invoice_id = invoice['id']
        
        logger.info(f"💰 Pagamento bem-sucedido: R$ {amount_paid:.2f} (Invoice: {invoice_id})")
        
        # Buscar usuário pelo stripe_customer_id
        user = await get_user_by_stripe_customer(customer_id)
        if not user:
            logger.error(f"❌ Usuário não encontrado para customer_id: {customer_id}")
            return
        
        # Adicionar créditos equivalentes ao valor pago (1:1)
        description = f"Assinatura mensal - Créditos R$ {amount_paid:.2f}"
        
        credit_result = await add_user_credits(
            user_id=user["id"],
            amount=amount_paid,
            description=description,
            stripe_invoice_id=invoice_id
        )
        
        logger.info(f"✅ Créditos adicionados: R$ {amount_paid:.2f} para {user['email']}")
        logger.info(f"💳 Novo saldo: R$ {credit_result['new_balance']:.2f}")
        
        # Opcional: Enviar notificação por email ou push notification
        # await send_payment_success_notification(user, amount_paid, credit_result['new_balance'])
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar pagamento bem-sucedido: {e}")


async def handle_subscription_created(subscription):
    """
    Processa criação de novas assinaturas
    IMPLEMENTAÇÃO: Sistema de upgrade/downgrade automático
    """
    try:
        customer_id = subscription['customer']
        subscription_id = subscription['id']
        status = subscription['status']
        
        logger.info(f"🔄 Nova assinatura criada: {subscription_id} (Status: {status})")
        
        # ✅ NOVA LÓGICA: Cancelar assinaturas anteriores do mesmo usuário
        await cancel_previous_subscriptions_webhook(customer_id, subscription_id)
        
        # Buscar usuário
        user = await get_user_by_stripe_customer(customer_id)
        if not user:
            logger.error(f"❌ Usuário não encontrado para customer_id: {customer_id}")
            return
        
        # Atualizar dados da assinatura no MariaDB se necessário
        # Verificar se já existe registro da assinatura
        check_sql = "SELECT id FROM subscriptions WHERE stripe_subscription_id = %s"
        check_result = await execute_sql(check_sql, (subscription_id,), "one")
        
        if not check_result["data"]:
            # Criar registro da assinatura no MariaDB
            insert_sql = """
            INSERT INTO subscriptions 
            (id, user_id, stripe_subscription_id, status, current_period_start, current_period_end, created_at)
            VALUES (UUID(), %s, %s, %s, %s, %s, %s)
            """
            
            from api.database.connection import generate_uuid
            insert_result = await execute_sql(insert_sql, (
                user["id"],
                subscription_id,
                status,
                datetime.fromtimestamp(subscription['current_period_start']),
                datetime.fromtimestamp(subscription['current_period_end']),
                datetime.now()
            ), "none")
            
            if insert_result["error"]:
                logger.error(f"❌ Erro ao registrar assinatura: {insert_result['error']}")
            else:
                logger.info(f"✅ Assinatura registrada no MariaDB: {subscription_id}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar nova assinatura: {e}")


async def handle_subscription_updated(subscription):
    """
    Processa atualizações de assinaturas
    """
    try:
        subscription_id = subscription['id']
        status = subscription['status']
        
        logger.info(f"🔄 Assinatura atualizada: {subscription_id} (Status: {status})")
        
        # Atualizar status no MariaDB
        update_sql = """
        UPDATE subscriptions 
        SET status = %s, 
            current_period_start = %s, 
            current_period_end = %s,
            updated_at = %s
        WHERE stripe_subscription_id = %s
        """
        
        update_result = await execute_sql(update_sql, (
            status,
            datetime.fromtimestamp(subscription['current_period_start']),
            datetime.fromtimestamp(subscription['current_period_end']),
            datetime.now(),
            subscription_id
        ), "none")
        
        if update_result["error"]:
            logger.error(f"❌ Erro ao atualizar assinatura: {update_result['error']}")
        else:
            logger.info(f"✅ Status da assinatura atualizado no MariaDB: {subscription_id}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar assinatura: {e}")


async def handle_subscription_canceled(subscription):
    """
    Processa cancelamento de assinaturas
    """
    try:
        subscription_id = subscription['id']
        customer_id = subscription['customer']
        
        logger.info(f"❌ Assinatura cancelada: {subscription_id}")
        
        # Buscar usuário
        user = await get_user_by_stripe_customer(customer_id)
        if user:
            logger.info(f"📧 Assinatura cancelada para: {user['email']}")
            
            # Atualizar status no MariaDB
            cancel_sql = """
            UPDATE subscriptions 
            SET status = 'canceled', updated_at = %s
            WHERE stripe_subscription_id = %s
            """
            
            cancel_result = await execute_sql(cancel_sql, (datetime.now(), subscription_id), "none")
            
            if cancel_result["error"]:
                logger.error(f"❌ Erro ao cancelar assinatura: {cancel_result['error']}")
            else:
                logger.info(f"✅ Assinatura cancelada no MariaDB: {subscription_id}")
            
            # Opcional: Enviar email de cancelamento
            # await send_subscription_canceled_notification(user)
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar cancelamento: {e}")


async def handle_payment_failed(invoice):
    """
    Processa falhas de pagamento
    """
    try:
        customer_id = invoice['customer']
        amount_due = invoice['amount_due'] / 100.0
        
        logger.warning(f"⚠️ Falha no pagamento: R$ {amount_due:.2f}")
        
        # Buscar usuário
        user = await get_user_by_stripe_customer(customer_id)
        if user:
            logger.warning(f"📧 Falha no pagamento para: {user['email']}")
            
            # Opcional: Enviar notificação de falha no pagamento
            # await send_payment_failed_notification(user, amount_due)
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar falha no pagamento: {e}")


async def get_user_by_stripe_customer(stripe_customer_id: str) -> dict:
    """
    Busca usuário pelo stripe_customer_id - migrado para MariaDB
    """
    try:
        sql = "SELECT id, email, name, credits FROM users WHERE stripe_customer_id = %s"
        result = await execute_sql(sql, (stripe_customer_id,), "one")
        
        if result["error"]:
            logger.error(f"❌ Erro SQL ao buscar usuário: {result['error']}")
            return None
        
        if result["data"]:
            return result["data"]
        else:
            logger.warning(f"⚠️ Usuário não encontrado para stripe_customer_id: {stripe_customer_id}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Erro ao buscar usuário por stripe_customer_id: {e}")
        return None


async def log_webhook_event(event_id: str, event_type: str, event_data: dict):
    """
    Registra evento de webhook para auditoria - migrado para MariaDB
    """
    try:
        # Verificar se evento já foi processado (evitar duplicatas)
        check_sql = "SELECT id FROM stripe_webhook_logs WHERE event_id = %s"
        check_result = await execute_sql(check_sql, (event_id,), "one")
        
        if not check_result["data"]:
            # Inserir novo webhook log no MariaDB
            insert_sql = """
            INSERT INTO stripe_webhook_logs 
            (id, event_id, event_type, webhook_data, processed, created_at)
            VALUES (UUID(), %s, %s, %s, %s, %s)
            """
            
            import json
            webhook_data_json = json.dumps(event_data)
            
            insert_result = await execute_sql(insert_sql, (
                event_id,
                event_type,
                webhook_data_json,
                False,
                datetime.now()
            ), "none")
            
            if insert_result["error"]:
                logger.error(f"❌ Erro ao registrar webhook: {insert_result['error']}")
            else:
                logger.info(f"📝 Webhook registrado no MariaDB: {event_id}")
        else:
            logger.info(f"ℹ️ Webhook já existente: {event_id}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao registrar webhook: {e}")


async def mark_webhook_processed(event_id: str):
    """
    Marca webhook como processado - migrado para MariaDB
    """
    try:
        update_sql = """
        UPDATE stripe_webhook_logs 
        SET processed = %s, processed_at = %s
        WHERE event_id = %s
        """
        
        update_result = await execute_sql(update_sql, (True, datetime.now(), event_id), "none")
        
        if update_result["error"]:
            logger.error(f"❌ Erro ao marcar webhook processado: {update_result['error']}")
        else:
            logger.info(f"✅ Webhook marcado como processado no MariaDB: {event_id}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao marcar webhook processado: {e}")


# Endpoint de teste para verificar se webhooks estão funcionando
@router.get("/webhook/test")
async def test_webhook():
    """Endpoint de teste para verificar se o webhook está funcionando"""
    return {
        "status": "webhook endpoint active",
        "timestamp": datetime.utcnow().isoformat(),
        "webhook_secret_configured": bool(webhook_secret)
    }
