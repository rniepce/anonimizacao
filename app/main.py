"""
TJMG Anonymizer Pipeline - FastAPI Application
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.routes import router
from app.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load models at startup so first request is fast."""
    logger.info("🚀 Pré-carregando modelos NER...")
    try:
        from app.core.pipeline import pipeline
        # Force NER engine initialization (triggers model download/load)
        test_text = "João da Silva, CPF 123.456.789-00"
        pipeline._ner_engine.extract_entities(test_text)
        logger.info("✅ Modelos NER carregados com sucesso")
    except Exception as e:
        logger.warning(f"⚠️ Erro ao pré-carregar modelos: {e}")
    yield


app = FastAPI(
    title="TJMG Anonymizer Pipeline",
    description="Pipeline de anonimização de documentos judiciais",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Job-ID",
        "X-Total-Redactions",
        "X-Original-Hash",
        "X-Anonymized-Hash",
        "X-Processing-Time-Ms",
        "X-Anonymization-Mode",
    ],
)

# Rotas da API
app.include_router(router, prefix=settings.API_PREFIX)

# Servir frontend estático (build React/Vite)
frontend_path = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


@app.get("/health")
async def health_check():
    """Endpoint de health check"""
    return {"status": "healthy", "version": "1.0.0"}
