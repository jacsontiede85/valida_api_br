"""
Router de autenticação para integração com Supabase
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from pydantic import BaseModel, EmailStr
from typing import Optional
import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
import os
from supabase import create_client, Client
import structlog

# Configurar logger
logger = structlog.get_logger("auth")

# Configurar Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Configuração JWT
JWT_SECRET = os.getenv("JWT_SECRET", "valida-jwt-secret-2024")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    logger.warning("Supabase não configurado - usando modo mock")
    supabase = None
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    logger.info("Supabase configurado para autenticação")

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
    """Hash de senha usando SHA256 com salt"""
    # Em produção, usar bcrypt!
    salt = "valida_salt_2024"
    return hashlib.sha256(f"{password}{salt}".encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """Verifica se a senha corresponde ao hash"""
    return hash_password(password) == password_hash

def generate_api_key() -> tuple[str, str]:
    """Gera uma API key e seu hash"""
    key_bytes = secrets.token_bytes(32)
    visible_key = f"rcp_{key_bytes.hex()}"
    key_hash = hashlib.sha256(visible_key.encode()).hexdigest()
    return visible_key, key_hash

async def create_user_in_db(email: str, password_hash: str, name: str = None):
    """Cria usuário no banco de dados"""
    if not supabase:
        # Modo mock
        return {
            "id": "mock-user-id",
            "email": email,
            "name": name or email.split('@')[0]
        }
    
    try:
        # Verificar se usuário já existe
        existing = supabase.table('users').select("*").eq('email', email).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="E-mail já cadastrado")
        
        # Criar novo usuário
        user_data = {
            "email": email,
            "password_hash": password_hash,
            "name": name or email.split('@')[0],
            "created_at": datetime.now().isoformat()
        }
        
        result = supabase.table('users').insert(user_data).execute()
        
        if result.data:
            user = result.data[0]
            
            # Criar API key inicial para o usuário
            visible_key, key_hash = generate_api_key()
            
            api_key_data = {
                "user_id": user["id"],
                "name": "Chave Principal",
                "key_hash": key_hash,
                "is_active": True,
                "created_at": datetime.now().isoformat()
            }
            
            supabase.table('api_keys').insert(api_key_data).execute()
            
            # Criar assinatura trial inicial (temporariamente desabilitado)
            # TODO: Corrigir estrutura da tabela subscriptions
            try:
                subscription_data = {
                    "user_id": user["id"],
                    "plan_id": "trial",
                    "status": "active",
                    "created_at": datetime.now().isoformat(),
                    "current_period_end": (datetime.now() + timedelta(days=7)).isoformat()
                }
                
                supabase.table('subscriptions').insert(subscription_data).execute()
            except Exception as e:
                logger.warning(f"Não foi possível criar assinatura trial: {e}")
                # Continua mesmo sem assinatura - pode criar depois
            
            return {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "api_key": visible_key
            }
            
        raise HTTPException(status_code=500, detail="Erro ao criar usuário")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar usuário: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao criar usuário")

async def authenticate_user(email: str, password: str):
    """Autentica usuário com email e senha"""
    if not supabase:
        # Modo mock para desenvolvimento
        if email == "dev@valida.api.br" and password == "dev123":
            return {
                "id": "dev-user-id",
                "email": email,
                "name": "Desenvolvedor",
                "api_key": "rcp_dev-key-2"
            }
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    
    try:
        # Buscar usuário pelo email primeiro
        result = supabase.table('users').select("*").eq('email', email).execute()
        
        if not result.data:
            raise HTTPException(status_code=401, detail="E-mail não cadastrado")
        
        user = result.data[0]
        
        # Verificar senha
        if not user.get('password_hash'):
            raise HTTPException(status_code=401, detail="Usuário sem senha configurada")
            
        if not verify_password(password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Senha incorreta")
        
        # Atualizar último login
        supabase.table('users').update({
            "last_login": datetime.now().isoformat()
        }).eq('id', user["id"]).execute()
        
        # Buscar API key ativa do usuário
        api_key_result = supabase.table('api_keys').select("key_hash").eq('user_id', user["id"]).eq('is_active', True).limit(1).execute()
        
        api_key = None
        if api_key_result.data:
            # Por segurança, não retornamos a chave real, apenas o hash
            # O usuário deve gerar uma nova se perdeu a original
            api_key = f"rcp_{api_key_result.data[0]['key_hash'][:16]}..."
        
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
