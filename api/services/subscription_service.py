"""
Serviço de gerenciamento de assinaturas
"""
import structlog
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from api.middleware.auth_middleware import get_supabase_client

logger = structlog.get_logger("subscription_service")

class SubscriptionService:
    def __init__(self):
        self.supabase = get_supabase_client()
    
    async def get_available_plans(self) -> List[Dict[str, Any]]:
        """
        Retorna todos os planos de assinatura disponíveis
        """
        try:
            if not self.supabase:
                # Sem Supabase configurado
                return []
            
            # Buscar planos no Supabase
            response = self.supabase.table("subscription_plans").select("*").eq("is_active", True).execute()
            
            if not response.data:
                # Se não há planos no banco, retornar vazio
                return []
            
            # Converter dados do Supabase para formato esperado
            plans = []
            for plan in response.data:
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
            
            return plans
            
        except Exception as e:
            logger.error("erro_buscar_planos", error=str(e))
            raise e
    
    async def get_user_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém a assinatura atual do usuário
        """
        try:
            if not self.supabase:
                # Retornar assinatura mock
                return {
                    "id": "sub-123",
                    "user_id": user_id,
                    "plan_id": "professional",
                    "status": "active",
                    "current_period_start": datetime.now().isoformat(),
                    "current_period_end": (datetime.now() + timedelta(days=30)).isoformat(),
                    "cancel_at_period_end": False,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
            
            # Buscar assinatura no Supabase
            response = self.supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
            
            if response.data:
                return response.data[0]
            return None
            
        except Exception as e:
            logger.error("erro_buscar_assinatura", user_id=user_id, error=str(e))
            raise e
    
    async def change_subscription(self, user_id: str, plan_id: str, action: str) -> Dict[str, Any]:
        """
        Altera o plano de assinatura do usuário
        """
        try:
            if not self.supabase:
                # Mock para mudança de plano
                return {
                    "success": True,
                    "message": f"Plano alterado para {plan_id}",
                    "new_plan": plan_id,
                    "action": action
                }
            
            # Implementar lógica de mudança de plano no Supabase
            # Por enquanto, retornar mock
            return {
                "success": True,
                "message": f"Plano alterado para {plan_id}",
                "new_plan": plan_id,
                "action": action
            }
            
        except Exception as e:
            logger.error("erro_alterar_assinatura", user_id=user_id, plan_id=plan_id, error=str(e))
            raise e
    
    async def cancel_subscription(self, user_id: str) -> Dict[str, Any]:
        """
        Cancela a assinatura do usuário
        """
        try:
            if not self.supabase:
                # Mock para cancelamento
                return {
                    "success": True,
                    "message": "Assinatura cancelada com sucesso",
                    "cancelled_at": datetime.now().isoformat()
                }
            
            # Implementar lógica de cancelamento no Supabase
            return {
                "success": True,
                "message": "Assinatura cancelada com sucesso",
                "cancelled_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error("erro_cancelar_assinatura", user_id=user_id, error=str(e))
            raise e
    
    async def reactivate_subscription(self, user_id: str) -> Dict[str, Any]:
        """
        Reativa a assinatura do usuário
        """
        try:
            if not self.supabase:
                # Mock para reativação
                return {
                    "success": True,
                    "message": "Assinatura reativada com sucesso",
                    "reactivated_at": datetime.now().isoformat()
                }
            
            # Implementar lógica de reativação no Supabase
            return {
                "success": True,
                "message": "Assinatura reativada com sucesso",
                "reactivated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error("erro_reativar_assinatura", user_id=user_id, error=str(e))
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
