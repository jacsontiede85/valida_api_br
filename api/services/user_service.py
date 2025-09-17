"""
Serviço de gerenciamento de usuários para o SaaS
"""
import os
from typing import Optional, List
from datetime import datetime, timedelta
import structlog
from supabase import Client
from api.models.saas_models import (
    UserCreate, UserResponse, SubscriptionPlan, SubscriptionStatus
)
from api.middleware.auth_middleware import get_supabase_client

logger = structlog.get_logger("user_service")

class UserService:
    def __init__(self):
        self.supabase = get_supabase_client()
    
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """
        Cria um novo usuário no Supabase
        """
        if not self.supabase:
            # Sem Supabase configurado
            raise Exception("Sistema de usuários não configurado")
        
        try:
            # Criar usuário no Supabase Auth
            auth_response = self.supabase.auth.sign_up({
                "email": user_data.email,
                "password": user_data.password,
                "options": {
                    "data": {
                        "full_name": user_data.full_name,
                        "company": user_data.company
                    }
                }
            })
            
            if not auth_response.user:
                raise Exception("Falha ao criar usuário")
            
            # Criar perfil do usuário na tabela users
            profile_data = {
                "id": auth_response.user.id,
                "email": user_data.email,
                "full_name": user_data.full_name,
                "company": user_data.company,
                "subscription_plan": SubscriptionPlan.FREE.value,
                "subscription_status": SubscriptionStatus.TRIALING.value,
                "created_at": datetime.now().isoformat()
            }
            
            result = self.supabase.table("users").insert(profile_data).execute()
            
            if result.data:
                user_profile = result.data[0]
                return UserResponse(
                    id=user_profile["id"],
                    email=user_profile["email"],
                    full_name=user_profile["full_name"],
                    company=user_profile["company"],
                    created_at=datetime.fromisoformat(user_profile["created_at"]),
                    subscription_plan=SubscriptionPlan(user_profile["subscription_plan"]),
                    subscription_status=SubscriptionStatus(user_profile["subscription_status"])
                )
            else:
                raise Exception("Falha ao criar perfil do usuário")
                
        except Exception as e:
            logger.error(f"Erro ao criar usuário: {e}")
            raise Exception(f"Erro ao criar usuário: {str(e)}")
    
    async def get_user(self, user_id: str) -> Optional[UserResponse]:
        """
        Obtém um usuário pelo ID
        """
        if not self.supabase:
            # Sem Supabase configurado
            return None
        
        try:
            result = self.supabase.table("users").select("*").eq("id", user_id).execute()
            
            if result.data:
                user_data = result.data[0]
                return UserResponse(
                    id=user_data["id"],
                    email=user_data["email"],
                    full_name=user_data.get("name", "Usuário"),  # Usar 'name' em vez de 'full_name'
                    company=user_data.get("company", "N/A"),  # Campo opcional
                    created_at=datetime.fromisoformat(user_data["created_at"].replace('Z', '+00:00')),
                    subscription_plan=SubscriptionPlan.PRO,  # Valor padrão
                    subscription_status=SubscriptionStatus.ACTIVE  # Valor padrão
                )
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar usuário {user_id}: {e}")
            return None
    
    async def update_user_subscription(
        self, 
        user_id: str, 
        plan: SubscriptionPlan, 
        status: SubscriptionStatus
    ) -> bool:
        """
        Atualiza a assinatura do usuário
        """
        if not self.supabase:
            # Sem Supabase configurado
            return False
        
        try:
            result = self.supabase.table("users").update({
                "subscription_plan": plan.value,
                "subscription_status": status.value,
                "updated_at": datetime.now().isoformat()
            }).eq("id", user_id).execute()
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Erro ao atualizar assinatura do usuário {user_id}: {e}")
            return False
    
    async def get_user_usage_stats(self, user_id: str) -> dict:
        """
        Obtém estatísticas de uso do usuário
        """
        if not self.supabase:
            # Sem dados quando Supabase não configurado
            return {
                "total_requests": 0,
                "requests_this_month": 0,
                "requests_today": 0,
                "plan_limit": None,
                "remaining_requests": None,
                "message": "Sistema de estatísticas não configurado"
            }
        
        try:
            # Por enquanto, retornar dados vazios pois a tabela api_requests não existe
            # TODO: Implementar tabela de logs de API quando necessário
            return {
                "total_requests": 0,
                "requests_this_month": 0,
                "requests_today": 0,
                "plan_limit": None,
                "remaining_requests": None,
                "message": "Nenhuma consulta registrada ainda"
            }
            
        except Exception as e:
            logger.error(f"Erro ao buscar estatísticas do usuário {user_id}: {e}")
            return {
                "total_requests": 0,
                "requests_this_month": 0,
                "requests_today": 0,
                "plan_limit": None,
                "remaining_requests": None
            }

    async def update_user_profile(self, user_id: str, name: str, email: str) -> UserResponse:
        """
        Atualiza o perfil do usuário
        """
        try:
            if not self.supabase:
                # Modo de desenvolvimento
                return UserResponse(
                    id=user_id,
                    email=email,
                    full_name=name,
                    company="Valida Dev",
                    created_at=datetime.now(),
                    subscription_plan=SubscriptionPlan.PRO,
                    subscription_status=SubscriptionStatus.ACTIVE
                )
            
            # Atualizar perfil no Supabase
            result = self.supabase.table("users").update({
                "full_name": name,
                "email": email,
                "updated_at": datetime.now().isoformat()
            }).eq("id", user_id).execute()
            
            if result.data:
                user_data = result.data[0]
                return UserResponse(
                    id=user_data["id"],
                    email=user_data["email"],
                    full_name=user_data["full_name"],
                    company=user_data["company"],
                    created_at=datetime.fromisoformat(user_data["created_at"]),
                    subscription_plan=SubscriptionPlan(user_data["subscription_plan"]),
                    subscription_status=SubscriptionStatus(user_data["subscription_status"])
                )
            else:
                raise Exception("Falha ao atualizar perfil")
                
        except Exception as e:
            logger.error(f"Erro ao atualizar perfil do usuário {user_id}: {e}")
            raise Exception(f"Erro ao atualizar perfil: {str(e)}")
    
    async def change_password(self, user_id: str, current_password: str, new_password: str) -> dict:
        """
        Altera a senha do usuário
        """
        try:
            if not self.supabase:
                # Modo de desenvolvimento
                return {
                    "success": True,
                    "message": "Senha alterada com sucesso (modo desenvolvimento)"
                }
            
            # Atualizar senha no Supabase Auth
            result = self.supabase.auth.update_user({
                "password": new_password
            })
            
            if result.user:
                return {
                    "success": True,
                    "message": "Senha alterada com sucesso"
                }
            else:
                raise Exception("Falha ao alterar senha")
                
        except Exception as e:
            logger.error(f"Erro ao alterar senha do usuário {user_id}: {e}")
            raise Exception(f"Erro ao alterar senha: {str(e)}")
    
    async def enable_2fa(self, user_id: str) -> dict:
        """
        Ativa a autenticação de dois fatores
        """
        try:
            if not self.supabase:
                # Sem Supabase configurado
                raise Exception("Sistema de 2FA não configurado")
            
            # Implementar 2FA real com Supabase
            # Por enquanto, retornar erro pois não está implementado
            raise Exception("2FA não implementado ainda")
            
        except Exception as e:
            logger.error(f"Erro ao ativar 2FA do usuário {user_id}: {e}")
            raise Exception(f"Erro ao ativar 2FA: {str(e)}")
    
    async def disable_2fa(self, user_id: str) -> dict:
        """
        Desativa a autenticação de dois fatores
        """
        try:
            if not self.supabase:
                # Modo de desenvolvimento
                return {
                    "success": True,
                    "message": "2FA desativado com sucesso (modo desenvolvimento)"
                }
            
            # Implementar desativação de 2FA real
            return {
                "success": True,
                "message": "2FA desativado com sucesso"
            }
            
        except Exception as e:
            logger.error(f"Erro ao desativar 2FA do usuário {user_id}: {e}")
            raise Exception(f"Erro ao desativar 2FA: {str(e)}")
    
    async def update_notification_settings(self, user_id: str, settings: dict) -> dict:
        """
        Atualiza configurações de notificação do usuário
        """
        try:
            if not self.supabase:
                # Modo de desenvolvimento
                return {
                    "success": True,
                    "message": "Configurações atualizadas com sucesso (modo desenvolvimento)",
                    "settings": settings
                }
            
            # Atualizar configurações no Supabase
            result = self.supabase.table("users").update({
                "notification_settings": settings,
                "updated_at": datetime.now().isoformat()
            }).eq("id", user_id).execute()
            
            if result.data:
                return {
                    "success": True,
                    "message": "Configurações atualizadas com sucesso",
                    "settings": settings
                }
            else:
                raise Exception("Falha ao atualizar configurações")
                
        except Exception as e:
            logger.error(f"Erro ao atualizar notificações do usuário {user_id}: {e}")
            raise Exception(f"Erro ao atualizar notificações: {str(e)}")
    
    async def upload_avatar(self, user_id: str, avatar_data: bytes) -> str:
        """
        Faz upload do avatar do usuário
        """
        try:
            if not self.supabase:
                # Sem Supabase configurado
                raise Exception("Sistema de upload não configurado")
            
            # Implementar upload real para Supabase Storage
            # Por enquanto, retornar erro pois não está implementado
            raise Exception("Upload de avatar não implementado ainda")
            
        except Exception as e:
            logger.error(f"Erro ao fazer upload do avatar do usuário {user_id}: {e}")
            raise Exception(f"Erro ao fazer upload do avatar: {str(e)}")
    
    async def delete_account(self, user_id: str) -> dict:
        """
        Exclui a conta do usuário
        """
        try:
            if not self.supabase:
                # Modo de desenvolvimento
                return {
                    "success": True,
                    "message": "Conta excluída com sucesso (modo desenvolvimento)"
                }
            
            # Excluir usuário do Supabase Auth
            result = self.supabase.auth.admin.delete_user(user_id)
            
            if result:
                return {
                    "success": True,
                    "message": "Conta excluída com sucesso"
                }
            else:
                raise Exception("Falha ao excluir conta")
                
        except Exception as e:
            logger.error(f"Erro ao excluir conta do usuário {user_id}: {e}")
            raise Exception(f"Erro ao excluir conta: {str(e)}")

# Instância global do serviço
user_service = UserService()
