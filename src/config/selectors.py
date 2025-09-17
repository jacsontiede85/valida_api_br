"""
Seletores CSS específicos do site resolve.cenprot.org.br
Baseado na análise do site e documentação
"""

class ResolveSelectors:
    """Seletores CSS para navegação no site Resolve CenProt"""
    
    # === PÁGINA DE LOGIN ===
    LOGIN_INPUT = "#cpfCnpj"
    CHECKBOX_TITULAR = "#confirmarTitular"
    CONTINUE_BTN = "button:has-text('Continuar')"
    
    # === 2FA (Autenticação de 2 Fatores) ===
    OTP_INPUT_BASE = "input[name^='otp-']"  # Base para os 6 campos
    OTP_FIELDS = [f"input[name='otp-{i}']" for i in range(6)]  # 6 campos individuais
    
    # === DASHBOARD ===
    DASHBOARD_HOME = "text=Dashboard"
    SEARCH_LINK = "text=Consulta Pública"
    
    # === PÁGINA DE CONSULTA ===
    SEARCH_INPUT = "input[name='document'][placeholder*='Digite o CPF ou CNPJ']"
    SEARCH_BTN = "button:has-text('Consultar')"
    
    # === RESULTADOS DA CONSULTA ===
    NO_PROTESTS = "text='Protestos não encontrados'"
    PROTESTS_FOUND = "text='Protestos encontrados'"
    RESULT_STATUS = ".text-\\[\\#4F4F4F\\].text-xl.font-semibold.w-full"
    CONSULTATION_DATE = ".text-\\[\\#888888\\] span"
    
    # === ESTADOS E CARTÓRIOS ===
    STATE_SECTIONS = ".mt-6:has(h1)"  # Seções de cada estado
    STATE_NAME = "h1"  # Nome do estado dentro da seção
    CARTORIOS_TABLE = "tbody tr"  # Linhas da tabela de cartórios
    
    # Campos específicos da tabela
    CARTORIO_NAME = "td:first-child"
    CARTORIO_CITY = "td:nth-child(2)"
    CARTORIO_QTDE_TITULOS = "td:nth-child(3)"
    
    # === BOTÕES E AÇÕES ===
    DETAILS_BTN = "button:has-text('Detalhes')"
    CLOSE_MODAL = "button:has(svg[viewBox='0 0 32 32'])"
    
    # === MODAL DE DETALHES DO CARTÓRIO ===
    MODAL_DIALOG = "[role='dialog']"
    MODAL_ENDERECO = "p:contains('Endereço:') .text-\\[\\#323739\\]"
    MODAL_TELEFONE = "p:contains('Telefone:') .text-\\[\\#323739\\]"
    
    # === TÍTULOS DETALHADOS NO MODAL ===
    TITULOS_CONTAINER = ".grid.md\\:grid-cols-2 .flex.flex-col"
    TITULO_CODIGO = "p:contains('Código:') .text-\\[\\#323739\\]"
    TITULO_DOCUMENTO = "p:contains('Documento:') .text-\\[\\#323739\\]"
    TITULO_VALOR = ".bg-\\[\\#A1F5A7\\] p"  # Valor com fundo verde
    
    # === NAVEGAÇÃO E LOADING ===
    LOADING_INDICATOR = ".loading, [data-loading='true'], .spinner"
    PAGINATION = ".pagination, [data-pagination]"
    
    # === ERROR HANDLING ===
    ERROR_MESSAGE = ".error-message, .alert-error, [data-error]"
    TIMEOUT_MESSAGE = "text='Tempo esgotado'"
    NETWORK_ERROR = "text='Erro de conexão'"
    
    @classmethod
    def get_otp_field(cls, index: int) -> str:
        """Retorna o seletor para um campo específico de OTP (0-5)"""
        if 0 <= index <= 5:
            return f"input[name='otp-{index}']"
        raise ValueError(f"Índice OTP inválido: {index}. Deve estar entre 0 e 5.")
    
    @classmethod
    def get_all_otp_fields(cls) -> list[str]:
        """Retorna todos os seletores dos campos OTP"""
        return cls.OTP_FIELDS
    
    @classmethod
    def is_valid_selector(cls, selector: str) -> bool:
        """Valida se um seletor CSS está bem formado"""
        # Validação básica - pode ser expandida
        return bool(selector and isinstance(selector, str) and len(selector.strip()) > 0)
