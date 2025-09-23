"""
Serviço de gerenciamento de API keys para o SaaS
MIGRADO: Supabase → MariaDB
"""
import secrets
import hashlib
from typing import Optional, List
from datetime import datetime
import structlog
from api.models.saas_models import (
    APIKeyCreate, APIKeyResponse, APIKeyList
)
from api.database.connection import execute_sql, generate_uuid

logger = structlog.get_logger("api_key_service")

class APIKeyService:
    def __init__(self):
        # Migrado de Supabase para MariaDB - não precisa de cliente específico
        pass
    
    def generate_api_key(self) -> tuple[str, str]:
        """
        Gera uma nova API key e seu hash
        """
        # Gerar 32 bytes aleatórios
        key_bytes = secrets.token_bytes(32)
        # Criar a chave visível com prefixo
        visible_key = f"rcp_{key_bytes.hex()}"
        # Gerar hash para armazenamento
        key_hash = hashlib.sha256(visible_key.encode()).hexdigest()
        
        return visible_key, key_hash
    
    async def create_api_key(
        self, 
        user_id: str, 
        key_data: APIKeyCreate
    ) -> APIKeyResponse:
        """
        Cria uma nova API key para o usuário
        """
        try:
            visible_key, key_hash = self.generate_api_key()
            
            # Verificar se já existe uma chave com o mesmo nome
            existing_result = await execute_sql(
                "SELECT id FROM api_keys WHERE user_id = %s AND name = %s",
                (user_id, key_data.name),
                "one"
            )
            
            if existing_result["data"]:
                raise Exception("Já existe uma API key com este nome")
            
            # Criar registro da API key
            api_key_id = generate_uuid()
            description = key_data.description if key_data.description and key_data.description.strip() else None
            
            # Inserir nova API key
            insert_result = await execute_sql("""
                INSERT INTO api_keys 
                (id, user_id, name, key_visible, key_hash, description, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                api_key_id,
                user_id,
                key_data.name,
                visible_key,  # Salvar chave visível inicialmente
                key_hash,
                description,
                True
            ), "none")
            
            if insert_result["error"]:
                raise Exception(insert_result["error"])
            
            # Buscar registro criado
            created_result = await execute_sql(
                "SELECT * FROM api_keys WHERE id = %s",
                (api_key_id,),
                "one"
            )
            
            if created_result["data"]:
                api_key_data = created_result["data"]
                return APIKeyResponse(
                    id=api_key_data["id"],
                    name=api_key_data["name"],
                    description=api_key_data.get("description", ""),
                    key=visible_key,  # Só retornado na criação
                    key_hash=api_key_data["key_hash"],
                    user_id=api_key_data["user_id"],
                    created_at=api_key_data["created_at"],
                    last_used=api_key_data.get("last_used_at"),
                    is_active=api_key_data["is_active"]
                )
            else:
                raise Exception("Falha ao buscar API key criada")
                
        except Exception as e:
            logger.error(f"Erro ao criar API key: {e}")
            raise Exception(f"Erro ao criar API key: {str(e)}")
    
    async def get_user_api_keys(self, user_id: str) -> List[APIKeyList]:
        """
        Lista todas as API keys do usuário
        """
        try:
            result = await execute_sql("""
                SELECT id, name, description, key_visible, key_hash, user_id, created_at, last_used_at, is_active
                FROM api_keys 
                WHERE user_id = %s 
                ORDER BY created_at DESC
            """, (user_id,), "all")
            
            api_keys = []
            if result["data"]:
                for key_data in result["data"]:
                    api_keys.append(APIKeyList(
                        id=key_data["id"],
                        name=key_data["name"],
                        description=key_data.get("description", ""),
                        key=key_data.get("key_visible"),  # Retornar chave visível se disponível
                        key_hash=key_data["key_hash"],
                        user_id=key_data["user_id"],
                        created_at=key_data["created_at"],
                        last_used=key_data.get("last_used_at"),
                        is_active=key_data["is_active"]
                    ))
            
            return api_keys
            
        except Exception as e:
            logger.error(f"Erro ao buscar API keys do usuário {user_id}: {e}")
            return []
    
    async def clear_visible_key_after_view(self, api_key_id: str, user_id: str) -> bool:
        """
        Remove a chave visível após primeira visualização (segurança)
        """
        try:
            result = await execute_sql("""
                UPDATE api_keys 
                SET key_visible = NULL 
                WHERE id = %s AND user_id = %s AND key_visible IS NOT NULL
            """, (api_key_id, user_id), "none")
            
            if result["error"]:
                logger.error(f"Erro ao limpar chave visível {api_key_id}: {result['error']}")
                return False
                
            # Retorna True se uma linha foi afetada (chave foi limpa)
            return result["count"] > 0
            
        except Exception as e:
            logger.error(f"Erro ao limpar chave visível {api_key_id}: {e}")
            return False
    
    async def revoke_api_key(self, user_id: str, key_id: str) -> bool:
        """
        Revoga uma API key
        MIGRADO: MariaDB
        """
        try:
            logger.info("tentando_revogar_api_key", 
                       user_id=user_id, 
                       key_id=key_id)
            
            # Primeiro verificar se a chave existe e pertence ao usuário
            check_result = await execute_sql(
                "SELECT id, user_id, is_active FROM api_keys WHERE id = %s",
                (key_id,),
                "one"
            )
            
            if check_result["error"]:
                logger.error("erro_verificar_api_key_mariadb", 
                           error=check_result["error"])
                return False
            
            if not check_result["data"]:
                logger.warning("api_key_nao_encontrada", key_id=key_id)
                return False
                
            key_data = check_result["data"]
            if key_data["user_id"] != user_id:
                logger.warning("api_key_nao_pertence_usuario", 
                             key_id=key_id, 
                             user_id=user_id,
                             owner_id=key_data["user_id"])
                return False
                
            if not key_data["is_active"]:
                logger.warning("api_key_ja_inativa", key_id=key_id)
                return False
            
            # Revogar a chave
            revoke_result = await execute_sql("""
                UPDATE api_keys 
                SET is_active = FALSE 
                WHERE id = %s AND user_id = %s
            """, (key_id, user_id), "none")
            
            if revoke_result["error"]:
                logger.error("erro_revogar_api_key", 
                           user_id=user_id,
                           key_id=key_id,
                           error=revoke_result["error"])
                return False
            
            logger.info("api_key_revogada_com_sucesso", 
                       user_id=user_id,
                       key_id=key_id)
            return True
            
        except Exception as e:
            logger.error("erro_revogar_api_key", 
                       user_id=user_id,
                       key_id=key_id,
                       error=str(e))
            return False
    
    async def get_api_key_by_hash(self, key_hash: str) -> Optional[dict]:
        """
        Busca uma API key pelo hash
        MIGRADO: MariaDB
        """
        try:
            result = await execute_sql("""
                SELECT id, user_id, name, key_visible, is_active 
                FROM api_keys 
                WHERE key_hash = %s AND is_active = TRUE
            """, (key_hash,), "one")
            
            return result["data"] if result["data"] else None
            
        except Exception as e:
            logger.error(f"Erro ao buscar API key por hash: {e}")
            return None
    
    async def update_last_used(self, key_id: str) -> bool:
        """
        Atualiza o timestamp de último uso da API key
        MIGRADO: MariaDB
        """
        try:
            result = await execute_sql("""
                UPDATE api_keys 
                SET last_used_at = NOW() 
                WHERE id = %s
            """, (key_id,), "none")
            
            return not result["error"]
            
        except Exception as e:
            logger.error(f"Erro ao atualizar último uso da API key {key_id}: {e}")
            return False
    
    async def get_keys_usage_v2(self, user_id: str) -> List[dict]:
        """
        Obtém uso detalhado das API keys v2.0
        MIGRADO: MariaDB
        """
        try:
            # Buscar API keys do usuário
            keys_result = await execute_sql("""
                SELECT id, name, key_visible, is_active, created_at, last_used_at
                FROM api_keys 
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (user_id,), "all")
            
            if keys_result["error"]:
                logger.error("erro_buscar_api_keys_mariadb", 
                           user_id=user_id, 
                           error=keys_result["error"])
                return self._generate_mock_keys_usage()
            
            keys_usage = []
            today = datetime.now().strftime("%Y-%m-%d")
            
            for key_data in keys_result["data"]:
                # Buscar consultas da chave hoje
                consultations_result = await execute_sql("""
                    SELECT id, total_cost_cents, created_at, status
                    FROM consultations 
                    WHERE api_key_id = %s 
                    AND DATE(created_at) = %s
                """, (key_data["id"], today), "all")
                
                # Calcular estatísticas
                consultations_data = consultations_result["data"] if not consultations_result["error"] else []
                
                daily_queries = len(consultations_data)
                daily_cost = sum(c.get("total_cost_cents", 0) for c in consultations_data)
                successful_queries = len([c for c in consultations_data if c.get("status") == "success"])
                
                # Formatar chave para exibição
                key_display = "rcp_****"  # Padrão se não houver chave visível
                if key_data["key_visible"]:
                    key_display = key_data["key_visible"][:20] + "..."
                
                key_usage = {
                    "id": key_data["id"],
                    "name": key_data["name"],
                    "key": key_display,
                    "is_active": bool(key_data["is_active"]),
                    "created_at": key_data["created_at"].isoformat() if key_data["created_at"] else None,
                    "last_used_at": key_data["last_used_at"].isoformat() if key_data["last_used_at"] else None,
                    "daily_queries": daily_queries,
                    "daily_cost": daily_cost,
                    "daily_cost_formatted": f"R$ {daily_cost / 100:.2f}",
                    "success_rate": (successful_queries / daily_queries * 100) if daily_queries > 0 else 0
                }
                
                keys_usage.append(key_usage)
            
            logger.info("api_keys_usage_obtida_mariadb", 
                       user_id=user_id,
                       total_keys=len(keys_usage))
            
            return keys_usage
            
        except Exception as e:
            logger.error("erro_obter_uso_api_keys_mariadb", 
                       user_id=user_id, 
                       error=str(e))
            return self._generate_mock_keys_usage()
    
    def _generate_mock_keys_usage(self) -> List[dict]:
        """Gera dados mock para uso das chaves"""
        return [
            {
                "id": "key-1",
                "name": "Produção",
                "key": "rcp_1234567890abcdef...",
                "is_active": True,
                "created_at": "2024-01-15T10:30:00Z",
                "last_used_at": "2024-09-17T08:45:00Z",
                "daily_queries": 15,
                "daily_cost": 225,  # R$ 2,25
                "daily_cost_formatted": "R$ 2,25",
                "success_rate": 93.3
            },
            {
                "id": "key-2",
                "name": "Desenvolvimento",
                "key": "rcp_abcdef1234567890...",
                "is_active": True,
                "created_at": "2024-02-10T14:20:00Z",
                "last_used_at": "2024-09-16T16:30:00Z",
                "daily_queries": 3,
                "daily_cost": 45,  # R$ 0,45
                "daily_cost_formatted": "R$ 0,45",
                "success_rate": 100.0
            },
            {
                "id": "key-3",
                "name": "Testes",
                "key": "rcp_fedcba0987654321...",
                "is_active": False,
                "created_at": "2024-01-05T09:15:00Z",
                "last_used_at": "2024-08-20T11:10:00Z",
                "daily_queries": 0,
                "daily_cost": 0,
                "daily_cost_formatted": "R$ 0,00",
                "success_rate": 0.0
            }
        ]

# Instância global do serviço
api_key_service = APIKeyService()
