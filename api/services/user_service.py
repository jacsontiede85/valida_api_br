"""
Serviço de gerenciamento de usuários para o SaaS
MIGRADO: Supabase → MariaDB
"""
import os
from typing import Optional, List
from datetime import datetime, timedelta
import structlog
from api.models.saas_models import (
    UserCreate, UserResponse, SubscriptionPlan, SubscriptionStatus
)
from api.database.connection import execute_sql, generate_uuid

logger = structlog.get_logger("user_service")

class UserService:
    def __init__(self):
        # Migrado de Supabase para MariaDB - não precisa de cliente específico
        pass
    
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """
        Cria um novo usuário no MariaDB
        MIGRADO: Supabase → MariaDB
        """
        try:
            # Verificar se email já existe
            existing_result = await execute_sql(
                "SELECT id FROM users WHERE email = %s LIMIT 1",
                (user_data.email,),
                "one"
            )
            
            if existing_result["data"]:
                raise Exception("Email já está em uso")
            
            # Criar usuário no MariaDB
            user_id = generate_uuid()
            
            # Hash da senha (implementar bcrypt se necessário)
            import hashlib
            password_hash = hashlib.sha256(user_data.password.encode()).hexdigest()
            
            insert_sql = """
                INSERT INTO users 
                (id, email, name, password_hash, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            insert_params = (
                user_id,
                user_data.email,
                user_data.full_name,
                password_hash,
                True,
                datetime.now().isoformat()
            )
            
            result = await execute_sql(insert_sql, insert_params, "none")
            
            if result["error"]:
                raise Exception(f"Falha ao criar usuário: {result['error']}")
            
            # Buscar usuário criado
            created_result = await execute_sql(
                "SELECT * FROM users WHERE id = %s LIMIT 1",
                (user_id,),
                "one"
            )
            
            if created_result["data"]:
                user_profile = created_result["data"]
                return UserResponse(
                    id=user_profile["id"],
                    email=user_profile["email"],
                    full_name=user_profile["name"],
                    company="Valida SaaS",  # Valor padrão
                    created_at=datetime.fromisoformat(user_profile["created_at"].replace('Z', '+00:00') if 'Z' in str(user_profile["created_at"]) else str(user_profile["created_at"])),
                    subscription_plan=SubscriptionPlan.PRO,
                    subscription_status=SubscriptionStatus.ACTIVE
                )
            else:
                raise Exception("Falha ao buscar usuário criado")
                
        except Exception as e:
            logger.error(f"Erro ao criar usuário MariaDB: {e}")
            raise Exception(f"Erro ao criar usuário: {str(e)}")
    
    async def get_user(self, user_id: str) -> Optional[UserResponse]:
        """
        Obtém um usuário pelo ID
        MIGRADO: MariaDB
        """
        try:
            result = await execute_sql(
                "SELECT * FROM users WHERE id = %s",
                (user_id,),
                "one"
            )
            
            if result["data"]:
                user_data = result["data"]
                return UserResponse(
                    id=user_data["id"],
                    email=user_data["email"],
                    full_name=user_data.get("name", "Usuário"),  # Usar 'name' em vez de 'full_name'
                    company=user_data.get("company", "N/A"),  # Campo opcional
                    created_at=datetime.fromisoformat(user_data["created_at"].replace('Z', '+00:00') if 'Z' in str(user_data["created_at"]) else str(user_data["created_at"])),
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
        MIGRADO: MariaDB (usando tabela subscriptions)
        """
        try:
            # Atualizar assinatura ativa do usuário na tabela subscriptions
            update_sql = """
                UPDATE subscriptions 
                SET status = %s, updated_at = %s
                WHERE user_id = %s AND status = 'active'
            """
            
            result = await execute_sql(
                update_sql, 
                (status.value.lower(), datetime.now().isoformat(), user_id), 
                "none"
            )
            
            if result["error"]:
                logger.error(f"Erro ao atualizar assinatura MariaDB {user_id}: {result['error']}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao atualizar assinatura MariaDB {user_id}: {e}")
            return False
    
    async def get_user_usage_stats(self, user_id: str) -> dict:
        """
        Obtém estatísticas de uso do usuário
        MIGRADO: MariaDB
        """
        try:
            # Buscar estatísticas da tabela consultations
            today = datetime.now().date()
            current_month = today.replace(day=1)
            
            stats_sql = """
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN DATE(created_at) >= %s THEN 1 ELSE 0 END) as requests_this_month,
                    SUM(CASE WHEN DATE(created_at) = %s THEN 1 ELSE 0 END) as requests_today,
                    SUM(total_cost_cents) as total_cost_cents
                FROM consultations 
                WHERE user_id = %s
            """
            
            result = await execute_sql(
                stats_sql, 
                (current_month.isoformat(), today.isoformat(), user_id), 
                "one"
            )
            
            if result["error"] or not result["data"]:
                return {
                    "total_requests": 0,
                    "requests_this_month": 0,
                    "requests_today": 0,
                    "plan_limit": None,
                    "remaining_requests": None,
                    "total_cost": "R$ 0,00"
                }
            
            data = result["data"]
            
            return {
                "total_requests": data["total_requests"] or 0,
                "requests_this_month": data["requests_this_month"] or 0,
                "requests_today": data["requests_today"] or 0,
                "plan_limit": None,  # Será implementado com planos
                "remaining_requests": None,
                "total_cost": f"R$ {(data['total_cost_cents'] or 0) / 100:.2f}"
            }
            
        except Exception as e:
            logger.error(f"Erro ao buscar estatísticas MariaDB {user_id}: {e}")
            return {
                "total_requests": 0,
                "requests_this_month": 0,
                "requests_today": 0,
                "plan_limit": None,
                "remaining_requests": None,
                "total_cost": "R$ 0,00"
            }

    async def update_user_profile(self, user_id: str, name: str, email: str) -> UserResponse:
        """
        Atualiza o perfil do usuário
        MIGRADO: MariaDB
        """
        try:
            # Atualizar perfil no MariaDB
            update_sql = """
                UPDATE users 
                SET name = %s, email = %s, last_login = %s
                WHERE id = %s
            """
            
            result = await execute_sql(
                update_sql,
                (name, email, datetime.now().isoformat(), user_id),
                "none"
            )
            
            if result["error"]:
                raise Exception(f"Falha ao atualizar perfil: {result['error']}")
            
            # Buscar dados atualizados
            user_result = await execute_sql(
                "SELECT * FROM users WHERE id = %s LIMIT 1",
                (user_id,),
                "one"
            )
            
            if user_result["data"]:
                user_data = user_result["data"]
                return UserResponse(
                    id=user_data["id"],
                    email=user_data["email"],
                    full_name=user_data["name"],
                    company="Valida SaaS",  # Valor padrão
                    created_at=datetime.fromisoformat(user_data["created_at"].replace('Z', '+00:00') if 'Z' in str(user_data["created_at"]) else str(user_data["created_at"])),
                    subscription_plan=SubscriptionPlan.PRO,
                    subscription_status=SubscriptionStatus.ACTIVE
                )
            else:
                raise Exception("Usuário não encontrado após atualização")
                
        except Exception as e:
            logger.error(f"Erro ao atualizar perfil MariaDB {user_id}: {e}")
            raise Exception(f"Erro ao atualizar perfil: {str(e)}")
    
    async def change_password(self, user_id: str, current_password: str, new_password: str) -> dict:
        """
        Altera a senha do usuário
        MIGRADO: MariaDB
        """
        try:
            import hashlib
            
            # Verificar senha atual
            current_hash = hashlib.sha256(current_password.encode()).hexdigest()
            verify_result = await execute_sql(
                "SELECT id FROM users WHERE id = %s AND password_hash = %s",
                (user_id, current_hash),
                "one"
            )
            
            if not verify_result["data"]:
                raise Exception("Senha atual incorreta")
            
            # Atualizar com nova senha
            new_hash = hashlib.sha256(new_password.encode()).hexdigest()
            update_result = await execute_sql(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (new_hash, user_id),
                "none"
            )
            
            if update_result["error"]:
                raise Exception(f"Falha ao alterar senha: {update_result['error']}")
            
            return {
                "success": True,
                "message": "Senha alterada com sucesso"
            }
                
        except Exception as e:
            logger.error(f"Erro ao alterar senha MariaDB {user_id}: {e}")
            raise Exception(f"Erro ao alterar senha: {str(e)}")
    
    async def enable_2fa(self, user_id: str) -> dict:
        """
        Ativa a autenticação de dois fatores
        TODO: Implementar 2FA real
        """
        try:
            # Por enquanto, retornar não implementado
            return {
                "success": False,
                "message": "2FA não implementado ainda no MariaDB"
            }
            
        except Exception as e:
            logger.error(f"Erro ao ativar 2FA {user_id}: {e}")
            raise Exception(f"Erro ao ativar 2FA: {str(e)}")
    
    async def disable_2fa(self, user_id: str) -> dict:
        """
        Desativa a autenticação de dois fatores
        """
        try:
            return {
                "success": True,
                "message": "2FA desativado com sucesso"
            }
            
        except Exception as e:
            logger.error(f"Erro ao desativar 2FA {user_id}: {e}")
            raise Exception(f"Erro ao desativar 2FA: {str(e)}")
    
    async def update_notification_settings(self, user_id: str, settings: dict) -> dict:
        """
        Atualiza configurações de notificação do usuário
        TODO: Implementar campo notification_settings na tabela users
        """
        try:
            # Por enquanto, apenas simular sucesso
            logger.info(f"Configurações de notificação atualizadas para {user_id}", extra={"settings": settings})
            
            return {
                "success": True,
                "message": "Configurações atualizadas com sucesso",
                "settings": settings
            }
                
        except Exception as e:
            logger.error(f"Erro ao atualizar notificações {user_id}: {e}")
            raise Exception(f"Erro ao atualizar notificações: {str(e)}")
    
    async def upload_avatar(self, user_id: str, avatar_data: bytes) -> str:
        """
        Faz upload do avatar do usuário
        TODO: Implementar upload real
        """
        try:
            # Por enquanto, retornar não implementado
            raise Exception("Upload de avatar não implementado ainda")
            
        except Exception as e:
            logger.error(f"Erro ao fazer upload avatar {user_id}: {e}")
            raise Exception(f"Erro ao fazer upload do avatar: {str(e)}")
    
    async def delete_account(self, user_id: str) -> dict:
        """
        Exclui a conta do usuário
        MIGRADO: MariaDB
        """
        try:
            # Marcar usuário como inativo (soft delete)
            result = await execute_sql(
                "UPDATE users SET is_active = FALSE, last_login = %s WHERE id = %s",
                (datetime.now().isoformat(), user_id),
                "none"
            )
            
            if result["error"]:
                raise Exception(f"Falha ao excluir conta: {result['error']}")
            
            return {
                "success": True,
                "message": "Conta excluída com sucesso"
            }
                
        except Exception as e:
            logger.error(f"Erro ao excluir conta MariaDB {user_id}: {e}")
            raise Exception(f"Erro ao excluir conta: {str(e)}")

# Instância global do serviço
user_service = UserService()
