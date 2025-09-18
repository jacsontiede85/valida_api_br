"""
Cliente HTTP para API oficial do Resolve CenProt
Implementa fluxo de autenticação 2FA e consultas de CNPJ
"""

import httpx
import asyncio
from typing import Optional, Dict, Any
import structlog
from datetime import datetime, timedelta
import json

from ..config.settings import settings
from ..models.api_oficial_models import ApiTokenResponse, ApiProtestsResponse, ApiOficialMapper
from ..models.protest_models import ConsultaCNPJResult
from .email_extractor import EmailCodeExtractor

logger = structlog.get_logger(__name__)


class ApiOficialClient:
    """Cliente para API oficial do Resolve CenProt com padrão Singleton"""
    
    _instance: Optional['ApiOficialClient'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'ApiOficialClient':
        """Implementa padrão Singleton para reutilizar token JWT entre consultas"""
        if cls._instance is None:
            cls._instance = super(ApiOficialClient, cls).__new__(cls)
            logger.info("nova_instancia_singleton_api_oficial_criada")
        else:
            logger.info("reutilizando_instancia_singleton_api_oficial")
        return cls._instance
    
    def __init__(self):
        # Evitar reinicialização se já foi inicializado
        if ApiOficialClient._initialized:
            return
            
        self.base_url = settings.RESOLVE_CENPROT_API_BASE_URL
        self.login = settings.RESOLVE_CENPROT_LOGIN
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.email_extractor = EmailCodeExtractor(
            email_address=settings.RESOLVE_EMAIL,
            email_password=settings.RESOLVE_EMAIL_PASSWORD,
            imap_server=settings.RESOLVE_IMAP_SERVER
        )
        
        # HTTP client singleton para evitar fechamento prematuro
        self._client = None
        
        # Marcar como inicializado
        ApiOficialClient._initialized = True
        logger.info("singleton_api_oficial_inicializado")
    
    @property
    async def client(self) -> httpx.AsyncClient:
        """Obtém cliente HTTP singleton"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._client
    
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        await self.email_extractor.disconnect()
        
    async def close(self):
        """Fecha o cliente HTTP e desconecta do email"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        await self.email_extractor.disconnect()
    
    def _is_token_expired(self) -> bool:
        """Verifica se o token atual expirou"""
        if not self.access_token or not self.token_expires_at:
            return True
        return datetime.now() >= self.token_expires_at
    
    async def _generate_2fa_token(self) -> bool:
        """
        Passo 1: Gerar token 2FA e enviar para email
        
        Returns:
            bool: True se token foi gerado com sucesso
        """
        try:
            logger.info("gerando_token_2fa", login=self.login[:8] + "****")
            
            url = f"{self.base_url}/auth/v2/generate-token/{self.login}"
            
            # Usar cabeçalhos realísticos (sem Authorization para generate-token)
            headers = self._get_realistic_headers_no_auth()
            
            client = await self.client
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                logger.info("token_2fa_enviado_email_sucesso")
                return True
            else:
                logger.error("erro_gerar_token_2fa", 
                           status_code=response.status_code,
                           response_text=response.text)
                return False
                
        except Exception as e:
            logger.error("erro_gerar_token_2fa_exception", error=str(e))
            return False
    
    async def _extract_2fa_token_from_email(self) -> Optional[str]:
        """
        Passo 2: Extrair token 2FA do email
        
        Returns:
            str: Token 2FA extraído do email, ou None se falhou
        """
        try:
            logger.info("extraindo_token_2fa_do_email")
            
            # Aguardar um pouco para email chegar
            await asyncio.sleep(3)
            
            # Conectar ao email e extrair token 2FA
            if not await self.email_extractor.connect():
                logger.error("falha_conectar_email_para_2fa")
                return None
                
            # Usar extrator de email existente
            token_2fa = await self.email_extractor.get_most_recent_2fa_code(
                force_refresh=True,
                min_delay_seconds=3
            )
            
            if token_2fa:
                logger.info("token_2fa_extraido_email_sucesso", 
                          token_preview=token_2fa[:3] + "***")
                
                # Desconectar após extrair o token
                await self.email_extractor.disconnect()
                return token_2fa
            else:
                logger.error("token_2fa_nao_encontrado_email")
                await self.email_extractor.disconnect()
                return None
                
        except Exception as e:
            logger.error("erro_extrair_token_2fa_email", error=str(e))
            return None
    
    async def _validate_2fa_token(self, token_2fa: str) -> Optional[ApiTokenResponse]:
        """
        Passo 3: Validar token 2FA e obter JWT
        
        Args:
            token_2fa: Token 2FA extraído do email
            
        Returns:
            ApiTokenResponse: Dados do token JWT se válido
        """
        try:
            logger.info("validando_token_2fa", 
                       token_preview=token_2fa[:3] + "***",
                       login=self.login[:8] + "****")
            
            url = f"{self.base_url}/auth/v2/validate-token/user/{self.login}/{token_2fa}"
            
            # Usar cabeçalhos realísticos (sem Authorization para validate-token)
            headers = self._get_realistic_headers_no_auth()
            
            client = await self.client
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("message") == "Login efetuado com sucesso.":
                    # Salvar tokens e tempo de expiração
                    self.access_token = data["token"]
                    self.refresh_token = data["refreshToken"]
                    # JWT tokens geralmente expiram em 24h
                    self.token_expires_at = datetime.now() + timedelta(hours=23, minutes=30)
                    
                    logger.info("token_jwt_obtido_sucesso", 
                               user_name=data["user"]["name"],
                               expires_at=self.token_expires_at.strftime("%Y-%m-%d %H:%M:%S"))
                    
                    return ApiTokenResponse(
                        message=data["message"],
                        token=data["token"],
                        refreshToken=data["refreshToken"],
                        user=data["user"]
                    )
                else:
                    logger.error("resposta_inesperada_validacao", message=data.get("message"))
                    return None
            
            elif response.status_code == 400:
                # Token inválido ou expirado
                data = response.json()
                if data.get("message") == "Token inválido.":
                    logger.warning("token_2fa_invalido_ou_expirado")
                    return None
                
            logger.error("erro_validar_token_2fa", 
                       status_code=response.status_code,
                       response_text=response.text)
            return None
                
        except Exception as e:
            logger.error("erro_validar_token_2fa_exception", error=str(e))
            return None
    
    async def ensure_authenticated(self) -> bool:
        """
        Garante que temos um token JWT válido
        Executa fluxo 2FA completo se necessário
        
        Returns:
            bool: True se autenticado com sucesso
        """
        try:
            # Se token ainda é válido, não precisa refazer 2FA
            if not self._is_token_expired():
                logger.info("token_jwt_ainda_valido", 
                          expires_at=self.token_expires_at.strftime("%Y-%m-%d %H:%M:%S"))
                return True
            
            logger.info("iniciando_fluxo_2fa_completo")
            
            # Passo 1: Gerar token 2FA
            if not await self._generate_2fa_token():
                logger.error("falha_passo_1_gerar_token")
                return False
            
            # Passo 2: Aguardar e extrair token do email
            token_2fa = await self._extract_2fa_token_from_email()
            if not token_2fa:
                logger.error("falha_passo_2_extrair_email")
                return False
            
            # Passo 3: Validar token e obter JWT
            token_response = await self._validate_2fa_token(token_2fa)
            if not token_response:
                logger.error("falha_passo_3_validar_token")
                return False
            
            logger.info("fluxo_2fa_completo_sucesso", 
                       user=token_response.user["name"])
            return True
            
        except Exception as e:
            logger.error("erro_ensure_authenticated", error=str(e))
            return False
    
    async def consultar_cnpj(self, cnpj: str) -> ConsultaCNPJResult:
        """
        Passo 4: Consultar CNPJ via API oficial
        
        Args:
            cnpj: CNPJ para consultar
            
        Returns:
            ConsultaCNPJResult: Resultado da consulta compatível com sistema existente
        """
        try:
            logger.info("consultando_cnpj_api_oficial", cnpj=cnpj[:8] + "****")
            
            # Garantir autenticação
            if not await self.ensure_authenticated():
                raise Exception("Falha na autenticação 2FA")
            
            # Limpar CNPJ (remover formatação) para API oficial
            cnpj_limpo = self._clean_cnpj(cnpj)
            logger.info("cnpj_limpo_para_api", cnpj_original=cnpj[:8] + "****", cnpj_limpo=cnpj_limpo[:8] + "****")
            
            # Fazer requisição
            url = f"{self.base_url}/protests/v2/research/cenprot/{cnpj_limpo}"
            headers = self._get_realistic_headers(self.access_token)
            
            client = await self.client
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validar estrutura da resposta antes de processar
                if not isinstance(data, dict):
                    logger.error("resposta_api_oficial_nao_e_dict", 
                               cnpj=cnpj[:8] + "****",
                               data_type=type(data).__name__,
                               data_preview=str(data)[:200])
                    raise Exception(f"Resposta da API oficial não é um dicionário: {type(data).__name__}")
                
                if "protests" not in data:
                    logger.error("campo_protests_ausente_resposta_api", 
                               cnpj=cnpj[:8] + "****",
                               campos_disponiveis=list(data.keys()) if isinstance(data, dict) else "N/A")
                    raise Exception("Campo 'protests' ausente na resposta da API oficial")
                
                # Converter para modelo da API oficial
                api_response = ApiOficialMapper.from_api_dict_to_response(data)
                
                # Converter para modelo do sistema existente
                result = ApiOficialMapper.from_api_response_to_consulta_result(cnpj, api_response)
                
                logger.info("consulta_cnpj_api_oficial_sucesso", 
                          cnpj=cnpj[:8] + "****",
                          qtd_titulos=api_response.protests.qtdTitulos,
                          tem_protestos=api_response.protests.qtdTitulos > 0)
                
                return result
                
            elif response.status_code == 401:
                # Token expirado - tentar renovar uma vez
                logger.warning("token_expirado_tentando_renovar", cnpj=cnpj[:8] + "****")
                
                self.access_token = None  # Forçar novo 2FA
                
                if await self.ensure_authenticated():
                    # Retry uma vez
                    headers = self._get_realistic_headers(self.access_token)
                    client = await self.client
                    response = await client.get(url, headers=headers)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Validar estrutura da resposta antes de processar
                        if not isinstance(data, dict):
                            logger.error("resposta_api_oficial_nao_e_dict_apos_renovacao", 
                                       cnpj=cnpj[:8] + "****",
                                       data_type=type(data).__name__,
                                       data_preview=str(data)[:200])
                            raise Exception(f"Resposta da API oficial não é um dicionário após renovação: {type(data).__name__}")
                        
                        if "protests" not in data:
                            logger.error("campo_protests_ausente_resposta_api_apos_renovacao", 
                                       cnpj=cnpj[:8] + "****",
                                       campos_disponiveis=list(data.keys()) if isinstance(data, dict) else "N/A")
                            raise Exception("Campo 'protests' ausente na resposta da API oficial após renovação")
                        
                        api_response = ApiOficialMapper.from_api_dict_to_response(data)
                        result = ApiOficialMapper.from_api_response_to_consulta_result(cnpj, api_response)
                        
                        logger.info("consulta_cnpj_api_oficial_sucesso_apos_renovacao", 
                                  cnpj=cnpj[:8] + "****")
                        return result
                
                raise Exception("Unauthorized - falha na renovação do token")
            
            else:
                logger.error("erro_consulta_cnpj_api_oficial", 
                           cnpj=cnpj[:8] + "****",
                           status_code=response.status_code,
                           response_text=response.text)
                raise Exception(f"API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error("erro_consultar_cnpj_api_oficial", 
                       cnpj=cnpj[:8] + "****", 
                       error=str(e))
            raise
    
    def _get_realistic_headers(self, access_token: str) -> Dict[str, str]:
        """
        Gera cabeçalhos HTTP realísticos para simular requisição de navegador real
        Baseado nos cabeçalhos capturados do site oficial
        
        Args:
            access_token: Token JWT para Authorization
            
        Returns:
            Dict com cabeçalhos HTTP completos
        """
        return {
            # Cabeçalhos de autenticação
            "Authorization": f"Bearer {access_token}",
            
            # Cabeçalhos de conteúdo e aceitação
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd", 
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json",
            
            # Cabeçalhos de cache
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            
            # Cabeçalhos de origem e referência 
            "Origin": "https://resolve.cenprot.org.br",
            "Referer": "https://resolve.cenprot.org.br/",
            
            # Cabeçalhos de segurança
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors", 
            "Sec-Fetch-Site": "same-site",
            
            # User-Agent realístico (iPhone como na imagem)
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            
            # Outros cabeçalhos de prioridade
            "Priority": "u=1, i"
        }
    
    def _get_realistic_headers_no_auth(self) -> Dict[str, str]:
        """
        Gera cabeçalhos HTTP realísticos sem Authorization
        Para uso nas requisições de autenticação (generate-token, validate-token)
        
        Returns:
            Dict com cabeçalhos HTTP completos (sem Authorization)
        """
        return {
            # Cabeçalhos de conteúdo e aceitação
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd", 
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json",
            
            # Cabeçalhos de cache
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            
            # Cabeçalhos de origem e referência 
            "Origin": "https://resolve.cenprot.org.br",
            "Referer": "https://resolve.cenprot.org.br/",
            
            # Cabeçalhos de segurança
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors", 
            "Sec-Fetch-Site": "same-site",
            
            # User-Agent realístico (iPhone como na imagem)
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            
            # Outros cabeçalhos de prioridade
            "Priority": "u=1, i"
        }
    
    def _clean_cnpj(self, cnpj: str) -> str:
        """
        Remove formatação do CNPJ para uso na API oficial
        
        Args:
            cnpj: CNPJ com ou sem formatação
            
        Returns:
            str: CNPJ apenas com números
        """
        import re
        # Remover tudo que não é número
        cnpj_limpo = re.sub(r'[^\d]', '', cnpj)
        
        # Validar se tem 14 dígitos
        if len(cnpj_limpo) != 14:
            raise ValueError(f"CNPJ deve ter 14 dígitos, recebido: {len(cnpj_limpo)} dígitos")
        
        return cnpj_limpo
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status da autenticação"""
        return {
            "authenticated": not self._is_token_expired(),
            "token_expires_at": self.token_expires_at.isoformat() if self.token_expires_at else None,
            "login": self.login[:8] + "****" if self.login else None,
            "singleton_instance": True,
            "instance_id": id(self)
        }
    
    @classmethod
    def reset_singleton(cls):
        """
        Reseta o singleton (útil para testes e debugging)
        ATENÇÃO: Use apenas em casos especiais
        """
        if cls._instance:
            logger.warning("resetando_singleton_api_oficial")
            # Fechar conexões se existirem
            if hasattr(cls._instance, '_client') and cls._instance._client:
                # Não aguardar async aqui, apenas marcar para fechamento
                pass
            
            cls._instance = None
            cls._initialized = False
            logger.info("singleton_api_oficial_resetado")
