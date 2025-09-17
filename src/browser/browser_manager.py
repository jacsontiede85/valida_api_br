"""
Gestor do navegador Playwright para o RPA Resolve CenProt
"""

from playwright.async_api import Playwright, Browser, BrowserContext, Page, async_playwright
from typing import Optional, Dict, Any
import asyncio
import structlog
from pathlib import Path

from ..config.settings import settings

logger = structlog.get_logger(__name__)

class BrowserManager:
    """Gerenciador do navegador Playwright com configurações anti-detecção"""
    
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.initialized = False
        
    async def initialize(self) -> BrowserContext:
        """
        Inicializa o navegador com configurações otimizadas
        
        Returns:
            BrowserContext: Contexto do navegador configurado
        """
        if self.initialized:
            logger.info("browser_ja_inicializado")
            return self.context
            
        logger.info("inicializando_browser_playwright")
        
        try:
            # Inicializar Playwright
            self.playwright = await async_playwright().start()
            
            # Configurações do navegador
            browser_args = [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-extensions-file-access-check",
                "--disable-extensions-http-throttling",
                "--disable-extensions-https-requirement",
                "--disable-extensions",
                "--disable-plugins",
                "--disable-plugins-discovery",
                "--disable-preconnect",
                "--disable-sync",
                "--disable-translate",
                "--hide-scrollbars",
                "--mute-audio",
                "--no-first-run",
                "--no-pings",
                "--no-zygote",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-breakpad",
                "--disable-client-side-phishing-detection",
                "--disable-component-extensions-with-background-pages",
                "--disable-default-apps",
                "--disable-dev-shm-usage",
                "--disable-ipc-flooding-protection",
                "--disable-hang-monitor",
                "--disable-popup-blocking",
                "--disable-prompt-on-repost",
                "--disable-renderer-backgrounding",
                "--force-color-profile=srgb",
                "--metrics-recording-only",
                "--no-default-browser-check",
                "--no-first-run",
                "--password-store=basic",
                "--use-mock-keychain",
                "--export-tagged-pdf"
            ]
            
            # Inicializar navegador Chromium
            self.browser = await self.playwright.chromium.launch(
                headless=settings.HEADLESS,
                args=browser_args,
                timeout=settings.BROWSER_TIMEOUT
            )
            
            # Criar contexto com configurações anti-detecção
            context_options = {
                "viewport": {"width": 1366, "height": 768},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "locale": "pt-BR",
                "timezone_id": "America/Sao_Paulo",
                "permissions": ["geolocation"],
                "extra_http_headers": {
                    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-User": "?1",
                    "Sec-Fetch-Dest": "document"
                }
            }
            
            # Adicionar persistência se configurada
            user_data_dir = settings.SESSIONS_DIR / "browser_profile"
            if user_data_dir.exists():
                context_options["storage_state"] = str(user_data_dir / "state.json")
            
            self.context = await self.browser.new_context(**context_options)
            
            # Configurar interceptação para mascarar automação
            await self._setup_stealth_mode()
            
            self.initialized = True
            logger.info("browser_inicializado_com_sucesso", 
                       headless=settings.HEADLESS,
                       user_agent=context_options["user_agent"][:50])
            
            return self.context
            
        except Exception as e:
            logger.error("erro_inicializacao_browser", error=str(e))
            await self.close()
            raise
    
    async def _setup_stealth_mode(self):
        """Configura modo stealth para evitar detecção"""
        await self.context.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Mock languages and plugins
            Object.defineProperty(navigator, 'languages', {
                get: () => ['pt-BR', 'pt', 'en-US', 'en'],
            });
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Mock permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Randomize canvas fingerprint
            const getImageData = HTMLCanvasElement.prototype.getContext('2d').getImageData;
            HTMLCanvasElement.prototype.getContext('2d').getImageData = function(...args) {
                const imageData = getImageData.apply(this, args);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] += Math.floor(Math.random() * 10) - 5;
                    imageData.data[i + 1] += Math.floor(Math.random() * 10) - 5;
                    imageData.data[i + 2] += Math.floor(Math.random() * 10) - 5;
                }
                return imageData;
            };
            
            // Mock chrome runtime
            if (!window.chrome) {
                window.chrome = {};
            }
            
            if (!window.chrome.runtime) {
                window.chrome.runtime = {
                    onConnect: undefined,
                    onMessage: undefined
                };
            }
        """)
        
        logger.info("modo_stealth_configurado")
    
    async def new_page(self) -> Page:
        """
        Cria uma nova página no contexto atual
        
        Returns:
            Page: Nova página configurada
        """
        if not self.initialized:
            await self.initialize()
        
        self.page = await self.context.new_page()
        
        # Configurar timeouts
        self.page.set_default_timeout(settings.BROWSER_TIMEOUT)
        self.page.set_default_navigation_timeout(settings.BROWSER_TIMEOUT)
        
        # Event listeners para debugging
        self.page.on("console", lambda msg: logger.debug("browser_console", 
                                                        type=msg.type, 
                                                        text=msg.text))
        
        self.page.on("pageerror", lambda exc: logger.error("browser_page_error", 
                                                          error=str(exc)))
        
        logger.info("nova_pagina_criada")
        return self.page
    
    async def save_session_state(self):
        """Salva estado da sessão para reutilização"""
        if not self.context:
            return
            
        try:
            user_data_dir = settings.SESSIONS_DIR / "browser_profile"
            user_data_dir.mkdir(parents=True, exist_ok=True)
            
            state = await self.context.storage_state()
            state_file = user_data_dir / "state.json"
            
            with open(state_file, 'w', encoding='utf-8') as f:
                import json
                json.dump(state, f, indent=2)
            
            logger.info("estado_sessao_salvo", file=str(state_file))
            
        except Exception as e:
            logger.error("erro_salvar_estado_sessao", error=str(e))
    
    async def take_screenshot(self, name: str = "screenshot") -> Path:
        """
        Captura screenshot da página atual
        
        Args:
            name: Nome do arquivo (sem extensão)
            
        Returns:
            Path: Caminho do arquivo salvo
        """
        if not self.page:
            raise RuntimeError("Página não inicializada")
        
        screenshot_dir = settings.LOGS_DIR / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = screenshot_dir / f"{name}_{timestamp}.png"
        
        await self.page.screenshot(
            path=str(screenshot_path),
            full_page=True
        )
        
        logger.info("screenshot_capturado", path=str(screenshot_path))
        return screenshot_path
    
    async def wait_for_stable_dom(self, timeout: int = 5000):
        """
        Aguarda DOM estabilizar (sem mudanças por período determinado)
        
        Args:
            timeout: Timeout em milissegundos
        """
        if not self.page:
            return
            
        try:
            await self.page.wait_for_function("""
                () => {
                    return new Promise((resolve) => {
                        let timer;
                        const observer = new MutationObserver(() => {
                            clearTimeout(timer);
                            timer = setTimeout(() => {
                                observer.disconnect();
                                resolve(true);
                            }, 1000);
                        });
                        
                        observer.observe(document.body, {
                            childList: true,
                            subtree: true,
                            attributes: true
                        });
                        
                        timer = setTimeout(() => {
                            observer.disconnect();
                            resolve(true);
                        }, 1000);
                    });
                }
            """, timeout=timeout)
            
            logger.debug("dom_estabilizado")
            
        except Exception as e:
            logger.debug("timeout_aguardando_dom_estavel", error=str(e))
    
    async def close(self):
        """Fecha navegador e limpa recursos"""
        try:
            if self.page:
                await self.page.close()
                self.page = None
            
            if self.context:
                await self.save_session_state()
                await self.context.close()
                self.context = None
            
            if self.browser:
                await self.browser.close()
                self.browser = None
            
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            
            self.initialized = False
            logger.info("browser_fechado")
            
        except Exception as e:
            logger.error("erro_fechar_browser", error=str(e))
    
    def __del__(self):
        """Cleanup automático"""
        if self.initialized:
            logger.warning("browser_nao_fechado_adequadamente_use_close()")

# Funções utilitárias
async def with_retry(operation, max_retries: int = 3, delay: float = 1.0):
    """
    Executa operação com retry automático
    
    Args:
        operation: Função async para executar
        max_retries: Máximo de tentativas
        delay: Delay entre tentativas em segundos
    """
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return await operation()
        except Exception as e:
            last_exception = e
            logger.warning("tentativa_falhada", attempt=attempt + 1, error=str(e))
            
            if attempt < max_retries - 1:
                await asyncio.sleep(delay * (attempt + 1))  # Backoff exponencial
    
    raise last_exception

async def safe_click(page: Page, selector: str, timeout: int = 10000) -> bool:
    """
    Clica em elemento com verificações de segurança
    
    Args:
        page: Página do Playwright
        selector: Seletor CSS do elemento
        timeout: Timeout em milissegundos
        
    Returns:
        bool: True se clicou com sucesso
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        element = await page.query_selector(selector)
        
        if not element:
            return False
        
        # Verificar se elemento está visível e habilitado
        is_visible = await element.is_visible()
        is_enabled = await element.is_enabled()
        
        if not (is_visible and is_enabled):
            logger.warning("elemento_nao_clicavel", selector=selector, 
                          visible=is_visible, enabled=is_enabled)
            return False
        
        await element.click()
        return True
        
    except Exception as e:
        logger.error("erro_click_seguro", selector=selector, error=str(e))
        return False
