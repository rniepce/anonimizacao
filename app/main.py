"""
TJMG Anonymizer Pipeline - FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.routes import router
from app.config import settings

app = FastAPI(
    title="TJMG Anonymizer Pipeline",
    description="Pipeline de anonimização de documentos judiciais",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas da API
app.include_router(router, prefix=settings.API_PREFIX)

# Servir frontend estático
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


@app.get("/health")
async def health_check():
    """Endpoint de health check"""
    return {"status": "healthy", "version": "1.0.0"}
