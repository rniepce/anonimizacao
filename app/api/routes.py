"""
Rotas da API FastAPI
"""
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.api.schemas import (
    AnalyzeResponse,
    AnonymizeResponse,
    AuditLog,
    SensitiveData,
    SensitiveDataType,
    AllowlistEntry,
)
from app.core.pipeline import pipeline
from app.core.allowlist import allowlist_manager, AllowlistItem
from app.audit.logger import audit_logger


router = APIRouter()


def validate_file(file: UploadFile) -> None:
    """Valida arquivo enviado"""
    if not file.filename:
        raise HTTPException(400, "Nome de arquivo não fornecido")
    
    ext = file.filename.split('.')[-1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Extensão não permitida. Use: {settings.ALLOWED_EXTENSIONS}"
        )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_document(
    request: Request,
    file: UploadFile = File(...),
    classe_processual: Optional[str] = Form(None),
    vara: Optional[str] = Form(None),
    comarca: Optional[str] = Form(None),
):
    """
    Analisa um documento e identifica dados sensíveis.
    Não aplica anonimização, apenas retorna preview.
    """
    validate_file(file)
    start_time = time.time()
    job_id = str(uuid.uuid4())
    
    # Salvar arquivo temporariamente
    temp_path = settings.UPLOAD_DIR / f"{job_id}_{file.filename}"
    
    try:
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Analisar documento
        from app.core.pdf_handler import pdf_handler
        pdf_info = pdf_handler.get_info(temp_path)
        
        dados = pipeline.analyze_only(temp_path)
        
        tempo_ms = int((time.time() - start_time) * 1000)
        
        return AnalyzeResponse(
            job_id=job_id,
            arquivo=file.filename,
            total_paginas=pdf_info.total_paginas,
            tipo_pdf=pdf_info.tipo,
            dados_sensiveis=[
                SensitiveData(
                    tipo=SensitiveDataType(d.tipo) if d.tipo in SensitiveDataType.__members__ else SensitiveDataType.PESSOA,
                    valor=d.valor,
                    pagina=d.pagina,
                    posicao={"x": d.x0, "y": d.y0, "width": d.x1 - d.x0, "height": d.y1 - d.y0},
                    confianca=d.confianca,
                    contexto=None
                )
                for d in dados
            ],
            total_identificados=len(dados),
            tempo_processamento_ms=tempo_ms
        )
    
    finally:
        # Limpar arquivo temporário
        if temp_path.exists():
            temp_path.unlink()


@router.post("/anonymize")
async def anonymize_document(
    request: Request,
    file: UploadFile = File(...),
    classe_processual: Optional[str] = Form(None),
    vara: Optional[str] = Form(None),
    comarca: Optional[str] = Form(None),
):
    """
    Anonimiza um documento e retorna o PDF processado.
    """
    validate_file(file)
    job_id = str(uuid.uuid4())
    
    # Salvar arquivo
    input_path = settings.UPLOAD_DIR / f"{job_id}_{file.filename}"
    output_dir = settings.UPLOAD_DIR
    
    try:
        with open(input_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Processar documento
        result = pipeline.process(
            input_path=input_path,
            output_dir=output_dir,
            usuario=None,
            ip_origem=request.client.host if request.client else None
        )
        
        # Retornar arquivo anonimizado
        return FileResponse(
            path=result.arquivo_anonimizado,
            filename=result.arquivo_anonimizado.name,
            media_type="application/pdf",
            headers={
                "X-Job-ID": result.job_id,
                "X-Total-Redactions": str(len(result.dados_anonimizados)),
                "X-Original-Hash": result.hash_original,
                "X-Anonymized-Hash": result.hash_anonimizado,
                "X-Processing-Time-Ms": str(result.tempo_processamento_ms)
            }
        )
    
    except Exception as e:
        raise HTTPException(500, f"Erro ao processar documento: {str(e)}")
    
    finally:
        # Manter arquivos para auditoria (limpar depois via job)
        pass


@router.post("/anonymize/json", response_model=AnonymizeResponse)
async def anonymize_document_json(
    request: Request,
    file: UploadFile = File(...),
    classe_processual: Optional[str] = Form(None),
    vara: Optional[str] = Form(None),
    comarca: Optional[str] = Form(None),
):
    """
    Anonimiza um documento e retorna metadados JSON.
    Use /download/{job_id} para baixar o arquivo.
    """
    validate_file(file)
    job_id = str(uuid.uuid4())
    
    # Salvar arquivo
    input_path = settings.UPLOAD_DIR / f"{job_id}_{file.filename}"
    output_dir = settings.UPLOAD_DIR
    
    try:
        with open(input_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Processar documento
        result = pipeline.process(
            input_path=input_path,
            output_dir=output_dir,
            usuario=None,
            ip_origem=request.client.host if request.client else None
        )
        
        return AnonymizeResponse(
            job_id=result.job_id,
            arquivo_original=file.filename,
            arquivo_anonimizado=result.arquivo_anonimizado.name,
            hash_original=result.hash_original,
            hash_anonimizado=result.hash_anonimizado,
            total_redacoes=len(result.dados_anonimizados),
            dados_anonimizados=[
                SensitiveData(
                    tipo=SensitiveDataType(d.tipo) if d.tipo in SensitiveDataType.__members__ else SensitiveDataType.PESSOA,
                    valor=d.valor[:3] + "***",  # Mascarar valor
                    pagina=d.pagina,
                    posicao={"x": d.x0, "y": d.y0, "width": d.x1 - d.x0, "height": d.y1 - d.y0},
                    confianca=d.confianca,
                    contexto=None
                )
                for d in result.dados_anonimizados
            ],
            tempo_processamento_ms=result.tempo_processamento_ms
        )
    
    except Exception as e:
        raise HTTPException(500, f"Erro ao processar documento: {str(e)}")


@router.get("/download/{job_id}")
async def download_anonymized(job_id: str):
    """
    Baixa um arquivo anonimizado pelo job_id.
    """
    # Buscar arquivo pelo job_id
    for file_path in settings.UPLOAD_DIR.glob(f"*_anonimizado.pdf"):
        # Verificar no log de auditoria
        log = audit_logger.get_log(job_id)
        if log and log.arquivo_anonimizado == file_path.name:
            return FileResponse(
                path=file_path,
                filename=file_path.name,
                media_type="application/pdf"
            )
    
    raise HTTPException(404, "Arquivo não encontrado")


@router.get("/audit/{job_id}", response_model=AuditLog)
async def get_audit_log(job_id: str):
    """
    Consulta log de auditoria de um job.
    """
    log = audit_logger.get_log(job_id)
    
    if not log:
        raise HTTPException(404, "Job não encontrado")
    
    return AuditLog(
        job_id=log.job_id,
        timestamp=log.timestamp,
        arquivo_original=log.arquivo_original,
        hash_original=log.hash_original,
        hash_anonimizado=log.hash_anonimizado,
        total_redacoes=log.total_redacoes,
        regras_aplicadas=log.regras_aplicadas,
        usuario=log.usuario,
        ip_origem=log.ip_origem
    )


@router.get("/audit/stats")
async def get_audit_stats():
    """
    Retorna estatísticas gerais de auditoria.
    """
    return audit_logger.get_statistics()


@router.post("/allowlist")
async def add_to_allowlist(entry: AllowlistEntry):
    """
    Adiciona item à lista branca.
    """
    item = AllowlistItem(
        nome=entry.nome,
        tipo=entry.tipo,
        registro=entry.registro,
        ativo=entry.ativo
    )
    allowlist_manager.add_item(item)
    
    return {"message": f"'{entry.nome}' adicionado à lista branca"}


@router.get("/allowlist")
async def list_allowlist(tipo: Optional[str] = None):
    """
    Lista itens da lista branca.
    """
    items = allowlist_manager.list_all(tipo)
    return {
        "total": len(items),
        "items": [
            {"nome": i.nome, "tipo": i.tipo, "registro": i.registro, "ativo": i.ativo}
            for i in items
        ]
    }


@router.delete("/allowlist/{nome}")
async def remove_from_allowlist(nome: str):
    """
    Remove item da lista branca.
    """
    if allowlist_manager.remove_item(nome):
        return {"message": f"'{nome}' removido da lista branca"}
    
    raise HTTPException(404, "Item não encontrado na lista branca")


@router.get("/allowlist/stats")
async def get_allowlist_stats():
    """
    Retorna estatísticas da lista branca.
    """
    return allowlist_manager.get_stats()
