"""
Extrator de códigos 2FA do email (Gmail IMAP)
"""

import imaplib
import email
import re
import asyncio
import time
from typing import Optional, List
import structlog
from email.mime.text import MIMEText
from email.header import decode_header

from ..config.settings import settings

logger = structlog.get_logger(__name__)

class EmailCodeExtractor:
    """Extrator de códigos 2FA do Gmail via IMAP"""
    
    def __init__(self, email_address: str, email_password: str, imap_server: str = "imap.gmail.com"):
        self.email_address = email_address
        self.email_password = email_password
        self.imap_server = imap_server
        self.connection: Optional[imaplib.IMAP4_SSL] = None
        self.connected = False
        
    async def connect(self) -> bool:
        """
        Conecta ao servidor IMAP do Gmail
        
        Returns:
            bool: True se conectou com sucesso
        """
        try:
            logger.info("conectando_imap", server=self.imap_server, email=self.email_address)
            
            # Executar conexão em thread separada para não bloquear
            loop = asyncio.get_event_loop()
            self.connection = await loop.run_in_executor(
                None, 
                lambda: imaplib.IMAP4_SSL(self.imap_server)
            )
            
            # Login
            await loop.run_in_executor(
                None,
                self.connection.login,
                self.email_address,
                self.email_password
            )
            
            # Selecionar inbox
            await loop.run_in_executor(
                None,
                self.connection.select,
                "INBOX"
            )
            
            self.connected = True
            logger.info("conexao_imap_estabelecida")
            return True
            
        except Exception as e:
            logger.error("erro_conexao_imap", error=str(e))
            await self.disconnect()
            return False
    
    async def wait_for_2fa_code(self, timeout_minutes: int = 3) -> Optional[str]:
        """
        Aguarda e extrai código 2FA do email do Resolve CenProt
        
        Args:
            timeout_minutes: Timeout em minutos para aguardar o email
            
        Returns:
            Optional[str]: Código 2FA de 6 dígitos ou None se não encontrado
        """
        if not self.connected:
            if not await self.connect():
                return None
        
        logger.info("aguardando_codigo_2fa", timeout_minutes=timeout_minutes)
        
        timeout_seconds = timeout_minutes * 60
        start_time = time.time()
        check_interval = 5  # Verificar a cada 5 segundos
        
        # Padrões para identificar emails do Resolve CenProt
        sender_patterns = [
            "noreply@resolve.cenprot.org.br"
        ]
        
        # Padrões para extrair código 2FA baseado na estrutura real do email
        code_patterns = [
            # Padrão mais específico para o código na fonte grande
            r'font-size:50px[^>]*>\s*([A-Z0-9]{6})\s*<',  # Código em fonte de 50px
            r'<p[^>]*font-size:50px[^>]*>\s*([A-Z0-9]{6})\s*</p>',  # Código em parágrafo com fonte 50px
            
            # Padrão para o texto "Seu código de verificação é: XXXXXX"
            r'código de verificação é:\s*([A-Z0-9]{6})',
            r'verificação é:\s*([A-Z0-9]{6})',
            
            # Padrão genérico para códigos em tags HTML
            r'>\s*([A-Z0-9]{6})\s*<',  # Código entre tags HTML com espaços opcionais
            
            # Padrões de fallback
            r'\b([A-Z0-9]{6})\b',  # 6 caracteres alfanuméricos isolados
            r'código.*?([A-Z0-9]{6})',  # "código" seguido de 6 caracteres
            r'verificação.*?([A-Z0-9]{6})',  # "verificação" seguido de 6 caracteres
            
            # Para códigos separados (caso existam)
            r'([A-Z0-9]{3})[^\w]([A-Z0-9]{3})',  # 3 caracteres + separador + 3 caracteres
        ]
        
        while (time.time() - start_time) < timeout_seconds:
            try:
                # Buscar emails não lidos primeiro, depois recentes (últimos 10 minutos)  
                search_criteria_unread = 'UNSEEN'
                search_criteria_recent = '(SINCE "' + time.strftime('%d-%b-%Y', time.gmtime(time.time() - 600)) + '")'
                
                loop = asyncio.get_event_loop()
                
                # Tentar emails não lidos primeiro
                result, messages = await loop.run_in_executor(
                    None,
                    self.connection.search,
                    None,
                    search_criteria_unread
                )
                
                message_ids = []
                
                # Se há emails não lidos, priorizá-los
                if result == 'OK' and messages[0]:
                    unread_ids = messages[0].split()
                    logger.info("emails_nao_lidos_encontrados", count=len(unread_ids))
                    message_ids.extend(reversed(unread_ids))  # Mais recentes primeiro
                
                # Complementar com emails recentes se necessário
                if len(message_ids) < 5:
                    result, messages = await loop.run_in_executor(
                        None,
                        self.connection.search,
                        None,
                        search_criteria_recent
                    )
                    
                    if result == 'OK' and messages[0]:
                        recent_ids = messages[0].split()
                        # Adicionar apenas os que não estão já na lista
                        for recent_id in reversed(recent_ids[-10:]):
                            if recent_id not in message_ids:
                                message_ids.append(recent_id)
                
                logger.info("total_emails_para_verificar", count=len(message_ids))
                
                if message_ids:
                    # Verificar emails (já ordenados por prioridade)
                    for msg_id in message_ids[:15]:  # Máximo 15 emails
                        try:
                            # Buscar email
                            result, msg_data = await loop.run_in_executor(
                                None,
                                self.connection.fetch,
                                msg_id,
                                '(RFC822)'
                            )
                            
                            if result != 'OK':
                                continue
                            
                            # Parse do email
                            email_body = msg_data[0][1]
                            email_message = email.message_from_bytes(email_body)
                            
                            # Verificar remetente com decodificação adequada
                            sender_raw = email_message['From'] or ""
                            subject_raw = email_message['Subject'] or ""
                            sender = self._decode_email_header(sender_raw)
                            subject = self._decode_email_header(subject_raw)
                            
                            logger.info("verificando_email", 
                                       msg_id=msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id),
                                       sender=sender[:50], 
                                       subject=subject[:50])
                            
                            # Verificar se é do Resolve/CenProt (mais flexível)
                            is_resolve_email = (
                                any(pattern in sender.lower() for pattern in sender_patterns) or
                                any(pattern in subject.lower() for pattern in ["resolve", "cenprot", "verificação", "código"])
                            )
                            
                            if not is_resolve_email:
                                logger.debug("email_ignorado", sender=sender[:30])
                                continue
                            
                            logger.info("email_resolve_encontrado", sender=sender[:50])
                            
                            # Extrair conteúdo do email
                            email_content = await self._extract_email_content(email_message)
                            
                            # Log do conteúdo para debug (apenas uma parte)
                            logger.info("conteudo_email_extraido", 
                                       content_length=len(email_content),
                                       content_preview=email_content[:200].replace('\n', ' '))
                            
                            # Procurar código 2FA no conteúdo
                            code = self._extract_2fa_code(email_content, code_patterns)
                            
                            if code:
                                logger.info("codigo_2fa_encontrado", code=code[:3] + "***", full_code=code)
                                return code
                            else:
                                logger.warning("codigo_nao_encontrado_neste_email", 
                                             sender=sender[:30], 
                                             content_sample=email_content[:100].replace('\n', ' '))
                        
                        except Exception as e:
                            logger.debug("erro_processar_email", msg_id=msg_id, error=str(e))
                            continue
                
                # Aguardar antes da próxima verificação
                logger.debug("codigo_nao_encontrado_aguardando", 
                           elapsed=int(time.time() - start_time),
                           remaining=int(timeout_seconds - (time.time() - start_time)))
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error("erro_busca_emails", error=str(e))
                await asyncio.sleep(check_interval)
        
        logger.warning("timeout_aguardando_codigo_2fa", timeout_minutes=timeout_minutes)
        return None
    
    async def _extract_email_content(self, email_message) -> str:
        """Extrai conteúdo textual do email"""
        content = ""
        
        try:
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    if content_type in ["text/plain", "text/html"]:
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                content += payload.decode('utf-8', errors='ignore')
                        except:
                            continue
            else:
                payload = email_message.get_payload(decode=True)
                if payload:
                    content = payload.decode('utf-8', errors='ignore')
        
        except Exception as e:
            logger.debug("erro_extrair_conteudo_email", error=str(e))
        
        return content
    
    def _extract_2fa_code(self, content: str, patterns: List[str]) -> Optional[str]:
        """
        Extrai código 2FA do conteúdo usando método específico do Resolve CenProt primeiro,
        depois usa padrões regex como fallback
        """
        logger.info("iniciando_extracao_codigo_2fa", content_length=len(content))
        
        # 1️⃣ PRIMEIRO: Tentar método específico do Resolve CenProt
        code = self._extract_2fa_code_resolve_specific(content)
        if code:
            logger.info("codigo_extraido_metodo_especifico", codigo_masked=code[:2]+"****")
            return code
        
        # 2️⃣ FALLBACK: Usar padrões regex tradicionais
        logger.info("usando_padroes_fallback", patterns_count=len(patterns))
        
        content_clean = re.sub(r'\s+', ' ', content.lower())
        content_original = content  # Manter original para alguns padrões
        
        for i, pattern in enumerate(patterns):
            try:
                # Testar no conteúdo limpo
                matches = re.findall(pattern, content_clean, re.IGNORECASE)
                
                # Se não encontrou no limpo, testar no original
                if not matches:
                    matches = re.findall(pattern, content_original, re.IGNORECASE)
                
                logger.debug("pattern_testado_fallback", 
                           pattern_index=i, 
                           pattern=pattern[:30], 
                           matches_found=len(matches))
                
                for match in matches:
                    if isinstance(match, tuple):
                        # Para padrão com grupos - juntar os grupos
                        code = ''.join(str(group) for group in match if group)
                    else:
                        code = str(match)
                    
                    # Limpar e validar o código
                    code_clean = re.sub(r'[^A-Z0-9]', '', code.upper().strip())
                    
                    # Validar se é um código de 6 caracteres alfanuméricos
                    if len(code_clean) == 6 and re.match(r'^[A-Z0-9]{6}$', code_clean):
                        # Verificar se não é uma palavra comum (evitar "OFFICE", etc.)
                        excluded_words = ['OFFICE', 'EMAILS', 'MAILTO', 'BRASIL', 'CENTRO', 'WWWCEN']
                        if code_clean not in excluded_words:
                            logger.info("codigo_extraido_fallback", 
                                      pattern_used=pattern[:20],
                                      final_code_masked=code_clean[:2]+"****")
                            return code_clean
            
            except Exception as e:
                logger.debug("erro_pattern_2fa", pattern=pattern[:20], error=str(e))
                continue
        
        logger.warning("nenhum_codigo_encontrado_todos_metodos")
        return None
    
    async def disconnect(self):
        """Desconecta do servidor IMAP"""
        if self.connection and self.connected:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.connection.close)
                await loop.run_in_executor(None, self.connection.logout)
                logger.info("conexao_imap_encerrada")
            except Exception as e:
                logger.debug("erro_desconectar_imap", error=str(e))
            finally:
                self.connection = None
                self.connected = False
    
    async def test_connection(self) -> bool:
        """
        Testa conexão com o servidor de email
        
        Returns:
            bool: True se conexão está funcionando
        """
        logger.info("testando_conexao_email")
        
        if await self.connect():
            try:
                # Tentar buscar 1 email para validar acesso
                loop = asyncio.get_event_loop()
                result, messages = await loop.run_in_executor(
                    None,
                    self.connection.search,
                    None,
                    "ALL"
                )
                
                success = result == 'OK'
                logger.info("teste_conexao_email", success=success)
                return success
                
            except Exception as e:
                logger.error("erro_teste_conexao", error=str(e))
                return False
            finally:
                await self.disconnect()
        
        return False
    
    async def delete_email(self, msg_id: str) -> bool:
        """
        Deleta um email específico do servidor
        
        Args:
            msg_id: ID da mensagem para deletar
            
        Returns:
            bool: True se deletado com sucesso
        """
        try:
            if not self.connection:
                await self.connect()
                
            loop = asyncio.get_event_loop()
            
            # Marcar como deletado
            await loop.run_in_executor(
                None,
                self.connection.store,
                msg_id,
                '+FLAGS',
                '\\Deleted'
            )
            
            # Expurgar mensagens marcadas como deletadas
            await loop.run_in_executor(
                None,
                self.connection.expunge
            )
            
            logger.info("email_deletado_com_sucesso", msg_id=msg_id)
            return True
            
        except Exception as e:
            logger.error("erro_deletar_email", msg_id=msg_id, error=str(e))
            return False
    
    async def wait_for_new_2fa_email_simple(self, timeout_seconds: int = 30) -> Optional[str]:
        """
        Versão SIMPLIFICADA que aguarda email novo 2FA
        """
        logger.info("aguardando_novo_email_2fa_simplificado", timeout_seconds=timeout_seconds)
        
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            try:
                # Reconectar para emails frescos
                await self.disconnect()
                await self.connect()
                
                loop = asyncio.get_event_loop()
                
                # Buscar TODOS os emails para garantir que não perdemos nenhum
                result, messages = await loop.run_in_executor(
                    None,
                    self.connection.search,
                    None,
                    'ALL'
                )
                
                if result == 'OK' and messages[0]:
                    message_ids = messages[0].split()
                    
                    # Verificar os 3 emails mais recentes
                    recent_ids = message_ids[-3:] if len(message_ids) > 3 else message_ids
                    
                    for msg_id in reversed(recent_ids):  # Mais recente primeiro
                        try:
                            # Buscar email
                            status, msg_data = await loop.run_in_executor(
                                None,
                                self.connection.fetch,
                                msg_id,
                                '(RFC822)'
                            )
                            
                            if status != 'OK':
                                continue
                            
                            import email as email_module
                            email_message = email_module.message_from_bytes(msg_data[0][1])
                            
                            # Verificar se é do CenProt
                            sender_raw = email_message['From'] or ''
                            sender = self._decode_email_header(sender_raw)
                            
                            logger.info("verificando_email_encontrado", 
                                       msg_id=msg_id,
                                       sender=sender[:50])
                            
                            if not any(pattern in sender.lower() for pattern in ['resolve.cenprot', 'noreply@re', 'cenprot']):
                                logger.debug("email_nao_e_do_cenprot", sender=sender[:30])
                                continue
                            
                            logger.info("email_cenprot_encontrado_processando", msg_id=msg_id)
                            
                            # Extrair código
                            email_content = await self._extract_email_content(email_message)
                            
                            logger.info("conteudo_extraido_testando_codigo", 
                                       content_length=len(email_content),
                                       preview=email_content[:100])
                            
                            code = self._extract_2fa_code(email_content, self._get_2fa_patterns())
                            
                            if code:
                                logger.info("CODIGO_2FA_EXTRAIDO_COM_SUCESSO", 
                                           codigo_masked=code[:2]+"****",
                                           msg_id=msg_id)
                                
                                # Deletar email após sucesso
                                await self.delete_email(msg_id)
                                return code
                            else:
                                logger.warning("codigo_nao_extraido_deste_email", msg_id=msg_id)
                                
                        except Exception as e:
                            logger.debug("erro_processar_email_msg", msg_id=msg_id, error=str(e))
                            continue
                
                # Aguardar 3 segundos antes da próxima tentativa
                logger.debug("aguardando_3s_nova_tentativa")
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error("erro_aguardar_email_geral", error=str(e))
                await asyncio.sleep(5)
        
        logger.warning("timeout_email_2fa_nao_recebido", timeout_seconds=timeout_seconds)
        return None

    async def get_and_delete_latest_2fa_code(self, min_delay_seconds: int = 0) -> Optional[str]:
        """
        VERSÃO MELHORADA: Aguarda por email NOVO ao invés de processar emails antigos
        """
        logger.warning("USANDO_VERSAO_MELHORADA_aguarda_email_novo")
        
        if min_delay_seconds > 0:
            logger.info("aguardando_antes_buscar_email", seconds=min_delay_seconds)
            await asyncio.sleep(min_delay_seconds)
        
        # Aguardar especificamente por email novo (versão simplificada)
        code = await self.wait_for_new_2fa_email_simple(timeout_seconds=30)
        
        if code:
            logger.info("codigo_obtido_do_email_novo", code_masked=code[:2]+"****")
            return code
        else:
            logger.error("codigo_nao_obtido_email_novo")
            return None
    
    async def get_and_delete_latest_2fa_code_OLD_BUGGY(self, min_delay_seconds: int = 0) -> Optional[str]:
        """
        Busca o código 2FA mais recente e deleta o email para evitar reutilização
        
        Args:
            min_delay_seconds: Aguardar antes de buscar (para novos emails)
            
        Returns:
            Optional[str]: Código 2FA mais recente se encontrado
        """
        if min_delay_seconds > 0:
            logger.info("aguardando_novo_email", seconds=min_delay_seconds)
            await asyncio.sleep(min_delay_seconds)
        
        try:
            # Sempre reconectar para garantir emails mais recentes
            logger.info("reconectando_para_buscar_email_mais_recente")
            await self.disconnect()
            await self.connect()
            
            # Buscar emails não lidos primeiro
            search_criteria = 'UNSEEN'
            
            loop = asyncio.get_event_loop()
            result, messages = await loop.run_in_executor(
                None,
                self.connection.search,
                None,
                search_criteria
            )
            
            if result != 'OK' or not messages[0]:
                logger.info("nenhum_email_nao_lido_buscando_recentes")
                # Buscar emails recentes dos últimos 30 minutos
                search_criteria = '(SINCE "' + time.strftime('%d-%b-%Y', time.gmtime(time.time() - 1800)) + '")'
                result, messages = await loop.run_in_executor(
                    None,
                    self.connection.search,
                    None,
                    search_criteria
                )
            
            if result == 'OK' and messages[0]:
                message_ids = messages[0].split()
                
                # Verificar emails mais recentes primeiro
                recent_ids = message_ids[-2:] if len(message_ids) > 2 else message_ids
                
                for msg_id in reversed(recent_ids):  # Mais recente primeiro
                    try:
                        # Buscar email
                        status, msg_data = await loop.run_in_executor(
                            None,
                            self.connection.fetch,
                            msg_id,
                            '(RFC822)'
                        )
                        
                        if status != 'OK':
                            continue
                        
                        email_message = email.message_from_bytes(msg_data[0][1])
                        
                        # Verificar se é do resolve.cenprot com decodificação
                        sender_raw = email_message['From'] or ''
                        subject_raw = email_message['Subject'] or ''
                        sender = self._decode_email_header(sender_raw)
                        subject = self._decode_email_header(subject_raw)
                        
                        logger.info("verificando_email_detalhado", 
                                   msg_id=msg_id,
                                   sender_raw=sender_raw[:50],
                                   sender_decoded=sender[:50],
                                   subject=subject[:50])
                        
                        if not any(pattern in sender.lower() for pattern in ['resolve.cenprot', 'noreply@re', 'cenprot']):
                            logger.debug("email_nao_e_do_cenprot", sender_decoded=sender[:50])
                            continue
                        
                        logger.info("email_do_cenprot_encontrado", msg_id=msg_id)
                        
                        # Extrair conteúdo do email
                        try:
                            email_content = await self._extract_email_content(email_message)
                            logger.info("conteudo_email_extraido", 
                                       content_length=len(email_content),
                                       preview=email_content[:200])
                            
                            # Tentar extrair código com debug detalhado
                            patterns = self._get_2fa_patterns()
                            logger.info("tentando_extrair_codigo", total_patterns=len(patterns))
                            
                            code = self._extract_2fa_code(email_content, patterns)
                            
                            if code:
                                logger.info("codigo_extraido_com_sucesso", 
                                           code_masked=code[:2]+"****",
                                           code_length=len(code),
                                           msg_id=msg_id)
                                
                                # ✅ DELETAR EMAIL APÓS EXTRAIR CÓDIGO
                                delete_success = await self.delete_email(msg_id)
                                logger.info("email_deletado_apos_extracao", 
                                           msg_id=msg_id, 
                                           delete_success=delete_success)
                                
                                return code
                            else:
                                logger.warning("codigo_nao_encontrado_no_email", 
                                             msg_id=msg_id,
                                             content_preview=email_content[:300])
                        
                        except Exception as extract_error:
                            logger.error("erro_extrair_codigo_do_email", 
                                        msg_id=msg_id, 
                                        error=str(extract_error))
                        
                    except Exception as e:
                        logger.debug("erro_processar_email", msg_id=msg_id, error=str(e))
                        continue
            
            logger.warning("nenhum_codigo_2fa_encontrado")
            return None
            
        except Exception as e:
            logger.error("erro_buscar_e_deletar_codigo", error=str(e))
            return None

    def _extract_2fa_code_resolve_specific(self, content: str) -> Optional[str]:
        """
        Extrai código 2FA usando a estrutura específica do email do Resolve CenProt
        Busca o código entre as strings específicas identificadas pelo usuário
        """
        if not content:
            return None
            
        try:
            # Textos específicos do email do Resolve CenProt
            start_text = "Seu código de verificação chegou."
            end_text = "Este código é único e de uso exclusivo para validar seu acesso à Resolve. Nunca o compartilhe com terceiros."
            
            # Encontrar TODAS as posições do texto de início
            import re
            start_matches = []
            for match in re.finditer(re.escape(start_text), content):
                start_matches.append(match.end())
            
            end_pos = content.find(end_text)
            
            if not start_matches or end_pos == -1:
                logger.debug("textos_especificos_nao_encontrados", 
                           start_matches_found=len(start_matches), 
                           end_found=end_pos != -1)
                return None
            
            logger.debug("posicoes_encontradas", 
                        start_positions=start_matches, 
                        end_position=end_pos)
            
            # Usar a última ocorrência do texto de início (mais próxima do código)
            start_pos = start_matches[-1]
            code_section = content[start_pos:end_pos].strip()
            
            logger.info("secao_codigo_extraida", 
                       secao_length=len(code_section),
                       preview=code_section[:100])
            
            # Buscar código de 6 caracteres alfanuméricos na seção
            import re
            code_patterns = [
                r'\b([A-Z0-9]{6})\b',      # Código alfanumérico de 6 caracteres
                r'>\s*([A-Z0-9]{6})\s*<',  # Entre tags HTML
                r'([A-Z0-9]{6})',          # Qualquer sequência de 6 caracteres alfanuméricos
            ]
            
            for pattern in code_patterns:
                matches = re.findall(pattern, code_section, re.IGNORECASE)
                for match in matches:
                    code = match.upper().strip()
                    if len(code) == 6 and re.match(r'^[A-Z0-9]{6}$', code):
                        logger.info("codigo_2fa_extraido_com_sucesso", codigo=code)
                        return code
            
            logger.warning("codigo_nao_encontrado_na_secao", secao=code_section[:200])
            return None
            
        except Exception as e:
            logger.error("erro_extrair_codigo_resolve_specific", error=str(e))
            return None

    def _get_2fa_patterns(self) -> List[str]:
        """
        Padrões de fallback caso a extração específica falhe
        """
        return [
            # Padrão mais específico para o código na fonte grande
            r'font-size:50px[^>]*>\s*([A-Z0-9]{6})\s*<',  # Código em fonte de 50px
            
            # Padrões gerais para códigos 2FA
            r'>\s*([A-Z0-9]{6})\s*<',  # Código entre tags HTML
            r'\b([A-Z0-9]{6})\b',      # Código alfanumérico de 6 caracteres
            r'código[:\s]*([A-Z0-9]{6})',    # "código: ABC123"
            r'verificação[:\s]*([A-Z0-9]{6})', # "código de verificação: ABC123"
            r'acesso[:\s]*([A-Z0-9]{6})',     # "código de acesso: ABC123"
            
            # Padrões para códigos apenas numéricos (fallback)
            r'\b(\d{6})\b',            # 6 dígitos
            r'código[:\s]*(\d{6})',    # "código: 123456"
        ]

    def _decode_email_header(self, header_value: str) -> str:
        """
        Decodifica headers de email que podem estar em diferentes encodings
        """
        if not header_value:
            return ""
            
        try:
            # Decodificar header usando email.header.decode_header
            import email.header
            decoded_parts = email.header.decode_header(header_value)
            decoded_string = ""
            
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    # Se tem encoding específico, usar ele
                    if encoding:
                        decoded_string += part.decode(encoding, errors='ignore')
                    else:
                        # Tentar UTF-8 primeiro, depois ISO-8859-1
                        try:
                            decoded_string += part.decode('utf-8')
                        except UnicodeDecodeError:
                            decoded_string += part.decode('iso-8859-1', errors='ignore')
                else:
                    decoded_string += str(part)
            
            return decoded_string.strip()
            
        except Exception as e:
            logger.debug("erro_decodificar_header", header=header_value[:50], error=str(e))
            return str(header_value)

    async def get_most_recent_2fa_code(self, force_refresh: bool = False, min_delay_seconds: int = 0) -> Optional[str]:
        """
        Busca o código 2FA mais recente no email, ideal para retry após erro
        
        Args:
            force_refresh: Se deve reconectar para buscar emails mais novos
            min_delay_seconds: Aguardar antes de buscar (para novos emails)
            
        Returns:
            Optional[str]: Código 2FA mais recente se encontrado
        """
        if min_delay_seconds > 0:
            logger.info("aguardando_novo_email", seconds=min_delay_seconds)
            await asyncio.sleep(min_delay_seconds)
        
        try:
            if force_refresh or not self.connection:
                logger.info("reconectando_para_buscar_emails_mais_recentes")
                await self.disconnect()
                await self.connect()
            
            # Buscar apenas emails não lidos primeiro (mais eficiente)
            search_criteria = 'UNSEEN'
            
            loop = asyncio.get_event_loop()
            result, messages = await loop.run_in_executor(
                None,
                self.connection.search,
                None,
                search_criteria
            )
            
            if result != 'OK' or not messages[0]:
                logger.info("nenhum_email_nao_lido_buscando_recentes")
                # Se não há emails não lidos, buscar os mais recentes
                search_criteria = '(SINCE "' + time.strftime('%d-%b-%Y', time.gmtime(time.time() - 1800)) + '")'
                result, messages = await loop.run_in_executor(
                    None,
                    self.connection.search,
                    None,
                    search_criteria
                )
            
            if result == 'OK' and messages[0]:
                message_ids = messages[0].split()
                
                # Verificar apenas os emails mais recentes (últimos 3)
                recent_ids = message_ids[-3:] if len(message_ids) > 3 else message_ids
                
                for msg_id in reversed(recent_ids):  # Mais recente primeiro
                    try:
                        # Buscar email
                        status, msg_data = await loop.run_in_executor(
                            None,
                            self.connection.fetch,
                            msg_id,
                            '(RFC822)'
                        )
                        
                        if status != 'OK':
                            continue
                        
                        email_message = email.message_from_bytes(msg_data[0][1])
                        
                        # Verificar remetente com decodificação adequada
                        sender_raw = email_message['From'] or ''
                        sender = self._decode_email_header(sender_raw)
                        
                        logger.info("verificando_email_mais_recente", 
                                   msg_id=msg_id,
                                   sender_raw=sender_raw[:50],
                                   sender_decoded=sender[:50])
                        
                        if not any(pattern in sender.lower() for pattern in ['resolve.cenprot', 'noreply@re', 'cenprot']):
                            logger.debug("email_nao_e_do_cenprot", sender_decoded=sender[:50])
                            continue
                        
                        # Extrair código
                        email_content = await self._extract_email_content(email_message)
                        code = self._extract_2fa_code(email_content, self._get_2fa_patterns())
                        
                        if code:
                            logger.info("codigo_mais_recente_encontrado", 
                                       code_masked=code[:2]+"****",
                                       msg_id=msg_id)
                            return code
                        
                    except Exception as e:
                        logger.debug("erro_processar_email_recente", msg_id=msg_id, error=str(e))
                        continue
            
            logger.warning("nenhum_codigo_encontrado_em_emails_recentes")
            return None
            
        except Exception as e:
            logger.error("erro_buscar_codigo_mais_recente", error=str(e))
            return None

    async def cleanup_all_2fa_emails(self) -> int:
        """
        Remove todos os emails de 2FA para garantir limpeza completa
        
        Returns:
            int: Número de emails deletados
        """
        try:
            logger.info("iniciando_limpeza_completa_emails_2fa")
            
            if not self.connection:
                await self.connect()
            
            # Buscar todos os emails dos últimos 3 dias
            search_criteria = '(SINCE "' + time.strftime('%d-%b-%Y', time.gmtime(time.time() - 259200)) + '")'
            
            loop = asyncio.get_event_loop()
            result, messages = await loop.run_in_executor(
                None,
                self.connection.search,
                None,
                search_criteria
            )
            
            deleted_count = 0
            
            if result == 'OK' and messages[0]:
                message_ids = messages[0].split()
                
                for msg_id in message_ids:
                    try:
                        # Buscar email
                        status, msg_data = await loop.run_in_executor(
                            None,
                            self.connection.fetch,
                            msg_id,
                            '(RFC822)'
                        )
                        
                        if status != 'OK':
                            continue
                        
                        email_message = email.message_from_bytes(msg_data[0][1])
                        
                        # Verificar se é email do resolve.cenprot com decodificação
                        sender_raw = email_message['From'] or ''
                        subject_raw = email_message['Subject'] or ''
                        sender = self._decode_email_header(sender_raw)
                        subject = self._decode_email_header(subject_raw)
                        
                        if (any(pattern in sender.lower() for pattern in ['resolve.cenprot', 'noreply@re', 'cenprot']) or
                            any(pattern in subject.lower() for pattern in ['código', 'codigo', 'acesso', '2fa'])):
                            
                            # Deletar email
                            if await self.delete_email(msg_id):
                                deleted_count += 1
                        
                    except Exception as e:
                        logger.debug("erro_processar_email_limpeza", msg_id=msg_id, error=str(e))
                        continue
            
            logger.info("limpeza_emails_concluida", emails_deletados=deleted_count)
            return deleted_count
            
        except Exception as e:
            logger.error("erro_limpeza_completa_emails", error=str(e))
            return 0

    def __del__(self):
        """Cleanup automático"""
        if self.connected:
            logger.warning("conexao_email_nao_fechada_adequadamente")

# Função utilitária para validação de configurações de email
async def validate_email_config(email: str, password: str, server: str = "imap.gmail.com") -> bool:
    """
    Valida configurações de email
    
    Args:
        email: Endereço de email
        password: Senha ou app password
        server: Servidor IMAP
        
    Returns:
        bool: True se configurações são válidas
    """
    if not all([email, password]):
        logger.error("credenciais_email_incompletas")
        return False
    
    if "@" not in email:
        logger.error("email_invalido", email=email)
        return False
    
    extractor = EmailCodeExtractor(email, password, server)
    try:
        return await extractor.test_connection()
    finally:
        await extractor.disconnect()
