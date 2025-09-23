"""
Router de autenticação migrado para MariaDB
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from pydantic import BaseModel, EmailStr
from typing import Optional
import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
import os
import structlog
from passlib.context import CryptContext

# Importar componentes MariaDB
from api.database.connection import UserRepository, generate_uuid
from api.services.api_key_service import api_key_service
from api.models.saas_models import APIKeyCreate

# Configurar logger
logger = structlog.get_logger("auth")

# Configuração JWT
JWT_SECRET = os.getenv("JWT_SECRET", "valida-jwt-secret-2024")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Configurar Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

logger.info("Router de autenticação configurado para MariaDB")

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Modelos Pydantic
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None

class AuthResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    api_key: Optional[str] = None
    user_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    message: Optional[str] = None

def generate_token(user_id: str, email: str) -> str:
    """Gera um token JWT de autenticação"""
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def hash_password(password: str) -> str:
    """Hash da senha com bcrypt"""
    return pwd_context.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    """Verifica senha com bcrypt"""
    return pwd_context.verify(password, hashed_password)

def generate_api_key() -> tuple[str, str]:
    """Gera uma API key e seu hash"""
    key_bytes = secrets.token_bytes(32)
    visible_key = f"rcp_{key_bytes.hex()}"
    key_hash = hashlib.sha256(visible_key.encode()).hexdigest()
    return visible_key, key_hash

async def create_user_in_db(email: str, password_hash: str, name: str = None):
    """Cria usuário no banco de dados MariaDB"""
    try:
        # Verificar se usuário já existe
        existing_user = await UserRepository.get_by_email(email)
        if existing_user:
            raise HTTPException(status_code=400, detail="E-mail já cadastrado")
        
        # Criar novo usuário
        user_data = {
            "id": generate_uuid(),
            "email": email,
            "password_hash": password_hash,
            "name": name or email.split('@')[0],
            "is_active": True,
            "created_at": datetime.now()
        }
        
        # Inserir usuário no MariaDB
        user = await UserRepository.create(user_data)
        
        if user:
            # Criar API key inicial usando o serviço migrado
            try:
                api_key_data = APIKeyCreate(
                    name="Chave Principal",
                    description="Chave de API criada automaticamente no registro"
                )
                api_key_response = await api_key_service.create_api_key(user["id"], api_key_data)
                
                logger.info(f"API key criada para usuário {user['id']}")
                
                return {
                    "id": user["id"],
                    "email": user["email"], 
                    "name": user["name"],
                    "api_key": api_key_response.key if api_key_response else None
                }
                
            except Exception as e:
                logger.warning(f"Erro ao criar API key: {e}")
                # Retorna usuário mesmo sem API key
                return {
                    "id": user["id"],
                    "email": user["email"],
                    "name": user["name"],
                    "api_key": None
                }
        
        raise HTTPException(status_code=500, detail="Erro ao criar usuário")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar usuário: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao criar usuário")

async def authenticate_user(email: str, password: str):
    """Autentica usuário com email e senha usando MariaDB"""
    try:
        # Buscar usuário por email no MariaDB
        user = await UserRepository.get_by_email(email)
        
        if not user:
            raise HTTPException(status_code=401, detail="E-mail não cadastrado")
            
        # Verificar se está ativo
        if not user.get('is_active', True):
            raise HTTPException(status_code=401, detail="Usuário desativado")
        
        # Verificar senha com bcrypt
        if not user.get('password_hash'):
            raise HTTPException(status_code=401, detail="Usuário sem senha configurada")
            
        if not verify_password(password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Senha incorreta")
        
        # Atualizar último login
        await UserRepository.update(user["id"], {
            "last_login": datetime.now()
        })
        
        # Buscar API keys ativas do usuário usando o serviço migrado
        api_keys = await api_key_service.get_user_api_keys(user["id"])
        
        api_key = None
        if api_keys:
            # Por segurança, não retornamos a chave real, apenas indicamos que existe
            api_key = "rcp_[chave_existente_verifique_dashboard]"
        
        return {
            "id": user["id"],
            "email": user["email"],
            "name": user.get("name", email.split('@')[0]),
            "api_key": api_key
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro na autenticação: {e}")
        raise HTTPException(status_code=500, detail="Erro interno na autenticação")

@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, response: Response):
    """Endpoint de login"""
    try:
        user = await authenticate_user(request.email, request.password)
        
        # Gerar token JWT
        jwt_token = generate_token(user["id"], user["email"])
        
        # Definir cookie de sessão
        response.set_cookie(
            key="auth_token",
            value=jwt_token,
            max_age=86400,  # 24 horas
            httponly=True,
            secure=False,  # Em produção, mudar para True com HTTPS
            samesite="lax"
        )
        
        return AuthResponse(
            success=True,
            token=jwt_token,
            api_key=user.get("api_key"),
            user_id=user["id"],
            email=user["email"],
            name=user["name"],
            message="Login realizado com sucesso"
        )
        
    except HTTPException as e:
        return AuthResponse(
            success=False,
            message=e.detail
        )
    except Exception as e:
        logger.error(f"Erro no login: {e}")
        return AuthResponse(
            success=False,
            message="Erro ao realizar login"
        )

@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest, response: Response):
    """Endpoint de registro/cadastro"""
    try:
        # Validações básicas
        if len(request.password) < 8:
            raise HTTPException(status_code=400, detail="Senha deve ter pelo menos 8 caracteres")
        
        password_hash = hash_password(request.password)
        
        # Criar usuário
        user = await create_user_in_db(
            email=request.email,
            password_hash=password_hash,
            name=request.name
        )
        
        # Gerar token JWT
        jwt_token = generate_token(user["id"], user["email"])
        
        # Definir cookie de sessão
        response.set_cookie(
            key="auth_token",
            value=jwt_token,
            max_age=86400,  # 24 horas
            httponly=True,
            secure=False,  # Em produção, mudar para True com HTTPS
            samesite="lax"
        )
        
        return AuthResponse(
            success=True,
            token=jwt_token,
            api_key=user.get("api_key"),
            user_id=user["id"],
            email=user["email"],
            name=user["name"],
            message="Conta criada com sucesso! Você ganhou 7 dias de trial."
        )
        
    except HTTPException as e:
        return AuthResponse(
            success=False,
            message=e.detail
        )
    except Exception as e:
        logger.error(f"Erro no registro: {e}")
        return AuthResponse(
            success=False,
            message="Erro ao criar conta"
        )

@router.post("/logout")
async def logout(response: Response):
    """Endpoint de logout"""
    response.delete_cookie(key="session_token")
    return {"success": True, "message": "Logout realizado com sucesso"}

@router.get("/verify")
async def verify_session(request: Request):
    """Verifica se a sessão é válida"""
    session_token = request.cookies.get("session_token")
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Não autenticado")
    
    # Em produção, você verificaria o token no banco
    # Por ora, vamos apenas confirmar que existe
    
    return {
        "authenticated": True,
        "message": "Sessão válida"
    }

@router.get("/dev-login")
async def dev_login_info():
    """Informações de login para desenvolvimento"""
    if os.getenv('DEV_MODE', 'false').lower() == 'true':
        return {
            "message": "Use estas credenciais para desenvolvimento:",
            "email": "dev@valida.api.br",
            "password": "dev123",
            "note": "Estas credenciais só funcionam em DEV_MODE=true"
        }
    else:
        raise HTTPException(status_code=404, detail="Endpoint disponível apenas em modo desenvolvimento")
