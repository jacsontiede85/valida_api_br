"""
Conexão com banco de dados MariaDB (migração de Supabase)
"""
import pymysql
from pymysql.cursors import DictCursor
from typing import Optional, Dict, Any, List
import os
import structlog
from contextlib import contextmanager
import uuid

# Logger
logger = structlog.get_logger("database")

# Configuração MariaDB - usar variáveis corretas
from dotenv import load_dotenv

# Garantir que .env seja carregado
load_dotenv()

MARIADB_HOST = os.getenv("MARIADB_HOST", "localhost")
MARIADB_PORT = int(os.getenv("MARIADB_PORT", "3306"))
MARIADB_USER = os.getenv("MARIADB_USER", "valida_saas")
MARIADB_PASSWORD = os.getenv("MARIADB_PASS", "")  # Corrigido: MARIADB_PASS
MARIADB_DATABASE = os.getenv("MARIADB_DATABASE", "valida_saas")
MARIADB_CHARSET = os.getenv("MARIADB_CHARSET", "utf8mb4")

# Log de configuração para debug
logger.info("Configuração MariaDB carregada",
           host=MARIADB_HOST,
           port=MARIADB_PORT, 
           user=MARIADB_USER,
           database=MARIADB_DATABASE,
           has_password=bool(MARIADB_PASSWORD))

# Pool de conexões (singleton)
_connection_pool: Optional[pymysql.Connection] = None

def get_mariadb_connection() -> pymysql.Connection:
    """Retorna conexão MariaDB (singleton com reconexão automática)"""
    global _connection_pool
    
    if _connection_pool is None or not _connection_pool.open:
        if not MARIADB_HOST or not MARIADB_USER:
            raise ValueError("Variáveis MARIADB_HOST e MARIADB_USER são obrigatórias")
        
        try:
            _connection_pool = pymysql.connect(
                host=MARIADB_HOST,
                port=MARIADB_PORT,
                user=MARIADB_USER,
                password=MARIADB_PASSWORD,
                database=MARIADB_DATABASE,
                charset=MARIADB_CHARSET,
                cursorclass=DictCursor,
                autocommit=True,  # Auto-commit para compatibilidade
                connect_timeout=10,
                read_timeout=30,
                write_timeout=30
            )
            logger.info("Conexão MariaDB inicializada", 
                       host=MARIADB_HOST, 
                       database=MARIADB_DATABASE)
        except Exception as e:
            logger.error("Erro ao conectar com MariaDB", error=str(e))
            raise
    
    return _connection_pool

def get_db_connection():
    """Alias para get_mariadb_connection - compatibilidade"""
    return get_mariadb_connection()

# Função para compatibilidade com cliente Supabase (será removida após migração completa)
def get_supabase_client():
    """DEPRECATED: Compatibilidade temporária - usar get_mariadb_connection()"""
    logger.warning("get_supabase_client() está deprecated - migre para get_mariadb_connection()")
    return get_mariadb_connection()

@contextmanager
def get_db_cursor():
    """Context manager para cursor de banco de dados"""
    connection = get_mariadb_connection()
    cursor = connection.cursor()
    try:
        yield cursor
    except Exception as e:
        logger.error("Erro na execução de query", error=str(e))
        connection.rollback()
        raise
    finally:
        cursor.close()

# Funções de conveniência para operações SQL
async def execute_sql(sql: str, params: tuple = (), fetch: str = "all") -> Dict[str, Any]:
    """
    Executa query SQL no MariaDB
    
    Args:
        sql: Query SQL
        params: Parâmetros da query
        fetch: Tipo de retorno ("all", "one", "none")
    
    Returns:
        Dict com resultado da query
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(sql, params)
            
            if fetch == "all":
                data = cursor.fetchall()
            elif fetch == "one":
                data = cursor.fetchone()
            else:
                data = None
            
            return {
                "data": data,
                "count": cursor.rowcount,
                "error": None
            }
            
    except Exception as e:
        logger.error("Erro na execução SQL", sql=sql, error=str(e))
        return {
            "data": None,
            "count": 0, 
            "error": str(e)
        }

def generate_uuid() -> str:
    """Gera UUID compatível com MariaDB"""
    return str(uuid.uuid4())

async def execute_query(table: str, query_type: str = "select", **kwargs):
    """
    DEPRECATED: Função de compatibilidade com padrão Supabase
    Migre para execute_sql() para melhor performance
    """
    logger.warning("execute_query() deprecated - use execute_sql()")
    
    try:
        if query_type == "select":
            # Construir SELECT
            select_fields = kwargs.get("select", "*")
            conditions = []
            params = []
            
            for key, value in kwargs.items():
                if key.startswith("eq_"):
                    column = key[3:]
                    conditions.append(f"{column} = %s")
                    params.append(value)
            
            where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
            sql = f"SELECT {select_fields} FROM {table}{where_clause}"
            
            return await execute_sql(sql, tuple(params), "all")
            
        elif query_type == "insert":
            data = kwargs.get("data", {})
            if not data:
                raise ValueError("Dados obrigatórios para INSERT")
            
            # Adicionar UUID se não existir
            if 'id' not in data:
                data['id'] = generate_uuid()
            
            columns = list(data.keys())
            placeholders = ["%s"] * len(columns)
            values = list(data.values())
            
            sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            
            return await execute_sql(sql, tuple(values), "none")
            
        elif query_type == "update":
            data = kwargs.get("data", {})
            if not data:
                raise ValueError("Dados obrigatórios para UPDATE")
            
            set_clauses = []
            params = []
            
            for key, value in data.items():
                set_clauses.append(f"{key} = %s")
                params.append(value)
            
            conditions = []
            for key, value in kwargs.items():
                if key.startswith("eq_"):
                    column = key[3:]
                    conditions.append(f"{column} = %s")
                    params.append(value)
            
            if not conditions:
                raise ValueError("Condições WHERE obrigatórias para UPDATE")
            
            where_clause = f" WHERE {' AND '.join(conditions)}"
            sql = f"UPDATE {table} SET {', '.join(set_clauses)}{where_clause}"
            
            return await execute_sql(sql, tuple(params), "none")
            
        elif query_type == "delete":
            conditions = []
            params = []
            
            for key, value in kwargs.items():
                if key.startswith("eq_"):
                    column = key[3:]
                    conditions.append(f"{column} = %s")
                    params.append(value)
            
            if not conditions:
                raise ValueError("Condições WHERE obrigatórias para DELETE")
            
            where_clause = f" WHERE {' AND '.join(conditions)}"
            sql = f"DELETE FROM {table}{where_clause}"
            
            return await execute_sql(sql, tuple(params), "none")
            
    except Exception as e:
        logger.error(f"Erro na query {query_type} na tabela {table}", error=str(e))
        raise

# Funções específicas para tabelas principais
class UserRepository:
    """Repository para operações com usuários - Migrado para MariaDB"""
    
    @staticmethod
    async def get_by_id(user_id: str):
        """Busca usuário por ID"""
        result = await execute_sql("SELECT * FROM users WHERE id = %s", (user_id,), "one")
        return result["data"] if result["data"] else None
    
    @staticmethod
    async def get_by_email(email: str):
        """Busca usuário por email"""
        result = await execute_sql("SELECT * FROM users WHERE email = %s", (email,), "one")
        return result["data"] if result["data"] else None
    
    @staticmethod
    async def create(user_data: dict):
        """Cria novo usuário"""
        # Adicionar UUID se não existir
        if 'id' not in user_data:
            user_data['id'] = generate_uuid()
            
        columns = list(user_data.keys())
        placeholders = ["%s"] * len(columns)
        values = list(user_data.values())
        
        sql = f"INSERT INTO users ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        result = await execute_sql(sql, tuple(values), "none")
        
        if result["error"]:
            raise Exception(result["error"])
        
        # Retornar usuário criado
        return await UserRepository.get_by_id(user_data['id'])
    
    @staticmethod
    async def update(user_id: str, user_data: dict):
        """Atualiza usuário"""
        if not user_data:
            raise ValueError("Dados obrigatórios para UPDATE")
        
        set_clauses = []
        params = []
        
        for key, value in user_data.items():
            set_clauses.append(f"{key} = %s")
            params.append(value)
        
        params.append(user_id)  # Para WHERE
        sql = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = %s"
        
        result = await execute_sql(sql, tuple(params), "none")
        
        if result["error"]:
            raise Exception(result["error"])
            
        return await UserRepository.get_by_id(user_id)

class SubscriptionRepository:
    """Repository para operações com assinaturas - Migrado para MariaDB"""
    
    @staticmethod
    async def get_by_user_id(user_id: str):
        """Busca assinatura ativa do usuário"""
        sql = "SELECT * FROM subscriptions WHERE user_id = %s AND status = 'active' ORDER BY created_at DESC LIMIT 1"
        result = await execute_sql(sql, (user_id,), "one")
        return result["data"] if result["data"] else None
    
    @staticmethod
    async def create(subscription_data: dict):
        """Cria nova assinatura"""
        if 'id' not in subscription_data:
            subscription_data['id'] = generate_uuid()
            
        columns = list(subscription_data.keys())
        placeholders = ["%s"] * len(columns)
        values = list(subscription_data.values())
        
        sql = f"INSERT INTO subscriptions ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        result = await execute_sql(sql, tuple(values), "none")
        
        if result["error"]:
            raise Exception(result["error"])
            
        return await SubscriptionRepository.get_by_id(subscription_data['id'])
    
    @staticmethod
    async def get_by_id(subscription_id: str):
        """Busca assinatura por ID"""
        result = await execute_sql("SELECT * FROM subscriptions WHERE id = %s", (subscription_id,), "one")
        return result["data"] if result["data"] else None
    
    @staticmethod
    async def update(subscription_id: str, subscription_data: dict):
        """Atualiza assinatura"""
        if not subscription_data:
            raise ValueError("Dados obrigatórios para UPDATE")
        
        set_clauses = []
        params = []
        
        for key, value in subscription_data.items():
            set_clauses.append(f"{key} = %s")
            params.append(value)
        
        params.append(subscription_id)  # Para WHERE
        sql = f"UPDATE subscriptions SET {', '.join(set_clauses)} WHERE id = %s"
        
        result = await execute_sql(sql, tuple(params), "none")
        
        if result["error"]:
            raise Exception(result["error"])
            
        return await SubscriptionRepository.get_by_id(subscription_id)

class CreditTransactionRepository:
    """Repository para operações com transações de crédito - Migrado para MariaDB"""
    
    @staticmethod
    async def get_by_user_id(user_id: str, limit: int = 10):
        """Busca transações do usuário"""
        sql = "SELECT * FROM credit_transactions WHERE user_id = %s ORDER BY created_at DESC LIMIT %s"
        result = await execute_sql(sql, (user_id, limit), "all")
        return result["data"] if result["data"] else []
    
    @staticmethod
    async def create(transaction_data: dict):
        """Cria nova transação (trigger atualiza saldo automaticamente)"""
        if 'id' not in transaction_data:
            transaction_data['id'] = generate_uuid()
            
        columns = list(transaction_data.keys())
        placeholders = ["%s"] * len(columns)
        values = list(transaction_data.values())
        
        sql = f"INSERT INTO credit_transactions ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        result = await execute_sql(sql, tuple(values), "none")
        
        if result["error"]:
            raise Exception(result["error"])
            
        return await CreditTransactionRepository.get_by_id(transaction_data['id'])
    
    @staticmethod
    async def get_by_id(transaction_id: str):
        """Busca transação por ID"""
        result = await execute_sql("SELECT * FROM credit_transactions WHERE id = %s", (transaction_id,), "one")
        return result["data"] if result["data"] else None
    
    @staticmethod
    async def get_user_balance(user_id: str):
        """Calcula saldo atual do usuário (última transação)"""
        sql = "SELECT balance_after_cents FROM credit_transactions WHERE user_id = %s ORDER BY created_at DESC LIMIT 1"
        result = await execute_sql(sql, (user_id,), "one")
        
        if result["data"]:
            return result["data"]["balance_after_cents"]
        return 0

# Função de inicialização
async def init_database():
    """Inicializa conexão com banco de dados"""
    try:
        connection = get_mariadb_connection()
        logger.info("Banco de dados inicializado com sucesso")
        return True
    except Exception as e:
        logger.error("Falha ao inicializar banco de dados", error=str(e))
        return False

# Função de teste de conectividade
async def test_connection():
    """Testa conectividade com banco de dados"""
    try:
        result = await execute_sql("SELECT 1 as test", (), "one")
        return result["data"]["test"] == 1
    except Exception as e:
        logger.error("Falha no teste de conectividade", error=str(e))
        return False
