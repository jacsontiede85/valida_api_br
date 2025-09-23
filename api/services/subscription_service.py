"""
Serviço de gerenciamento de assinaturas
MIGRADO: Supabase → MariaDB
"""
import structlog
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from api.database.connection import execute_sql

logger = structlog.get_logger("subscription_service")

class SubscriptionService:
    def __init__(self):
        # Migrado de Supabase para MariaDB - não precisa de cliente específico
        pass
    
    async def get_available_plans(self) -> List[Dict[str, Any]]:
        """
        Retorna todos os planos de assinatura disponíveis
        MIGRADO: MariaDB
        """
        try:
            # Buscar planos ativos no MariaDB
            sql = """
                SELECT id, name, description, price_cents, queries_limit, api_keys_limit, is_active
                FROM subscription_plans 
                WHERE is_active = TRUE
                ORDER BY price_cents ASC
            """
            
            result = await execute_sql(sql)
            
            if result["error"] or not result["data"]:
                logger.info("Nenhum plano de assinatura encontrado no MariaDB")
                return []
            
            # Converter dados do MariaDB para formato esperado
            plans = []
            for plan in result["data"]:
                plans.append({
                    "id": plan["id"],
                    "name": plan["name"],
                    "description": plan["description"],
                    "price": plan["price_cents"] / 100,  # Converter centavos para reais
                    "currency": "BRL",
                    "interval": "month",
                    "features": self._get_plan_features(plan),
                    "limits": {
                        "queries_per_month": plan["queries_limit"],
                        "api_keys": plan["api_keys_limit"],
                        "history_months": 12 if plan["queries_limit"] else None
                    }
                })
            
            logger.info("planos_carregados", total=len(plans))
            return plans
            
        except Exception as e:
            logger.error("erro_buscar_planos_mariadb", error=str(e))
            raise e
    
    async def get_user_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém a assinatura atual do usuário
        MIGRADO: MariaDB
        """
        try:
            # Buscar assinatura no MariaDB
            sql = """
                SELECT s.id, s.user_id, s.plan_id, s.status, 
                       s.current_period_start, s.current_period_end, 
                       s.cancel_at_period_end, s.stripe_subscription_id,
                       s.created_at, s.updated_at,
                       sp.name as plan_name, sp.price_cents
                FROM subscriptions s
                LEFT JOIN subscription_plans sp ON s.plan_id = sp.id
                WHERE s.user_id = %s
                ORDER BY s.created_at DESC
                LIMIT 1
            """
            
            result = await execute_sql(sql, (user_id,))
            
            if result["error"] or not result["data"]:
                logger.info("assinatura_nao_encontrada", user_id=user_id)
                return None
            
            subscription = result["data"][0]
            return {
                "id": subscription["id"],
                "user_id": subscription["user_id"],
                "plan_id": subscription["plan_id"],
                "plan_name": subscription["plan_name"],
                "price_cents": subscription["price_cents"],
                "status": subscription["status"],
                "current_period_start": subscription["current_period_start"].isoformat() if subscription["current_period_start"] else None,
                "current_period_end": subscription["current_period_end"].isoformat() if subscription["current_period_end"] else None,
                "cancel_at_period_end": subscription["cancel_at_period_end"],
                "stripe_subscription_id": subscription["stripe_subscription_id"],
                "created_at": subscription["created_at"].isoformat() if subscription["created_at"] else None,
                "updated_at": subscription["updated_at"].isoformat() if subscription["updated_at"] else None
            }
            
        except Exception as e:
            logger.error("erro_buscar_assinatura_mariadb", user_id=user_id, error=str(e))
            raise e
    
    async def change_subscription(self, user_id: str, plan_id: str, action: str) -> Dict[str, Any]:
        """
        Altera o plano de assinatura do usuário
        MIGRADO: MariaDB
        """
        try:
            # Verificar se o plano existe
            plan_sql = "SELECT name, price_cents FROM subscription_plans WHERE id = %s AND is_active = TRUE"
            plan_result = await execute_sql(plan_sql, (plan_id,))
            
            if plan_result["error"] or not plan_result["data"]:
                logger.error("plano_nao_encontrado", user_id=user_id, plan_id=plan_id)
                return {
                    "success": False,
                    "error": "Plano não encontrado ou inativo",
                    "plan_id": plan_id
                }
            
            plan_info = plan_result["data"][0]
            
            # Atualizar ou criar assinatura
            if action == "upgrade" or action == "downgrade" or action == "change":
                # Verificar se usuário já tem assinatura
                current_sub_sql = "SELECT id FROM subscriptions WHERE user_id = %s ORDER BY created_at DESC LIMIT 1"
                current_sub_result = await execute_sql(current_sub_sql, (user_id,))
                
                if current_sub_result["data"]:
                    # Atualizar assinatura existente
                    update_sql = """
                        UPDATE subscriptions 
                        SET plan_id = %s, 
                            status = 'active',
                            updated_at = CURRENT_TIMESTAMP,
                            cancel_at_period_end = FALSE
                        WHERE user_id = %s
                    """
                    await execute_sql(update_sql, (plan_id, user_id))
                else:
                    # Criar nova assinatura
                    from api.database.connection import generate_uuid
                    new_id = generate_uuid()
                    
                    create_sql = """
                        INSERT INTO subscriptions 
                        (id, user_id, plan_id, status, current_period_start, current_period_end)
                        VALUES (%s, %s, %s, 'active', CURRENT_TIMESTAMP, DATE_ADD(CURRENT_TIMESTAMP, INTERVAL 1 MONTH))
                    """
                    await execute_sql(create_sql, (new_id, user_id, plan_id))
            
            logger.info("assinatura_alterada", user_id=user_id, plan_id=plan_id, action=action)
            
            return {
                "success": True,
                "message": f"Plano alterado para {plan_info['name']}",
                "new_plan": plan_id,
                "plan_name": plan_info['name'],
                "action": action,
                "price_cents": plan_info['price_cents']
            }
            
        except Exception as e:
            logger.error("erro_alterar_assinatura_mariadb", user_id=user_id, plan_id=plan_id, error=str(e))
            raise e
    
    async def cancel_subscription(self, user_id: str) -> Dict[str, Any]:
        """
        Cancela a assinatura do usuário
        MIGRADO: MariaDB
        """
        try:
            # Verificar se usuário tem assinatura ativa
            check_sql = "SELECT id, status FROM subscriptions WHERE user_id = %s ORDER BY created_at DESC LIMIT 1"
            result = await execute_sql(check_sql, (user_id,))
            
            if result["error"] or not result["data"]:
                return {
                    "success": False,
                    "error": "Usuário não possui assinatura ativa"
                }
            
            subscription = result["data"][0]
            
            if subscription["status"] == "cancelled":
                return {
                    "success": False,
                    "error": "Assinatura já está cancelada"
                }
            
            # Cancelar assinatura (marcar para cancelar ao final do período)
            cancel_sql = """
                UPDATE subscriptions 
                SET cancel_at_period_end = TRUE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND id = %s
            """
            
            await execute_sql(cancel_sql, (user_id, subscription["id"]))
            
            logger.info("assinatura_cancelada", user_id=user_id, subscription_id=subscription["id"])
            
            return {
                "success": True,
                "message": "Assinatura cancelada com sucesso. Permanecerá ativa até o final do período atual.",
                "cancelled_at": datetime.now().isoformat(),
                "subscription_id": subscription["id"]
            }
            
        except Exception as e:
            logger.error("erro_cancelar_assinatura_mariadb", user_id=user_id, error=str(e))
            raise e
    
    async def reactivate_subscription(self, user_id: str) -> Dict[str, Any]:
        """
        Reativa a assinatura do usuário
        MIGRADO: MariaDB
        """
        try:
            # Verificar se usuário tem assinatura
            check_sql = """
                SELECT id, status, cancel_at_period_end 
                FROM subscriptions 
                WHERE user_id = %s 
                ORDER BY created_at DESC LIMIT 1
            """
            result = await execute_sql(check_sql, (user_id,))
            
            if result["error"] or not result["data"]:
                return {
                    "success": False,
                    "error": "Usuário não possui assinatura"
                }
            
            subscription = result["data"][0]
            
            if subscription["status"] == "active" and not subscription["cancel_at_period_end"]:
                return {
                    "success": False,
                    "error": "Assinatura já está ativa"
                }
            
            # Reativar assinatura
            reactivate_sql = """
                UPDATE subscriptions 
                SET status = 'active',
                    cancel_at_period_end = FALSE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND id = %s
            """
            
            await execute_sql(reactivate_sql, (user_id, subscription["id"]))
            
            logger.info("assinatura_reativada", user_id=user_id, subscription_id=subscription["id"])
            
            return {
                "success": True,
                "message": "Assinatura reativada com sucesso",
                "reactivated_at": datetime.now().isoformat(),
                "subscription_id": subscription["id"]
            }
            
        except Exception as e:
            logger.error("erro_reativar_assinatura_mariadb", user_id=user_id, error=str(e))
            raise e
    
    
    def _get_plan_features(self, plan: Dict[str, Any]) -> List[str]:
        """
        Gera features baseadas no plano
        """
        features = []
        
        if plan["queries_limit"]:
            features.append(f"{plan['queries_limit']:,} consultas/mês".replace(",", "."))
        else:
            features.append("Consultas ilimitadas")
        
        if plan["api_keys_limit"]:
            features.append(f"{plan['api_keys_limit']} API Keys")
        else:
            features.append("API Keys ilimitadas")
        
        features.extend([
            "Suporte por email",
            "Histórico completo",
            "Analytics avançado"
        ])
        
        return features

# Instância global do serviço
subscription_service = SubscriptionService()
