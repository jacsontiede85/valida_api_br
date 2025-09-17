"""
API REST principal para Resolve CenProt
Ponto de entrada da API FastAPI com gerenciamento de sessão persistente
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from contextlib import asynccontextmanager
import uvicorn
import sys
import os
from pathlib import Path
import structlog
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Adicionar src ao path para reutilizar código existente
sys.path.append(str(Path(__file__).parent.parent / "src"))

from .services.session_manager import SessionManager
from .services.scraping_service import ScrapingService
from .routers import status, cnpj, session
from .middleware.error_handler import add_error_handlers
from src.config.logging_config import LoggingConfig

# Configurar logging
logger = LoggingConfig.setup_logging()

# Configurar serviços baseado na configuração  
from src.config.settings import settings

def create_services():
    """Cria serviços baseado na configuração atual"""
    if settings.USAR_RESOLVE_CENPROT_API_OFICIAL:
        # Modo API oficial - não inicializar RPA/SessionManager pesado
        logger.info("modo_api_oficial_sem_rpa", usar_api_oficial=True)
        session_manager = None
        scraping_service = ScrapingService(session_manager=None, api_oficial_only=True)
    else:
        # Modo RPA - inicializar SessionManager com pool de páginas
        logger.info("modo_rpa_com_pool", pool_size=7)
        session_manager = SessionManager(pool_size=7)
        scraping_service = ScrapingService(session_manager=session_manager, api_oficial_only=False)
    
    return session_manager, scraping_service

# Inicializar serviços
session_manager, scraping_service = create_services()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação com pool de páginas"""
    try:
        logger.info("iniciando_api_resolve_cenprot", version="1.0.0")
        
        # Startup: Inicializar apenas se usar RPA
        if session_manager:
            await session_manager.initialize()
            logger.info("api_iniciada_com_pool_de_paginas", pool_size=session_manager.pool_size)
        else:
            logger.info("api_iniciada_modo_api_oficial_sem_rpa")
        
        # Configurar services nos routers
        status.set_scraping_service(scraping_service)  # Novo: usar scraping_service
        status.set_session_manager(session_manager)   # Mantido para compatibilidade 
        cnpj.set_scraping_service(scraping_service)   # Atualizado
        session.set_session_manager(session_manager)   # Mantido como está
        
        yield
        
    except Exception as e:
        logger.error("erro_inicializacao_api", error=str(e))
        raise
    finally:
        # Shutdown: Limpar apenas se usar RPA
        if session_manager:
            await session_manager.cleanup()
            logger.info("api_encerrada_pool_limpo")
        else:
            logger.info("api_encerrada_modo_api_oficial")


# Criar aplicação FastAPI
app = FastAPI(
    title="Resolve CenProt API",
    description="API REST para consulta de protestos via resolve.cenprot.org.br",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, configurar domains específicos
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Middleware para monitoramento de carga do pool
@app.middleware("http")
async def monitor_concurrent_requests(request: Request, call_next):
    """Middleware para monitorar carga do pool em requisições de consulta"""
    if request.url.path.startswith("/cnpj") and session_manager:
        try:
            pool_status = await session_manager.get_pool_status()
            
            # Log da carga atual
            logger.info("requisicao_cnpj_recebida", 
                       path=request.url.path,
                       available_pages=pool_status["available_pages"],
                       active_pages=pool_status["active_pages"])
            
            # Processar requisição
            response = await call_next(request)
            
            # Adicionar headers de monitoramento
            response.headers["X-Pool-Available"] = str(pool_status["available_pages"])
            response.headers["X-Pool-Active"] = str(pool_status["active_pages"])
            response.headers["X-Pool-Size"] = str(session_manager.pool_size)
            
            return response
        except Exception as e:
            logger.error("erro_middleware_monitoring", error=str(e))
            # Continuar processamento mesmo se monitoring falhar
            return await call_next(request)
    else:
        # Outras requisições ou modo API oficial passam direto
        response = await call_next(request)
        
        # Adicionar headers indicando modo API oficial
        if request.url.path.startswith("/cnpj") and not session_manager:
            response.headers["X-Provider"] = "API_OFICIAL"
            
        return response

# Adicionar handlers de erro globais
add_error_handlers(app)

# Incluir routers
app.include_router(status.router, tags=["Status"])
app.include_router(cnpj.router, tags=["Consulta"])
app.include_router(session.router, prefix="/session", tags=["Sessão"])


@app.get("/")
async def root():
    """Endpoint raiz com informações da API"""
    return {
        "service": "Resolve CenProt API",
        "version": "2.0.0",
        "description": "API REST para consulta de protestos - Suporte RPA + API Oficial",
        "features": [
            "RPA (Robotic Process Automation) via navegador",
            "API oficial do Resolve CenProt", 
            "Seleção automática de provider via variável USAR_RESOLVE_CENPROT_API_OFICIAL",
            "Fallback automático RPA em caso de erro da API oficial"
        ],
        "docs": "/docs",
        "health": "/health", 
        "status": "/status",
        "pool_status": "/pool",
        "switch_provider": "/switch-provider"
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """
    Serve o favicon.ico para evitar erros 404 em navegadores.
    Tenta servir arquivo local ou retorna favicon básico.
    """
    # Caminho para favicon.ico na raiz da API
    favicon_path = Path(__file__).parent / "favicon.ico"
    
    if favicon_path.exists():
        # Se existe arquivo favicon.ico local, serve-o
        return FileResponse(
            path=str(favicon_path),
            media_type="image/x-icon",
            filename="favicon.ico"
        )
    else:
        # Retorna favicon básico em formato ICO (1x1 pixel transparente)
        # Dados de um favicon ICO 16x16 mínimo
        ico_data = bytes([
            0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x10, 0x10, 0x00, 0x00, 0x01, 0x00,
            0x20, 0x00, 0x68, 0x04, 0x00, 0x00, 0x16, 0x00, 0x00, 0x00, 0x28, 0x00,
            0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x01, 0x00,
            0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00
        ] + [0x00] * (16 * 16 * 4))  # 16x16 pixels transparentes
        
        return Response(
            content=ico_data,
            media_type="image/x-icon",
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache por 1 hora
                "Content-Disposition": "inline; filename=favicon.ico"
            }
        )


# Script de desenvolvimento
if __name__ == "__main__":
    import argparse
    
    # Obter porta padrão do .env ou usar 8000 como fallback
    default_port = int(os.getenv('SERVER_PORT', '8000'))
    
    parser = argparse.ArgumentParser(description="Iniciar Resolve CenProt API")
    parser.add_argument("--host", default="0.0.0.0", help="Host da API")
    parser.add_argument("--port", type=int, default=default_port, help=f"Porta da API (padrão: {default_port} do .env SERVER_PORT)")
    parser.add_argument("--reload", action="store_true", help="Habilitar reload automático")
    parser.add_argument("--log-level", default="info", help="Nível de log")
    
    args = parser.parse_args()
    
    # Log informativo sobre a porta utilizada
    port_source = "variável SERVER_PORT do .env" if os.getenv('SERVER_PORT') else "padrão (8000)"
    logger.info("configuracao_servidor", 
               host=args.host, 
               port=args.port, 
               port_source=port_source,
               reload=args.reload)
    
    print(f"🚀 Iniciando Resolve CenProt API na porta {args.port}...")
    print(f"⚙️  Porta configurada via: {port_source}")
    print(f"📝 Documentação disponível em: http://{args.host}:{args.port}/docs")
    print(f"🔍 Status da API em: http://{args.host}:{args.port}/status")
    print(f"💊 Health check em: http://{args.host}:{args.port}/health")
    
    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
        access_log=True
    )
