"""
Módulo de autenticação JWT para a API Stripe
"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import jwt
import os
from datetime import datetime
from pydantic import BaseModel
from supabase import create_client, Client
import structlog

# Logger
logger = structlog.get_logger("jwt_auth")

# Configuração JWT
JWT_SECRET = os.getenv("JWT_SECRET", "valida-jwt-secret-2024")
JWT_ALGORITHM = "HS256"

# Configuração Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Inicializar Supabase
supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Security scheme
security = HTTPBearer(auto_error=False)

class AuthUser(BaseModel):
    """Modelo do usuário autenticado"""
    id: str
    email: str
    name: str
    is_active: bool = True
    
    class Config:
        from_attributes = True

def decode_jwt_token(token: str) -> dict:
    """Decodifica token JWT"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )

async def get_user_from_db(user_id: str) -> Optional[dict]:
    """Busca usuário no banco de dados"""
    if not supabase:
        # Mock para desenvolvimento
        return {
            "id": user_id,
            "email": "dev@example.com",
            "name": "Dev User",
            "is_active": True
        }
    
    try:
        response = supabase.table("users").select("*").eq("id", user_id).single().execute()
        if response.data:
            return response.data
        return None
    except Exception as e:
        logger.error("Erro ao buscar usuário", user_id=user_id, error=str(e))
        return None

async def get_current_user_from_token(token: str) -> AuthUser:
    """Obtém usuário atual a partir do token"""
    # Decodificar token
    payload = decode_jwt_token(token)
    user_id = payload.get("sub")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido - user_id não encontrado"
        )
    
    # Buscar usuário no banco
    user_data = await get_user_from_db(user_id)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado"
        )
    
    if not user_data.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário inativo"
        )
    
    return AuthUser(**user_data)

async def get_current_user_from_cookie(request: Request) -> AuthUser:
    """Obtém usuário atual a partir do cookie"""
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token não encontrado nos cookies"
        )
    
    return await get_current_user_from_token(token)

async def get_current_user_from_header(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> AuthUser:
    """Obtém usuário atual a partir do header Authorization"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autorização não fornecido"
        )
    
    return await get_current_user_from_token(credentials.credentials)

async def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> AuthUser:
    """
    Middleware de autenticação que aceita tanto cookie quanto header Authorization
    """
    # Tentar primeiro pelo header Authorization (Bearer token)
    if credentials and credentials.credentials:
        try:
            return await get_current_user_from_header(credentials)
        except HTTPException:
            pass  # Se falhar, tentar pelo cookie
    
    # Tentar pelo cookie
    try:
        return await get_current_user_from_cookie(request)
    except HTTPException:
        pass
    
    # Se ambos falharam, retornar erro de não autorizado
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Acesso negado. Token de autenticação necessário."
    )

# Alias para compatibilidade
async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> AuthUser:
    """Alias para require_auth"""
    return await require_auth(request, credentials)
