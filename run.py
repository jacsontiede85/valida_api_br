#!/usr/bin/env python3
"""
Script principal para executar a API Resolve CenProt
Substitui o start_api.bat para funcionar melhor como serviço Windows
"""
import sys
import os
import subprocess
import logging
from pathlib import Path
try:
    from dotenv import load_dotenv
except ImportError:
    # Fallback para quando dotenv não estiver disponível no executável
    def load_dotenv(env_file=None, override=False):
        """Fallback para carregar variáveis de ambiente do arquivo .env"""
        if env_file and Path(env_file).exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        if override or key not in os.environ:
                            os.environ[key.strip()] = value.strip()
        elif Path('.env').exists():
            with open('.env', 'r', encoding='utf-8') as f:
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
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("ResolveCenprotAPI")

def check_virtual_env():
    """Verifica e ativa ambiente virtual se existir (apenas em modo desenvolvimento)"""
    # Se está rodando como executável compilado, pular verificação de venv
    if IS_FROZEN:
        logger.info("🚀 Executando como aplicação compilada")
        return True
        
    venv_path = Path("venv/Scripts/activate.bat")
    if venv_path.exists():
        logger.info("🔄 Ambiente virtual encontrado")
        # Adicionar o venv ao PATH do processo atual
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
    # Se está rodando como executável compilado, assumir que tudo está incluído
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
        # Se executável, procurar .env no diretório pai (raiz do projeto)
        base_dir = Path(sys.executable).parent.parent
        # Se não encontrar no pai, tentar no mesmo diretório do exe
        if not (base_dir / ".env").exists():
            base_dir = Path(sys.executable).parent
    else:
        # Se desenvolvimento, usar diretório atual
        base_dir = Path.cwd()
    
    # Forçar recarregamento do .env
    env_file = base_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)
        logger.info(f"📁 Arquivo .env carregado de: {env_file}")
    else:
        logger.warning(f"⚠️  Arquivo .env não encontrado em: {env_file}")
        # Tentar encontrar .env em outros locais comuns
        alternative_paths = [
            Path.cwd() / ".env",
            Path(__file__).parent / ".env",
            Path(__file__).parent.parent / ".env",
        ]
        for alt_path in alternative_paths:
            if alt_path.exists():
                load_dotenv(alt_path, override=True)
                logger.info(f"📁 Arquivo .env encontrado em: {alt_path}")
                break
    
    # Ler SERVER_PORT e limpar espaços
    port = os.getenv('SERVER_PORT', '8099').strip()
    try:
        return int(port)
    except ValueError:
        logger.warning(f"⚠️  Porta inválida '{port}', usando 8099")
        return 8099

def main():
    """Função principal"""
    try:
        logger.info("="*60)
        logger.info("Resolve CenProt API - Inicializador")
        logger.info("="*60)
        
        # Verificar ambiente virtual
        check_virtual_env()
        
        # Verificar dependências
        if not check_dependencies():
            logger.error("❌ Falha ao instalar dependências. Encerrando...")
            sys.exit(1)
        
        # Obter porta do servidor
        port = get_server_port()
        
        logger.info("")
        logger.info(f"🚀 Iniciando API na porta {port}...")
        logger.info(f"📝 Documentação: http://localhost:{port}/docs")
        logger.info(f"🔍 Status: http://localhost:{port}/status")
        logger.info("")
        
        # Executar a API
        try:
            # Importar e executar o módulo da API
            from api.main import app
            import uvicorn
            from fastapi.staticfiles import StaticFiles
            from fastapi.responses import HTMLResponse
            import os
            
            # Configurar arquivos estáticos
            app.mount("/static", StaticFiles(directory="static"), name="static")
            
            # Adicionar rotas para templates SaaS
            @app.get("/", response_class=HTMLResponse)
            async def dashboard():
                with open("templates/home.html", "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read())
            
            @app.get("/dashboard", response_class=HTMLResponse)
            async def dashboard_route():
                with open("templates/home.html", "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read())
            
            @app.get("/api-keys", response_class=HTMLResponse)
            async def api_keys():
                with open("templates/api-keys.html", "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read())
            
            @app.get("/assinatura", response_class=HTMLResponse)
            async def assinatura():
                with open("templates/assinatura.html", "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read())
            
            @app.get("/faturas", response_class=HTMLResponse)
            async def faturas():
                with open("templates/faturas.html", "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read())
            
            @app.get("/history", response_class=HTMLResponse)
            async def history():
                with open("templates/history.html", "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read())
            
            @app.get("/perfil", response_class=HTMLResponse)
            async def perfil():
                with open("templates/perfil.html", "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read())
            
            @app.get("/consultas", response_class=HTMLResponse)
            async def consultas():
                with open("templates/consultas.html", "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read())
            
            @app.get("/login", response_class=HTMLResponse)
            async def login():
                with open("templates/login.html", "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read())
            
            @app.get("/register", response_class=HTMLResponse)
            async def register():
                with open("templates/register.html", "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read())
            
            # Importar e adicionar rotas da API SaaS
            from api.routers.saas_routes import router as saas_router
            app.include_router(saas_router, prefix="/api/v1", tags=["SaaS"])
            
            # Configurar uvicorn
            uvicorn.run(
                app,
                host="0.0.0.0",
                port=2377,
                log_level="info",
                access_log=True
            )
            
        except ImportError as e:
            logger.error(f"❌ Erro ao importar módulos da API: {e}")
            logger.error("Verifique se o módulo 'api.main' existe e está configurado corretamente")
            sys.exit(1)
        except Exception as e:
            logger.error(f"❌ Erro ao executar API: {e}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("🛑 Interrupção recebida (Ctrl+C), encerrando...")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        sys.exit(1)
    finally:
        logger.info("👋 Encerrando Resolve CenProt API")

if __name__ == "__main__":
    main()
