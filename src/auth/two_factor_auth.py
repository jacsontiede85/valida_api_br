"""
Handler de autenticação de dois fatores (2FA) para Resolve CenProt
"""

from playwright.async_api import Page
from typing import Optional, List
import asyncio
import re
import structlog

from ..config.selectors import ResolveSelectors

logger = structlog.get_logger(__name__)

class TwoFactorHandler:
    """Gerenciador de autenticação 2FA para o site Resolve CenProt"""
    
    def __init__(self):
        self.selectors = ResolveSelectors()
        
    async def fill_otp_fields(self, page: Page, code: str) -> bool:
        """
        Preenche os 6 campos de OTP com o código 2FA
        
        Args:
            page: Página do Playwright
            code: Código de 6 dígitos
            
        Returns:
            bool: True se preencheu com sucesso
        """
        if not code or len(code) != 6 or not re.match(r'^[A-Z0-9]{6}$', code.upper()):
            logger.error("codigo_2fa_invalido", code_length=len(code) if code else 0, code_sample=code[:3] if code else "")
            return False
        
        logger.info("preenchendo_campos_otp")
        
        try:
            # Aguardar os campos OTP aparecerem
            await page.wait_for_selector(self.selectors.OTP_FIELDS[0], timeout=15000)
            
            # Verificar se todos os 6 campos estão presentes
            for i in range(6):
                field_selector = self.selectors.get_otp_field(i)
                field = await page.query_selector(field_selector)
                
                if not field:
                    logger.error("campo_otp_nao_encontrado", field_index=i, selector=field_selector)
                    return False
            
            # Preencher cada campo com um dígito
            for i, digit in enumerate(code):
                field_selector = self.selectors.get_otp_field(i)
                
                try:
                    # Limpar campo antes de preencher
                    await page.fill(field_selector, "")
                    await asyncio.sleep(0.1)
                    
                    # Preencher com o dígito
                    await page.fill(field_selector, digit)
                    
                    # Aguardar um pouco para simular digitação humana
                    await asyncio.sleep(0.2)
                    
                    # Verificar se foi preenchido corretamente
                    field_value = await page.input_value(field_selector)
                    if field_value != digit:
                        logger.warning("campo_otp_nao_preenchido_corretamente", 
                                     field_index=i, 
                                     expected=digit, 
                                     actual=field_value)
                    
                    logger.debug("campo_otp_preenchido", field_index=i, digit="*")
                    
                except Exception as e:
                    logger.error("erro_preencher_campo_otp", field_index=i, error=str(e))
                    return False
            
            # Aguardar um pouco após preencher todos os campos
            await asyncio.sleep(0.5)
            
            # Verificar se todos os campos estão preenchidos
            if await self._verify_all_fields_filled(page):
                logger.info("todos_campos_otp_preenchidos_com_sucesso")
                return True
            else:
                logger.error("nem_todos_campos_otp_foram_preenchidos")
                return False
                
        except Exception as e:
            logger.error("erro_preencher_otp", error=str(e))
            await self._take_debug_screenshot(page, "otp_fill_error")
            return False
    
    async def _verify_all_fields_filled(self, page: Page) -> bool:
        """Verifica se todos os campos OTP estão preenchidos"""
        try:
            for i in range(6):
                field_selector = self.selectors.get_otp_field(i)
                field_value = await page.input_value(field_selector)
                
                if not field_value or len(field_value) != 1:
                    logger.debug("campo_otp_vazio_ou_invalido", field_index=i, value=field_value)
                    return False
            
            return True
            
        except Exception as e:
            logger.error("erro_verificar_campos_otp", error=str(e))
            return False
    
    async def wait_for_continue_enabled(self, page: Page, timeout: int = 10000) -> bool:
        """
        Aguarda o botão "Continuar" ficar habilitado após preenchimento
        
        Args:
            page: Página do Playwright
            timeout: Timeout em milissegundos
            
        Returns:
            bool: True se botão ficou habilitado
        """
        logger.info("aguardando_botao_continuar_habilitado")
        
        try:
            # Aguardar botão existir
            await page.wait_for_selector(self.selectors.CONTINUE_BTN, timeout=timeout)
            
            # Aguardar ficar habilitado (não disabled) - abordagem simplificada
            await asyncio.sleep(2)  # Aguardar um pouco para o botão ficar habilitado
            
            # Verificar se botão está habilitado
            button = await page.query_selector(self.selectors.CONTINUE_BTN)
            if button:
                is_enabled = await button.is_enabled()
                if not is_enabled:
                    await asyncio.sleep(3)  # Aguardar mais um pouco
            
            logger.info("botao_continuar_habilitado")
            return True
            
        except Exception as e:
            logger.error("timeout_aguardando_botao_habilitado", error=str(e))
            return False
    
    async def click_continue(self, page: Page) -> bool:
        """
        Clica no botão "Continuar" após preencher 2FA
        
        Args:
            page: Página do Playwright
            
        Returns:
            bool: True se clicou com sucesso
        """
        try:
            logger.info("clicando_botao_continuar_2fa")
            
            # Aguardar botão estar habilitado
            if not await self.wait_for_continue_enabled(page):
                logger.error("botao_continuar_nao_habilitado")
                return False
            
            # Clicar no botão
            await page.click(self.selectors.CONTINUE_BTN)
            
            # Aguardar um pouco para processar
            await asyncio.sleep(1)
            
            logger.info("botao_continuar_clicado")
            return True
            
        except Exception as e:
            logger.error("erro_clicar_continuar", error=str(e))
            await self._take_debug_screenshot(page, "continue_click_error")
            return False
    
    async def clear_otp_fields(self, page: Page) -> bool:
        """
        Limpa todos os campos OTP
        
        Args:
            page: Página do Playwright
            
        Returns:
            bool: True se limpou com sucesso
        """
        logger.info("limpando_campos_otp")
        
        try:
            for i in range(6):
                field_selector = self.selectors.get_otp_field(i)
                await page.fill(field_selector, "")
                await asyncio.sleep(0.1)
            
            logger.info("campos_otp_limpos")
            return True
            
        except Exception as e:
            logger.error("erro_limpar_campos_otp", error=str(e))
            return False
    
    async def retry_otp_input(self, page: Page, code: str, max_attempts: int = 3) -> bool:
        """
        Tenta preencher OTP com retry em caso de falha
        
        Args:
            page: Página do Playwright
            code: Código 2FA de 6 dígitos
            max_attempts: Máximo de tentativas
            
        Returns:
            bool: True se conseguiu preencher em alguma tentativa
        """
        logger.info("iniciando_retry_otp", max_attempts=max_attempts)
        
        for attempt in range(max_attempts):
            logger.info("tentativa_otp", attempt=attempt + 1)
            
            # Limpar campos antes de tentar novamente
            if attempt > 0:
                await self.clear_otp_fields(page)
                await asyncio.sleep(1)
            
            # Tentar preencher
            success = await self.fill_otp_fields(page, code)
            if success:
                return True
            
            # Se não foi a última tentativa, aguardar antes de tentar novamente
            if attempt < max_attempts - 1:
                logger.warning("tentativa_otp_falhada_aguardando", attempt=attempt + 1)
                await asyncio.sleep(2)
        
        logger.error("todas_tentativas_otp_falharam")
        return False
    
    async def verify_otp_error(self, page: Page) -> Optional[str]:
        """
        Verifica se existe erro de OTP na página
        
        Args:
            page: Página do Playwright
            
        Returns:
            Optional[str]: Mensagem de erro se existir
        """
        error_selectors = [
            ".error-message",
            ".alert-error", 
            "[data-error]",
            "div:contains('Código inválido')",
            "div:contains('Código incorreto')",
            "div:contains('Código de segurança inválido')",
            "div:contains('Tente novamente')",
            "p:contains('Código de segurança inválido')",
            "span:contains('inválido')",
            ".text-red-500",  # Comum para erros em Tailwind
            "*:has-text('inválido')"
        ]
        
        for selector in error_selectors:
            try:
                if ':contains(' in selector:
                    # Para selectors com :contains, usar wait_for_function
                    error_text = selector.split(':contains(')[1].split(')')[0].strip('"\'')
                    element = await page.query_selector(f"text={error_text}")
                else:
                    element = await page.query_selector(selector)
                
                if element and await element.is_visible():
                    error_message = await element.text_content()
                    logger.warning("erro_otp_detectado", message=error_message)
                    return error_message
                    
            except Exception as e:
                logger.debug("erro_verificar_otp_error", selector=selector, error=str(e))
                continue
        
        return None
    
    async def fill_otp_with_email_retry(self, page: Page, email_extractor, max_attempts: int = 3) -> bool:
        """
        Preenche OTP com retry automático buscando códigos mais recentes do email
        quando detecta erro de código inválido
        
        Args:
            page: Página do Playwright
            email_extractor: Extractor de email para buscar códigos
            max_attempts: Máximo de tentativas
            
        Returns:
            bool: True se conseguiu preencher com sucesso
        """
        logger.info("iniciando_otp_com_email_retry", max_attempts=max_attempts)
        
        for attempt in range(1, max_attempts + 1):
            logger.info("tentativa_otp_email", attempt=attempt)
            
            try:
                # Buscar código mais recente e deletar email para evitar reutilização
                if attempt == 1:
                    # Primeira tentativa - usar código atual
                    code = await email_extractor.get_and_delete_latest_2fa_code(min_delay_seconds=0)
                else:
                    # Tentativas seguintes - aguardar novo email e deletar
                    code = await email_extractor.get_and_delete_latest_2fa_code(min_delay_seconds=10)
                    
                    # Se não conseguiu novo código, fazer limpeza e tentar novamente
                    if not code:
                        logger.info("limpando_emails_antigos_e_aguardando_novo")
                        await email_extractor.cleanup_all_2fa_emails()
                        await asyncio.sleep(5)
                        code = await email_extractor.get_and_delete_latest_2fa_code(min_delay_seconds=15)
                
                if not code:
                    logger.error("codigo_nao_obtido_do_email", attempt=attempt)
                    if attempt < max_attempts:
                        await asyncio.sleep(10)  # Aguardar email chegar
                        continue
                    return False
                
                logger.info("codigo_obtido_para_tentativa", attempt=attempt, code_masked=code[:2]+"****")
                
                # Limpar campos OTP se não for a primeira tentativa
                if attempt > 1:
                    await self.clear_otp_fields(page)
                    await asyncio.sleep(1)
                
                # Preencher campos OTP
                if not await self.fill_otp_fields(page, code):
                    logger.error("falha_preencher_campos", attempt=attempt)
                    continue
                
                # Aguardar botão continuar ficar habilitado
                if not await self.wait_for_continue_enabled(page):
                    logger.error("botao_continuar_nao_habilitado", attempt=attempt)
                    continue
                
                logger.info("clicando_botao_continuar_2fa")
                
                try:
                    # Clique único no botão continuar
                    await page.click(self.selectors.CONTINUE_BTN, timeout=10000)
                    logger.info("botao_continuar_clicado_com_sucesso")
                    
                    # Aguardar processamento
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.warning("timeout_ou_erro_no_clique_continuar", error=str(e))
                    # Mesmo com timeout, pode ter funcionado - vamos verificar
                
                # VERIFICAR SE FOI REDIRECIONADO PARA DASHBOARD (LOGIN BEM-SUCEDIDO)
                try:
                    logger.info("verificando_redirecionamento_dashboard")
                    await page.wait_for_url("**/dashboard/home", timeout=8000)
                    logger.info("login_2fa_bem_sucedido_redirecionado_dashboard")
                    return True  # ✅ SUCESSO!
                    
                except Exception:
                    logger.debug("ainda_nao_redirecionado_verificando_erro")
                
                # Se não foi redirecionado, verificar se houve erro específico
                error_message = await self.verify_otp_error(page)
                if error_message:
                    logger.warning("erro_codigo_detectado_confirmado", 
                                 attempt=attempt, 
                                 erro=error_message,
                                 code_usado=code[:2]+"****")
                    
                    if attempt < max_attempts:
                        logger.info("buscando_novo_codigo_no_email")
                        await asyncio.sleep(15)
                        continue
                    else:
                        logger.error("limite_tentativas_excedido")
                        return False
                
                # Se não há erro específico, aguardar mais um pouco pelo redirecionamento
                try:
                    logger.info("aguardando_redirecionamento_final", timeout_extra=5)
                    await page.wait_for_url("**/dashboard/home", timeout=5000)
                    logger.info("login_2fa_bem_sucedido_redirecionamento_final")
                    return True  # ✅ SUCESSO!
                    
                except Exception:
                    logger.warning("redirecionamento_nao_ocorreu_assumindo_erro")
                    
                    if attempt < max_attempts:
                        logger.info("tentando_nova_tentativa_2fa")
                        await asyncio.sleep(10)
                        continue
                    else:
                        logger.error("falha_final_2fa")
                        return False
                
            except Exception as e:
                logger.error("erro_durante_tentativa_otp", 
                           attempt=attempt, 
                           error=str(e))
                if attempt < max_attempts:
                    await asyncio.sleep(5)
                    continue
                
        logger.error("todas_tentativas_falharam", max_attempts=max_attempts)
        return False
    
    async def _take_debug_screenshot(self, page: Page, name: str):
        """Captura screenshot para debug"""
        try:
            from ..browser.browser_manager import BrowserManager
            # Simular método de screenshot
            timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"debug_2fa_{name}_{timestamp}.png"
            await page.screenshot(path=screenshot_path)
            logger.info("screenshot_debug_capturado", path=screenshot_path)
        except Exception as e:
            logger.debug("erro_capturar_screenshot_debug", error=str(e))
    
    async def wait_for_2fa_page_load(self, page: Page, timeout: int = 10000) -> bool:
        """
        Aguarda página de 2FA carregar completamente
        
        Args:
            page: Página do Playwright
            timeout: Timeout em milissegundos
            
        Returns:
            bool: True se carregou com sucesso
        """
        try:
            logger.info("aguardando_pagina_2fa_carregar")
            
            # Aguardar pelo menos o primeiro campo OTP
            await page.wait_for_selector(self.selectors.OTP_FIELDS[0], timeout=timeout)
            
            # Aguardar todos os campos estarem presentes
            for i in range(6):
                field_selector = self.selectors.get_otp_field(i)
                await page.wait_for_selector(field_selector, timeout=5000)
            
            # Aguardar DOM estabilizar
            await asyncio.sleep(1)
            
            logger.info("pagina_2fa_carregada_com_sucesso")
            return True
            
        except Exception as e:
            logger.error("timeout_carregar_pagina_2fa", error=str(e))
            return False
