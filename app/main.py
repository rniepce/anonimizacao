"""
TJMG Anonymizer Pipeline - FastAPI Application
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.api.routes import router
from app.config import settings

logger = logging.getLogger(__name__)

# ─── Rate Limiter ─────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])


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

# ─── Rate Limiting ────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── CORS (restrito por variável de ambiente) ─────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
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


# ─── Security Headers Middleware ──────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    """Adiciona headers de segurança em todas as respostas (OWASP)."""
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    return response


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
