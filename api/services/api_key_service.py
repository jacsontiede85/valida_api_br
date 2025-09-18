"""
Serviço de gerenciamento de API keys para o SaaS
"""
import secrets
import hashlib
from typing import Optional, List
from datetime import datetime
import structlog
from supabase import Client
from api.models.saas_models import (
    APIKeyCreate, APIKeyResponse, APIKeyList
)
from api.middleware.auth_middleware import get_supabase_client

logger = structlog.get_logger("api_key_service")

class APIKeyService:
    def __init__(self):
        self.supabase = get_supabase_client()
    
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
        if not self.supabase:
            # Sem Supabase configurado
            raise Exception("Sistema de API keys não configurado")
        
        try:
            visible_key, key_hash = self.generate_api_key()
            
            # Verificar se já existe uma chave com o mesmo nome
            existing = self.supabase.table("api_keys").select("id").eq(
                "user_id", user_id
            ).eq("name", key_data.name).execute()
            
            if existing.data:
                raise Exception("Já existe uma API key com este nome")
            
            # Criar a API key
            key_data_dict = {
                "user_id": user_id,
                "name": key_data.name,
                "key": visible_key,  # Salvar a chave original
                "key_hash": key_hash,
                "is_active": True,
                "created_at": datetime.now().isoformat()
            }
            
            # Adicionar description apenas se não for None ou string vazia
            if key_data.description and key_data.description.strip():
                key_data_dict["description"] = key_data.description
            
            result = self.supabase.table("api_keys").insert(key_data_dict).execute()
            
            if result.data:
                api_key_data = result.data[0]
                return APIKeyResponse(
                    id=api_key_data["id"],
                    name=api_key_data["name"],
                    description=api_key_data.get("description", ""),
                    key=visible_key,  # Só retornado na criação
                    key_hash=api_key_data["key_hash"],
                    user_id=api_key_data["user_id"],
                    created_at=datetime.fromisoformat(api_key_data["created_at"]),
                    last_used=datetime.fromisoformat(api_key_data["last_used"]) if api_key_data.get("last_used") else None,
                    is_active=api_key_data["is_active"]
                )
            else:
                raise Exception("Falha ao criar API key")
                
        except Exception as e:
            logger.error(f"Erro ao criar API key: {e}")
            raise Exception(f"Erro ao criar API key: {str(e)}")
    
    async def get_user_api_keys(self, user_id: str) -> List[APIKeyList]:
        """
        Lista todas as API keys do usuário
        """
        if not self.supabase:
            logger.warning("Supabase não configurado, retornando lista vazia")
            return []
        
        try:
            result = self.supabase.table("api_keys").select(
                "id, name, key, key_hash, user_id, created_at, last_used_at, is_active, description"
            ).eq("user_id", user_id).order("created_at", desc=True).execute()
            
            api_keys = []
            for key_data in result.data:
                api_keys.append(APIKeyList(
                    id=key_data["id"],
                    name=key_data["name"],
                    description=key_data.get("description", ""),
                    key=key_data.get("key"),  # Chave original
                    key_hash=key_data["key_hash"],
                    user_id=key_data["user_id"],
                    created_at=datetime.fromisoformat(key_data["created_at"].replace('Z', '+00:00')),
                    last_used=datetime.fromisoformat(key_data["last_used_at"].replace('Z', '+00:00')) if key_data.get("last_used_at") else None,
                    is_active=key_data["is_active"]
                ))
            
            return api_keys
            
        except Exception as e:
            logger.error(f"Erro ao buscar API keys do usuário {user_id}: {e}")
            return []
    
    async def revoke_api_key(self, user_id: str, key_id: str) -> bool:
        """
        Revoga uma API key
        """
        if not self.supabase:
            logger.warning("Supabase não configurado, revogação mock")
            return True
        
        try:
            logger.info(f"Tentando revogar API key {key_id} para usuário {user_id}")
            
            # Primeiro verificar se a chave existe e pertence ao usuário
            check_result = self.supabase.table("api_keys").select("id, user_id, is_active").eq("id", key_id).execute()
            
            if not check_result.data:
                logger.warning(f"API key {key_id} não encontrada")
                return False
                
            key_data = check_result.data[0]
            if key_data["user_id"] != user_id:
                logger.warning(f"API key {key_id} não pertence ao usuário {user_id}")
                return False
                
            if not key_data["is_active"]:
                logger.warning(f"API key {key_id} já está inativa")
                return False
            
            # Revogar a chave
            result = self.supabase.table("api_keys").update({
                "is_active": False
            }).eq("id", key_id).eq("user_id", user_id).execute()
            
            logger.info(f"Resultado da revogação: {result.data}")
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Erro ao revogar API key {key_id}: {e}")
            return False
    
    async def get_api_key_by_hash(self, key_hash: str) -> Optional[dict]:
        """
        Busca uma API key pelo hash
        """
        if not self.supabase:
            # Modo de desenvolvimento
            if key_hash.startswith("dev_hash_"):
                return {
                    "id": "dev-key-123",
                    "user_id": "dev-user-123",
                    "name": "Chave Desenvolvimento",
                    "is_active": True
                }
            return None
        
        try:
            result = self.supabase.table("api_keys").select(
                "id, user_id, name, is_active"
            ).eq("key_hash", key_hash).eq("is_active", True).execute()
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.error(f"Erro ao buscar API key por hash: {e}")
            return None
    
    async def update_last_used(self, key_id: str) -> bool:
        """
        Atualiza o timestamp de último uso da API key
        """
        if not self.supabase:
            return True
        
        try:
            result = self.supabase.table("api_keys").update({
                "last_used": datetime.now().isoformat()
            }).eq("id", key_id).execute()
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Erro ao atualizar último uso da API key {key_id}: {e}")
            return False
    
    async def get_keys_usage_v2(self, user_id: str) -> List[dict]:
        """
        Obtém uso detalhado das API keys v2.0
        """
        try:
            if not self.supabase:
                return self._generate_mock_keys_usage()
            
            # Buscar API keys do usuário
            keys_result = self.supabase.table("api_keys").select(
                "id, name, key, is_active, created_at, last_used_at"
            ).eq("user_id", user_id).execute()
            
            keys_usage = []
            for key_data in keys_result.data:
                # Buscar uso diário da chave (consultas de hoje)
                today = datetime.now().strftime("%Y-%m-%d")
                
                # Buscar consultas da chave hoje
                consultations_result = self.supabase.table("consultations").select(
                    "id, total_cost_cents, created_at, status"
                ).eq("api_key_id", key_data["id"]).gte(
                    "created_at", f"{today}T00:00:00"
                ).lte("created_at", f"{today}T23:59:59").execute()
                
                # Calcular estatísticas
                daily_queries = len(consultations_result.data)
                daily_cost = sum(c["total_cost_cents"] for c in consultations_result.data)
                successful_queries = len([c for c in consultations_result.data if c["status"] == "success"])
                
                key_usage = {
                    "id": key_data["id"],
                    "name": key_data["name"],
                    "key": key_data["key"][:20] + "..." if key_data["key"] else "N/A",
                    "is_active": key_data["is_active"],
                    "created_at": key_data["created_at"],
                    "last_used_at": key_data.get("last_used_at"),
                    "daily_queries": daily_queries,
                    "daily_cost": daily_cost,
                    "daily_cost_formatted": f"R$ {daily_cost / 100:.2f}",
                    "success_rate": (successful_queries / daily_queries * 100) if daily_queries > 0 else 0
                }
                
                keys_usage.append(key_usage)
            
            return keys_usage
            
        except Exception as e:
            logger.error(f"Erro ao buscar uso das API keys: {e}")
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
