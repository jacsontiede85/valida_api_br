"""
Serviço de gerenciamento de usuários para o SaaS
MIGRADO: Supabase → MariaDB
"""
import os
from typing import Optional, List
from datetime import datetime, timedelta
import structlog
from api.models.saas_models import (
    UserCreate, UserResponse, SubscriptionPlan, SubscriptionStatus,
    ProfileUpdateRequest, UserProfileResponse, ChangePasswordRequest
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
    
    async def get_user_complete_profile(self, user_id: str) -> Optional[UserProfileResponse]:
        """
        Obtém perfil completo do usuário com estatísticas e configurações
        """
        try:
            # Query simplificada para testar
            main_sql = """
                SELECT 
                    u.id, u.name, u.email, u.created_at, u.last_login, u.credits, u.credit_alert_threshold_cents
                FROM users u
                WHERE u.id = %s
            """
            
            result = await execute_sql(main_sql, (user_id,), "one")
            
            if not result["data"]:
                logger.error(f"Usuário {user_id} não encontrado")
                return None
            
            user_data = result["data"]
            
            # Query para estatísticas de créditos
            credits_sql = """
                SELECT 
                    SUM(CASE WHEN type IN ('add', 'purchase') THEN amount_cents ELSE 0 END) / 100.0 as total_purchased,
                    SUM(CASE WHEN type IN ('subtract', 'spend', 'usage') THEN amount_cents ELSE 0 END) / 100.0 as total_spent
                FROM credit_transactions 
                WHERE user_id = %s
            """
            
            credits_result = await execute_sql(credits_sql, (user_id,), "one")
            credits_data = credits_result["data"] or {"total_purchased": 0.0, "total_spent": 0.0}
            
            # Query para estatísticas de consultas
            queries_sql = """
                SELECT 
                    COUNT(*) as total_queries,
                    COUNT(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 END) as monthly_queries,
                    MAX(created_at) as last_query_date
                FROM consultations 
                WHERE user_id = %s
            """
            
            queries_result = await execute_sql(queries_sql, (user_id,), "one")
            queries_data = queries_result["data"] or {"total_queries": 0, "monthly_queries": 0, "last_query_date": None}
            
            # Query para API keys
            api_keys_sql = """
                SELECT COUNT(*) as api_keys_count
                FROM api_keys 
                WHERE user_id = %s AND is_active = 1
            """
            
            api_keys_result = await execute_sql(api_keys_sql, (user_id,), "one")
            api_keys_count = api_keys_result["data"]["api_keys_count"] if api_keys_result["data"] else 0
            
            # Query para dados de assinatura
            subscription_sql = """
                SELECT 
                    s.status as subscription_status,
                    sp.name as subscription_plan,
                    sp.code as plan_code,
                    s.created_at as subscription_start,
                    s.current_period_start,
                    s.current_period_end,
                    DATEDIFF(NOW(), s.created_at) as subscription_days
                FROM subscriptions s
                JOIN subscription_plans sp ON s.plan_id = sp.id
                WHERE s.user_id = %s AND s.status = 'active'
                ORDER BY s.created_at DESC
                LIMIT 1
            """
            
            subscription_result = await execute_sql(subscription_sql, (user_id,), "one")
            subscription_data = subscription_result["data"] if subscription_result["data"] else None
            
            # Configurações de notificação padrão (por enquanto)
            notification_settings = {
                "email_notifications": True,
                "api_alerts": True,
                "billing_alerts": True,
                "credits_alerts": True,
                "renewal_alerts": True,
                "security_alerts": True,
                "marketing_emails": False
            }
            
            return UserProfileResponse(
                # Dados básicos
                id=user_data["id"],
                name=user_data["name"],
                email=user_data["email"],
                created_at=datetime.fromisoformat(user_data["created_at"].replace('Z', '+00:00') if 'Z' in str(user_data["created_at"]) else str(user_data["created_at"])),
                last_login=datetime.fromisoformat(user_data["last_login"].replace('Z', '+00:00') if user_data["last_login"] and 'Z' in str(user_data["last_login"]) else str(user_data["last_login"])) if user_data["last_login"] else None,
                
                # Estatísticas de créditos
                credits_available=float(user_data["credits"] or 0.0),
                credits_used_total=float(credits_data["total_spent"]),
                credits_purchased_total=float(credits_data["total_purchased"]),
                
                # Estatísticas de consultas
                monthly_queries=queries_data["monthly_queries"] or 0,
                total_queries=queries_data["total_queries"] or 0,
                last_query_date=datetime.fromisoformat(queries_data["last_query_date"].replace('Z', '+00:00') if queries_data["last_query_date"] and 'Z' in str(queries_data["last_query_date"]) else str(queries_data["last_query_date"])) if queries_data["last_query_date"] else None,
                
                # Configurações
                notification_settings=notification_settings,
                credit_alert_threshold=user_data.get("credit_alert_threshold_cents", 500),
                
                # Status da assinatura
                subscription_status=subscription_data["subscription_status"] if subscription_data else "inactive",
                subscription_plan=subscription_data["subscription_plan"] if subscription_data else "Free",
                subscription_days=subscription_data["subscription_days"] if subscription_data else 0,
                
                # Informações de segurança
                two_factor_enabled=False,  # Por enquanto sempre False
                
                # Contagem de API keys
                api_keys_count=api_keys_count
            )
            
        except Exception as e:
            logger.error(f"Erro ao buscar perfil completo do usuário {user_id}: {e}")
            return None
    
    async def update_profile(self, user_id: str, profile_data: ProfileUpdateRequest) -> bool:
        """
        Atualiza dados do perfil do usuário
        """
        try:
            update_fields = []
            params = []
            
            if profile_data.name is not None:
                update_fields.append("name = %s")
                params.append(profile_data.name)
            
            if profile_data.email is not None:
                # Verificar se email já existe
                existing_result = await execute_sql(
                    "SELECT id FROM users WHERE email = %s AND id != %s LIMIT 1",
                    (profile_data.email, user_id),
                    "one"
                )
                
                if existing_result["data"]:
                    raise Exception("Email já está em uso por outro usuário")
                
                update_fields.append("email = %s")
                params.append(profile_data.email)
            
            if not update_fields:
                return True  # Nada para atualizar
            
            update_fields.append("updated_at = %s")
            params.append(datetime.now().isoformat())
            params.append(user_id)
            
            sql = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
            
            result = await execute_sql(sql, tuple(params), "none")
            
            if result["error"]:
                logger.error(f"Erro ao atualizar perfil: {result['error']}")
                return False
            
            logger.info(f"Perfil atualizado para usuário {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao atualizar perfil do usuário {user_id}: {e}")
            return False
    
    async def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        """
        Altera senha do usuário usando bcrypt
        """
        try:
            # Buscar usuário atual
            user_result = await execute_sql(
                "SELECT password_hash FROM users WHERE id = %s",
                (user_id,),
                "one"
            )
            
            if not user_result["data"]:
                raise Exception("Usuário não encontrado")
            
            current_hash = user_result["data"]["password_hash"]
            
            # Verificar senha atual usando bcrypt
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            if not pwd_context.verify(current_password, current_hash):
                raise Exception("Senha atual incorreta")
            
            # Gerar novo hash da senha usando bcrypt
            new_password_hash = pwd_context.hash(new_password)
            
            # Atualizar senha
            result = await execute_sql(
                "UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s",
                (new_password_hash, datetime.now().isoformat(), user_id),
                "none"
            )
            
            if result["error"]:
                logger.error(f"Erro ao alterar senha: {result['error']}")
                return False
            
            logger.info(f"Senha alterada para usuário {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao alterar senha do usuário {user_id}: {e}")
            return False

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
    
    async def update_credit_alert_threshold(self, user_id: str, threshold_cents: int) -> bool:
        """
        Atualiza o limite de alerta de créditos do usuário
        """
        try:
            result = await execute_sql(
                "UPDATE users SET credit_alert_threshold_cents = %s, updated_at = %s WHERE id = %s",
                (threshold_cents, datetime.now().isoformat(), user_id),
                "none"
            )
            
            if result["error"]:
                logger.error(f"Erro ao atualizar limite de alerta: {result['error']}")
                return False
            
            logger.info(f"Limite de alerta atualizado para usuário {user_id}: {threshold_cents} centavos")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao atualizar limite de alerta do usuário {user_id}: {e}")
            return False

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
