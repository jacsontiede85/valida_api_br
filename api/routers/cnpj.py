"""
Router de Consulta CNPJ da API Resolve CenProt
"""

import os
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from ..models.api_models import CNPJRequest, CNPJResponse
from ..models.error_models import ValidationError, SessionError, ScrapingError, PoolTimeoutError
from ..services.scraping_service import ScrapingService
import structlog
from dotenv import load_dotenv

# Adicionar o diretório raiz ao path para importar módulos do projeto
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent  # resolve_cenprot/

# Adicionar paths necessários para importações
sys.path.append(str(project_root))

# Carregar variáveis de ambiente
load_dotenv('resolve-cenprot.exe.env')

# Importar OracleProtestoManager
try:
    from src.utils.oracle_protest_manager import OracleProtestoManager
    ORACLE_AVAILABLE = True
except ImportError as e:
    structlog.get_logger(__name__).warning("oracle_protest_manager_nao_disponivel", error=str(e))
    ORACLE_AVAILABLE = False
    OracleProtestoManager = None  # Definir como None quando importação falhar

logger = structlog.get_logger(__name__)

router = APIRouter()

# Referência global para scraping_service (será definida no main.py)
scraping_service = None

# Instância global para Oracle Protest Manager
oracle_manager = None

# Verificar se salvamento no banco está ativado
IS_SALVAR_CONSULTAS_ORACLE = os.getenv('IS_SALVAR_CONSULTAS_ORACLE', 'false').lower() == 'true'

# Log da configuração do banco de dados Oracle na inicialização
db_user_configured = bool(os.getenv('DB_USER', '').strip())
db_password_configured = bool(os.getenv('DB_PASSWORD', '').strip())

logger.info("configuracao_banco_oracle", 
           is_salvar_consultas_oracle=IS_SALVAR_CONSULTAS_ORACLE,
           oracle_available=ORACLE_AVAILABLE,
           db_user_configured=db_user_configured,
           db_password_configured=db_password_configured,
           config_env=f"IS_SALVAR_CONSULTAS_ORACLE={os.getenv('IS_SALVAR_CONSULTAS_ORACLE', 'false')}")

# Avisos se credenciais não estão configuradas
if IS_SALVAR_CONSULTAS_ORACLE and not (db_user_configured and db_password_configured):
    missing_vars = []
    if not db_user_configured:
        missing_vars.append('DB_USER')
    if not db_password_configured:
        missing_vars.append('DB_PASSWORD')
    
    logger.warning("credenciais_oracle_faltantes", 
                  missing_variables=missing_vars,
                  message=f"Para ativar salvamento no banco Oracle, defina: {', '.join(missing_vars)} no arquivo .env")


def set_scraping_service(service):
    """Define o scraping service para este router"""
    global scraping_service
    scraping_service = service


def set_session_manager(manager):
    """Define o session manager para este router (mantido para compatibilidade)"""
    # Mantido apenas para compatibilidade
    pass


def get_oracle_manager():
    """Obtém instância do Oracle Protest Manager"""
    global oracle_manager
    
    if oracle_manager is None and ORACLE_AVAILABLE and IS_SALVAR_CONSULTAS_ORACLE:
        try:
            oracle_manager = OracleProtestoManager()
            logger.info("oracle_protest_manager_inicializado")
        except Exception as e:
            logger.error("erro_inicializar_oracle_manager", error=str(e))
            
    return oracle_manager


def verificar_existencia_protestos(data: dict) -> bool:
    """
    Verifica se existem protestos nos dados da consulta.
    
    Args:
        data: Dados da consulta (campo 'data' da resposta)
        
    Returns:
        True se existem protestos, False caso contrário
    """
    try:
        cenprot_protestos = data.get('cenprotProtestos', {})
        
        # Se cenprotProtestos está vazio ou None, não há protestos
        if not cenprot_protestos:
            return False
        
        # Verifica se é uma resposta de erro (código 606 = sem protestos)
        if 'code' in cenprot_protestos and 'message' in cenprot_protestos:
            code = cenprot_protestos.get('code')
            message = cenprot_protestos.get('message', '')
            
            # Código 606 indica "Não encontrado protestos"
            if code == 606 or "Não encontrado protestos" in message:
                return False
        
        # Verifica se há protestos em alguma UF
        for uf, protestos_uf in cenprot_protestos.items():
            if isinstance(protestos_uf, list) and len(protestos_uf) > 0:
                for protesto_info in protestos_uf:
                    # Verifica se há quantidade de títulos maior que 0
                    qtd_titulos = protesto_info.get('quantidadeTitulos', 0)
                    if qtd_titulos > 0:
                        return True
                    
                    # Verifica se há protestos na lista
                    protestos_list = protesto_info.get('protestos', [])
                    if len(protestos_list) > 0:
                        return True
        
        return False
        
    except Exception as e:
        logger.warning("erro_verificar_protestos", error=str(e), data_type=type(data).__name__)
        return False


async def salvar_resultado_banco(cnpj: str, api_result: dict) -> None:
    """
    Salva resultado da consulta no banco de dados Oracle se configurado.
    
    Args:
        cnpj: CNPJ consultado
        api_result: Resultado completo da API (formato CNPJResponse)
    """
    if not IS_SALVAR_CONSULTAS_ORACLE:
        logger.debug("salvamento_banco_desativado", cnpj=cnpj, config="IS_SALVAR_CONSULTAS_ORACLE=false")
        return
    
    if not ORACLE_AVAILABLE:
        logger.warning("oracle_manager_nao_disponivel", cnpj=cnpj, 
                      message="OracleProtestoManager não pôde ser importado")
        return
    
    manager = get_oracle_manager()
    if not manager:
        logger.warning("oracle_manager_nao_inicializado", cnpj=cnpj)
        return
    
    try:
        logger.info("iniciando_salvamento_banco", cnpj=cnpj)
        
        # Usar função específica para API resolve.cenprot.org.br
        success, message = manager.processar_resultado_api_resolve_cenprot(api_result)
        
        if success:
            logger.info("salvamento_banco_sucesso", cnpj=cnpj, message=message)
        else:
            logger.error("salvamento_banco_falha", cnpj=cnpj, message=message)
            
    except Exception as e:
        logger.error("erro_salvamento_banco", cnpj=cnpj, error=str(e), 
                    error_type=type(e).__name__)


def get_scraping_service() -> ScrapingService:
    """Dependency injection para ScrapingService"""
    if not scraping_service:
        raise HTTPException(status_code=503, detail="Service não inicializado")
    return scraping_service


@router.post("/cnpj", response_model=CNPJResponse)
async def consultar_cnpj(
    request: CNPJRequest,
    scraping_service: ScrapingService = Depends(get_scraping_service)
):
    """
    Realiza consulta de CNPJ e retorna dados no formato padrão
    """
    try:
        # Validar e normalizar CNPJ já é feito pelo modelo Pydantic
        cnpj = request.cnpj
        
        logger.info("iniciando_consulta_cnpj_api", cnpj=cnpj)
        
        # Realizar consulta
        result = await scraping_service.consultar_cnpj(cnpj)
        
        # Converter para dict usando model_dump (Pydantic V2) com segurança
        try:
            if hasattr(result, 'model_dump'):
                result_dict = result.model_dump()
            else:
                # Fallback para Pydantic V1
                result_dict = result.dict()
        except Exception as serialize_error:
            logger.error("erro_serializar_result", 
                       cnpj=request.cnpj, 
                       error=str(serialize_error),
                       result_type=type(result).__name__)
            
            # Fallback seguro - criar resultado básico (sem protestos)
            result_dict = {
                "cnpj": request.cnpj,
                "cenprotProtestos": {},
                "dataHora": "2025-09-10 12:00:00.000000",
                "link_pdf": f"/Erro serialização: {str(serialize_error)}"
            }
        
        # Verificar se existem protestos
        existe_protestos = verificar_existencia_protestos(result_dict)
        
        logger.info("consulta_cnpj_api_finalizada", 
                   cnpj=cnpj, 
                   tem_protestos=existe_protestos,
                   cenprotProtestos_presente=bool(result_dict.get('cenprotProtestos')))
        
        # Criar resposta da API
        api_response = CNPJResponse(
            success=True,
            existe_protestos=existe_protestos,
            data=result_dict,
            message=f"Consulta realizada com sucesso para CNPJ {cnpj}"
        )
        
        # Salvar no banco de dados Oracle se configurado (apenas se sucesso)
        if api_response.success:
            await salvar_resultado_banco(cnpj, api_response.model_dump())
        
        return api_response
        
    except ValueError as e:
        # Erro de validação do CNPJ
        logger.warning("erro_validacao_cnpj_api", cnpj=request.cnpj, error=str(e))
        raise HTTPException(
            status_code=400,
            detail=ValidationError(message=str(e)).dict()
        )
    except TimeoutError as e:
        # Erro de timeout do pool
        logger.error("timeout_pool_consulta_cnpj", cnpj=request.cnpj, error=str(e))
        raise HTTPException(
            status_code=503,
            detail=PoolTimeoutError(message=f"Pool de páginas ocupado: {str(e)}").dict()
        )
    except Exception as e:
        # Verificar se é erro de sessão
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ["sessão", "login", "session", "autenticação"]):
            logger.error("erro_sessao_consulta_cnpj", cnpj=request.cnpj, error=str(e))
            raise HTTPException(
                status_code=503,
                detail=SessionError(message=f"Erro de sessão: {str(e)}").dict()
            )
        
        # Verificar se é erro da API oficial
        if any(keyword in error_str for keyword in ["api oficial", "resposta da api", "campo 'protests'", "não é um dicionário"]):
            logger.error("erro_api_oficial_consulta_cnpj", cnpj=request.cnpj, error=str(e))
            raise HTTPException(
                status_code=502,
                detail=ScrapingError(message=f"Erro na API oficial: {str(e)}").dict()
            )
        
        # Outros erros de scraping
        logger.error("erro_scraping_consulta_cnpj", cnpj=request.cnpj, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=ScrapingError(message=f"Erro durante consulta: {str(e)}").dict()
        )


@router.get("/cnpj/{cnpj}", response_model=CNPJResponse)
async def consultar_cnpj_get(
    cnpj: str,
    scraping_service: ScrapingService = Depends(get_scraping_service)
):
    """
    Consulta CNPJ via GET (alternativa ao POST)
    """
    try:
        # Criar request object e reutilizar lógica do POST
        request = CNPJRequest(cnpj=cnpj)
        return await consultar_cnpj(request, scraping_service)
    except ValueError as e:
        # Erro de validação será capturado pelo Pydantic
        logger.warning("erro_validacao_cnpj_get", cnpj=cnpj, error=str(e))
        raise HTTPException(
            status_code=400,
            detail=ValidationError(message=f"CNPJ inválido: {str(e)}").dict()
        )
