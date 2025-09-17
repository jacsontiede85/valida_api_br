"""
Middleware de autenticação para o SaaS
"""
import os
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import structlog
from supabase import create_client, Client
from dotenv import load_dotenv
from api.middleware.mock_auth import get_mock_auth

# Carregar variáveis de ambiente
load_dotenv()

logger = structlog.get_logger("auth_middleware")

# Configuração do Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Cliente Supabase - usar SERVICE_ROLE_KEY para operações administrativas
supabase_client: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logger.info("Cliente Supabase configurado com SERVICE_ROLE_KEY")
    except Exception as e:
        logger.error(f"Erro ao configurar Supabase: {e}")
        supabase_client = None
elif SUPABASE_URL and SUPABASE_ANON_KEY:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        logger.info("Cliente Supabase configurado com ANON_KEY")
    except Exception as e:
        logger.error(f"Erro ao configurar Supabase: {e}")
        supabase_client = None
else:
    logger.warning("Variáveis de ambiente do Supabase não configuradas - usando modo mock")

# Esquema de autenticação
security = HTTPBearer(auto_error=False)

class AuthUser:
    def __init__(self, user_id: str, email: str, api_key: Optional[str] = None):
        self.user_id = user_id
        self.email = email
        self.api_key = api_key

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[AuthUser]:
    """
    Obtém o usuário atual baseado no token JWT ou API key
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    
    # Verificar se é uma API key
    if token.startswith("rcp_"):
        if not supabase_client:
            logger.warning("Supabase não configurado, usando modo mock para API key")
            mock_auth = get_mock_auth()
            result = mock_auth.get_user_by_api_key(token)
            if result and result[0] and result[1]:
                user_data, api_key_data = result
                return AuthUser(
                    user_id=user_data["id"],
                    email=user_data["email"],
                    api_key=token
                )
            else:
                raise HTTPException(status_code=401, detail="API key inválida")
        
        # Buscar usuário pela API key no Supabase
        try:
            # Calcular o hash da chave visível para buscar no banco
            import hashlib
            key_hash = hashlib.sha256(token.encode()).hexdigest()
            logger.info(f"Buscando API key com hash: {key_hash}")
            
            result = supabase_client.table("api_keys").select(
                "id, user_id, name, is_active, users(id, email, name)"
            ).eq("key_hash", key_hash).execute()
            
            logger.info(f"Resultado da busca: {len(result.data)} chaves encontradas")
            
            if result.data and len(result.data) > 0:
                api_key_data = result.data[0]
                if api_key_data["is_active"]:
                    user_data = api_key_data["users"]
                    return AuthUser(
                        user_id=api_key_data["user_id"],
                        email=user_data["email"],
                        api_key=token
                    )
                else:
                    raise HTTPException(status_code=401, detail="API key inativa")
            else:
                raise HTTPException(status_code=401, detail="API key não encontrada")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erro ao verificar API key: {e}")
            raise HTTPException(status_code=401, detail="Erro interno na verificação da API key")
    
    # Se não há cliente Supabase configurado, usar modo mock para JWT
    if not supabase_client:
        logger.warning("Supabase não configurado, usando modo mock para JWT")
        mock_auth = get_mock_auth()
        user_data = mock_auth.get_user_by_token(token)
        if user_data:
            return AuthUser(
                user_id=user_data["id"],
                email=user_data["email"]
            )
        else:
            raise HTTPException(status_code=401, detail="Token inválido")
    
    try:
        # Verificar se é um token JWT do Supabase
        response = supabase_client.auth.get_user(token)
        if response.user:
            return AuthUser(
                user_id=response.user.id,
                email=response.user.email
            )
        else:
            raise HTTPException(status_code=401, detail="Token inválido")
                
    except Exception as e:
        logger.error(f"Erro na autenticação: {e}")
        raise HTTPException(status_code=401, detail="Erro na autenticação")

async def require_auth(user: Optional[AuthUser] = Depends(get_current_user)) -> AuthUser:
    """
    Requer autenticação obrigatória
    """
    if not user:
        raise HTTPException(status_code=401, detail="Autenticação necessária")
    return user

async def require_api_key(user: Optional[AuthUser] = Depends(get_current_user)) -> AuthUser:
    """
    Requer API key válida
    """
    if not user or not user.api_key:
        raise HTTPException(status_code=401, detail="API key necessária")
    return user

def get_supabase_client() -> Optional[Client]:
    """
    Retorna o cliente Supabase configurado
    """
    return supabase_client
