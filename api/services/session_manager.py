"""
Gerenciador de Sessão com Pool de Páginas para Requisições Concorrentes
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import structlog

# Adicionar src ao path para reutilizar código existente
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from src.browser.browser_manager import BrowserManager
from src.auth.login_manager import LoginManager
from src.auth.email_extractor import EmailCodeExtractor
from src.config.settings import settings

logger = structlog.get_logger(__name__)


class SessionManager:
    """Gerencia sessão persistente com pool de páginas para múltiplas requisições"""
    
    def __init__(self, pool_size: int = 3):
        self.browser_manager: Optional[BrowserManager] = None
        self.login_manager: Optional[LoginManager] = None
        self.email_extractor: Optional[EmailCodeExtractor] = None
        self.context = None
        
        # Pool de páginas para requisições paralelas
        self.pool_size = pool_size
        self.page_pool = asyncio.Queue(maxsize=pool_size)
        self.active_pages = {}  # Rastreamento de páginas em uso
        
        # Sistema de refresh automático para manter páginas ativas
        self.auto_refresh_enabled = True
        self.refresh_interval = 60  # segundos
        self.refresh_task: Optional[asyncio.Task] = None
        self.all_pages = {}  # Registro de todas as páginas criadas
        
        self.is_initialized = False
        self.is_logged_in = False
        self.last_login: Optional[datetime] = None
        self.last_activity: Optional[datetime] = None
        self.login_cnpj: Optional[str] = None
        
    async def initialize(self):
        """Inicializa navegador e cria pool de páginas"""
        if self.is_initialized:
            return
            
        try:
            logger.info("inicializando_session_manager_pool", pool_size=self.pool_size)
            
            # Inicializar componentes base
            self.browser_manager = BrowserManager()
            self.email_extractor = EmailCodeExtractor(
                settings.RESOLVE_EMAIL,
                settings.RESOLVE_EMAIL_PASSWORD,
                settings.RESOLVE_IMAP_SERVER
            )
            self.login_manager = LoginManager(self.email_extractor)
            
            # Inicializar contexto compartilhado (sessão/cookies)
            self.context = await self.browser_manager.initialize()
            
            # Realizar login inicial em página temporária
            await self._perform_initial_login()
            
            if self.is_logged_in:
                # 🔄 CORREÇÃO: Criar apenas pool inicial mínimo (1 página)
                await self._create_initial_pool()
                
                # Iniciar sistema de refresh automático
                await self._start_auto_refresh()
                
                self.is_initialized = True
                logger.info("session_manager_inicializado_pool_lazy", 
                           pool_inicial=1,
                           pool_maximo=self.pool_size,
                           auto_refresh=self.auto_refresh_enabled)
            else:
                raise Exception("Falha no login inicial")
                
        except Exception as e:
            logger.error("erro_inicializar_session_manager_pool", error=str(e))
            raise
    
    async def _perform_initial_login(self):
        """Realiza login inicial e prepara primeira página do pool"""
        try:
            # Criar primeira página que será reutilizada no pool
            self.initial_page = await self.context.new_page()
            
            cnpj_login = settings.RESOLVE_CENPROT_LOGIN
            success = await self.login_manager.perform_full_login(self.initial_page, cnpj_login)
            
            if success:
                # Navegar direto para página de consulta após login
                await self.initial_page.goto("https://resolve.cenprot.org.br/app/dashboard/search/public-search")
                await self.initial_page.wait_for_load_state("networkidle")
                
                self.is_logged_in = True
                self.last_login = datetime.now()
                self.login_cnpj = cnpj_login
                logger.info("login_inicial_realizado_pool_reutilizavel", cnpj=cnpj_login)
            else:
                logger.warning("falha_login_inicial_pool", cnpj=cnpj_login)
                # Se falhou, fechar a página
                await self.initial_page.close()
                self.initial_page = None
                
        except Exception as e:
            logger.error("erro_login_inicial_pool", error=str(e))
            if hasattr(self, 'initial_page') and self.initial_page:
                try:
                    await self.initial_page.close()
                    self.initial_page = None
                except:
                    pass
    
    async def _create_initial_pool(self):
        """🔄 CORREÇÃO: Cria pool inicial apenas com página já logada (evita múltiplos 2FA)"""
        try:
            # Contador para próximas páginas sob demanda
            self.pages_created_count = 1
            
            # Adicionar apenas página inicial (já logada) ao pool
            if hasattr(self, 'initial_page') and self.initial_page:
                initial_page_info = {
                    "page": self.initial_page,
                    "id": "page_0",
                    "created_at": datetime.now(),
                    "usage_count": 0,
                    "in_use": False,
                    "logged_in": True,
                    "last_login": self.last_login
                }
                
                # Registrar no controle geral de páginas
                self.all_pages["page_0"] = initial_page_info
                
                await self.page_pool.put(initial_page_info)
                logger.info("pool_inicial_lazy_criado", 
                           page_id="page_0", 
                           pool_size=1,
                           max_pool_size=self.pool_size,
                           estrategia="lazy_creation")
            else:
                raise Exception("Página inicial não encontrada")
                
        except Exception as e:
            logger.error("erro_criar_pool_inicial_lazy", error=str(e))
            raise

    async def _create_page_on_demand(self) -> dict:
        """🆕 NOVO: Cria nova página sob demanda quando pool está vazio"""
        try:
            # Verificar limite máximo
            if self.pages_created_count >= self.pool_size:
                raise Exception(f"Limite máximo de páginas atingido: {self.pool_size}")
            
            page_id = f"page_{self.pages_created_count}"
            cnpj_login = settings.RESOLVE_CENPROT_LOGIN
            
            logger.info("criando_pagina_sob_demanda", 
                       page_id=page_id,
                       total_criadas=self.pages_created_count,
                       max_pool=self.pool_size)
            
            # Criar nova página no contexto autenticado
            page = await self.context.new_page()
            
            # Fazer login individual nesta página
            login_success = await self.login_manager.perform_full_login(page, cnpj_login)
            
            if login_success:
                # Navegar direto para página de consulta após login
                await page.goto("https://resolve.cenprot.org.br/app/dashboard/search/public-search")
                await page.wait_for_load_state("networkidle")
                
                page_info = {
                    "page": page,
                    "id": page_id,
                    "created_at": datetime.now(),
                    "usage_count": 0,
                    "in_use": True,  # Já marca como em uso pois será retornada imediatamente
                    "logged_in": True,
                    "last_login": datetime.now(),
                    "created_on_demand": True
                }
                
                # Adicionar ao registro geral
                self.all_pages[page_id] = page_info
                self.pages_created_count += 1
                
                logger.info("pagina_sob_demanda_criada_sucesso", 
                           page_id=page_id,
                           total_pages_ativas=len(self.all_pages),
                           pool_size_atual=self.page_pool.qsize())
                
                return page_info
            else:
                logger.error("falha_login_pagina_sob_demanda", page_id=page_id)
                await page.close()
                raise Exception(f"Falha no login da página sob demanda {page_id}")
                
        except Exception as e:
            logger.error("erro_criar_pagina_sob_demanda", 
                        pages_created=getattr(self, 'pages_created_count', 0),
                        error=str(e))
            raise
    
    async def _start_auto_refresh(self):
        """Inicia sistema de refresh automático para manter páginas ativas"""
        if self.auto_refresh_enabled:
            self.refresh_task = asyncio.create_task(self._auto_refresh_pages())
            logger.info("auto_refresh_iniciado", 
                       interval=self.refresh_interval,
                       total_pages=len(self.all_pages))
    
    async def _auto_refresh_pages(self):
        """Task de background que faz refresh automático das páginas ociosas"""
        try:
            while self.auto_refresh_enabled and self.is_initialized:
                await asyncio.sleep(self.refresh_interval)
                
                if not self.all_pages:
                    continue
                
                # Fazer refresh apenas em páginas que NÃO estão em uso
                idle_pages = []
                for page_id, page_info in self.all_pages.items():
                    if not page_info.get("in_use", False):
                        idle_pages.append((page_id, page_info))
                
                if idle_pages:
                    logger.info("iniciando_refresh_automatico", 
                               idle_pages=len(idle_pages),
                               total_pages=len(self.all_pages))
                    
                    # Fazer refresh de todas as páginas ociosas em paralelo
                    refresh_tasks = [
                        self._refresh_idle_page(page_id, page_info) 
                        for page_id, page_info in idle_pages
                    ]
                    
                    # Aguardar todos os refreshes concluírem
                    await asyncio.gather(*refresh_tasks, return_exceptions=True)
                
        except asyncio.CancelledError:
            logger.info("auto_refresh_task_cancelada")
        except Exception as e:
            logger.error("erro_auto_refresh_task", error=str(e))
    
    async def _refresh_idle_page(self, page_id: str, page_info: dict):
        """Faz refresh de uma página específica que está ociosa"""
        try:
            # 🛡️ VERIFICAÇÃO DUPLA DE SEGURANÇA
            # Re-verificar se página ainda está ociosa no momento exato do refresh
            if page_info.get("in_use", False):
                logger.info("refresh_cancelado_pagina_em_uso", 
                           page_id=page_id,
                           motivo="página ficou ativa durante verificação")
                return
            
            # Verificação adicional no registro geral
            if page_id in self.all_pages and self.all_pages[page_id].get("in_use", False):
                logger.info("refresh_cancelado_registro_geral", 
                           page_id=page_id,
                           motivo="página ativa no registro geral")
                return
            
            # Verificação final: se está na lista de páginas ativas
            if page_id in self.active_pages:
                logger.info("refresh_cancelado_active_pages", 
                           page_id=page_id,
                           motivo="página encontrada em active_pages")
                return
            
            page = page_info["page"]
            
            logger.info("refresh_seguro_iniciado", 
                       page_id=page_id,
                       verificacoes_passaram="todas_ok")
            
            # Verificar se está na URL esperada (home)
            current_url = page.url
            
            if "/dashboard/home" in current_url:
                # 🛡️ VERIFICAÇÃO FINAL antes de executar o refresh
                if page_info.get("in_use", False) or page_id in self.active_pages:
                    logger.warning("refresh_abortado_ultima_verificacao", 
                                  page_id=page_id,
                                  motivo="página ficou ativa no último momento")
                    return
                
                # Fazer refresh simples apenas se REALMENTE está ociosa
                logger.info("executando_refresh_verificado", page_id=page_id)
                await page.reload(wait_until="networkidle", timeout=10000)
                
                # Atualizar timestamp
                page_info["last_refresh"] = datetime.now()
                
                logger.info("pagina_refresh_automatico_sucesso", 
                           page_id=page_id,
                           url=current_url[:50])
            else:
                # 🛡️ VERIFICAÇÃO FINAL antes de navegar de volta
                if page_info.get("in_use", False) or page_id in self.active_pages:
                    logger.warning("navegacao_abortada_ultima_verificacao", 
                                  page_id=page_id,
                                  motivo="página ficou ativa no último momento")
                    return
                
                # Se não está na URL correta, navegar para home
                logger.info("executando_navegacao_verificada", page_id=page_id, url_anterior=current_url[:50])
                await page.goto("https://resolve.cenprot.org.br/app/dashboard/home")
                await page.wait_for_load_state("networkidle", timeout=10000)
                
                page_info["last_refresh"] = datetime.now()
                page_info["redirected"] = True
                
                logger.info("pagina_redirecionada_para_home", 
                           page_id=page_id,
                           previous_url=current_url[:50])
                
        except Exception as e:
            logger.warning("erro_refresh_pagina_ociosa", 
                          page_id=page_id, 
                          error=str(e))
    
    async def _stop_auto_refresh(self):
        """Para o sistema de refresh automático"""
        self.auto_refresh_enabled = False
        
        if self.refresh_task and not self.refresh_task.done():
            self.refresh_task.cancel()
            try:
                await self.refresh_task
            except asyncio.CancelledError:
                pass
        
        logger.info("auto_refresh_parado")
    
    async def get_page_from_pool(self, timeout: int = 45):
        """🔄 NOVO: Obtém página do pool ou cria sob demanda se necessário"""
        try:
            # Primeiro tentar obter página existente do pool (com timeout curto)
            try:
                page_info = await asyncio.wait_for(
                    self.page_pool.get(), 
                    timeout=2  # Timeout curto para verificar se há páginas disponíveis
                )
                
                # Marcar como em uso
                page_info["in_use"] = True
                page_info["usage_count"] += 1
                page_info["last_used"] = datetime.now()
                
                # Registrar página ativa
                self.active_pages[page_info["id"]] = page_info
                
                # Atualizar no registro geral (para o auto refresh)
                if page_info["id"] in self.all_pages:
                    self.all_pages[page_info["id"]].update(page_info)
                
                self.last_activity = datetime.now()
                
                logger.info("pagina_obtida_do_pool_existente", 
                           page_id=page_info["id"],
                           usage_count=page_info["usage_count"],
                           pool_remaining=self.page_pool.qsize())
                
                return page_info
                
            except asyncio.TimeoutError:
                # Pool vazio - criar página sob demanda se possível
                if self.pages_created_count < self.pool_size:
                    logger.info("pool_vazio_criando_pagina_sob_demanda", 
                               pages_criadas=self.pages_created_count,
                               max_pool=self.pool_size)
                    
                    page_info = await self._create_page_on_demand()
                    
                    # Registrar página ativa
                    self.active_pages[page_info["id"]] = page_info
                    page_info["usage_count"] = 1
                    page_info["last_used"] = datetime.now()
                    
                    self.last_activity = datetime.now()
                    
                    return page_info
                else:
                    # Limite máximo atingido - aguardar com timeout original
                    logger.warning("limite_pool_atingido_aguardando_retorno", 
                                  pages_criadas=self.pages_created_count,
                                  max_pool=self.pool_size)
                    
                    page_info = await asyncio.wait_for(
                        self.page_pool.get(), 
                        timeout=timeout
                    )
                    
                    # Marcar como em uso
                    page_info["in_use"] = True
                    page_info["usage_count"] += 1
                    page_info["last_used"] = datetime.now()
                    
                    # Registrar página ativa
                    self.active_pages[page_info["id"]] = page_info
                    
                    # Atualizar no registro geral
                    if page_info["id"] in self.all_pages:
                        self.all_pages[page_info["id"]].update(page_info)
                    
                    self.last_activity = datetime.now()
                    
                    logger.info("pagina_obtida_apos_aguardar", 
                               page_id=page_info["id"],
                               usage_count=page_info["usage_count"])
                    
                    return page_info
            
        except asyncio.TimeoutError:
            logger.error("timeout_definitivo_obter_pagina", 
                        timeout=timeout,
                        active_pages=len(self.active_pages),
                        pool_size=self.pool_size,
                        pages_created=self.pages_created_count)
            raise Exception(f"Timeout ({timeout}s): todas as {self.pool_size} páginas estão em uso")
        except Exception as e:
            logger.error("erro_obter_pagina_pool_ou_criar", error=str(e))
            raise
    
    async def return_page_to_pool(self, page_info: dict):
        """Retorna página para o pool após uso"""
        try:
            page_id = page_info["id"]
            
            # Remover do registro de páginas ativas
            if page_id in self.active_pages:
                del self.active_pages[page_id]
            
            # Marcar como disponível
            page_info["in_use"] = False
            page_info["returned_at"] = datetime.now()
            
            # Atualizar no registro geral (para o auto refresh)
            if page_id in self.all_pages:
                self.all_pages[page_id].update(page_info)
            
            # Navegar para home após consulta (estado neutro e limpo)
            try:
                await page_info["page"].goto("https://resolve.cenprot.org.br/app/dashboard/home")
                # Aguardar página carregar completamente
                await page_info["page"].wait_for_load_state("networkidle", timeout=5000)
                logger.info("pagina_navegada_para_home", page_id=page_id)
            except Exception as e:
                # Se falhar, página pode estar em estado inconsistente
                logger.warning("falha_navegar_pagina_home", page_id=page_id, error=str(e))
            
            # Retornar ao pool
            await self.page_pool.put(page_info)
            
            logger.info("pagina_retornada_ao_pool", 
                       page_id=page_id,
                       usage_count=page_info["usage_count"],
                       pool_available=self.page_pool.qsize())
            
        except Exception as e:
            logger.error("erro_retornar_pagina_pool", 
                        page_id=page_info.get("id", "unknown"), 
                        error=str(e))
    
    async def validate_page_session(self, page) -> bool:
        """
        Valida se a página ainda está logada fazendo refresh e verificando URL
        
        Returns:
            True: Sessão válida (ainda na página de consulta)
            False: Sessão expirada (redirecionado para /app/auth)
        """
        try:
            logger.info("validando_sessao_pagina", url_atual=page.url)
            
            # Fazer refresh da página para verificar se ainda está logado
            await page.reload(wait_until="networkidle", timeout=15000)
            
            # Aguardar um pouco para qualquer redirecionamento ocorrer
            await asyncio.sleep(1)
            
            # Verificar URL atual após refresh
            current_url = page.url
            
            if "/app/auth" in current_url:
                logger.warning("sessao_expirada_detectada", url=current_url)
                return False
            elif "/search/public-search" in current_url:
                logger.info("sessao_valida_confirmada", url=current_url)
                return True
            elif "/dashboard/home" in current_url:
                logger.info("sessao_valida_em_home", url=current_url)
                # Navegar para página de consulta já que vamos fazer uma consulta
                await page.goto("https://resolve.cenprot.org.br/app/dashboard/search/public-search")
                await page.wait_for_load_state("networkidle", timeout=10000)
                return True
            else:
                logger.warning("url_inesperada_apos_refresh", url=current_url)
                # Tentar navegar para página de consulta
                await page.goto("https://resolve.cenprot.org.br/app/dashboard/search/public-search")
                await page.wait_for_load_state("networkidle", timeout=10000)
                
                if "/app/auth" in page.url:
                    return False
                else:
                    return True
                    
        except Exception as e:
            logger.error("erro_validar_sessao_pagina", error=str(e))
            return False
    
    async def perform_relogin_on_page(self, page) -> bool:
        """
        Realiza novo login em uma página que perdeu a sessão
        
        Args:
            page: Página que precisa de re-login
            
        Returns:
            True: Re-login bem-sucedido
            False: Falha no re-login
        """
        try:
            logger.info("iniciando_relogin_pagina")
            
            cnpj_login = settings.RESOLVE_CENPROT_LOGIN
            success = await self.login_manager.perform_full_login(page, cnpj_login)
            
            if success:
                # Navegar direto para página de consulta após re-login
                await page.goto("https://resolve.cenprot.org.br/app/dashboard/search/public-search")
                await page.wait_for_load_state("networkidle", timeout=10000)
                
                logger.info("relogin_pagina_realizado_com_sucesso")
                return True
            else:
                logger.error("falha_relogin_pagina")
                return False
                
        except Exception as e:
            logger.error("erro_relogin_pagina", error=str(e))
            return False

    async def get_pool_status(self) -> Dict[str, Any]:
        """Retorna status do pool de páginas"""
        return {
            "pool_size": self.pool_size,
            "available_pages": self.page_pool.qsize(),
            "active_pages": len(self.active_pages),
            "active_page_ids": list(self.active_pages.keys()),
            "total_pages_created": self.pool_size
        }
    
    def _is_session_valid(self) -> bool:
        """Verifica se a sessão ainda é válida (últimas 2 horas)"""
        if not self.last_login:
            return False
            
        session_age = datetime.now() - self.last_login
        return session_age < timedelta(hours=2)
    
    async def _cleanup_expired_pool(self):
        """
        🛠️ CORREÇÃO: Limpa pool de páginas expiradas para evitar duplicação
        """
        try:
            logger.info("iniciando_limpeza_pool_expirado", 
                       pool_size_atual=self.page_pool.qsize(),
                       active_pages=len(self.active_pages),
                       all_pages=len(self.all_pages))
            
            # 1. Fechar todas as páginas ativas
            pages_fechadas = 0
            for page_id, page_info in list(self.active_pages.items()):
                try:
                    await page_info["page"].close()
                    pages_fechadas += 1
                except Exception as e:
                    logger.warning("erro_fechar_pagina_ativa", page_id=page_id, error=str(e))
            
            self.active_pages.clear()
            
            # 2. Limpar todas as páginas do pool
            while not self.page_pool.empty():
                try:
                    page_info = await self.page_pool.get()
                    await page_info["page"].close()
                    pages_fechadas += 1
                except Exception as e:
                    logger.warning("erro_fechar_pagina_pool", error=str(e))
            
            # 3. Fechar páginas no registro geral
            for page_id, page_info in list(self.all_pages.items()):
                try:
                    if not page_info["page"].is_closed():
                        await page_info["page"].close()
                        pages_fechadas += 1
                except Exception as e:
                    logger.warning("erro_fechar_pagina_all_pages", page_id=page_id, error=str(e))
            
            self.all_pages.clear()
            
            # 4. Fechar initial_page se existir
            if hasattr(self, 'initial_page') and self.initial_page:
                try:
                    if not self.initial_page.is_closed():
                        await self.initial_page.close()
                        pages_fechadas += 1
                except Exception as e:
                    logger.warning("erro_fechar_initial_page", error=str(e))
                self.initial_page = None
            
            logger.info("limpeza_pool_expirado_concluida", 
                       pages_fechadas=pages_fechadas,
                       pool_limpo=self.page_pool.empty(),
                       registros_limpos=(len(self.active_pages) == 0 and len(self.all_pages) == 0))
            
        except Exception as e:
            logger.error("erro_cleanup_expired_pool", error=str(e))
            raise
    
    async def ensure_logged_in(self) -> bool:
        """Garante que a sessão está ativa"""
        if not self.is_initialized:
            await self.initialize()
        
        if self.is_logged_in and self._is_session_valid():
            return True
            
        # Re-login necessário após timeout de sessão
        logger.warning("sessao_expirada_detectada_relogin_necessario", 
                      last_login=self.last_login,
                      is_logged_in=self.is_logged_in)
        try:
            # 🛠️ CORREÇÃO: Limpar pool antigo antes de recriar
            await self._cleanup_expired_pool()
            
            # Realizar novo login e recriar pool
            await self._perform_initial_login()
            
            if self.is_logged_in:
                # Recriar pool inicial (lazy) com páginas frescas
                await self._create_initial_pool()
                logger.info("pool_inicial_recriado_apos_sessao_expirada", pool_size=1, max_size=self.pool_size)
            
            return self.is_logged_in
        except Exception as e:
            logger.error("erro_ensure_logged_in_pool", error=str(e))
            return False
    
    async def renew_session(self) -> bool:
        """Force renewal da sessão"""
        try:
            self.is_logged_in = False
            return await self.ensure_logged_in()
        except Exception as e:
            logger.error("erro_renew_session_pool", error=str(e))
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status completo da sessão com informações do pool"""
        base_status = {
            "active": self.is_initialized,
            "logged_in": self.is_logged_in,
            "last_activity": self.last_activity,
            "last_login": self.last_login,
            "login_cnpj": self.login_cnpj
        }
        
        # Adicionar informações do pool se disponível
        if hasattr(self, 'page_pool'):
            base_status.update({
                "pool_enabled": True,
                "pool_size": self.pool_size,
                "available_pages": self.page_pool.qsize(),
                "active_requests": len(self.active_pages)
            })
        else:
            base_status["pool_enabled"] = False
        
        return base_status
    
    async def cleanup(self):
        """Limpa todos os recursos incluindo pool de páginas"""
        try:
            # Parar sistema de refresh automático
            await self._stop_auto_refresh()
            
            # Fechar todas as páginas ativas
            for page_info in self.active_pages.values():
                try:
                    await page_info["page"].close()
                except:
                    pass
            
            # Fechar páginas no pool
            while not self.page_pool.empty():
                try:
                    page_info = await self.page_pool.get()
                    await page_info["page"].close()
                except:
                    pass
            
            # Cleanup padrão
            if self.email_extractor:
                self.email_extractor.disconnect()
            if self.browser_manager:
                await self.browser_manager.close()
                
            logger.info("session_manager_pool_cleanup_completo")
            
        except Exception as e:
            logger.error("erro_cleanup_session_manager_pool", error=str(e))
