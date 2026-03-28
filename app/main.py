"""
TJMG Anonymizer Pipeline - FastAPI Application
"""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.api.routes import router
from app.config import settings

logger = logging.getLogger(__name__)

# ─── Rate Limiter ─────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])

# TTL de arquivos temporários em segundos (padrão: 24h)
UPLOAD_TTL_SECONDS: int = 60 * 60 * 24
# Intervalo de verificação da limpeza (padrão: 1h)
CLEANUP_INTERVAL_SECONDS: int = 60 * 60


async def _cleanup_old_uploads() -> None:
    """
    Task em background que remove arquivos de upload expirados (TTL).
    Executa periodicamente a cada CLEANUP_INTERVAL_SECONDS.
    """
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        cutoff = time.time() - UPLOAD_TTL_SECONDS
        removed = 0
        for f in settings.UPLOAD_DIR.iterdir():
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
            except OSError:
                pass
        if removed:
            logger.info(f"🧹 Limpeza de uploads: {removed} arquivo(s) removido(s) (TTL={UPLOAD_TTL_SECONDS}s)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação:
    - Startup: pré-carrega modelos NER, inicia task de limpeza
    - Shutdown: cancela task de limpeza
    """
    logger.info("🚀 Pré-carregando modelos NER...")
    try:
        from app.core.pipeline import pipeline
        # Force NER engine initialization (triggers model download/load)
        test_text = "João da Silva, CPF 123.456.789-00"
        pipeline._ner_engine.extract_entities(test_text)
        logger.info("✅ Modelos NER carregados com sucesso")
    except Exception as e:
        logger.warning(f"⚠️ Erro ao pré-carregar modelos: {e}")

    # Iniciar task de limpeza periódica de uploads
    cleanup_task = asyncio.create_task(_cleanup_old_uploads())
    logger.info(f"🧹 Task de limpeza iniciada (TTL={UPLOAD_TTL_SECONDS}s, intervalo={CLEANUP_INTERVAL_SECONDS}s)")

    yield

    # Shutdown: cancelar task de limpeza
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("👋 Limpeza encerrada. Aplicação desligada.")


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
