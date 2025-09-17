"""
Configurações centralizadas do sistema RPA Resolve CenProt
"""

import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

class Settings:
    """Configurações centralizadas do sistema"""
    
    # Diretório base do projeto
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    
    # Credenciais Resolve CenProt
    RESOLVE_CENPROT_LOGIN: str = os.getenv("RESOLVE_CENPROT_LOGIN", "")
    RESOLVE_CENPROT_URL: str = os.getenv("RESOLVE_CENPROT_URL", "https://resolve.cenprot.org.br")
    
    # API Oficial vs RPA
    USAR_RESOLVE_CENPROT_API_OFICIAL: bool = os.getenv("USAR_RESOLVE_CENPROT_API_OFICIAL", "false").lower() == "true"
    RESOLVE_CENPROT_API_BASE_URL: str = os.getenv("RESOLVE_CENPROT_API_BASE_URL", "https://api.resolve.cenprot.org.br/para-voce/api")
    
    # Configurações de Email para 2FA
    RESOLVE_EMAIL: str = os.getenv("RESOLVE_EMAIL", "")
    RESOLVE_EMAIL_PASSWORD: str = os.getenv("RESOLVE_EMAIL_PASSWORD", "")
    RESOLVE_IMAP_SERVER: str = os.getenv("RESOLVE_IMAP_SERVER", "imap.gmail.com")
    
    # Crawl4AI / LLM
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    CRAWL4AI_PROVIDER: str = os.getenv("CRAWL4AI_PROVIDER", "openai/gpt-4o-mini")
    
    # Performance
    MAX_CONCURRENT_REQUESTS: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "3"))
    REQUEST_DELAY_MIN: float = float(os.getenv("REQUEST_DELAY_MIN", "1.0"))
    REQUEST_DELAY_MAX: float = float(os.getenv("REQUEST_DELAY_MAX", "3.0"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    
    # Browser/Playwright
    HEADLESS: bool = os.getenv("HEADLESS", "true").lower() == "true"
    BROWSER_TIMEOUT: int = int(os.getenv("BROWSER_TIMEOUT", "30000"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE_MAX_SIZE: str = os.getenv("LOG_FILE_MAX_SIZE", "10MB")
    LOG_FILES_BACKUP_COUNT: int = int(os.getenv("LOG_FILES_BACKUP_COUNT", "5"))
    
    # Diretórios de dados
    DATA_DIR: Path = BASE_DIR / "data"
    INPUT_DIR: Path = DATA_DIR / "input"
    OUTPUT_DIR: Path = DATA_DIR / "output"
    LOGS_DIR: Path = DATA_DIR / "logs"
    SESSIONS_DIR: Path = DATA_DIR / "sessions"
    
    def __post_init__(self):
        """Criar diretórios necessários após inicialização"""
        for directory in [self.DATA_DIR, self.INPUT_DIR, self.OUTPUT_DIR, self.LOGS_DIR, self.SESSIONS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def validate_required_settings(cls) -> bool:
        """Valida se todas as configurações obrigatórias estão presentes"""
        settings = cls()
        required_fields = [
            "RESOLVE_CENPROT_LOGIN",
            "RESOLVE_EMAIL", 
            "RESOLVE_EMAIL_PASSWORD"
        ]
        
        missing_fields = []
        for field in required_fields:
            if not getattr(settings, field):
                missing_fields.append(field)
        
        if missing_fields:
            print(f"❌ Configurações obrigatórias não encontradas: {missing_fields}")
            return False
            
        print("✅ Todas as configurações obrigatórias estão presentes")
        return True

# Instância global das configurações
settings = Settings()
settings.__post_init__()
