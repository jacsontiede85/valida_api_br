"""
Configuração de logging estruturado para o sistema RPA
"""

import structlog
import logging
import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import pytz

from .settings import settings

class LoggingConfig:
    """Configuração centralizada de logging estruturado"""
    
    @staticmethod
    def _brazil_timestamper(logger, method_name, event_dict):
        """
        Processador customizado de timestamp para usar horário de Brasília (America/Sao_Paulo).
        """
        brazil_tz = pytz.timezone('America/Sao_Paulo')
        now = datetime.now(brazil_tz)
        event_dict["timestamp"] = now.isoformat()
        return event_dict
    
    @staticmethod
    def setup_logging() -> structlog.BoundLogger:
        """
        Configura o sistema de logging estruturado
        
        Returns:
            structlog.BoundLogger: Logger configurado
        """
        # Criar diretório de logs se não existir
        settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Arquivo de log com timestamp
        log_file = settings.LOGS_DIR / f"resolve_rpa_{datetime.now().strftime('%Y%m%d')}.log"
        
        # Configurar logging padrão do Python
        logging.basicConfig(
            level=getattr(logging, settings.LOG_LEVEL.upper()),
            format="%(message)s",
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Configurar structlog
        structlog.configure(
            processors=[
                LoggingConfig._brazil_timestamper,  # Usar timestamp brasileiro
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.dev.set_exc_info,
                LoggingConfig._add_context_processor,
                structlog.processors.JSONRenderer()
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(logging, settings.LOG_LEVEL.upper())
            ),
            logger_factory=structlog.WriteLoggerFactory(),
            cache_logger_on_first_use=True,
        )
        
        return structlog.get_logger("resolve_rpa")
    
    @staticmethod
    def _add_context_processor(logger, method_name, event_dict):
        """Adiciona contexto adicional aos logs"""
        event_dict["service"] = "resolve_rpa"
        event_dict["version"] = "1.0.0"
        return event_dict
    
    @staticmethod
    def setup_performance_logging() -> structlog.BoundLogger:
        """
        Configura logging específico para métricas de performance
        
        Returns:
            structlog.BoundLogger: Logger para performance
        """
        perf_log_file = settings.LOGS_DIR / f"performance_{datetime.now().strftime('%Y%m%d')}.log"
        
        perf_handler = logging.FileHandler(perf_log_file, encoding='utf-8')
        perf_logger = logging.getLogger("performance")
        perf_logger.addHandler(perf_handler)
        perf_logger.setLevel(logging.INFO)
        
        return structlog.get_logger("performance")

# Funções utilitárias para logging
def log_operation_start(logger: structlog.BoundLogger, operation: str, **context):
    """Loga o início de uma operação"""
    logger.info("operation_started", operation=operation, **context)

def log_operation_success(logger: structlog.BoundLogger, operation: str, duration: float = None, **context):
    """Loga o sucesso de uma operação"""
    log_data = {"operation": operation, "status": "success", **context}
    if duration:
        log_data["duration_seconds"] = duration
    logger.info("operation_completed", **log_data)

def log_operation_error(logger: structlog.BoundLogger, operation: str, error: Exception, **context):
    """Loga um erro em uma operação"""
    logger.error(
        "operation_failed",
        operation=operation,
        error_type=type(error).__name__,
        error_message=str(error),
        **context
    )

def log_scraping_metrics(logger: structlog.BoundLogger, 
                        cnpj: str,
                        success: bool,
                        duration: float,
                        protestos_found: int = 0,
                        cartorios_count: int = 0):
    """Loga métricas específicas de scraping"""
    # Usar timezone brasileiro para consistency
    brazil_tz = pytz.timezone('America/Sao_Paulo')
    timestamp_br = datetime.now(brazil_tz).isoformat()
    
    logger.info(
        "scraping_metrics",
        cnpj=cnpj,
        success=success,
        duration_seconds=duration,
        protestos_found=protestos_found,
        cartorios_count=cartorios_count,
        timestamp=timestamp_br
    )

# Decorador para logging automático
def logged_operation(operation_name: str):
    """
    Decorador para logging automático de operações
    
    Args:
        operation_name (str): Nome da operação para logging
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            logger = structlog.get_logger()
            start_time = datetime.now()
            
            log_operation_start(logger, operation_name)
            
            try:
                result = await func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                log_operation_success(logger, operation_name, duration)
                return result
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                log_operation_error(logger, operation_name, e, duration_seconds=duration)
                raise
        
        def sync_wrapper(*args, **kwargs):
            logger = structlog.get_logger()
            start_time = datetime.now()
            
            log_operation_start(logger, operation_name)
            
            try:
                result = func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                log_operation_success(logger, operation_name, duration)
                return result
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                log_operation_error(logger, operation_name, e, duration_seconds=duration)
                raise
        
        return async_wrapper if hasattr(func, '__code__') and func.__code__.co_flags & 0x80 else sync_wrapper
    return decorator
