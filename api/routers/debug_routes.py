"""
Rotas temporárias para debug do sistema de créditos
"""

from fastapi import APIRouter, Header, HTTPException
from typing import Optional
import structlog
from datetime import datetime

from api.middleware.auth_middleware import get_supabase_client

router = APIRouter()
logger = structlog.get_logger("debug_routes")

@router.get("/debug/user-credits")
async def debug_user_credits(authorization: Optional[str] = Header(None)):
    """
    Endpoint de debug para verificar créditos do usuário
    Aceita tanto JWT token quanto API key
    """
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Token necessário")
        
        token = authorization.replace("Bearer ", "")
        user_id = "c81cf3f0-f3e6-4075-8ba0-ddbba9955de0"  # ID fixo para debug
        
        logger.info(f"Debug: Buscando créditos para user_id: {user_id}")
        logger.info(f"Debug: Token recebido: {token[:20]}...")
        
        # Conectar ao Supabase
        supabase = get_supabase_client()
        if not supabase:
            logger.warning("Supabase não configurado - retornando dados mock")
            return {
                "source": "mock",
                "user_id": user_id,
                "available": 1000.01,
                "total": 1010.00,
                "used": 9.99,
                "message": "Dados mock - Supabase não configurado"
            }
        
        # Buscar créditos do usuário
        try:
            user_credits_result = supabase.table("user_credits").select("*").eq("user_id", user_id).execute()
            
            if user_credits_result.data:
                credits = user_credits_result.data[0]
                
                return {
                    "source": "supabase",
                    "user_id": user_id,
                    "available": credits['available_credits_cents'] / 100.0,
                    "total": credits['total_purchased_cents'] / 100.0,
                    "used": credits['total_used_cents'] / 100.0,
                    "raw_data": credits,
                    "message": "Dados obtidos do Supabase"
                }
            else:
                logger.warning(f"Nenhum registro de créditos encontrado para user_id: {user_id}")
                return {
                    "source": "supabase",
                    "user_id": user_id,
                    "available": 0.0,
                    "total": 0.0,
                    "used": 0.0,
                    "message": "Usuário não encontrado na tabela user_credits"
                }
                
        except Exception as db_error:
            logger.error(f"Erro ao buscar créditos no banco: {db_error}")
            raise HTTPException(status_code=500, detail=f"Erro no banco de dados: {str(db_error)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro geral no debug de créditos: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@router.get("/debug/transactions")
async def debug_user_transactions(authorization: Optional[str] = Header(None)):
    """
    Endpoint de debug para verificar transações do usuário
    """
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Token necessário")
        
        user_id = "c81cf3f0-f3e6-4075-8ba0-ddbba9955de0"  # ID fixo para debug
        
        # Conectar ao Supabase
        supabase = get_supabase_client()
        if not supabase:
            return {
                "source": "mock",
                "user_id": user_id,
                "transactions": [],
                "message": "Supabase não configurado"
            }
        
        # Buscar últimas 10 transações
        transactions_result = supabase.table("credit_transactions").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(10).execute()
        
        transactions = []
        for txn in transactions_result.data:
            transactions.append({
                "id": txn["id"],
                "type": txn["type"],
                "amount_cents": txn["amount_cents"],
                "amount_reais": txn["amount_cents"] / 100.0,
                "balance_after_cents": txn.get("balance_after_cents"),
                "balance_after_reais": (txn.get("balance_after_cents") or 0) / 100.0,
                "description": txn["description"],
                "created_at": txn["created_at"]
            })
        
        return {
            "source": "supabase",
            "user_id": user_id,
            "total_transactions": len(transactions),
            "transactions": transactions,
            "message": f"Últimas {len(transactions)} transações"
        }
        
    except Exception as e:
        logger.error(f"Erro ao buscar transações: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@router.get("/debug/all-tables")
async def debug_all_tables(authorization: Optional[str] = Header(None)):
    """
    Endpoint de debug para verificar todos os dados relacionados ao usuário
    """
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Token necessário")
        
        user_id = "c81cf3f0-f3e6-4075-8ba0-ddbba9955de0"  # ID fixo para debug
        
        # Conectar ao Supabase
        supabase = get_supabase_client()
        if not supabase:
            return {
                "source": "mock",
                "message": "Supabase não configurado"
            }
        
        result = {
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        
        # Buscar dados da tabela users
        try:
            user_result = supabase.table("users").select("id, email, name, credits, created_at").eq("id", user_id).execute()
            result["users_table"] = user_result.data[0] if user_result.data else None
        except Exception as e:
            result["users_table_error"] = str(e)
        
        # Buscar dados da tabela user_credits
        try:
            credits_result = supabase.table("user_credits").select("*").eq("user_id", user_id).execute()
            result["user_credits_table"] = credits_result.data[0] if credits_result.data else None
        except Exception as e:
            result["user_credits_table_error"] = str(e)
        
        # Buscar API keys
        try:
            api_keys_result = supabase.table("api_keys").select("id, name, is_active, created_at").eq("user_id", user_id).execute()
            result["api_keys_table"] = api_keys_result.data
        except Exception as e:
            result["api_keys_table_error"] = str(e)
        
        # Buscar últimas 5 transações
        try:
            transactions_result = supabase.table("credit_transactions").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(5).execute()
            result["recent_transactions"] = transactions_result.data
        except Exception as e:
            result["recent_transactions_error"] = str(e)
        
        return result
        
    except Exception as e:
        logger.error(f"Erro no debug completo: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
