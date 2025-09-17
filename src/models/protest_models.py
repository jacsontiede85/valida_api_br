"""
Modelos de dados Pydantic para o sistema RPA Resolve CenProt
Baseado no JSON exemplo: docs/exemplo_00138947000163.json
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import re

class ProtestoDetalhado(BaseModel):
    """Modelo para cada protesto individual"""
    cpfCnpj: str = Field(description="CNPJ do protesto")
    data: Optional[str] = Field(default=None, description="Data do protesto")
    dataProtesto: Optional[str] = Field(default=None, description="Data específica do protesto")
    dataVencimento: str = Field(default="", description="Data de vencimento")
    autorizacaoCancelamento: bool = Field(description="Se permite cancelamento")
    custasCancelamento: str = Field(default="", description="Custas para cancelamento")
    valor: str = Field(description="Valor monetário do protesto")

    @validator('cpfCnpj')
    def validate_cnpj(cls, v):
        """Valida formato do CNPJ"""
        if not v:
            return v
        # Remove caracteres especiais para validação
        cnpj_digits = re.sub(r'[^\d]', '', v)
        if len(cnpj_digits) != 14:
            raise ValueError('CNPJ deve ter 14 dígitos')
        return v

    @validator('valor')
    def validate_valor(cls, v):
        """Valida formato do valor monetário"""
        if not v:
            return v
        # Aceita formatos: 1.234,56 ou 1234.56 ou 1234,56
        if not re.match(r'^\d{1,3}(\.\d{3})*,\d{2}$|^\d+,\d{2}$|^\d+\.\d{2}$', v):
            # Se não está no formato esperado, tenta normalizar
            pass
        return v

class CartorioProtesto(BaseModel):
    """Modelo para dados do cartório"""
    cartorio: str = Field(description="Nome completo do cartório")
    obterDetalhes: Optional[str] = Field(default=None, description="Link ou referência para detalhes")
    cidade: str = Field(description="Cidade do cartório")
    quantidadeTitulos: int = Field(description="Quantidade de títulos")
    endereco: str = Field(description="Endereço completo do cartório")
    telefone: str = Field(description="Telefone do cartório")
    protestos: List[ProtestoDetalhado] = Field(default_factory=list, description="Lista de protestos detalhados")

    @validator('quantidadeTitulos')
    def validate_quantidade_titulos(cls, v):
        """Valida quantidade de títulos"""
        if v < 0:
            raise ValueError('Quantidade de títulos não pode ser negativa')
        return v

    @validator('telefone')
    def validate_telefone(cls, v):
        """Valida formato do telefone"""
        if not v:
            return v
        # Remove caracteres especiais
        phone_digits = re.sub(r'[^\d]', '', v)
        if len(phone_digits) < 10:
            # Permite telefones com pelo menos 10 dígitos
            pass
        return v

class ConsultaCNPJResult(BaseModel):
    """Resultado completo da consulta de um CNPJ"""
    cnpj: str = Field(description="CNPJ consultado")
    cenprotProtestos: Dict[str, List[CartorioProtesto]] = Field(
        default_factory=dict,
        description="Protestos organizados por estado"
    )
    dataHora: str = Field(description="Data/hora da consulta")
    link_pdf: str = Field(description="Link para PDF ou status")

    @validator('cnpj')
    def validate_cnpj(cls, v):
        """Valida formato do CNPJ consultado"""
        if not v:
            raise ValueError('CNPJ é obrigatório')
        # Remove caracteres especiais para validação
        cnpj_digits = re.sub(r'[^\d]', '', v)
        if len(cnpj_digits) != 14:
            raise ValueError('CNPJ deve ter 14 dígitos')
        return v

    @validator('dataHora')
    def validate_data_hora(cls, v):
        """Valida formato da data/hora"""
        if not v:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        return v

    def has_protests(self) -> bool:
        """Verifica se existem protestos encontrados"""
        return len(self.cenprotProtestos) > 0

    def get_total_protests_count(self) -> int:
        """Retorna total de protestos encontrados"""
        total = 0
        for estado_cartorios in self.cenprotProtestos.values():
            for cartorio in estado_cartorios:
                total += len(cartorio.protestos)
        return total

    def get_states_with_protests(self) -> List[str]:
        """Retorna lista de estados com protestos"""
        return list(self.cenprotProtestos.keys())

    class Config:
        """Configuração do modelo"""
        json_schema_extra = {
            "example": {
                "cnpj": "00138947000163",
                "cenprotProtestos": {
                    "BA": [
                        {
                            "cartorio": "TABELIONATO DE NOTAS E PROTESTO DE TITULOS DE UBAÍRA",
                            "obterDetalhes": None,
                            "cidade": "UBAÍRA",
                            "quantidadeTitulos": 3,
                            "endereco": "RUA FERNANDES BARRETO, 283, CENTRO - UBAÍRA",
                            "telefone": "7535442309",
                            "protestos": [
                                {
                                    "cpfCnpj": "00138947000163",
                                    "data": None,
                                    "dataProtesto": None,
                                    "dataVencimento": "",
                                    "autorizacaoCancelamento": False,
                                    "custasCancelamento": "",
                                    "valor": "658,80"
                                }
                            ]
                        }
                    ]
                },
                "dataHora": "2025-08-08 20:16:09.725198",
                "link_pdf": "/token/.../Download de PDF desabilitado"
            }
        }

class ConsultaStatus(BaseModel):
    """Status de uma consulta em andamento"""
    cnpj: str
    status: str  # "pending", "processing", "completed", "failed"
    message: str = ""
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error_details: Optional[str] = None

class BatchConsultaResult(BaseModel):
    """Resultado de processamento em lote"""
    total_cnpjs: int
    successful_consultations: int
    failed_consultations: int
    results: List[ConsultaCNPJResult]
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def get_success_rate(self) -> float:
        """Retorna taxa de sucesso em percentual"""
        if self.total_cnpjs == 0:
            return 0.0
        return (self.successful_consultations / self.total_cnpjs) * 100

# Aliases para compatibilidade
CenprotResult = ConsultaCNPJResult
ProtestDetail = ProtestoDetalhado
CartorioDetail = CartorioProtesto
