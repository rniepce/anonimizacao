"""
Configurações da aplicação
"""
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações globais do pipeline"""
    
    # Diretórios
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    UPLOAD_DIR: Path = DATA_DIR / "uploads"
    ALLOWLIST_DIR: Path = DATA_DIR / "allowlist"
    LOGS_DIR: Path = BASE_DIR / "logs"
    
    # OCR
    OCR_DPI: int = 300
    OCR_LANGUAGE: str = "por"
    OCR_CONFIDENCE_THRESHOLD: int = 60
    
    # NLP
    SPACY_MODEL: str = "pt_core_news_lg"
    
    # Anonimização
    REDACTION_COLOR: tuple = (0, 0, 0)  # Preto
    REDACTION_TEXT: str = "[ANONIMIZADO]"
    
    # API
    API_PREFIX: str = "/api"
    MAX_FILE_SIZE_MB: int = 100
    ALLOWED_EXTENSIONS: set = {"pdf", "docx"}
    
    class Config:
        env_prefix = "TJMG_"


settings = Settings()

# Criar diretórios necessários
for dir_path in [settings.UPLOAD_DIR, settings.ALLOWLIST_DIR, settings.LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)
