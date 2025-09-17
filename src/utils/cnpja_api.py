import os
import re
import json
import time
import logging
import locale
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
import requests
from requests.exceptions import RequestException
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# Configuração do diretório para logs - Padronizado
ROOT_DIR = Path(__file__).resolve().parent.parent  # /app
LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Diretório específico para logs da CNPJa API
LOG_DIR_CNPJA_API = LOG_DIR / "cnpja_api"
LOG_DIR_CNPJA_API.mkdir(parents=True, exist_ok=True)

# Diretório para logs de respostas brutas da API
LOG_DIR_CNPJA_RESPONSES = LOG_DIR / "cnpja_responses"
LOG_DIR_CNPJA_RESPONSES.mkdir(parents=True, exist_ok=True)

# Configuração de logging
logger = logging.getLogger('CNPJaAPI')
logger.setLevel(logging.INFO)

# Remover handlers existentes para evitar duplicação
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Criar handler para arquivo de log
log_file = LOG_DIR_CNPJA_API / "CNPJaAPI.log"
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)

# Definir formato
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(formatter)

# Adicionar handler ao logger
logger.addHandler(file_handler)

class CNPJaAPIError(Exception):
    """Classe base para erros relacionados à API CNPJa."""
    pass

class CNPJaInvalidCNPJError(CNPJaAPIError):
    """Erro lançado quando o CNPJ fornecido tem formato inválido."""
    pass

class CNPJaNotFoundError(CNPJaAPIError):
    """Erro lançado quando o CNPJ não é encontrado na base."""
    pass

class CNPJaRateLimitError(CNPJaAPIError):
    """Erro lançado quando o limite de requisições é excedido."""
    pass

class CNPJaAuthError(CNPJaAPIError):
    """Erro lançado quando há problemas de autenticação."""
    pass

class CNPJaServerError(CNPJaAPIError):
    """Erro lançado quando ocorre um erro interno no servidor da API."""
    pass

class CNPJaAPI:
    """
    Cliente para integração com a API CNPJa.
    
    Esta classe fornece métodos para consulta de dados de CNPJ utilizando
    a API CNPJa (https://cnpja.com/api).
    
    Atributos:
        BASE_URL (str): URL base da API CNPJa.
        api_key (str): Chave de API para autenticação.
        cache (dict): Cache local para armazenar resultados de consultas recentes.
        last_request_time (float): Timestamp da última requisição feita.
        request_queue (list): Fila de requisições pendentes.
    """
    
    BASE_URL = "https://api.cnpja.com/office/"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa o cliente da API CNPJa.
        
        Args:
            api_key: Chave de API para autenticação. Se não fornecida, 
                    tenta obter da variável de ambiente API_KEY_CNPJA.
        
        Raises:
            CNPJaAuthError: Se a chave de API não for fornecida nem encontrada
                            nas variáveis de ambiente.
        """
        self.api_key = api_key or os.environ.get("API_KEY_CNPJA")
        if not self.api_key:
            raise CNPJaAuthError("API Key não fornecida. Defina a variável de ambiente API_KEY_CNPJA ou forneça a chave no construtor.")
        
        # Inicializa o cache como um dicionário: {cnpj: {"data": {...}, "timestamp": datetime, "params": {...}}}
        self.cache = {}
        
        # Controle de taxa de requisições (rate limiting)
        self.last_request_time = 0
        self.request_queue = []
        
        # Configuração de locale para formatação de valores monetários
        try:
            locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
        except locale.Error:
            # Se não conseguir definir o locale para pt_BR, usa o padrão
            logger.warning("Não foi possível definir o locale para pt_BR. Usando o padrão do sistema.")
        
    
    def _validate_cnpj(self, cnpj: str) -> bool:
        """
        Valida se o CNPJ tem um formato válido.
        
        Args:
            cnpj: Número do CNPJ a ser validado.
            
        Returns:
            True se o CNPJ for válido, False caso contrário.
        """
        # Remove caracteres não numéricos
        cnpj = re.sub(r'\D', '', cnpj)
        
        # Verifica se tem 14 dígitos
        if len(cnpj) != 14:
            return False
            
        # Verifica se todos os dígitos são iguais
        if len(set(cnpj)) == 1:
            return False
            
        # Validação do primeiro dígito verificador
        soma = 0
        peso = 5
        for i in range(12):
            soma += int(cnpj[i]) * peso
            peso = 9 if peso == 2 else peso - 1
            
        digito1 = 11 - (soma % 11)
        digito1 = 0 if digito1 > 9 else digito1
        
        if int(cnpj[12]) != digito1:
            return False
            
        # Validação do segundo dígito verificador
        soma = 0
        peso = 6
        for i in range(13):
            soma += int(cnpj[i]) * peso
            peso = 9 if peso == 2 else peso - 1
            
        digito2 = 11 - (soma % 11)
        digito2 = 0 if digito2 > 9 else digito2
        
        return int(cnpj[13]) == digito2
    
    def _format_cnpj(self, cnpj: str) -> str:
        """
        Formata o CNPJ, removendo caracteres especiais.
        
        Args:
            cnpj: Número do CNPJ a ser formatado.
            
        Returns:
            CNPJ formatado contendo apenas números.
        """
        return re.sub(r'\D', '', cnpj)
    
    def format_cnpj_display(self, cnpj: str) -> str:
        """
        Formata o CNPJ para exibição no padrão XX.XXX.XXX/XXXX-XX.
        
        Args:
            cnpj: Número do CNPJ a ser formatado.
            
        Returns:
            CNPJ formatado no padrão XX.XXX.XXX/XXXX-XX.
        """
        cnpj = self._format_cnpj(cnpj)
        if len(cnpj) != 14:
            return cnpj
        
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    
    def _format_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Converte data do formato ISO (YYYY-MM-DD) para o formato brasileiro (DD/MM/YYYY).
        
        Args:
            date_str: String da data no formato ISO ou None.
            
        Returns:
            String da data no formato brasileiro ou None se a entrada for None.
        """
        if not date_str:
            return None
            
        try:
            date_obj = datetime.fromisoformat(date_str)
            return date_obj.strftime('%d/%m/%Y')
        except ValueError:
            logger.warning(f"Formato de data inválido: {date_str}")
            return date_str
    
    def _format_currency(self, value: Optional[float]) -> Optional[str]:
        """
        Formata um valor numérico para o formato de moeda brasileira.
        
        Args:
            value: Valor numérico ou None.
            
        Returns:
            String formatada como moeda (ex: R$ 1.234,56) ou None se a entrada for None.
        """
        if value is None:
            return None
            
        try:
            return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        except (ValueError, TypeError):
            logger.warning(f"Erro ao formatar valor monetário: {value}")
            return str(value)
    
    def _check_cache(self, cnpj: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Verifica se há dados em cache para o CNPJ solicitado.
        
        Args:
            cnpj: Número do CNPJ a ser consultado.
            params: Parâmetros da consulta.
            
        Returns:
            Dados em cache se disponíveis e válidos, None caso contrário.
        """
        if cnpj in self.cache:
            cache_entry = self.cache[cnpj]
            cache_params = cache_entry.get('params', {})
            
            # Obtém o maxAge dos parâmetros ou usa padrão de 2 dias
            max_age = params.get('maxAge', 2)
            
            # Verifica se o cache é válido considerando o maxAge
            cache_age = datetime.now() - cache_entry['timestamp']
            if cache_age.days <= max_age:
                # Verifica se os parâmetros são compatíveis
                # Exclui parâmetros relacionados ao cache que não afetam o conteúdo dos dados
                cache_params_to_ignore = {'maxAge', 'maxStale', 'strategy'}
                for key, value in params.items():
                    if key not in cache_params_to_ignore and cache_params.get(key) != value:
                        return None
                
                logger.info(f"✅ Usando dados em cache para o CNPJ {cnpj} (idade: {cache_age.days} dias)")
                return cache_entry['data']
        
        return None
    
    def _add_to_cache(self, cnpj: str, data: Dict[str, Any], params: Dict[str, Any]) -> None:
        """
        Adiciona os dados ao cache local.
        
        Args:
            cnpj: Número do CNPJ.
            data: Dados retornados pela API.
            params: Parâmetros usados na consulta.
        """
        self.cache[cnpj] = {
            'data': data,
            'timestamp': datetime.now(),
            'params': params
        }
        
    def _wait_for_rate_limit(self) -> None:
        """
        Aguarda o tempo necessário para respeitar o limite de requisições.
        A API CNPJa permite até 3 requisições por minuto.
        """
        now = time.time()
        elapsed = now - self.last_request_time
        
        # Se a última requisição foi feita há menos de 20 segundos, aguarda
        if elapsed < 20 and self.last_request_time > 0:
            wait_time = 20 - elapsed
            logger.debug(f"Aguardando {wait_time:.2f} segundos para respeitar o rate limit")
            time.sleep(wait_time)
            
        self.last_request_time = time.time()
    

    # Consulta dados de um CNPJ na API CNPJa. (DADOS BRUTOS DA API)
    def get_cnpj_data(self, cnpj: str, **params) -> Dict[str, Any]:
        """
        Consulta dados de um CNPJ na API CNPJa.
        
        Args:
            cnpj: Número do CNPJ a ser consultado.
            **params: Parâmetros opcionais da consulta:
                maxAge (int): Idade máxima em dias para dados do cache (20 dias por padrão).
                maxStale (int): Tempo máximo em dias para aceitar dados do cache quando a API estiver indisponível.
                simples (bool): Indica se deve retornar informações do Simples Nacional (sempre True).
                registrations (str): Filtro para inscrições estaduais (sempre 'BR' para obter todos os estados).
                geocoding (bool): Indica se deve retornar informações de geolocalização (sempre True).
                suframa (bool): Indica se deve retornar informações de SUFRAMA (sempre True).
                strategy (str): Estratégia de cache ('CACHE_IF_FRESH' por padrão).
                
        Returns:
            Dicionário com os dados do CNPJ consultado.
            
        Raises:
            CNPJaInvalidCNPJError: Se o CNPJ fornecido tem formato inválido.
            CNPJaNotFoundError: Se o CNPJ não é encontrado na base.
            CNPJaRateLimitError: Se o limite de requisições é excedido.
            CNPJaAuthError: Se há problemas de autenticação.
            CNPJaServerError: Se ocorre um erro interno no servidor da API.
            CNPJaAPIError: Para outros erros relacionados à API.
        """
        # Formata e valida o CNPJ
        formatted_cnpj = self._format_cnpj(cnpj)
        if not self._validate_cnpj(formatted_cnpj):
            raise CNPJaInvalidCNPJError(f"CNPJ inválido: {cnpj}")
        
        # Configura estratégia de cache por padrão
        if 'strategy' not in params:
            params['strategy'] = 'CACHE_IF_FRESH'
        
        if 'maxAge' not in params:
            params['maxAge'] = 20
        
        # Log da configuração de cache
        strategy = params.get('strategy', 'CACHE_IF_FRESH')
        max_age = params.get('maxAge', 20)
        logger.info(f"🗄️ Configuração de cache: strategy={strategy}, maxAge={max_age} dias para CNPJ {formatted_cnpj}")
        
        
        # Constrói a URL da requisição
        url = f"{self.BASE_URL}{formatted_cnpj}"
        
        # Prepara os headers da requisição
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Prepara os parâmetros, convertendo booleanos para strings 'true'/'false'
        formatted_params = {}
        for key, value in params.items():
            if isinstance(value, bool):
                formatted_params[key] = str(value).lower()  # Converte True para 'true' e False para 'false'
            else:
                formatted_params[key] = value
        
        # Log da URL completa com parâmetros para diagnóstico
        param_str = "&".join([f"{k}={v}" for k, v in formatted_params.items()])
        logger.debug(f"URL de requisição: {url}?{param_str}")
        
        # Aguarda o rate limit se necessário
        self._wait_for_rate_limit()
        
        try:
            # Faz a requisição para a API
            response = requests.get(url, headers=headers, params=formatted_params)
            
            # Log dos parâmetros enviados e recebidos
            logger.debug(f"Parâmetros enviados: {formatted_params}")
            logger.debug(f"Status code: {response.status_code}")
            logger.debug(f"Headers da resposta: {response.headers}")
            
            # Salva a resposta bruta em arquivo JSON
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            response_log_file = LOG_DIR_CNPJA_RESPONSES / f"{formatted_cnpj}_{timestamp}_response.json"
            
            # Cria um dicionário com os dados da resposta
            response_data = {
                "url": url,
                "method": "GET",
                "params": formatted_params,
                "headers_sent": dict(headers),
                "status_code": response.status_code,
                "headers_received": dict(response.headers),
                "timestamp": datetime.now().isoformat(),
                "response_body": response.json() if response.status_code == 200 else response.text
            }
            
            # Salva o arquivo
            try:
                with open(response_log_file, "w", encoding="utf-8") as f:
                    json.dump(response_data, f, indent=4, ensure_ascii=False)
                logger.info(f"Resposta da API salva em {response_log_file}")
            except Exception as e:
                logger.error(f"Erro ao salvar resposta da API: {str(e)}")
            
            # Trata os erros com base no status code
            if response.status_code == 200:
                data = response.json()
                # Log para debug
                logger.debug(f"Resposta da API para CNPJ {formatted_cnpj}: {json.dumps(data, indent=2)}")
                # Adiciona ao cache
                self._add_to_cache(formatted_cnpj, data, params)
                return data
            elif response.status_code == 400:
                raise CNPJaAPIError(f"Requisição inválida: {response.text}")
            elif response.status_code == 401:
                raise CNPJaAuthError("Credenciais inválidas ou expiradas")
            elif response.status_code == 403:
                raise CNPJaAuthError("Acesso negado")
            elif response.status_code == 404:
                raise CNPJaNotFoundError(f"CNPJ {cnpj} não encontrado")
            elif response.status_code == 429:
                wait_time = int(response.headers.get('Retry-After', 60))
                logger.warning(f"Limite de requisições excedido. Aguardando {wait_time} segundos.")
                time.sleep(wait_time)
                # Tenta novamente após aguardar
                return self.get_cnpj_data(cnpj, **params)
            elif response.status_code == 503:
                # Serviço temporariamente indisponível - tentar fallback
                error_data = response.json() if response.text else {}
                service_name = error_data.get('message', 'serviço').replace(' service is offline', '')
                logger.warning(f"Serviço {service_name} temporariamente offline. Tentando fallback...")
                
                # Tentar sem o serviço problemático
                if 'simples' in params and params['simples']:
                    logger.info("Tentando consulta sem dados do Simples Nacional...")
                    fallback_params = params.copy()
                    fallback_params['simples'] = False
                    return self.get_cnpj_data(cnpj, **fallback_params)
                else:
                    raise CNPJaServerError(f"Serviço {service_name} temporariamente offline: {response.text}")
            elif response.status_code >= 500:
                raise CNPJaServerError(f"Erro interno do servidor: {response.text}")
            else:
                raise CNPJaAPIError(f"Erro desconhecido. Status: {response.status_code}, Resposta: {response.text}")
                
        except RequestException as e:
            logger.error(f"Erro na requisição HTTP: {str(e)}")
            # Verifica se podemos usar cache mesmo expirado (fallback)
            if params.get('enable_cache_fallback', False) and formatted_cnpj in self.cache:
                logger.warning(f"Usando cache expirado para o CNPJ {formatted_cnpj} devido a falha na requisição")
                return self.cache[formatted_cnpj]['data']
            raise CNPJaAPIError(f"Erro na comunicação com a API: {str(e)}")
    
    def extract_basic_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrai informações básicas da empresa da resposta da API.
        
        Args:
            data: Dados completos retornados pela API.
            
        Returns:
            Dicionário com informações básicas da empresa.
        """
        company_data = data.get('company', {})
        status = data.get('status', {})
        
        # Formatar natureza jurídica com ID
        nature = company_data.get('nature', {})
        nature_id = nature.get('id')
        nature_text = nature.get('text')
        
        if nature_id and nature_text:
            natureza_juridica = f"{nature_id} - {nature_text.upper()}"
        else:
            natureza_juridica = nature_text
        
        # Formatar porte da empresa com ID e acrônimo
        size = company_data.get('size', {})
        size_acronym = size.get('acronym')
        size_text = size.get('text')
        
        if size_acronym and size_text:
            porte = f"{size_acronym} - {size_text.upper()}"
        else:
            porte = size_text
        
        # Processar capital social como número (sem formatação)
        capital_social = company_data.get('equity')
        
        return {
            'cnpj': data.get('taxId'),
            'razao_social': company_data.get('name'),
            'nome_fantasia': data.get('alias'),
            'data_fundacao': self._format_date(data.get('founded')),
            'data_situacao': self._format_date(data.get('statusDate')),
            'situacao': status.get('text') if status else None,
            'porte': porte,
            'capital_social': capital_social,
            'natureza_juridica': natureza_juridica,
            'matriz_filial': 'Matriz' if data.get('head') else 'Filial',
            'ultima_atualizacao': self._format_date(data.get('updated'))
        }
    
    def extract_address_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrai informações de endereço da empresa da resposta da API.
        
        Args:
            data: Dados completos retornados pela API.
            
        Returns:
            Dicionário com informações de endereço da empresa.
        """
        address = data.get('address', {})
        country = address.get('country', {})
        
        # Log para debug de latitude e longitude
        if 'latitude' in address and 'longitude' in address:
            lat = address.get('latitude')
            long = address.get('longitude')
            if lat is not None and long is not None:
                logger.info(f"✓ Coordenadas de geolocalização obtidas com sucesso: lat={lat}, long={long}")
            else:
                logger.warning("⚠ Coordenadas estão presentes na resposta mas com valores None")
        else:
            logger.warning("❌ Coordenadas de geolocalização não encontradas na resposta da API - geocoding pode não ter funcionado")
            
        return {
            'logradouro': address.get('street'),
            'numero': address.get('number'),
            'complemento': address.get('details'),
            'bairro': address.get('district'),
            'cep': address.get('zip'),
            'cidade': address.get('city'),
            'uf': address.get('state'),
            'pais': country.get('name') if country else 'Brasil',
            'latitude': address.get('latitude'),
            'longitude': address.get('longitude'),
            'municipio_ibge': address.get('municipality')
        }
    
    def extract_contact_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrai informações de contato da empresa da resposta da API.
        
        Args:
            data: Dados completos retornados pela API.
            
        Returns:
            Dicionário com informações de contato da empresa.
        """
        phones = data.get('phones', [])
        emails = data.get('emails', [])
        
        formatted_phones = []
        for phone in phones:
            phone_type = phone.get('type', '')
            area_code = phone.get('area', '')
            number = phone.get('number', '')
            formatted_phones.append({
                'tipo': phone_type,
                'telefone': f"({area_code}) {number}"
            })
        
        formatted_emails = []
        for email in emails:
            formatted_emails.append({
                'propriedade': email.get('ownership', ''),
                'email': email.get('address', ''),
                'dominio': email.get('domain', '')
            })
            
        return {
            'telefones': formatted_phones,
            'emails': formatted_emails
        }
    
    def extract_activity_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrai informações de atividade da empresa da resposta da API.
        
        Args:
            data: Dados completos retornados pela API.
            
        Returns:
            Dicionário com informações de atividade da empresa.
        """
        main_activity = data.get('mainActivity', {})
        side_activities = data.get('sideActivities', [])
        
        formatted_side_activities = []
        for activity in side_activities:
            formatted_side_activities.append({
                'id': activity.get('id'),
                'descricao': activity.get('text')
            })
        
        return {
            'cnae_principal': {
                'id': main_activity.get('id'),
                'descricao': main_activity.get('text')
            },
            'cnaes_secundarios': formatted_side_activities
        }
    
    def extract_partners_info(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extrai informações dos sócios da empresa da resposta da API.
        
        Args:
            data: Dados completos retornados pela API.
            
        Returns:
            Lista de dicionários com informações dos sócios.
        """
        company_data = data.get('company', {})
        members = company_data.get('members', [])
        
        formatted_members = []
        for member in members:
            person = member.get('person', {})
            role = member.get('role', {})
            
            formatted_members.append({
                'nome': person.get('name'),
                'documento': person.get('taxId'),
                'tipo_pessoa': person.get('type'),
                'cargo': role.get('text'),
                'data_entrada': self._format_date(member.get('since')),
                'faixa_etaria': person.get('age')
            })
            
        return formatted_members
    
    def extract_simples_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrai informações do Simples Nacional e SIMEI da resposta da API.
        
        Args:
            data: Dados completos retornados pela API.
            
        Returns:
            Dicionário com informações do Simples Nacional e SIMEI.
        """
        company_data = data.get('company', {})
        simples = company_data.get('simples', {})
        simei = company_data.get('simei', {})
        
        # Log para debug de informações do Simples e SIMEI
        logger.debug(f"Dados Simples: {simples}")
        logger.debug(f"Dados SIMEI: {simei}")
        
        # Log informativo sobre o status do Simples Nacional e SIMEI
        simples_optante = simples.get('optant', False)
        simei_optante = simei.get('optant', False)
        
        if simples_optante:
            logger.info(f"✓ Empresa é optante pelo Simples Nacional desde {simples.get('since', 'data não informada')}")
        else:
            logger.info("ℹ Empresa NÃO é optante pelo Simples Nacional")
            
        if simei_optante:
            logger.info(f"✓ Empresa é optante pelo SIMEI desde {simei.get('since', 'data não informada')}")
        else:
            logger.info("ℹ Empresa NÃO é optante pelo SIMEI")
        
        return {
            'simples_nacional': {
                'optante': simples.get('optant', False),
                'data_opcao': self._format_date(simples.get('since'))
            },
            'simei': {
                'optante': simei.get('optant', False),
                'data_opcao': self._format_date(simei.get('since'))
            }
        }
    
    def extract_registrations_info(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extrai informações sobre registros estaduais (inscrições estaduais) da resposta da API.
        
        Args:
            data: Dados completos retornados pela API.
            
        Returns:
            Lista de dicionários com informações sobre registros estaduais.
        """
        registrations = data.get('registrations', [])
        
        # Log informativo sobre a quantidade de registros encontrados
        if registrations:
            logger.info(f"✓ Encontrados {len(registrations)} registro(s) estadual(is)")
        else:
            logger.warning("⚠ Nenhum registro estadual encontrado na resposta da API")
        
        formatted_registrations = []
        for reg in registrations:
            status = reg.get('status', {})
            reg_type = reg.get('type', {})
            uf = reg.get('state')
            numero = reg.get('number')
            ativo = reg.get('enabled', False)
            situacao = status.get('text') if status else None
            
            # Log detalhado de cada registro
            status_text = "ATIVO" if ativo else "INATIVO"
            logger.info(f"  📋 UF: {uf} | IE: {numero} | Status: {status_text} | Situação: {situacao}")
            
            formatted_registrations.append({
                'uf': uf,
                'numero': numero,
                'ativo': ativo,
                'data_situacao': self._format_date(reg.get('statusDate')),
                'situacao': situacao,
                'tipo': reg_type.get('text') if reg_type else None
            })
            
        return formatted_registrations
    
    def extract_suframa_info(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extrai informações de SUFRAMA da empresa da resposta da API.
        
        Args:
            data: Dados completos retornados pela API.
            
        Returns:
            Lista de dicionários com informações de SUFRAMA da empresa.
            
        Example:
            >>> api = CNPJaAPI()
            >>> dados = api.get_all_company_info("04337168000148", suframa=True)
            >>> suframa_data = dados['suframa']
            >>> print(suframa_data[0]['numero'])  # "200106023"
            >>> print(suframa_data[0]['status']['texto'])  # "Ativa"
            >>> print(len(suframa_data[0]['incentivos']))  # 2
        """
        suframa_data = data.get('suframa', [])
        
        if not suframa_data:
            return []
        
        extracted_suframa = []
        
        for suframa_item in suframa_data:
            # Extrair informações básicas do registro SUFRAMA
            suframa_info = {
                'numero': suframa_item.get('number'),
                'data_inicio': self._format_date(suframa_item.get('since')),
                'aprovado': suframa_item.get('approved'),
                'data_aprovacao': self._format_date(suframa_item.get('approvalDate')),
                'status': None,
                'incentivos': []
            }
            
            # Extrair status do registro
            status = suframa_item.get('status', {})
            if status:
                suframa_info['status'] = {
                    'id': status.get('id'),
                    'texto': status.get('text')
                }
            
            # Extrair incentivos fiscais
            incentives = suframa_item.get('incentives', [])
            for incentive in incentives:
                incentive_info = {
                    'tributo': incentive.get('tribute'),
                    'beneficio': incentive.get('benefit'),
                    'finalidade': incentive.get('purpose'),
                    'base_legal': incentive.get('basis')
                }
                suframa_info['incentivos'].append(incentive_info)
            
            extracted_suframa.append(suframa_info)
        
        return extracted_suframa

    def validate_cnpj_format(self, cnpj: str) -> bool:
        """
        Valida o formato do CNPJ sem consultar a API.
        
        Args:
            cnpj: Número do CNPJ a ser validado.
            
        Returns:
            True se o formato do CNPJ for válido, False caso contrário.
        """
        return self._validate_cnpj(cnpj)
    
    def clear_cache(self) -> None:
        """Limpa todo o cache local."""
        self.cache = {}
    
    def remove_from_cache(self, cnpj: str) -> None:
        """
        Remove um CNPJ específico do cache local.
        
        Args:
            cnpj: Número do CNPJ a ser removido do cache.
        """
        formatted_cnpj = self._format_cnpj(cnpj)
        if formatted_cnpj in self.cache:
            del self.cache[formatted_cnpj]
            logger.info(f"CNPJ {formatted_cnpj} removido do cache")

    
    # Consulta dados de um CNPJ na API CNPJa. (DADOS ESTRUTURADOS COM DEVIDAS CONVERSÕES)
    def get_all_company_info(self, cnpj: str, **params) -> Dict[str, Any]:
        """
        Retorna um dicionário com as informações da empresa extraídas de forma estruturada,
        incluindo apenas os parâmetros que foram habilitados na consulta.
        
        Args:
            cnpj: Número do CNPJ a ser consultado.
            **params: Parâmetros opcionais da consulta que determinam quais dados extrair:
                - simples: Se True, inclui dados do Simples Nacional
                - registrations: Se especificado, inclui registros estaduais
                - geocoding: Se True, inclui dados de geolocalização no endereço
                - suframa: Se True, inclui dados de SUFRAMA
                - partners: Se True, inclui dados de sócios
                - activities: Se True, inclui dados de atividades econômicas
                - contact: Se True, inclui dados de contato
                - address: Se True, inclui dados de endereço
                - basic: Se True, inclui dados básicos (sempre incluído por padrão)
            
        Returns:
            Dicionário com as informações da empresa estruturadas por categoria,
            contendo apenas os parâmetros habilitados.
            
        Raises:
            CNPJaInvalidCNPJError: Se o CNPJ fornecido tem formato inválido.
            CNPJaNotFoundError: Se o CNPJ não é encontrado na base.
            CNPJaRateLimitError: Se o limite de requisições é excedido.
            CNPJaAuthError: Se há problemas de autenticação.
            CNPJaServerError: Se ocorre um erro interno no servidor da API.
            CNPJaAPIError: Para outros erros relacionados à API.
        """
        # Filtrar parâmetros válidos para a API CNPJa
        # A API só aceita: simples, registrations, geocoding, suframa, strategy
        api_params = {}
        valid_api_params = ['simples', 'registrations', 'geocoding', 'suframa', 'strategy']
        
        for param, value in params.items():
            if param in valid_api_params and value is not None:
                api_params[param] = value
        
        # Obtém os dados da API (pode ser parcial se alguns serviços estiverem offline)
        try:
            data = self.get_cnpj_data(cnpj, **api_params)
        except CNPJaServerError as e:
            # Se for erro de serviço offline, tentar com parâmetros mínimos
            if "offline" in str(e).lower():
                logger.warning(f"Alguns serviços estão offline. Tentando consulta básica para CNPJ {cnpj}")
                minimal_params = {'strategy': api_params.get('strategy', 'CACHE_IF_FRESH')}
                data = self.get_cnpj_data(cnpj, **minimal_params)
            else:
                raise
        
        # Inicializa o dicionário de dados estruturados
        structured_data = {}
        
        # Sempre inclui dados básicos (informações essenciais da empresa)
        structured_data['basico'] = self.extract_basic_info(data)
        
        # Inclui endereço se geocoding estiver habilitado ou se address for True
        if params.get('geocoding', False) or params.get('address', True):
            structured_data['endereco'] = self.extract_address_info(data)
        
        # Inclui contato se contact for True (padrão: True)
        if params.get('contact', True):
            structured_data['contato'] = self.extract_contact_info(data)
        
        # Inclui atividades econômicas se activities for True (padrão: True)
        if params.get('activities', True):
            structured_data['atividades'] = self.extract_activity_info(data)
        
        # Inclui sócios se partners for True (padrão: True)
        if params.get('partners', True):
            structured_data['socios'] = self.extract_partners_info(data)
        
        # Inclui dados do Simples Nacional se simples for True
        if params.get('simples', False):
            structured_data['simples'] = self.extract_simples_info(data)
        
        # Inclui registros estaduais se registrations for especificado
        if params.get('registrations'):
            structured_data['registros_estaduais'] = self.extract_registrations_info(data)
        
        # Inclui dados de SUFRAMA se suframa for True
        if params.get('suframa', False):
            structured_data['suframa'] = self.extract_suframa_info(data)
        
        # Log de aviso se alguns dados não estiverem disponíveis
        requested_categories = []
        if params.get('simples', False):
            requested_categories.append('simples')
        if params.get('registrations'):
            requested_categories.append('registros_estaduais')
        if params.get('suframa', False):
            requested_categories.append('suframa')
        
        missing_categories = [cat for cat in requested_categories if cat not in structured_data]
        if missing_categories:
            logger.warning(f"Dados não disponíveis para CNPJ {cnpj}: {', '.join(missing_categories)} (serviços podem estar offline)")
        
        return structured_data


if __name__ == "__main__":
    cnpj_limpo = "25113317000165"

    # Inicializar cliente da API CNPJa
    api_cnpja = CNPJaAPI()
    
    api_params = {}

    # add consulta Simples Nacional (Dados para MEIs)
    api_params['simples'] = True
    
    # registros estaduais de todo o Brasil (Inscrições Estaduais)
    api_params['registrations'] = 'BR'
    
    # Garantir que estamos solicitando dados de geolocalização
    api_params['geocoding'] = True

    # add consulta SUFRAMA (Dados para SUFRAMA)
    api_params['suframa'] = True
    
    # Configurar estratégia de cache (CACHE_IF_FRESH / ONLINE (sem cache))
    api_params['strategy'] = 'CACHE_IF_FRESH'
    
    # Obter dados do CNPJ da API CNPJa
    dados_cnpja = api_cnpja.get_all_company_info(cnpj_limpo, **api_params)
    # dados_cnpja = api_cnpja.get_cnpj_data(cnpj_limpo, **api_params)

    import json
    print(json.dumps(dados_cnpja, ensure_ascii=True, indent=2))
