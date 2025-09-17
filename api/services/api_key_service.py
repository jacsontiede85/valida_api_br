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

# Instância global do serviço
api_key_service = APIKeyService()
