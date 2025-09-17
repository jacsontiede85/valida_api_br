"""
Middleware de Tratamento Global de Erros
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


def add_error_handlers(app: FastAPI):
    """Adiciona handlers de erro globais à aplicação FastAPI"""
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handler para exceções HTTP padrão"""
        logger.warning("http_exception", 
                      url=str(request.url), 
                      status_code=exc.status_code,
                      detail=exc.detail)
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "http_error",
                "message": str(exc.detail),
                "status_code": exc.status_code,
                "path": str(request.url.path),
                "timestamp": datetime.now().isoformat()
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handler para erros de validação do Pydantic"""
        logger.warning("validation_error", 
                      url=str(request.url),
                      errors=exc.errors())
        
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "message": "Dados de entrada inválidos",
                "detail": exc.errors(),
                "path": str(request.url.path),
                "timestamp": datetime.now().isoformat()
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handler para exceções não tratadas"""
        logger.error("unhandled_exception", 
                    url=str(request.url),
                    error=str(exc),
                    exc_type=type(exc).__name__)
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "Erro interno do servidor",
                "path": str(request.url.path),
                "timestamp": datetime.now().isoformat()
            }
        )
