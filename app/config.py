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
    OCR_ENGINE: str = "tesseract"  # 'tesseract' | 'paddle'
    
    # NLP / NER
    SPACY_MODEL: str = "pt_core_news_lg"
    NER_ENGINE: str = "spacy"  # 'spacy' | 'gliner' | 'gliner_deep' | 'transformer'
    NER_TRANSFORMER_MODEL: str = "pierreguillou/bert-base-cased-pt-lenerbr"
    GLINER_MODEL: str = "urchade/gliner_multi_pii-v1"
    GLINER_DEEP_MODEL: str = "Ai4Privacy/star-pii-gliner-multi-v1"
    GLINER_CONFIDENCE: float = 0.5
    
    # Detecção visual (documentos escaneados)
    DETECT_FACES: bool = True
    DETECT_SIGNATURES: bool = True
    FACE_CONFIDENCE: float = 0.5
    
    # Anonimização
    REDACTION_COLOR: tuple = (0, 0, 0)  # Preto
    REDACTION_TEXT: str = "[ANONIMIZADO]"
    ANONYMIZATION_MODE: str = "redact"  # 'redact' | 'pseudonymize'
    
    # API
    API_PREFIX: str = "/api"
    MAX_FILE_SIZE_MB: int = 200
    ALLOWED_EXTENSIONS: set = {"pdf", "docx"}
    
    class Config:
        env_prefix = "TJMG_"


settings = Settings()

# Criar diretórios necessários
for dir_path in [settings.UPLOAD_DIR, settings.ALLOWLIST_DIR, settings.LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)
