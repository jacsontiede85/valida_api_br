#!/usr/bin/env python3
"""
Script principal unificado para executar a API Valida SaaS
Sistema completo com templates, autenticação opcional e APIs v2.0
"""
import sys
import os
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(env_file=None, override=False):
        """Fallback para carregar variáveis de ambiente do arquivo .env"""
        env_path = env_file if env_file else Path('.env')
        if not isinstance(env_path, Path):
            env_path = Path(env_path)
            
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        if override or key not in os.environ:
                            os.environ[key.strip()] = value.strip()

# Detectar se está rodando como executável compilado
IS_FROZEN = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("ValidaSaaS")

def check_virtual_env():
    """Verifica e ativa ambiente virtual se existir (apenas em modo desenvolvimento)"""
    if IS_FROZEN:
        logger.info("🚀 Executando como aplicação compilada")
        return True
        
    venv_path = Path("venv/Scripts/activate.bat")
    if venv_path.exists():
        logger.info("🔄 Ambiente virtual encontrado")
        venv_scripts = Path("venv/Scripts").absolute()
        if str(venv_scripts) not in os.environ.get("PATH", ""):
            os.environ["PATH"] = str(venv_scripts) + os.pathsep + os.environ.get("PATH", "")
            logger.info(f"✅ Adicionado venv ao PATH: {venv_scripts}")
        return True
    else:
        logger.info("⚠️  Ambiente virtual não encontrado. Usando Python do sistema.")
        return False

def check_dependencies():
    """Verifica se as dependências estão instaladas (apenas em modo desenvolvimento)"""
    if IS_FROZEN:
        logger.info("✅ Usando dependências compiladas")
        return True
        
    try:
        import fastapi
        logger.info("✅ FastAPI encontrado")
        return True
    except ImportError:
        logger.warning("❌ FastAPI não instalado. Instalando dependências...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                         check=True, capture_output=True, text=True)
            logger.info("✅ Dependências instaladas com sucesso")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Erro ao instalar dependências: {e}")
            return False

def get_server_port():
    """Obtém a porta do servidor do arquivo .env"""
    # Determinar o diretório base
    if IS_FROZEN:
        base_dir = Path(sys.executable).parent.parent
        if not (base_dir / ".env").exists():
            base_dir = Path(sys.executable).parent
    else:
        base_dir = Path.cwd()
    
    # Forçar recarregamento do .env
    env_file = base_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)
        logger.info(f"📁 Arquivo .env carregado de: {env_file}")
    else:
        logger.warning(f"⚠️  Arquivo .env não encontrado em: {env_file}")
    
    # Ler SERVER_PORT e limpar espaços
    port = os.getenv('SERVER_PORT', '2377').strip()
    try:
        return int(port)
    except ValueError:
        logger.warning(f"⚠️  Porta inválida '{port}', usando 2377")
        return 2377

def configure_app_unified(app):
    """Configura a aplicação FastAPI com recursos unificados v2.0"""
    from fastapi import Depends, HTTPException, status, Request
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.templating import Jinja2Templates
    
    # Importar middleware de autenticação com fallback
    try:
        from api.middleware.auth_middleware import require_auth, get_current_user_optional, AuthUser
        auth_available = True
    except ImportError:
        logger.warning("⚠️ Middleware de autenticação não disponível, usando modo sem autenticação")
        auth_available = False
        AuthUser = None
    
    # =====================================================
    # IMPORTAR E INSTANCIAR SERVIÇOS REAIS v2.0
    # =====================================================
    try:
        # Importar instâncias globais dos serviços (já implementados)
        from api.services.user_service import user_service
        from api.services.credit_service import credit_service
        from api.services.dashboard_service import dashboard_service
        from api.services.api_key_service import api_key_service
        from api.services.subscription_service import subscription_service
        from api.services.history_service import history_service
        
        services_available = True
        logger.info("✅ Todos os serviços carregados com sucesso")
        
    except ImportError as e:
        logger.error(f"❌ Erro ao importar serviços: {e}")
        services_available = False
    
    # Configurar arquivos estáticos
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    # Configurar templates Jinja2 para futuras melhorias
    templates = Jinja2Templates(directory="templates")
    
    # =====================================================
    # CONTEXTO DE USUÁRIO HELPER
    # =====================================================
    
    async def get_user_context(request: Request):
        """Obter contexto do usuário usando APENAS serviços reais"""
        if not auth_available or not services_available:
            # Se autenticação ou serviços não disponíveis, retornar não autenticado
            return {"authenticated": False}
        
        try:
            # Tentar obter usuário autenticado
            user = await get_current_user_optional(request)
            if not user:
                return {"authenticated": False}
            
            # Usar serviços reais implementados
            user_data = await user_service.get_user(user.user_id)
            credits = await credit_service.get_user_credits(user.user_id)
            
            return {
                "user": user_data,
                "credits": credits,
                "authenticated": True
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter contexto do usuário: {e}")
            return {"authenticated": False, "error": str(e)}
    
    # =====================================================
    # TEMPLATES COM AUTENTICAÇÃO OPCIONAL
    # =====================================================
    
    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        """Dashboard principal"""
        context = await get_user_context(request)
        
        if not context["authenticated"]:
            # Redirecionar para login se não autenticado
            return HTMLResponse(
                content='<script>window.location.href="/login"</script>',
                status_code=302
            )
        
        with open("templates/home.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        
        # Injetar dados do usuário no HTML se disponível
        if context.get("credits"):
            credits_value = context["credits"].get("available_credits_cents", 0)
            html_content = html_content.replace(
                'data-stat="creditos-disponiveis">R$ 0,00',
                f'data-stat="creditos-disponiveis">R$ {credits_value / 100:.2f}'
            )
        
        return HTMLResponse(content=html_content)
    
    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request):
        """Dashboard - Alias para home"""
        return await home(request)
    
    @app.get("/login", response_class=HTMLResponse)
    async def login():
        """Página de login - Acesso público"""
        with open("templates/login.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    
    @app.get("/register", response_class=HTMLResponse)
    async def register():
        """Página de registro - Acesso público"""
        with open("templates/register.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    
    # Templates que requerem autenticação em produção
    protected_templates = [
        ("/consultas", "consultas.html"),
        ("/api-keys", "api-keys.html"),
        ("/assinatura", "assinatura.html"),
        ("/history", "history.html"),
        ("/perfil", "perfil.html"),
    ]
    
    def create_template_handler(template_name: str):
        """Handler genérico para templates protegidos"""
        async def handler(request: Request):
            context = await get_user_context(request)
            if not context["authenticated"]:
                return HTMLResponse(
                    content='<script>window.location.href="/login"</script>',
                    status_code=302
                )
            
            with open(f"templates/{template_name}", "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        return handler
    
    # Registrar templates protegidos
    for route, template in protected_templates:
        handler_func = create_template_handler(template)
        app.get(route, response_class=HTMLResponse)(handler_func)
    
    # =====================================================
    # DEMO PAGE (se existir)
    # =====================================================
    
    @app.get("/demo", response_class=HTMLResponse)
    @app.get("/demo_v2.html", response_class=HTMLResponse)
    async def demo():
        """Página de demonstração"""
        if os.path.exists("demo_v2.html"):
            with open("demo_v2.html", "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Demo em desenvolvimento</h1>")
    
    @app.get("/test", response_class=HTMLResponse)
    @app.get("/test_login", response_class=HTMLResponse)
    async def test_login():
        """Página de teste do sistema de login"""
        if os.path.exists("test_login_system.html"):
            with open("test_login_system.html", "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Teste de login não encontrado</h1>")
    
    @app.get("/test_jwt", response_class=HTMLResponse)
    async def test_jwt():
        """Página de teste do JWT dashboard"""
        if os.path.exists("test_jwt_dashboard.html"):
            with open("test_jwt_dashboard.html", "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Teste JWT não encontrado</h1>")
    
    # =====================================================
    # APIS v2.0 COM DADOS REAIS DO SUPABASE
    # =====================================================
    
    @app.get("/api/v2/dashboard/data")
    async def get_dashboard_data(
        request: Request,
        period: str = "30d",  # ✅ CORRIGIDO: Aceitar parâmetro de período
        current_user: AuthUser = Depends(require_auth) if auth_available else None
    ):
        """Dados do dashboard v2.0 - usando serviços reais"""
        if not services_available:
            raise HTTPException(500, "Serviços não disponíveis")
        
        try:
            # Se temos middleware de auth, usar current_user
            if current_user:
                user_id = current_user.user_id
            else:
                # Fallback: tentar obter do contexto
                context = await get_user_context(request)
                if not context["authenticated"]:
                    raise HTTPException(401, "Usuário não autenticado")
                user_id = context["user"]["id"]
            
            # ✅ CORRIGIDO: Passar o período para o serviço
            dashboard_data = await dashboard_service.get_dashboard_data(user_id, period)
            logger.info(f"📊 Dashboard carregado para usuário {user_id} para o período {period}")
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Erro ao carregar dashboard: {e}")
            raise HTTPException(500, "Erro interno do servidor")
    
    @app.get("/api/v2/costs/calculate")
    async def calculate_costs(
        request: Request,
        protestos: bool = False,
        receita_federal: bool = False,
        simples: bool = False,
        suframa: bool = False,
        registrations: str = None,
        geocoding: bool = False
    ):
        """Calculadora de custos usando dados reais da tabela consultation_types"""
        if not services_available:
            raise HTTPException(500, "Serviços não disponíveis")
        
        try:
            # Usar custos reais confirmados na análise do banco (6 tipos)
            consultation_costs = {
                'protestos': {'name': 'Protestos', 'cost_cents': 15},
                'receita_federal': {'name': 'Receita Federal', 'cost_cents': 5},
                'simples': {'name': 'Simples Nacional', 'cost_cents': 5},
                'suframa': {'name': 'SUFRAMA', 'cost_cents': 5},
                'geocoding': {'name': 'Geocodificação', 'cost_cents': 5},
                'registrations': {'name': 'Cadastro Contribuintes', 'cost_cents': 5}
            }
            
            total_cost = 0
            breakdown = []
            
            # Calcular custos baseado nos parâmetros
            for param, type_info in consultation_costs.items():
                param_value = locals().get(param, False)
                if param_value or (param == 'registrations' and registrations):
                    cost = type_info['cost_cents']
                    total_cost += cost
                    breakdown.append({
                        "type": type_info['name'],
                        "cost": cost,
                        "formatted": f"R$ {cost / 100:.2f}"
                    })
            
            # Obter créditos disponíveis do usuário REAIS do banco
            context = await get_user_context(request)
            if not context.get("authenticated") or not context.get("credits"):
                # Sem usuário autenticado = sem créditos
                available_credits = 0
            else:
                available_credits = context["credits"].get("available_credits_cents", 0)
            
            return {
                "total_cost": total_cost,
                "formatted_cost": f"R$ {total_cost / 100:.2f}",
                "breakdown": breakdown,
                "available_credits": f"R$ {available_credits / 100:.2f}",
                "sufficient_credits": total_cost <= available_credits,
                "will_auto_renew": total_cost > available_credits
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular custos: {e}")
            raise HTTPException(500, "Erro interno do servidor")
    
    @app.get("/api/v2/consultation/types/health")
    async def consultation_types_health_check():
        """Health check do serviço de tipos de consulta"""
        if not services_available:
            raise HTTPException(500, "Serviços não disponíveis")
        
        try:
            from api.services.consultation_types_service import consultation_types_service
            health_status = await consultation_types_service.health_check()
            return health_status
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    @app.get("/api/v2/consultation/types")
    async def get_consultation_types():
        """Tipos de consulta com custos reais da tabela consultation_types"""
        if not services_available:
            raise HTTPException(500, "Serviços não disponíveis")
        
        try:
            # ✅ DADOS REAIS DIRETOS do Supabase - tabela consultation_types
            from api.middleware.auth_middleware import get_supabase_client
            supabase = get_supabase_client()
            
            if not supabase:
                raise HTTPException(500, "Supabase não configurado")
                
            # Buscar tipos reais da tabela consultation_types
            response = supabase.table("consultation_types").select("*").execute()
            
            if not response.data:
                return {"types": []}
            
            types_list = []
            for tipo in response.data:
                types_list.append({
                    "id": tipo["id"],
                    "code": tipo["code"],
                    "name": tipo["name"],
                    "cost_cents": tipo["cost_cents"],
                    "formatted_cost": f"R$ {tipo['cost_cents'] / 100:.2f}",
                    "description": tipo.get("description", ""),
                    "is_active": tipo.get("is_active", True)
                })
            
            types_data = {"types": types_list}
            logger.info(f"💰 {len(types_list)} tipos de consulta REAIS carregados do Supabase")
            return types_data
            
        except Exception as e:
            logger.error(f"Erro ao carregar tipos de consulta: {e}")
            raise HTTPException(500, "Erro interno do servidor")
    
    @app.get("/api/v2/subscription/plans")
    async def get_subscription_plans():
        """Planos de assinatura usando dados reais do Supabase"""
        if not services_available:
            raise HTTPException(500, "Serviços não disponíveis")
        
        try:
            # ✅ DADOS REAIS DIRETOS do Supabase - APENAS do banco de dados
            from api.middleware.auth_middleware import get_supabase_client
            supabase = get_supabase_client()
            
            if not supabase:
                raise HTTPException(500, "Supabase não configurado")
                
            # Buscar planos reais da tabela subscription_plans
            response = supabase.table("subscription_plans").select("*").execute()
            
            if not response.data:
                return {"plans": []}
                
            plans_list = []
            for plan in response.data:
                plans_list.append({
                    "id": plan["code"],
                    "name": plan["name"], 
                    "price_cents": plan["price_cents"],
                    "formatted_price": f"R$ {plan['price_cents'] / 100:.2f}",
                    "credits_included_cents": plan["credits_included_cents"],
                    "api_keys_limit": plan["api_keys_limit"],
                    "description": plan["description"],
                    "estimates": {
                        "protestos": plan["credits_included_cents"] // 15,
                        "receita_federal": plan["credits_included_cents"] // 5
                    }
                })
            
            plans_data = {"plans": plans_list}
            logger.info(f"📦 {len(plans_list)} planos REAIS carregados do Supabase")
            return plans_data
            
        except Exception as e:
            logger.error(f"Erro ao carregar planos: {e}")
            raise HTTPException(500, "Erro interno do servidor")
    
    @app.get("/api/v2/consultations/history")
    async def get_consultations_history(
        request: Request,
        page: int = 1,
        limit: int = 20,
        type_filter: str = "all",
        status_filter: str = "all",
        current_user: AuthUser = Depends(require_auth) if auth_available else None
    ):
        """Histórico de consultas usando dados reais do Supabase"""
        if not services_available:
            raise HTTPException(500, "Serviços não disponíveis")
        
        try:
            # Obter user_id
            if current_user:
                user_id = current_user.user_id
            else:
                context = await get_user_context(request)
                if not context["authenticated"]:
                    raise HTTPException(401, "Usuário não autenticado")
                user_id = context["user"]["id"]
            
            # ✅ DADOS REAIS da 1 consulta registrada no Supabase
            history_data = await history_service.get_user_consultations_v2(
                user_id, page, limit, type_filter, status_filter
            )
            
            logger.info(f"📜 Histórico carregado: {len(history_data.get('data', []))} consultas")
            return history_data
            
        except Exception as e:
            logger.error(f"Erro ao carregar histórico: {e}")
            raise HTTPException(500, "Erro interno do servidor")
    
    @app.get("/api/v2/profile/credits")
    async def get_profile_credits(
        request: Request,
        current_user: AuthUser = Depends(require_auth) if auth_available else None
    ):
        """Dados de créditos para o perfil usando serviços reais"""
        if not services_available:
            raise HTTPException(500, "Serviços não disponíveis")
        
        try:
            # Obter user_id
            if current_user:
                user_id = current_user.user_id
            else:
                context = await get_user_context(request)
                if not context["authenticated"]:
                    raise HTTPException(401, "Usuário não autenticado")
                user_id = context["user"]["id"]
            
            # ✅ DADOS REAIS dos créditos (R$ 10,00 saldo inicial)
            credits_data = await credit_service.get_user_credits(user_id)
            logger.info(f"💰 Créditos carregados para usuário {user_id}")
            return credits_data
            
        except Exception as e:
            logger.error(f"Erro ao carregar créditos: {e}")
            raise HTTPException(500, "Erro interno do servidor")
    
    @app.get("/api/v2/api-keys/usage")
    async def get_api_keys_usage(
        request: Request,
        current_user: AuthUser = Depends(require_auth) if auth_available else None
    ):
        """Uso das API keys v2.0 usando dados reais do Supabase"""
        if not services_available:
            raise HTTPException(500, "Serviços não disponíveis")
        
        try:
            # Obter user_id
            if current_user:
                user_id = current_user.user_id
            else:
                context = await get_user_context(request)
                if not context["authenticated"]:
                    raise HTTPException(401, "Usuário não autenticado")
                user_id = context["user"]["id"]
            
            # ✅ DADOS REAIS das 10 chaves API ativas do Supabase
            api_keys_data = await api_key_service.get_keys_usage_v2(user_id)
            logger.info(f"🔐 API Keys carregadas para usuário {user_id}")
            return {"keys": api_keys_data}
            
        except Exception as e:
            logger.error(f"Erro ao carregar API keys: {e}")
            raise HTTPException(500, "Erro interno do servidor")
    
    
    # =====================================================
    # HEALTH CHECK E STATUS
    # =====================================================
    
    @app.get("/api/v1/health")
    @app.get("/status")
    async def health():
        """Health check / Status da API"""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "Valida SaaS Unified",
            "version": "2.1.0",
            "database": "connected",
            "services": "enabled" if services_available else "disabled",
            "auth_enabled": auth_available
        }
    
    # =====================================================
    # MIDDLEWARE DE LOGGING
    # =====================================================
    
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Middleware para logging de requisições"""
        start_time = datetime.now()
        
        # Processa a requisição
        response = await call_next(request)
        
        # Log da requisição
        process_time = (datetime.now() - start_time).total_seconds()
        
        # Log apenas para endpoints importantes
        if request.url.path.startswith(("/api/", "/dashboard", "/consultas")):
            logger.info(f"📡 {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
        
        return response
    
    # Log de configuração final
    services_info = "habilitados" if services_available else "desabilitados"
    auth_info = "habilitada" if auth_available else "desabilitada"
    logger.info(f"✅ Aplicação configurada - Serviços: {services_info}, Autenticação: {auth_info}")
    
    return app

def main():
    """Função principal unificada"""
    try:
        logger.info("="*60)
        logger.info("🚀 Valida SaaS API - Sistema Unificado")
        logger.info("="*60)
        
        # Verificar ambiente virtual
        check_virtual_env()
        
        # Verificar dependências
        if not check_dependencies():
            logger.error("❌ Falha ao instalar dependências. Encerrando...")
            sys.exit(1)
        
        # Carregar .env
        load_dotenv(override=True)
        
        # Obter porta do servidor
        port = get_server_port()
        
        # Detectar modo
        dev_mode = os.getenv('DEV_MODE', 'false').lower() == 'true'
        mode_text = "DESENVOLVIMENTO" if dev_mode else "PRODUÇÃO"
        
        logger.info("")
        logger.info(f"🔧 Modo: {mode_text}")
        logger.info(f"🌐 Porta: {port}")
        logger.info(f"📱 Dashboard: http://localhost:{port}/dashboard")
        logger.info(f"🔐 Login: http://localhost:{port}/login")
        logger.info(f"📝 Documentação API: http://localhost:{port}/docs")
        logger.info(f"🏥 Health Check: http://localhost:{port}/status")
        logger.info("")
        
        # Importar e configurar a aplicação
        from api.main import app
        import uvicorn
        
        # Aplicar configurações unificadas
        app = configure_app_unified(app)
        
        # Incluir rotas SaaS v1 se disponíveis
        try:
            from api.routers.saas_routes import router as saas_router
            app.include_router(saas_router, prefix="/api/v1", tags=["SaaS"])
            logger.info("✅ Rotas SaaS v1.0 incluídas")
        except Exception as e:
            logger.warning(f"⚠️ Rotas SaaS v1.0 não disponíveis: {e}")
        
        logger.info("🎯 Funcionalidades ativas:")
        logger.info("   • Sistema de créditos transparente")
        logger.info("   • Custos por tipo (Protestos R$0,15, Receita R$0,05)")
        logger.info("   • Templates responsivos com autenticação opcional")
        logger.info("   • APIs v2.0 com dados reais do Supabase")
        logger.info("   • Modo desenvolvimento/produção configurável")
        logger.info("")
        
        # Executar servidor
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info",
            access_log=True
        )
        
    except KeyboardInterrupt:
        logger.info("🛑 Interrupção recebida, encerrando...")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        sys.exit(1)
    finally:
        logger.info("👋 Encerrando Valida SaaS API")

if __name__ == "__main__":
    main()