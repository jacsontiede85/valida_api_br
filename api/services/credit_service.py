"""
Serviço para gerenciamento de créditos e renovação automática
"""
import structlog
import stripe
import os
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from fastapi import HTTPException

from api.middleware.auth_middleware import get_supabase_client

logger = structlog.get_logger("credit_service")

# Configurar Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class InsufficientCreditsError(Exception):
    """Erro quando usuário não tem créditos suficientes e renovação falhou"""
    pass

class CreditService:
    def __init__(self):
        self.supabase = get_supabase_client()
    
    async def get_user_credits(self, user_id: str) -> Dict[str, Any]:
        """
        Obtém informações de crédito do usuário
        """
        try:
            response = self.supabase.table("user_credits").select("*").eq("user_id", user_id).execute()
            
            if response.data:
                return response.data[0]
            else:
                # Criar registro inicial de créditos
                return await self.create_initial_credits(user_id)
                
        except Exception as e:
            logger.error("erro_obter_creditos", user_id=user_id, error=str(e))
            raise
    
    async def create_initial_credits(self, user_id: str) -> Dict[str, Any]:
        """
        Cria registro inicial de créditos para novo usuário
        """
        try:
            initial_credits = {
                "user_id": user_id,
                "available_credits_cents": 1000,  # R$ 10,00 de boas-vindas
                "total_purchased_cents": 1000,
                "total_used_cents": 0,
                "auto_renewal_count": 0
            }
            
            response = self.supabase.table("user_credits").insert(initial_credits).execute()
            
            # Registrar transação de boas-vindas
            await self.log_credit_transaction(
                user_id=user_id,
                transaction_type="purchase",
                amount_cents=1000,
                balance_after_cents=1000,
                description="Créditos de boas-vindas",
                stripe_payment_id=None
            )
            
            logger.info("creditos_iniciais_criados", user_id=user_id, credits=1000)
            return response.data[0]
            
        except Exception as e:
            logger.error("erro_criar_creditos_iniciais", user_id=user_id, error=str(e))
            raise
    
    async def check_and_renew_credits(self, user_id: str, required_credits_cents: int) -> bool:
        """
        Verifica se usuário tem créditos suficientes
        Se não tiver, tenta renovar automaticamente
        
        Args:
            user_id: ID do usuário
            required_credits_cents: Créditos necessários em centavos
            
        Returns:
            bool: True se tem créditos suficientes (após possível renovação)
            
        Raises:
            InsufficientCreditsError: Se não conseguiu renovar
        """
        try:
            # Obter créditos atuais
            user_credits = await self.get_user_credits(user_id)
            current_balance = user_credits["available_credits_cents"]
            
            logger.info("verificando_creditos", 
                       user_id=user_id,
                       saldo_atual=current_balance,
                       necessario=required_credits_cents)
            
            # Se tem créditos suficientes, retornar OK
            if current_balance >= required_credits_cents:
                return True
            
            # Créditos insuficientes - tentar renovação automática
            logger.info("creditos_insuficientes_tentando_renovacao", 
                       user_id=user_id,
                       deficit=required_credits_cents - current_balance)
            
            success = await self.process_auto_renewal(user_id)
            
            if not success:
                raise InsufficientCreditsError(
                    f"Créditos insuficientes (R$ {current_balance/100:.2f}) e falha na renovação automática"
                )
            
            return True
            
        except InsufficientCreditsError:
            raise
        except Exception as e:
            logger.error("erro_verificar_creditos", user_id=user_id, error=str(e))
            raise InsufficientCreditsError(f"Erro no sistema de créditos: {str(e)}")
    
    async def process_auto_renewal(self, user_id: str) -> bool:
        """
        Processa renovação automática de créditos
        
        Args:
            user_id: ID do usuário
            
        Returns:
            bool: True se renovação foi bem-sucedida
        """
        try:
            # Obter plano do usuário
            subscription = await self.get_user_subscription(user_id)
            if not subscription or not subscription.get("auto_renewal_enabled", True):
                logger.warning("renovacao_automatica_desabilitada", user_id=user_id)
                return False
            
            # Obter detalhes do plano
            plan = await self.get_subscription_plan(subscription["plan_id"])
            if not plan:
                logger.error("plano_nao_encontrado", user_id=user_id, plan_id=subscription["plan_id"])
                return False
            
            renewal_amount = plan["price_cents"]
            credits_to_add = plan["credits_included_cents"]
            
            logger.info("iniciando_renovacao_automatica",
                       user_id=user_id,
                       plano=plan["name"],
                       valor=renewal_amount,
                       creditos=credits_to_add)
            
            # Processar pagamento no Stripe
            stripe_payment_id = await self.process_stripe_payment(
                user_id=user_id,
                amount_cents=renewal_amount,
                description=f"Renovação automática - {plan['name']}"
            )
            
            if not stripe_payment_id:
                logger.error("falha_pagamento_stripe", user_id=user_id)
                return False
            
            # Adicionar créditos
            await self.add_credits(
                user_id=user_id,
                amount_cents=credits_to_add,
                transaction_type="auto_renewal",
                description=f"Renovação automática - {plan['name']}",
                stripe_payment_id=stripe_payment_id
            )
            
            # Atualizar contador de renovações
            await self.update_renewal_count(user_id)
            
            logger.info("renovacao_automatica_concluida",
                       user_id=user_id,
                       creditos_adicionados=credits_to_add,
                       payment_id=stripe_payment_id)
            
            return True
            
        except Exception as e:
            logger.error("erro_renovacao_automatica", user_id=user_id, error=str(e))
            return False
    
    async def process_stripe_payment(self, user_id: str, amount_cents: int, description: str) -> Optional[str]:
        """
        Processa pagamento no Stripe
        
        Returns:
            str: ID do pagamento no Stripe se bem-sucedido, None caso contrário
        """
        try:
            # Obter método de pagamento padrão do usuário
            customer_data = await self.get_stripe_customer(user_id)
            if not customer_data or not customer_data.get("default_payment_method"):
                logger.error("metodo_pagamento_nao_encontrado", user_id=user_id)
                return None
            
            # Criar Payment Intent
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency='brl',
                customer=customer_data["stripe_customer_id"],
                payment_method=customer_data["default_payment_method"],
                confirm=True,
                description=description,
                metadata={
                    "user_id": user_id,
                    "type": "auto_renewal"
                }
            )
            
            if intent.status == "succeeded":
                logger.info("pagamento_stripe_sucesso",
                           user_id=user_id,
                           amount=amount_cents,
                           payment_intent=intent.id)
                return intent.id
            else:
                logger.error("pagamento_stripe_falhou",
                           user_id=user_id,
                           status=intent.status,
                           payment_intent=intent.id)
                return None
                
        except stripe.error.CardError as e:
            logger.error("erro_cartao_stripe", user_id=user_id, error=str(e))
            return None
        except Exception as e:
            logger.error("erro_pagamento_stripe", user_id=user_id, error=str(e))
            return None
    
    async def get_stripe_customer(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém dados do cliente no Stripe
        """
        try:
            # Buscar dados do Stripe no banco (assumindo que existe uma tabela stripe_customers)
            response = self.supabase.table("users").select("stripe_customer_id, default_payment_method").eq("id", user_id).execute()
            
            if response.data and response.data[0].get("stripe_customer_id"):
                return {
                    "stripe_customer_id": response.data[0]["stripe_customer_id"],
                    "default_payment_method": response.data[0].get("default_payment_method")
                }
            
            return None
            
        except Exception as e:
            logger.error("erro_obter_cliente_stripe", user_id=user_id, error=str(e))
            return None
    
    async def add_credits(self, user_id: str, amount_cents: int, transaction_type: str = "purchase", 
                         description: str = "", stripe_payment_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Adiciona créditos ao usuário
        """
        try:
            # Obter saldo atual
            user_credits = await self.get_user_credits(user_id)
            current_balance = user_credits["available_credits_cents"]
            new_balance = current_balance + amount_cents
            
            # Atualizar saldo
            update_data = {
                "available_credits_cents": new_balance,
                "total_purchased_cents": user_credits["total_purchased_cents"] + amount_cents,
                "updated_at": datetime.now().isoformat()
            }
            
            if transaction_type == "auto_renewal":
                update_data["last_auto_renewal"] = datetime.now().isoformat()
            
            response = self.supabase.table("user_credits").update(update_data).eq("user_id", user_id).execute()
            
            # Registrar transação
            await self.log_credit_transaction(
                user_id=user_id,
                transaction_type=transaction_type,
                amount_cents=amount_cents,
                balance_after_cents=new_balance,
                description=description,
                stripe_payment_id=stripe_payment_id
            )
            
            logger.info("creditos_adicionados",
                       user_id=user_id,
                       amount=amount_cents,
                       new_balance=new_balance,
                       type=transaction_type)
            
            return response.data[0]
            
        except Exception as e:
            logger.error("erro_adicionar_creditos", user_id=user_id, error=str(e))
            raise
    
    async def deduct_credits(self, user_id: str, amount_cents: int, 
                           consultation_id: Optional[str] = None,
                           description: str = "") -> Dict[str, Any]:
        """
        Deduz créditos do usuário
        """
        try:
            # Obter saldo atual
            user_credits = await self.get_user_credits(user_id)
            current_balance = user_credits["available_credits_cents"]
            
            if current_balance < amount_cents:
                raise ValueError(f"Saldo insuficiente: {current_balance} < {amount_cents}")
            
            new_balance = current_balance - amount_cents
            
            # Atualizar saldo
            update_data = {
                "available_credits_cents": new_balance,
                "total_used_cents": user_credits["total_used_cents"] + amount_cents,
                "updated_at": datetime.now().isoformat()
            }
            
            response = self.supabase.table("user_credits").update(update_data).eq("user_id", user_id).execute()
            
            # Registrar transação
            await self.log_credit_transaction(
                user_id=user_id,
                consultation_id=consultation_id,
                transaction_type="usage",
                amount_cents=-amount_cents,  # Negativo para deduções
                balance_after_cents=new_balance,
                description=description
            )
            
            logger.info("creditos_deduzidos",
                       user_id=user_id,
                       amount=amount_cents,
                       new_balance=new_balance,
                       consultation_id=consultation_id)
            
            return response.data[0]
            
        except Exception as e:
            logger.error("erro_deduzir_creditos", user_id=user_id, error=str(e))
            raise
    
    async def log_credit_transaction(self, user_id: str, transaction_type: str, amount_cents: int, 
                                   balance_after_cents: int, description: str = "",
                                   consultation_id: Optional[str] = None,
                                   stripe_payment_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Registra transação de crédito
        """
        try:
            transaction_data = {
                "user_id": user_id,
                "consultation_id": consultation_id,
                "type": transaction_type,
                "amount_cents": amount_cents,
                "balance_after_cents": balance_after_cents,
                "description": description,
                "stripe_payment_id": stripe_payment_id,
                "created_at": datetime.now().isoformat()
            }
            
            response = self.supabase.table("credit_transactions").insert(transaction_data).execute()
            
            logger.debug("transacao_credito_registrada",
                        user_id=user_id,
                        type=transaction_type,
                        amount=amount_cents)
            
            return response.data[0]
            
        except Exception as e:
            logger.error("erro_registrar_transacao", user_id=user_id, error=str(e))
            raise
    
    async def get_user_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém assinatura ativa do usuário
        """
        try:
            response = self.supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("status", "active").execute()
            
            return response.data[0] if response.data else None
            
        except Exception as e:
            logger.error("erro_obter_assinatura", user_id=user_id, error=str(e))
            return None
    
    async def get_subscription_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém detalhes do plano de assinatura
        """
        try:
            response = self.supabase.table("subscription_plans").select("*").eq("id", plan_id).execute()
            
            return response.data[0] if response.data else None
            
        except Exception as e:
            logger.error("erro_obter_plano", plan_id=plan_id, error=str(e))
            return None
    
    async def update_renewal_count(self, user_id: str) -> bool:
        """
        Atualiza contador de renovações automáticas
        """
        try:
            # Atualizar user_credits
            self.supabase.table("user_credits").update({
                "auto_renewal_count": self.supabase.rpc("increment_renewal_count", {"user_id": user_id}),
                "updated_at": datetime.now().isoformat()
            }).eq("user_id", user_id).execute()
            
            # Atualizar subscriptions  
            self.supabase.table("subscriptions").update({
                "auto_renewal_count": self.supabase.rpc("increment_subscription_renewal", {"user_id": user_id}),
                "last_auto_renewal": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }).eq("user_id", user_id).execute()
            
            return True
            
        except Exception as e:
            logger.error("erro_atualizar_contador_renovacao", user_id=user_id, error=str(e))
            return False
    
    async def get_credit_balance_formatted(self, user_id: str) -> Dict[str, Any]:
        """
        Obtém saldo de créditos formatado para exibição
        """
        try:
            user_credits = await self.get_user_credits(user_id)
            
            return {
                "available_credits_reais": user_credits["available_credits_cents"] / 100,
                "available_credits_cents": user_credits["available_credits_cents"],
                "total_purchased_reais": user_credits["total_purchased_cents"] / 100,
                "total_used_reais": user_credits["total_used_cents"] / 100,
                "auto_renewal_count": user_credits["auto_renewal_count"],
                "last_auto_renewal": user_credits.get("last_auto_renewal")
            }
            
        except Exception as e:
            logger.error("erro_formatar_saldo", user_id=user_id, error=str(e))
            return {
                "available_credits_reais": 0.0,
                "available_credits_cents": 0,
                "total_purchased_reais": 0.0,
                "total_used_reais": 0.0,
                "auto_renewal_count": 0,
                "last_auto_renewal": None
            }
    
    async def get_credit_transactions(self, user_id: str, limit: int = 10) -> list:
        """
        Obtém transações de créditos do usuário
        """
        try:
            if not self.supabase:
                return self._generate_mock_transactions(limit)
            
            # Buscar transações recentes
            result = self.supabase.table("credit_transactions").select(
                "*"
            ).eq("user_id", user_id).order(
                "created_at", desc=True
            ).limit(limit).execute()
            
            transactions = []
            for txn in result.data:
                transactions.append({
                    "id": txn["id"],
                    "type": txn["type"],
                    "amount_cents": txn["amount_cents"],
                    "amount_formatted": f"R$ {abs(txn['amount_cents']) / 100:.2f}" if txn["amount_cents"] < 0 else f"R$ {txn['amount_cents'] / 100:.2f}",
                    "balance_after_cents": txn["balance_after_cents"],
                    "description": txn["description"],
                    "created_at": txn["created_at"],
                    "stripe_payment_id": txn.get("stripe_payment_id"),
                    "is_credit": txn["amount_cents"] > 0,
                    "is_debit": txn["amount_cents"] < 0
                })
            
            return transactions
            
        except Exception as e:
            logger.error(f"erro_buscar_transacoes user_id={user_id}: {e}")
            return self._generate_mock_transactions(limit)
    
    def _generate_mock_transactions(self, limit: int) -> list:
        """Gera transações mock para desenvolvimento"""
        transactions = [
            {
                "id": "txn-1",
                "type": "purchase",
                "amount_cents": 1000,  # R$ 10,00
                "amount_formatted": "R$ 10,00",
                "balance_after_cents": 1000,
                "description": "Créditos de boas-vindas - Migração v2.0",
                "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
                "stripe_payment_id": None,
                "is_credit": True,
                "is_debit": False
            },
            {
                "id": "txn-2",
                "type": "usage",
                "amount_cents": -20,  # -R$ 0,20
                "amount_formatted": "R$ 0,20",
                "balance_after_cents": 980,
                "description": "Consulta CNPJ 12.345.678/0001-90 (Protestos + Receita Federal)",
                "created_at": (datetime.now() - timedelta(hours=2)).isoformat(),
                "stripe_payment_id": None,
                "is_credit": False,
                "is_debit": True
            },
            {
                "id": "txn-3",
                "type": "usage",
                "amount_cents": -15,  # -R$ 0,15
                "amount_formatted": "R$ 0,15",
                "balance_after_cents": 965,
                "description": "Consulta CNPJ 98.765.432/0001-12 (Protestos)",
                "created_at": (datetime.now() - timedelta(hours=4)).isoformat(),
                "stripe_payment_id": None,
                "is_credit": False,
                "is_debit": True
            },
            {
                "id": "txn-4",
                "type": "usage",
                "amount_cents": -5,  # -R$ 0,05
                "amount_formatted": "R$ 0,05",
                "balance_after_cents": 960,
                "description": "Consulta CNPJ 11.222.333/0001-44 (Receita Federal)",
                "created_at": (datetime.now() - timedelta(hours=6)).isoformat(),
                "stripe_payment_id": None,
                "is_credit": False,
                "is_debit": True
            }
        ]
        
        return transactions[:limit]

# Instância global do serviço
credit_service = CreditService()
