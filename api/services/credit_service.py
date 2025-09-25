"""
Serviço de Gerenciamento de Créditos
Responsável por adicionar, consumir e consultar créditos dos usuários
Migrado para MariaDB com custos dinâmicos da tabela consultation_types
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
import structlog
from fastapi import HTTPException

from api.database.connection import execute_sql, generate_uuid

logger = structlog.get_logger(__name__)


class InsufficientCreditsError(Exception):
    """
    Exceção customizada para quando o usuário não tem créditos suficientes
    """
    def __init__(self, current_balance: float, required_amount: float, message: str = None):
        self.current_balance = current_balance
        self.required_amount = required_amount
        if message is None:
            message = f"Créditos insuficientes. Saldo: R$ {current_balance:.2f}, Necessário: R$ {required_amount:.2f}"
        self.message = message
        super().__init__(self.message)


# Cache para custos de consulta (evita múltiplas queries ao banco)
_consultation_costs_cache = {}
_cache_last_updated = None
CACHE_TTL_SECONDS = 300  # 5 minutos


async def add_user_credits(
    user_id: str, 
    amount: float, 
    description: str,
    stripe_payment_intent_id: Optional[str] = None,
    stripe_invoice_id: Optional[str] = None
) -> dict:
    """
    Adiciona créditos ao usuário via transação
    O trigger do banco MariaDB atualizará automaticamente o saldo em users.credits
    """
    try:
        amount_cents = int(amount * 100)
        transaction_id = generate_uuid()
        
        # Query SQL para inserir transação de crédito
        sql = """
        INSERT INTO credit_transactions 
        (id, user_id, type, amount_cents, description, stripe_payment_intent_id, stripe_invoice_id, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        params = (
            transaction_id,
            user_id, 
            "purchase",
            amount_cents,
            description,
            stripe_payment_intent_id,
            stripe_invoice_id,
            datetime.now()
        )
        
        result = await execute_sql(sql, params, "none")
        
        if result["error"]:
            raise HTTPException(status_code=500, detail=f"Erro ao inserir transação: {result['error']}")
        
        logger.info(f"✅ Créditos adicionados: R$ {amount:.2f} para usuário {user_id}")
        
        # Buscar saldo atualizado (o trigger já atualizou users.credits)
        balance = await get_user_balance(user_id)
        
        return {
            "transaction_id": transaction_id,
            "amount_added": amount,
            "new_balance": balance,
            "description": description
        }
            
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar créditos: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao adicionar créditos: {str(e)}")


async def consume_credits(
    user_id: str, 
    amount: float, 
    description: str,
    consultation_id: Optional[str] = None
) -> dict:
    """
    Consome créditos do usuário para uma consulta
    Verifica saldo antes de debitar
    """
    try:
        # Verificar saldo atual
        current_balance = await get_user_balance(user_id)
        if current_balance < amount:
            # Lançar exceção customizada para créditos insuficientes
            raise InsufficientCreditsError(
                current_balance=current_balance,
                required_amount=amount
            )
        
        # Registrar consumo (valor negativo para debitar)
        amount_cents = int(-amount * 100)  # Negativo para debitar
        transaction_id = generate_uuid()
        
        # Query SQL para inserir transação de débito
        sql = """
        INSERT INTO credit_transactions 
        (id, user_id, consultation_id, type, amount_cents, description, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        params = (
            transaction_id,
            user_id,
            consultation_id,
            "spend",
            amount_cents,
            description,
            datetime.now()
        )
        
        result = await execute_sql(sql, params, "none")
        
        if result["error"]:
            raise HTTPException(status_code=500, detail=f"Erro ao registrar consumo: {result['error']}")
        
        logger.info(f"💰 Créditos consumidos: R$ {amount:.2f} do usuário {user_id}")
        
        # Buscar saldo atualizado (o trigger já atualizou users.credits)
        new_balance = await get_user_balance(user_id)
        
        return {
            "transaction_id": transaction_id,
            "amount_consumed": amount,
            "new_balance": new_balance,
            "description": description
        }
            
    except InsufficientCreditsError:
        raise  # Re-raise insufficient credits error
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"❌ Erro ao consumir créditos: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao consumir créditos: {str(e)}")


async def get_user_balance(user_id: str) -> float:
    """
    Retorna o saldo atual de créditos do usuário da tabela users
    """
    try:
        # Query SQL para buscar saldo do usuário
        sql = "SELECT credits FROM users WHERE id = %s"
        result = await execute_sql(sql, (user_id,), "one")
        
        if result["error"]:
            logger.error(f"❌ Erro SQL ao buscar créditos: {result['error']}")
            return 0.0
        
        if result["data"]:
            credits = result["data"].get("credits", 0)
            # Converter Decimal para float se necessário
            return float(credits) if credits is not None else 0.0
        else:
            logger.warning(f"⚠️ Usuário {user_id} não encontrado para consulta de créditos")
            return 0.0
            
    except Exception as e:
        logger.error(f"❌ Erro ao buscar créditos do usuário {user_id}: {e}")
        return 0.0


async def get_user_credit_summary(user_id: str) -> dict:
    """
    Retorna um resumo completo dos créditos do usuário
    """
    try:
        # Buscar saldo atual
        current_balance = await get_user_balance(user_id)
        
        # Buscar estatísticas de transações com query SQL simplificada
        sql = """
        SELECT 
            type, 
            SUM(ABS(amount_cents)) as total_amount,
            COUNT(*) as count
        FROM credit_transactions 
        WHERE user_id = %s 
        GROUP BY type
        """
        
        result = await execute_sql(sql, (user_id,), "all")
        
        total_purchased = 0.0
        total_spent = 0.0
        transaction_count = 0
        
        if result["data"]:
            for row in result["data"]:
                # Converter Decimal para float antes da divisão
                total_amount = float(row["total_amount"]) if row["total_amount"] else 0.0
                amount = total_amount / 100.0
                count = row["count"]
                transaction_count += count
                
                if row["type"] in ["purchase", "add"]:
                    total_purchased += amount
                elif row["type"] in ["spend", "subtract"]:
                    total_spent += amount
        
        return {
            "available": current_balance,
            "total_purchased": total_purchased,
            "total_spent": total_spent,
            "transaction_count": transaction_count
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar resumo de créditos: {e}")
        return {
            "available": 0.0,
            "total_purchased": 0.0,
            "total_spent": 0.0,
            "transaction_count": 0
        }


async def get_recent_credit_transactions(user_id: str, limit: int = 10) -> list:
    """
    Retorna as transações recentes de crédito do usuário
    """
    try:
        # Query SQL para buscar transações recentes
        sql = """
        SELECT 
            id, type, amount_cents, description, created_at, 
            stripe_payment_intent_id, stripe_invoice_id
        FROM credit_transactions 
        WHERE user_id = %s 
        ORDER BY created_at DESC 
        LIMIT %s
        """
        
        result = await execute_sql(sql, (user_id, limit), "all")
        
        if result["error"]:
            logger.error(f"❌ Erro SQL ao buscar transações: {result['error']}")
            return []
        
        if result["data"]:
            # Formatear transações para o frontend
            formatted_transactions = []
            for transaction in result["data"]:
                # Converter Decimal para float se necessário
                amount_cents = float(transaction["amount_cents"]) if transaction["amount_cents"] else 0.0
                formatted_transactions.append({
                    "id": transaction["id"],
                    "type": transaction["type"],
                    "amount": abs(amount_cents) / 100.0,
                    "amount_cents": int(amount_cents),
                    "description": transaction["description"],
                    "created": transaction["created_at"].isoformat() if transaction["created_at"] else None,
                    "status": "completed",  # Por enquanto todas são completed
                    "stripe_payment_intent_id": transaction.get("stripe_payment_intent_id"),
                    "stripe_invoice_id": transaction.get("stripe_invoice_id")
                })
            
            return formatted_transactions
        else:
            return []
            
    except Exception as e:
        logger.error(f"❌ Erro ao buscar transações recentes: {e}")
        return []


async def validate_sufficient_credits(user_id: str, required_amount: float) -> bool:
    """
    Valida se o usuário tem créditos suficientes para uma operação
    """
    try:
        current_balance = await get_user_balance(user_id)
        return current_balance >= required_amount
    except Exception as e:
        logger.error(f"❌ Erro ao validar créditos suficientes: {e}")
        return False


async def get_consultation_cost(consultation_type: str) -> float:
    """
    Retorna o custo de uma consulta baseado no tipo
    Busca dinamicamente da tabela consultation_types com cache
    """
    global _consultation_costs_cache, _cache_last_updated
    
    try:
        # Verificar se cache precisa ser atualizado
        now = datetime.now()
        if (_cache_last_updated is None or 
            (now - _cache_last_updated).total_seconds() > CACHE_TTL_SECONDS):
            await _reload_consultation_costs_cache()
            _cache_last_updated = now
        
        # Buscar no cache
        consultation_code = consultation_type.lower()
        if consultation_code in _consultation_costs_cache:
            return _consultation_costs_cache[consultation_code]
        
        # Se não encontrado no cache, tentar buscar direto do banco
        sql = """
        SELECT cost_cents 
        FROM consultation_types 
        WHERE code = %s AND is_active = 1
        LIMIT 1
        """
        
        result = await execute_sql(sql, (consultation_code,), "one")
        
        if result["data"] and result["data"]["cost_cents"] is not None:
            cost_reais = result["data"]["cost_cents"] / 100.0
            # Adicionar ao cache para próxima consulta
            _consultation_costs_cache[consultation_code] = cost_reais
            return cost_reais
        
        # Fallback para valor padrão se não encontrado
        logger.warning(f"⚠️ Tipo de consulta não encontrado: {consultation_type}, usando custo padrão")
        return 0.03  # R$ 0,03 padrão
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar custo de consulta: {e}")
        return 0.03  # R$ 0,03 como fallback seguro


async def _reload_consultation_costs_cache():
    """
    Recarrega cache de custos da tabela consultation_types
    """
    global _consultation_costs_cache
    
    try:
        sql = """
        SELECT code, cost_cents 
        FROM consultation_types 
        WHERE is_active = 1
        """
        
        result = await execute_sql(sql, (), "all")
        
        if result["error"]:
            logger.error(f"❌ Erro SQL ao carregar custos: {result['error']}")
            return
        
        # Atualizar cache (converter centavos para reais)
        new_cache = {}
        if result["data"]:
            for row in result["data"]:
                code = row["code"].lower()
                cost_reais = row["cost_cents"] / 100.0
                new_cache[code] = cost_reais
                
            _consultation_costs_cache = new_cache
            logger.info(f"✅ Cache de custos atualizado: {len(new_cache)} tipos carregados")
        
    except Exception as e:
        logger.error(f"❌ Erro ao recarregar cache de custos: {e}")


async def calculate_total_consultation_cost(consultation_types: list) -> float:
    """
    Calcula o custo total de uma consulta baseado nos tipos solicitados
    """
    total_cost = 0.0
    
    for consultation_type in consultation_types:
        cost = await get_consultation_cost(consultation_type)
        total_cost += cost
    
    return total_cost


async def get_all_consultation_costs() -> dict:
    """
    Retorna todos os custos de consulta disponíveis
    """
    global _consultation_costs_cache, _cache_last_updated
    
    # Verificar se cache precisa ser atualizado
    now = datetime.now()
    if (_cache_last_updated is None or 
        (now - _cache_last_updated).total_seconds() > CACHE_TTL_SECONDS):
        await _reload_consultation_costs_cache()
        _cache_last_updated = now
    
    return _consultation_costs_cache.copy()


class CreditService:
    """
    Classe wrapper para manter compatibilidade com importações existentes
    """
    
    def __init__(self):
        # Custos serão carregados dinamicamente da tabela consultation_types
        self.costs = {}  # Mantido vazio, será preenchido via get_all_costs()
    
    async def get_user_credits(self, user_id: str) -> dict:
        """Wrapper para função get_user_balance"""
        balance = await get_user_balance(user_id)
        return {
            "available_credits_cents": int(balance * 100),
            "available": balance
        }
    
    async def add_user_credits(self, user_id: str, amount: float, description: str, 
                              stripe_payment_intent_id: str = None, stripe_invoice_id: str = None):
        """Wrapper para função add_user_credits"""
        return await add_user_credits(user_id, amount, description, stripe_payment_intent_id, stripe_invoice_id)
    
    async def consume_credits(self, user_id: str, amount: float, description: str, consultation_id: str = None):
        """Wrapper para função consume_credits"""
        return await consume_credits(user_id, amount, description, consultation_id)
    
    async def get_user_credit_summary(self, user_id: str):
        """Wrapper para função get_user_credit_summary"""
        return await get_user_credit_summary(user_id)
    
    async def validate_sufficient_credits(self, user_id: str, required_amount: float):
        """Wrapper para função validate_sufficient_credits"""
        return await validate_sufficient_credits(user_id, required_amount)
    
    async def get_consultation_cost(self, consultation_type: str):
        """Wrapper para função get_consultation_cost"""
        return await get_consultation_cost(consultation_type)
    
    async def get_all_costs(self) -> dict:
        """
        Retorna todos os custos de consulta disponíveis
        Atualiza também o cache interno self.costs
        """
        costs = await get_all_consultation_costs()
        self.costs = costs
        return costs


# Instância singleton para compatibilidade
credit_service = CreditService()
