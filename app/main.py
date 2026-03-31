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


async def _preload_models() -> None:
    """
    Pré-carrega modelos NER em background.
    Executado como asyncio.create_task para não bloquear o startup do uvicorn.
    O servidor responde ao healthcheck imediatamente enquanto os modelos carregam.
    """
    # Pequena espera para o servidor subir completamente
    await asyncio.sleep(2)
    try:
        loop = asyncio.get_event_loop()
        import functools

        def _load():
            from app.core.pipeline import get_pipeline
            p = get_pipeline()
            test_text = "João da Silva, CPF 123.456.789-00"
            p._ner_engine.extract_entities(test_text)

        await loop.run_in_executor(None, _load)
        logger.info("\u2705 Modelos NER carregados com sucesso (background warm-up)")
    except Exception as e:
        logger.warning(f"⚠️ Erro ao pré-carregar modelos: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação:
    - Startup: dispara warm-up de modelos e limpeza em background (não bloqueia)
    - Shutdown: cancela tasks de background
    """
    logger.info("🚀 Servidor iniciando — modelos NER carregando em background...")

    # Iniciar pré-carregamento de modelos em background (não bloqueia o startup)
    warmup_task = asyncio.create_task(_preload_models())

    # Iniciar task de limpeza periódica de uploads
    cleanup_task = asyncio.create_task(_cleanup_old_uploads())
    logger.info(f"🧹 Task de limpeza iniciada (TTL={UPLOAD_TTL_SECONDS}s, intervalo={CLEANUP_INTERVAL_SECONDS}s)")

    yield

    # Shutdown: cancelar tasks de background
    for task in (warmup_task, cleanup_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("👋 Aplicação desligada.")


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

@app.get("/health")
async def health_check():
    """Endpoint de health check — deve estar ANTES do mount estático."""
    return {"status": "healthy", "version": "1.0.0"}


# Servir frontend estático (build React/Vite)
# IMPORTANTE: mount estático deve ser o ÚLTIMO — captura todas as rotas não definidas
frontend_path_static = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_path_static.exists():
    app.mount("/", StaticFiles(directory=frontend_path_static, html=True), name="frontend")
