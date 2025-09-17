"""
Gestor principal de login para o Resolve CenProt
Coordena todo o fluxo de autenticação incluindo 2FA
"""

from playwright.async_api import Page, BrowserContext
from typing import Optional
import asyncio
import re
import structlog

from .two_factor_auth import TwoFactorHandler
from .email_extractor import EmailCodeExtractor
from ..config.selectors import ResolveSelectors
from ..config.settings import settings

logger = structlog.get_logger(__name__)

class LoginManager:
    """Gerenciador completo do fluxo de login do Resolve CenProt"""
    
    def __init__(self, email_extractor: EmailCodeExtractor):
        self.email_extractor = email_extractor
        self.two_factor = TwoFactorHandler()
        self.selectors = ResolveSelectors()
        self.is_logged_in = False
        self.current_session_cnpj: Optional[str] = None
        
    async def perform_full_login(self, page: Page, cnpj: str) -> bool:
        """
        Executa o fluxo completo de login baseado nos passos documentados
        
        Args:
            page: Página do Playwright
            cnpj: CNPJ para fazer login
            
        Returns:
            bool: True se login foi bem-sucedido
        """
        try:
            logger.info("iniciando_login_completo", cnpj=cnpj[:8] + "****")
            
            # Passo 1: Navegar para página de autenticação
            if not await self._navigate_to_auth_page(page):
                return False
            
            # Passo 2: Preencher CNPJ
            if not await self._fill_cnpj(page, cnpj):
                return False
            
            # Passo 3: Primeira continuação
            if not await self._first_continue(page):
                return False
            
            # Passo 4: Marcar checkbox titular
            if not await self._check_titular_checkbox(page):
                return False
            
            # Passo 5: Segunda continuação
            if not await self._second_continue(page):
                return False
            
            # Passo 6: Terceira continuação (dispara 2FA)
            if not await self._third_continue_trigger_2fa(page):
                return False
            
            # Passo 7: Aguardar e processar 2FA
            if not await self._process_2fa(page):
                return False
            
            # Passo 8: Validar redirecionamento para dashboard
            if not await self._validate_dashboard_redirect(page):
                return False
            
            # Sucesso!
            self.is_logged_in = True
            self.current_session_cnpj = cnpj
            logger.info("login_completo_realizado_com_sucesso", cnpj=cnpj[:8] + "****")
            
            return True
            
        except Exception as e:
            logger.error("falha_no_login_completo", cnpj=cnpj[:8] + "****", error=str(e))
            await self._take_error_screenshot(page, f"login_error_{cnpj}")
            return False
    
    async def _navigate_to_auth_page(self, page: Page) -> bool:
        """Passo 1: Navegar para página de autenticação"""
        try:
            logger.info("navegando_para_pagina_auth")
            
            await page.goto(f"{settings.RESOLVE_CENPROT_URL}/app/auth")
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            # Verificar se chegou na página correta
            current_url = page.url
            if "/app/auth" not in current_url:
                logger.error("url_auth_incorreta", current_url=current_url)
                return False
            
            # Aguardar campo CNPJ aparecer
            await page.wait_for_selector(self.selectors.LOGIN_INPUT, timeout=10000)
            
            logger.info("pagina_auth_carregada_com_sucesso")
            return True
            
        except Exception as e:
            logger.error("erro_navegar_auth", error=str(e))
            return False
    
    async def _fill_cnpj(self, page: Page, cnpj: str) -> bool:
        """Passo 2: Preencher campo CNPJ"""
        try:
            logger.info("preenchendo_campo_cnpj")
            
            # Limpar campo antes de preencher
            await page.fill(self.selectors.LOGIN_INPUT, "")
            await asyncio.sleep(0.5)
            
            # Preencher CNPJ
            await page.fill(self.selectors.LOGIN_INPUT, cnpj)
            
            # Verificar se foi preenchido corretamente
            field_value = await page.input_value(self.selectors.LOGIN_INPUT)
            if not field_value:
                logger.error("campo_cnpj_vazio")
                return False
            
            # Verificar se CNPJ está presente (pode estar formatado)
            cnpj_digits = re.sub(r'[^\d]', '', cnpj)
            field_digits = re.sub(r'[^\d]', '', field_value)
            
            if cnpj_digits != field_digits:
                logger.error("cnpj_nao_preenchido_corretamente", 
                           expected_digits=cnpj_digits, 
                           field_digits=field_digits,
                           field_value=field_value)
                return False
            
            logger.info("cnpj_preenchido_com_sucesso")
            return True
            
        except Exception as e:
            logger.error("erro_preencher_cnpj", error=str(e))
            return False
    
    async def _first_continue(self, page: Page) -> bool:
        """Passo 3: Primeira continuação"""
        try:
            logger.info("primeiro_continue")
            
            await page.click(self.selectors.CONTINUE_BTN)
            await asyncio.sleep(1)
            
            # Verificar se prosseguiu (checkbox deve aparecer)
            try:
                await page.wait_for_selector(self.selectors.CHECKBOX_TITULAR, timeout=5000)
                logger.info("primeiro_continue_realizado")
                return True
            except:
                logger.error("checkbox_titular_nao_apareceu_apos_primeiro_continue")
                return False
            
        except Exception as e:
            logger.error("erro_primeiro_continue", error=str(e))
            return False
    
    async def _check_titular_checkbox(self, page: Page) -> bool:
        """Passo 4: Marcar checkbox titular"""
        try:
            logger.info("marcando_checkbox_titular")
            
            # Verificar se checkbox existe e não está marcado
            checkbox = await page.query_selector(self.selectors.CHECKBOX_TITULAR)
            if not checkbox:
                logger.error("checkbox_titular_nao_encontrado")
                return False
            
            is_checked = await checkbox.is_checked()
            if not is_checked:
                await page.check(self.selectors.CHECKBOX_TITULAR)
                await asyncio.sleep(0.5)
                
                # Verificar se foi marcado
                is_now_checked = await checkbox.is_checked()
                if not is_now_checked:
                    logger.error("checkbox_nao_foi_marcado")
                    return False
            
            logger.info("checkbox_titular_marcado")
            return True
            
        except Exception as e:
            logger.error("erro_marcar_checkbox", error=str(e))
            return False
    
    async def _second_continue(self, page: Page) -> bool:
        """Passo 5: Segunda continuação"""
        try:
            logger.info("segundo_continue")
            
            await page.click(self.selectors.CONTINUE_BTN)
            await asyncio.sleep(1)
            
            logger.info("segundo_continue_realizado")
            return True
            
        except Exception as e:
            logger.error("erro_segundo_continue", error=str(e))
            return False
    
    async def _third_continue_trigger_2fa(self, page: Page) -> bool:
        """Passo 6: Terceira continuação que dispara 2FA"""
        try:
            logger.info("terceiro_continue_disparando_2fa")
            
            await page.click(self.selectors.CONTINUE_BTN)
            
            # Aguardar página de 2FA aparecer
            if await self.two_factor.wait_for_2fa_page_load(page, timeout=15000):
                logger.info("pagina_2fa_carregada_apos_terceiro_continue")
                return True
            else:
                logger.error("pagina_2fa_nao_carregou_apos_terceiro_continue")
                return False
            
        except Exception as e:
            logger.error("erro_terceiro_continue", error=str(e))
            return False
    
    async def _process_2fa(self, page: Page) -> bool:
        """Passo 7: Processar autenticação 2FA"""
        try:
            logger.info("processando_2fa")
            
            # Processar 2FA com sistema de limpeza automática de emails
            logger.info("aguardando_codigo_2fa_por_email")
            
            # ✅ USAR NOVO SISTEMA COM DETECÇÃO DE ERRO E LIMPEZA AUTOMÁTICA
            success = await self.two_factor.fill_otp_with_email_retry(
                page, 
                self.email_extractor, 
                max_attempts=4  # Mais tentativas para recuperação automática
            )
            
            if not success:
                logger.error("falha_processar_2fa_apos_todas_tentativas")
                # Fazer limpeza final se ainda falhou
                await self.email_extractor.cleanup_all_2fa_emails()
                return False
            
            # ✅ SE CHEGOU AQUI, O 2FA FOI BEM-SUCEDIDO
            # O método fill_otp_with_email_retry já:
            # - Preencheu os campos
            # - Clicou o botão continuar  
            # - Verificou redirecionamento para dashboard
            # - Retornou True apenas se tudo funcionou
            
            logger.info("2fa_processado_com_sucesso_redirecionamento_confirmado")
            return True
            
        except Exception as e:
            logger.error("erro_processar_2fa", error=str(e))
            return False
    
    async def _validate_dashboard_redirect(self, page: Page) -> bool:
        """Passo 8: Validar redirecionamento para dashboard - VERSÃO ULTRA OTIMIZADA"""
        try:
            logger.info("validando_redirecionamento_dashboard_ultra_otimizado")
            
            # Verificação inteligente: primeiro checar se já está na URL certa
            current_url = page.url
            if "/dashboard/home" in current_url:
                logger.info("ja_esta_no_dashboard_url_correta", url=current_url)
                return True
            
            # Se não está, aguardar redirecionamento com timeout menor
            try:
                await page.wait_for_url("**/dashboard/home", timeout=5000)  # Reduzido para 5s
                current_url = page.url
                logger.info("redirecionamento_dashboard_confirmado", url=current_url)
                return True
            except:
                # Se timeout, verificar URL uma última vez
                current_url = page.url
                if "/dashboard/home" in current_url:
                    logger.info("dashboard_encontrado_apos_timeout", url=current_url)
                    return True
                else:
                    logger.error("falha_redirecionamento_dashboard", current_url=current_url)
                    return False
            
        except Exception as e:
            logger.error("erro_validar_dashboard", error=str(e))
            current_url = page.url if page else "unknown"
            logger.error("url_atual_apos_erro", current_url=current_url)
            return False
    
    async def is_already_logged_in(self, page: Page) -> bool:
        """
        Verifica se já está logado checando a URL atual
        
        Args:
            page: Página do Playwright
            
        Returns:
            bool: True se já está logado
        """
        try:
            current_url = page.url
            
            # Se está na página de dashboard, provavelmente já está logado
            if "/dashboard" in current_url:
                logger.info("sessao_ja_ativa", current_url=current_url)
                self.is_logged_in = True
                return True
            
            # Tentar navegar para dashboard para testar
            await page.goto(f"{settings.RESOLVE_CENPROT_URL}/app/dashboard/home")
            await asyncio.sleep(2)
            
            final_url = page.url
            if "/dashboard/home" in final_url:
                logger.info("sessao_ativa_confirmada", final_url=final_url)
                self.is_logged_in = True
                return True
            
            logger.info("sessao_nao_ativa_login_necessario")
            return False
            
        except Exception as e:
            logger.debug("erro_verificar_login_existente", error=str(e))
            return False
    
    async def logout(self, page: Page) -> bool:
        """
        Realiza logout se necessário
        
        Args:
            page: Página do Playwright
            
        Returns:
            bool: True se fez logout ou não estava logado
        """
        try:
            if not self.is_logged_in:
                return True
            
            logger.info("realizando_logout")
            
            # Tentar encontrar botão de logout
            logout_selectors = [
                "button:contains('Sair')",
                "a:contains('Logout')",
                "button:contains('Logout')",
                "[data-logout]"
            ]
            
            for selector in logout_selectors:
                try:
                    if "contains" in selector:
                        text = selector.split("contains('")[1].split("')")[0]
                        element = await page.query_selector(f"text={text}")
                    else:
                        element = await page.query_selector(selector)
                    
                    if element and await element.is_visible():
                        await element.click()
                        logger.info("logout_realizado")
                        self.is_logged_in = False
                        self.current_session_cnpj = None
                        return True
                        
                except Exception as e:
                    logger.debug("erro_logout_selector", selector=selector, error=str(e))
                    continue
            
            # Se não encontrou botão, tentar limpar cookies
            await page.context.clear_cookies()
            logger.info("cookies_limpos_logout_forçado")
            self.is_logged_in = False
            self.current_session_cnpj = None
            
            return True
            
        except Exception as e:
            logger.error("erro_realizar_logout", error=str(e))
            return False
    
    async def _take_error_screenshot(self, page: Page, filename: str):
        """Captura screenshot em caso de erro"""
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = settings.LOGS_DIR / "screenshots" / f"{filename}_{timestamp}.png"
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            
            await page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info("screenshot_erro_capturado", path=str(screenshot_path))
            
        except Exception as e:
            logger.debug("erro_capturar_screenshot", error=str(e))
    
    def get_login_status(self) -> dict:
        """Retorna status atual do login"""
        return {
            "is_logged_in": self.is_logged_in,
            "current_cnpj": self.current_session_cnpj[:8] + "****" if self.current_session_cnpj else None,
            "email_configured": bool(self.email_extractor.email_address),
        }
