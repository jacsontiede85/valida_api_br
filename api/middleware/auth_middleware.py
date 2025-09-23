"""
Middleware de autenticação para o SaaS
MIGRADO: Supabase → MariaDB
"""
import os
import jwt
from datetime import datetime
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import structlog
from dotenv import load_dotenv
from api.middleware.mock_auth import get_mock_auth

# Carregar variáveis de ambiente
load_dotenv()

logger = structlog.get_logger("auth_middleware")

# Configuração JWT
JWT_SECRET = os.getenv("JWT_SECRET", "valida-jwt-secret-2024")
JWT_ALGORITHM = "HS256"

# MIGRADO: Removidas configurações Supabase - agora usa MariaDB
logger.info("Middleware de autenticação configurado para MariaDB")

# Esquema de autenticação
security = HTTPBearer(auto_error=False)

class AuthUser:
    def __init__(self, user_id: str, email: str, api_key: Optional[str] = None):
        self.user_id = user_id
        self.email = email
        self.api_key = api_key

def verify_jwt_token(token: str) -> Optional[dict]:
    """
    Verifica um token JWT gerado pelo nosso sistema
    """
    try:
        logger.info(f"🔍 Verificando JWT token: {token[:30]}...")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        logger.info(f"✅ JWT válido para usuário: {payload.get('email')}")
        
        # Verificar se o token não expirou
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
            logger.warning("❌ Token JWT expirado")
            return None
            
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("❌ Token JWT expirado")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"❌ Token JWT inválido: {e}")
        return None

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[AuthUser]:
    """
    Obtém o usuário atual baseado no token JWT ou API key
    """
    if not credentials:
        logger.warning("❌ Nenhuma credencial fornecida")
        return None
    
    token = credentials.credentials
    logger.info(f"🔍 Token recebido: {token[:30]}...")
    
    # Primeiro, tentar verificar como nosso JWT
    jwt_payload = verify_jwt_token(token)
    if jwt_payload:
        logger.info(f"✅ Usuário autenticado via JWT: {jwt_payload.get('email')}")
        
        # Buscar API key ativa do usuário para logging
        active_api_key = None
        try:
            from api.services.api_key_service import api_key_service
            user_api_keys = await api_key_service.get_user_api_keys(jwt_payload.get("user_id"))
            active_keys = [k for k in user_api_keys if k.is_active]
            if active_keys:
                active_api_key = f"rcp_{active_keys[0].key_hash[:8]}****"  # Simular chave para logging
                logger.info(f"API key ativa encontrada para usuário: {active_api_key}")
        except Exception as e:
            logger.warning(f"Erro ao buscar API key do usuário: {e}")
        
        return AuthUser(
            user_id=jwt_payload.get("user_id"),
            email=jwt_payload.get("email"),
            api_key=active_api_key
        )
    
    # Verificar se é uma API key (MIGRADO: MariaDB)
    if token.startswith("rcp_"):
        try:
            # Calcular o hash da chave visível para buscar no MariaDB
            import hashlib
            key_hash = hashlib.sha256(token.encode()).hexdigest()
            logger.info(f"Buscando API key com hash: {key_hash[:16]}...")
            
            # Usar APIKeyService migrado para MariaDB
            from api.services.api_key_service import api_key_service
            api_key_data = await api_key_service.get_api_key_by_hash(key_hash)
            
            logger.info(f"Resultado da busca: {'1' if api_key_data else '0'} chaves encontradas")
            
            if api_key_data:
                if api_key_data["is_active"]:
                    # Buscar dados do usuário
                    from api.database.connection import execute_sql
                    user_result = await execute_sql(
                        "SELECT id, email, name FROM users WHERE id = %s",
                        (api_key_data["user_id"],),
                        "one"
                    )
                    
                    if user_result["data"]:
                        user_data = user_result["data"]
                        logger.info(f"✅ API key válida para usuário: {user_data['email']}")
                        return AuthUser(
                            user_id=api_key_data["user_id"],
                            email=user_data["email"],
                            api_key=token
                        )
                    else:
                        raise HTTPException(status_code=401, detail="Usuário não encontrado")
                else:
                    raise HTTPException(status_code=401, detail="API key inativa")
            else:
                raise HTTPException(status_code=401, detail="API key não encontrada")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erro ao verificar API key: {e}")
            raise HTTPException(status_code=401, detail="Erro interno na verificação da API key")
    
    # Se não foi JWT nem API key, token inválido
    logger.warning(f"❌ Token não reconhecido como JWT ou API key válida: {token[:20]}...")
    logger.warning(f"   Token completo: {token}")
    raise HTTPException(status_code=401, detail="Token inválido")

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

async def validate_jwt_or_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> AuthUser:
    """
    Valida tanto tokens JWT (sessão web) quanto API keys (integração externa)
    Para uso em endpoints que precisam funcionar tanto no frontend quanto via API externa
    """
    if not credentials:
        raise HTTPException(
            status_code=401, 
            detail={"error": "http_error", "message": "Autenticação necessária", "path": "/api/v1/cnpj/consult", "status_code": 401, "timestamp": datetime.now().isoformat()}
        )
    
    token = credentials.credentials
    logger.info(f"🔍 Validando token híbrido: {token[:10]}...")
    
    # Primeiro, tentar como token JWT (para frontend)
    jwt_payload = verify_jwt_token(token)
    if jwt_payload:
        logger.info(f"✅ Usuário autenticado via JWT: {jwt_payload.get('email')}")
        
        # Buscar API key ativa do usuário para logging
        active_api_key = None
        try:
            from api.services.api_key_service import api_key_service
            user_api_keys = await api_key_service.get_user_api_keys(jwt_payload.get("user_id"))
            active_keys = [k for k in user_api_keys if k.is_active]
            if active_keys:
                active_api_key = f"rcp_{active_keys[0].key_hash[:8]}****"  # Simular chave para logging
                logger.info(f"API key ativa encontrada para usuário: {active_api_key}")
        except Exception as e:
            logger.warning(f"Erro ao buscar API key do usuário: {e}")
        
        return AuthUser(
            user_id=jwt_payload.get("user_id"),
            email=jwt_payload.get("email"),
            api_key=active_api_key
        )
    
    # Se não é JWT, tentar como API key (para integração externa)
    if token.startswith("rcp_"):
        logger.info(f"🔑 Tentando validar como API key: {token[:10]}...")
        
        # Buscar usuário pela API key no MariaDB (MIGRADO)
        try:
            # Calcular o hash da chave visível para buscar no MariaDB
            import hashlib
            key_hash = hashlib.sha256(token.encode()).hexdigest()
            logger.info(f"Buscando API key com hash: {key_hash[:16]}...")
            
            # Usar APIKeyService migrado para MariaDB
            from api.services.api_key_service import api_key_service
            api_key_data = await api_key_service.get_api_key_by_hash(key_hash)
            
            logger.info(f"Resultado da busca: {'1' if api_key_data else '0'} chaves encontradas")
            
            if api_key_data:
                if api_key_data["is_active"]:
                    # Buscar dados do usuário no MariaDB
                    from api.database.connection import execute_sql
                    user_result = await execute_sql(
                        "SELECT id, email, name FROM users WHERE id = %s",
                        (api_key_data["user_id"],),
                        "one"
                    )
                    
                    if user_result["data"]:
                        user_data = user_result["data"]
                        logger.info(f"✅ API key válida para usuário: {user_data['email']}")
                        return AuthUser(
                            user_id=api_key_data["user_id"],
                            email=user_data["email"],
                            api_key=token
                        )
                    else:
                        logger.warning(f"❌ Usuário não encontrado para API key: {token[:10]}...")
                        raise HTTPException(
                            status_code=401, 
                            detail={"error": "http_error", "message": "Autenticação necessária", "path": "/api/v1/cnpj/consult", "status_code": 401, "timestamp": datetime.now().isoformat()}
                        )
                else:
                    logger.warning(f"❌ API key inativa: {token[:10]}...")
                    raise HTTPException(
                        status_code=401, 
                        detail={"error": "http_error", "message": "Autenticação necessária", "path": "/api/v1/cnpj/consult", "status_code": 401, "timestamp": datetime.now().isoformat()}
                    )
            else:
                logger.warning(f"❌ API key não encontrada: {token[:10]}...")
                raise HTTPException(
                    status_code=401, 
                    detail={"error": "http_error", "message": "Autenticação necessária", "path": "/api/v1/cnpj/consult", "status_code": 401, "timestamp": datetime.now().isoformat()}
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erro ao verificar API key: {e}")
            raise HTTPException(
                status_code=401, 
                detail={"error": "http_error", "message": "Autenticação necessária", "path": "/api/v1/cnpj/consult", "status_code": 401, "timestamp": datetime.now().isoformat()}
            )
    
    # Se não é JWT nem API key válida, erro
    logger.warning(f"❌ Token não é JWT nem API key válida: {token[:20]}...")
    raise HTTPException(
        status_code=401, 
        detail={"error": "http_error", "message": "Autenticação necessária", "path": "/api/v1/cnpj/consult", "status_code": 401, "timestamp": datetime.now().isoformat()}
    )

def get_supabase_client():
    """
    DEPRECATED: Função mantida apenas para compatibilidade - sistema migrado para MariaDB
    """
    logger.warning("get_supabase_client() is deprecated - system migrated to MariaDB")
    return None

async def get_current_user_optional(request: Request) -> Optional[AuthUser]:
    """
    Obtém o usuário atual de forma opcional (não obrigatória)
    Usado para páginas que podem mostrar conteúdo personalizado se autenticado
    """
    try:
        # Tentar extrair token do Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # Tentar cookie de sessão se não houver header
            # Primeiro tentar auth_token (JWT), depois session_token (legacy)
            auth_token = request.cookies.get("auth_token")
            session_token = request.cookies.get("session_token")
            
            if auth_token:
                auth_header = f"Bearer {auth_token}"
            elif session_token:
                auth_header = f"Bearer {session_token}"
            else:
                return None
        
        # Simular HTTPAuthorizationCredentials
        token = auth_header.replace("Bearer ", "")
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )
        
        # Usar a função existente get_current_user
        user = await get_current_user(credentials)
        return user
        
    except HTTPException:
        # Se autenticação falhar, retornar None ao invés de erro
        return None
    except Exception as e:
        logger.warning(f"Erro ao obter usuário opcional: {e}")
        return None
