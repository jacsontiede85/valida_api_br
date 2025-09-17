"""
Modelos de dados para API oficial do Resolve CenProt
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .protest_models import ConsultaCNPJResult


@dataclass
class ApiTokenResponse:
    """Resposta da validação do token 2FA"""
    message: str
    token: str
    refreshToken: str
    user: Dict[str, Any]
    

@dataclass
class ApiUser:
    """Dados do usuário da API oficial"""
    userId: int
    document: str
    name: str
    phone: str
    email: str


@dataclass  
class ApiTitulo:
    """Título individual de protesto da API oficial"""
    cpfCnpj: str
    dataProtesto: str
    dataVencimento: str
    valorProtestado: str
    anuenciaVencida: bool
    temAnuencia: bool
    nomeApresentante: str
    nomeCedente: str
    nm_chave: str
    vl_custas: Optional[str] = None


@dataclass
class ApiCartorio:
    """Cartório da API oficial"""
    nomeCartorio: str
    endereco: str
    bairro: str
    cidade: str
    telefone: str
    codIBGE: str
    numeroCartorio: str
    qtdTitulos: int
    titulos: List[ApiTitulo]


@dataclass
class ApiEstado:
    """Estado com cartórios da API oficial"""
    uf: str
    dadosCartorio: List[ApiCartorio]


@dataclass
class ApiProtestsData:
    """Dados de protestos da API oficial"""
    dataConsulta: str
    cpfCnpj: str
    qtdTitulos: int
    cartorio: Optional[List[ApiEstado]] = None


@dataclass
class ApiProtestsResponse:
    """Resposta completa da consulta de protestos"""
    status: str
    protests: ApiProtestsData
    

class ApiOficialMapper:
    """Mapper para converter dados da API oficial para modelos existentes"""
    
    @staticmethod
    def _format_currency_value(value: str) -> str:
        """
        Formata valores monetários para padrão brasileiro com prefixo R$ e vírgula decimal.
        
        Args:
            value: Valor a ser formatado (pode estar com ponto ou vírgula decimal)
            
        Returns:
            str: Valor formatado no padrão "R$XXX,XX" ou string vazia se valor inválido
        """
        if not value or value.strip() == "":
            return ""
        
        try:
            # Remove espaços e prefixos existentes
            value_clean = value.strip()
            if value_clean.startswith("R$"):
                value_clean = value_clean[2:].strip()
            
            # Remove outros caracteres não numéricos (exceto ponto e vírgula)
            import re
            value_clean = re.sub(r'[^\d.,]', '', value_clean)
            
            if not value_clean:
                return ""
            
            # Se já tem vírgula como decimal, apenas adiciona prefixo
            if ',' in value_clean and '.' not in value_clean:
                return f"R${value_clean}"
            
            # Se tem ponto como decimal (formato americano), converte para vírgula
            if '.' in value_clean:
                # Verifica se é separador de milhar ou decimal
                if value_clean.count('.') == 1:
                    # Se há apenas um ponto, pode ser decimal
                    parts = value_clean.split('.')
                    if len(parts) == 2 and len(parts[1]) <= 2:
                        # Formato decimal: converte ponto para vírgula
                        value_clean = f"{parts[0]},{parts[1]}"
                    else:
                        # Formato de milhar: remove pontos
                        value_clean = value_clean.replace('.', '')
                else:
                    # Múltiplos pontos: separadores de milhar
                    value_clean = value_clean.replace('.', '')
            
            return f"R${value_clean}"
            
        except Exception:
            # Em caso de erro, retorna string vazia
            return ""
    
    @staticmethod
    def from_api_response_to_consulta_result(
        cnpj: str, 
        api_response: ApiProtestsResponse
    ) -> "ConsultaCNPJResult":
        """
        Converte resposta da API oficial para ConsultaCNPJResult
        
        Args:
            cnpj: CNPJ consultado
            api_response: Resposta da API oficial
            
        Returns:
            ConsultaCNPJResult: Objeto compatível com o sistema existente
        """
        from .protest_models import ConsultaCNPJResult, CartorioProtesto, ProtestoDetalhado
        
        # Se não tem protestos
        if api_response.protests.qtdTitulos == 0:
            return ConsultaCNPJResult(
                cnpj=cnpj,
                cenprotProtestos={},
                dataHora=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                link_pdf="/API oficial - sem protestos"
            )
        
        # Converter protestos por estado
        cartorios_por_estado = {}
        
        if api_response.protests.cartorio:
            for estado in api_response.protests.cartorio:
                cartorios_estado = []
                
                for cartorio_api in estado.dadosCartorio:
                    # Converter títulos para protestos detalhados
                    protestos = []
                    for titulo in cartorio_api.titulos:
                        # Formatação padronizada de valores monetários
                        valor_formatado = ApiOficialMapper._format_currency_value(titulo.valorProtestado)
                        custas_formatadas = ApiOficialMapper._format_currency_value(titulo.vl_custas or "")
                        
                        protesto = ProtestoDetalhado(
                            cpfCnpj=titulo.cpfCnpj,
                            data=titulo.dataProtesto,
                            dataProtesto=titulo.dataProtesto,
                            dataVencimento=titulo.dataVencimento,
                            autorizacaoCancelamento=titulo.temAnuencia,
                            custasCancelamento=custas_formatadas,
                            valor=valor_formatado
                        )
                        protestos.append(protesto)
                    
                    # Criar cartório
                    cartorio = CartorioProtesto(
                        cartorio=cartorio_api.nomeCartorio,
                        obterDetalhes=None,
                        cidade=cartorio_api.cidade,
                        quantidadeTitulos=cartorio_api.qtdTitulos,
                        endereco=f"{cartorio_api.endereco}, {cartorio_api.bairro}",
                        telefone=cartorio_api.telefone,
                        protestos=protestos
                    )
                    cartorios_estado.append(cartorio)
                
                if cartorios_estado:
                    cartorios_por_estado[estado.uf] = cartorios_estado
        
        return ConsultaCNPJResult(
            cnpj=cnpj,
            cenprotProtestos=cartorios_por_estado,
            dataHora=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            link_pdf="/API oficial - consulta realizada"
        )
    
    @staticmethod
    def from_api_dict_to_response(data: Dict[str, Any]) -> ApiProtestsResponse:
        """Converte dict JSON para ApiProtestsResponse"""
        protests_data = data["protests"]
        
        # Converter cartórios se existirem
        cartorios = None
        if "cartorio" in protests_data and protests_data["cartorio"]:
            cartorios = []
            for estado_data in protests_data["cartorio"]:
                cartorios_estado = []
                for cartorio_data in estado_data["dadosCartorio"]:
                    titulos = []
                    for titulo_data in cartorio_data.get("titulos", []):
                        # Garantir que campos obrigatórios estejam presentes
                        # A API oficial pode não retornar alguns campos
                        if 'anuenciaVencida' not in titulo_data:
                            titulo_data['anuenciaVencida'] = False
                        if 'temAnuencia' not in titulo_data:
                            titulo_data['temAnuencia'] = False
                        if 'dataProtesto' not in titulo_data:
                            titulo_data['dataProtesto'] = ""
                        if 'dataVencimento' not in titulo_data:
                            titulo_data['dataVencimento'] = ""
                        if 'nomeApresentante' not in titulo_data:
                            titulo_data['nomeApresentante'] = ""
                        if 'nomeCedente' not in titulo_data:
                            titulo_data['nomeCedente'] = ""
                        if 'nm_chave' not in titulo_data:
                            titulo_data['nm_chave'] = ""
                        
                        titulo = ApiTitulo(**titulo_data)
                        titulos.append(titulo)
                    
                    cartorio = ApiCartorio(
                        nomeCartorio=cartorio_data["nomeCartorio"],
                        endereco=cartorio_data["endereco"],
                        bairro=cartorio_data["bairro"],
                        cidade=cartorio_data["cidade"],
                        telefone=cartorio_data["telefone"],
                        codIBGE=cartorio_data["codIBGE"],
                        numeroCartorio=cartorio_data["numeroCartorio"],
                        qtdTitulos=cartorio_data["qtdTitulos"],
                        titulos=titulos
                    )
                    cartorios_estado.append(cartorio)
                
                estado = ApiEstado(
                    uf=estado_data["uf"],
                    dadosCartorio=cartorios_estado
                )
                cartorios.append(estado)
        
        # Criar protests data
        protests = ApiProtestsData(
            dataConsulta=protests_data["dataConsulta"],
            cpfCnpj=protests_data["cpfCnpj"],
            qtdTitulos=protests_data["qtdTitulos"],
            cartorio=cartorios
        )
        
        return ApiProtestsResponse(
            status=data["status"],
            protests=protests
        )
