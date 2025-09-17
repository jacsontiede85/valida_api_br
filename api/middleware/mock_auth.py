"""
Middleware de autenticação mock para desenvolvimento
"""
import structlog
from typing import Optional
from datetime import datetime, timedelta
import jwt
import os

logger = structlog.get_logger("mock_auth")

# Chave secreta para JWT (em produção, usar variável de ambiente)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")

class MockAuth:
    def __init__(self):
        self.users = {
            "dev-user-123": {
                "id": "dev-user-123",
                "email": "dev@valida.com.br",
                "full_name": "Usuário Desenvolvimento",
                "company": "Valida Dev",
                "subscription_plan": "professional",
                "subscription_status": "active",
                "created_at": datetime.now().isoformat()
            }
        }
        self.api_keys = {
            "rcp_dev-key-1": {
                "id": "dev-key-1",
                "user_id": "dev-user-123",
                "name": "Chave de Desenvolvimento",
                "key_hash": "rcp_dev-key-1",
                "status": "active",
                "created_at": datetime.now().isoformat()
            },
            "rcp_dev-key-2": {
                "id": "dev-key-2",
                "user_id": "dev-user-123",
                "name": "Chave de Desenvolvimento",
                "key_hash": "rcp_dev-key-2",
                "status": "active",
                "created_at": datetime.now().isoformat()
            }
        }
    
    def create_mock_token(self, user_id: str) -> str:
        """
        Cria um token JWT mock para o usuário
        """
        payload = {
            "user_id": user_id,
            "email": self.users[user_id]["email"],
            "exp": datetime.utcnow() + timedelta(hours=24),
            "iat": datetime.utcnow(),
            "type": "access"
        }
        
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        return token
    
    def verify_token(self, token: str) -> Optional[dict]:
        """
        Verifica e decodifica um token JWT
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expirado")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Token inválido")
            return None
    
    def get_user_by_token(self, token: str) -> Optional[dict]:
        """
        Obtém usuário pelo token
        """
        payload = self.verify_token(token)
        if not payload:
            return None
        
        user_id = payload.get("user_id")
        if user_id in self.users:
            return self.users[user_id]
        return None
    
    def get_user_by_api_key(self, api_key: str) -> Optional[tuple[dict, dict]]:
        """
        Obtém usuário e API key pela chave de API
        """
        if api_key in self.api_keys:
            key_data = self.api_keys[api_key]
            user_id = key_data["user_id"]
            if user_id in self.users:
                return self.users[user_id], key_data
        return None, None
    
    def create_mock_api_key(self, user_id: str, name: str) -> dict:
        """
        Cria uma nova API key mock
        """
        key_id = f"dev-key-{len(self.api_keys) + 1}"
        api_key = f"rcp_{key_id}"
        
        self.api_keys[api_key] = {
            "id": key_id,
            "user_id": user_id,
            "name": name,
            "key_hash": api_key,
            "status": "active",
            "created_at": datetime.now().isoformat()
        }
        
        return {
            "id": key_id,
            "key": api_key,
            "name": name,
            "status": "active",
            "created_at": datetime.now().isoformat()
        }
    
    def get_user_api_keys(self, user_id: str) -> list:
        """
        Obtém todas as API keys do usuário
        """
        return [
            {
                "id": key_data["id"],
                "name": key_data["name"],
                "status": key_data["status"],
                "created_at": key_data["created_at"],
                "last_used": None
            }
            for key_data in self.api_keys.values()
            if key_data["user_id"] == user_id
        ]

# Instância global do mock auth
mock_auth = MockAuth()

def get_mock_auth() -> MockAuth:
    """
    Retorna a instância do mock auth
    """
    return mock_auth
