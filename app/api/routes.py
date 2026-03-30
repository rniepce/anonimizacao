"""
Rotas da API FastAPI
"""
import asyncio
import json
import logging
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.api.schemas import (
    AnalyzeResponse,
    AnalyzePreviewResponse,
    AnonymizeResponse,
    AuditLog,
    SensitiveData,
    SensitiveDataType,
    SelectiveAnonymizeRequest,
    AllowlistEntry,
)
from app.core.pipeline import get_pipeline
from app.core.allowlist import allowlist_manager, AllowlistItem
from app.core.progress import progress_manager
from app.audit.logger import audit_logger

logger = logging.getLogger(__name__)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# ─── MIME types permitidos por extensão ───────────────────────
ALLOWED_MIMES = {
    "pdf": ["application/pdf"],
    "docx": [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",  # docx é um zip internamente
    ],
}


def sanitize_filename(filename: str) -> str:
    """Remove caracteres perigosos e path traversal do filename."""
    # Pegar apenas o nome base (remove ../ e diretórios)
    filename = os.path.basename(filename)
    # Remover caracteres especiais (manter letras, números, -, _, .)
    filename = re.sub(r'[^\w\-.]', '_', filename)
    # Evitar nomes vazios
    return filename or "upload"


def validate_file(file: UploadFile, content_bytes: bytes | None = None, content_length: int = 0) -> None:
    """Valida arquivo enviado: extensão, tamanho e tipo real (magic bytes)."""
    if not file.filename:
        raise HTTPException(400, "Nome de arquivo não fornecido")

    ext = file.filename.split('.')[-1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Extensão não permitida. Use: {settings.ALLOWED_EXTENSIONS}"
        )

    # Verificar tamanho do arquivo
    max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if content_length > max_size:
        raise HTTPException(
            413,
            f"Arquivo muito grande. Máximo: {settings.MAX_FILE_SIZE_MB}MB"
        )

    # Verificar tipo real do conteúdo via magic bytes
    if content_bytes:
        try:
            import magic
            detected_mime = magic.from_buffer(content_bytes[:2048], mime=True)
            allowed = ALLOWED_MIMES.get(ext, [])
            if detected_mime not in allowed:
                raise HTTPException(
                    400,
                    f"Conteúdo do arquivo não corresponde à extensão .{ext}. "
                    f"Tipo detectado: {detected_mime}"
                )
        except ImportError:
            pass  # python-magic não disponível, pular verificação


def _cleanup_job_files(job_id: str, *extra_paths: Path) -> None:
    """Remove arquivos temporários de um job do diretório de uploads."""
    for f in settings.UPLOAD_DIR.glob(f"{job_id}_*"):
        try:
            f.unlink()
        except OSError:
            pass
    for p in extra_paths:
        if p and p.exists():
            try:
                p.unlink()
            except OSError:
                pass


# ─── Execução bloqueante em thread pool ───────────────────────
async def _run_pipeline_in_executor(fn, *args, **kwargs):
    """
    Executa funções bloqueantes do pipeline em thread pool,
    evitando bloquear o event loop assíncrono da FastAPI.
    """
    loop = asyncio.get_event_loop()
    import functools
    return await loop.run_in_executor(None, functools.partial(fn, **kwargs) if kwargs else fn, *args)


@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit(settings.RATE_LIMIT)
async def analyze_document(
    request: Request,
    file: UploadFile = File(...),
    classe_processual: Optional[str] = Form(None),
    vara: Optional[str] = Form(None),
    comarca: Optional[str] = Form(None),
    ner_mode: Optional[str] = Form(None),  # 'standard' | 'deep' | 'legacy'
):
    """
    Analisa um documento e identifica dados sensíveis.
    Não aplica anonimização, apenas retorna preview.
    """
    content = await file.read()
    validate_file(file, content_bytes=content)
    safe_name = sanitize_filename(file.filename or "upload")
    start_time = time.time()
    job_id = str(uuid.uuid4())

    # Salvar arquivo temporariamente
    temp_path = settings.UPLOAD_DIR / f"{job_id}_{safe_name}"

    try:
        with open(temp_path, "wb") as f:
            f.write(content)

        # Analisar documento (bloqueante → thread pool)
        from app.core.pdf_handler import pdf_handler
        pdf_info = await _run_pipeline_in_executor(pdf_handler.get_info, temp_path)
        dados = await _run_pipeline_in_executor(get_pipeline().analyze_only, temp_path, ner_mode)

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao analisar documento job={job_id}: {type(e).__name__}: {e}")
        raise HTTPException(500, f"Erro ao analisar documento: {type(e).__name__}")
    finally:
        # Limpar arquivo temporário
        _cleanup_job_files(job_id, temp_path)


@router.post("/analyze-preview", response_model=AnalyzePreviewResponse)
@limiter.limit(settings.RATE_LIMIT)
async def analyze_preview(
    request: Request,
    file: UploadFile = File(...),
    classe_processual: Optional[str] = Form(None),
    vara: Optional[str] = Form(None),
    comarca: Optional[str] = Form(None),
    ner_mode: Optional[str] = Form(None),
):
    """
    Analisa documento, gera PDF com destaques visuais e retorna
    as entidades identificadas para revisão interativa.
    """
    content = await file.read()
    validate_file(file, content_bytes=content)
    safe_name = sanitize_filename(file.filename or "upload")
    start_time = time.time()
    job_id = str(uuid.uuid4())

    # Salvar arquivo
    temp_path = settings.UPLOAD_DIR / f"{job_id}_{safe_name}"
    # Manter o original para anonimização seletiva posterior
    original_path = settings.UPLOAD_DIR / f"{job_id}_original_{safe_name}"
    preview_path = settings.UPLOAD_DIR / f"{job_id}_preview.pdf"

    try:
        with open(temp_path, "wb") as f:
            f.write(content)

        # Copiar original (será usado pelo anonymize-selective)
        shutil.copy2(temp_path, original_path)

        # Obter info do PDF
        from app.core.pdf_handler import pdf_handler
        pdf_info = await _run_pipeline_in_executor(pdf_handler.get_info, temp_path)

        # Analisar documento (bloqueante → thread pool)
        dados = await _run_pipeline_in_executor(get_pipeline().analyze_only, temp_path, ner_mode)

        # Extrair texto por página para o visualizador interativo
        import fitz as fitz_lib
        texto_por_pagina: dict[int, str] = {}
        try:
            doc_text = fitz_lib.open(str(temp_path))
            for page_num_idx, page_obj in enumerate(doc_text, start=1):
                texto_por_pagina[page_num_idx] = page_obj.get_text()
            doc_text.close()
        except Exception:
            pass  # Se falhar, retorna vazio — viewer mostrará aviso

        # Gerar PDF de preview com highlights visuais
        from app.core.redactor import redactor, RedactionArea
        areas = [
            RedactionArea(
                pagina=d.pagina,
                x0=d.x0,
                y0=d.y0,
                x1=d.x1,
                y1=d.y1,
                tipo=d.tipo,
                valor_original=d.valor
            )
            for d in dados
        ]

        if areas:
            await _run_pipeline_in_executor(redactor.add_overlay_boxes, temp_path, preview_path, areas)
        else:
            shutil.copy2(temp_path, preview_path)

        tempo_ms = int((time.time() - start_time) * 1000)

        return AnalyzePreviewResponse(
            job_id=job_id,
            arquivo=file.filename,
            total_paginas=pdf_info.total_paginas,
            tipo_pdf=pdf_info.tipo,
            preview_url=f"/api/preview/{job_id}",
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
            tempo_processamento_ms=tempo_ms,
            texto_por_pagina=texto_por_pagina,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao analisar preview job={job_id}: {type(e).__name__}: {e}")
        # Limpar arquivos em caso de erro (exceto original — pode ter sido salvo)
        for p in [temp_path, preview_path]:
            if p.exists():
                p.unlink()
        raise HTTPException(500, f"Erro ao analisar documento: {type(e).__name__}")

    finally:
        # Limpar apenas o temp, manter original e preview para uso posterior
        if temp_path.exists():
            temp_path.unlink()


@router.get("/preview/{job_id}")
async def get_preview(job_id: str):
    """
    Serve o PDF de preview com destaques visuais.
    """
    preview_path = settings.UPLOAD_DIR / f"{job_id}_preview.pdf"

    if not preview_path.exists():
        raise HTTPException(404, "Preview não encontrado")

    return FileResponse(
        path=preview_path,
        filename=f"preview_{job_id}.pdf",
        media_type="application/pdf"
    )


@router.get("/preview/{job_id}/page/{page_num}")
async def get_preview_page(job_id: str, page_num: int):
    """
    Renderiza uma página do PDF de preview como imagem PNG.
    Usa PyMuPDF para renderização server-side (funciona em todos os browsers).
    """
    import fitz
    import io

    preview_path = settings.UPLOAD_DIR / f"{job_id}_preview.pdf"

    if not preview_path.exists():
        raise HTTPException(404, "Preview não encontrado")

    try:
        doc = fitz.open(str(preview_path))

        if page_num < 1 or page_num > len(doc):
            doc.close()
            raise HTTPException(400, f"Página {page_num} inválida. Total: {len(doc)}")

        page = doc[page_num - 1]
        # Renderizar em resolução adequada (2x = 144 DPI)
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        total_pages = len(doc)

        img_bytes = pix.tobytes("png")
        doc.close()

        return StreamingResponse(
            io.BytesIO(img_bytes),
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Page-Number": str(page_num),
                "X-Total-Pages": str(total_pages),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao renderizar página job={job_id} page={page_num}: {e}")
        raise HTTPException(500, f"Erro ao renderizar página: {type(e).__name__}")


@router.post("/anonymize-selective")
@limiter.limit(settings.RATE_LIMIT)  # FIX: endpoint antes sem rate limit
async def anonymize_selective(
    request: Request,
    body: SelectiveAnonymizeRequest,
):
    """
    Anonimiza seletivamente com base nas entidades confirmadas pelo usuário.
    Recebe lista de entidades selecionadas + termos customizados.
    """
    job_id = body.job_id

    # Encontrar o arquivo original salvo pelo analyze-preview
    original_files = list(settings.UPLOAD_DIR.glob(f"{job_id}_original_*"))
    if not original_files:
        raise HTTPException(404, "Arquivo original não encontrado. Execute /analyze-preview primeiro.")

    input_path = original_files[0]
    mode = body.mode or settings.ANONYMIZATION_MODE
    suffix = "_pseudonimizado" if mode == "pseudonymize" else "_anonimizado"
    output_path = settings.UPLOAD_DIR / f"{job_id}{suffix}.pdf"

    try:
        from app.core.redactor import redactor, RedactionArea

        # Converter entidades confirmadas em RedactionAreas
        areas = []
        for entity in body.entities:
            pos = entity.posicao
            areas.append(RedactionArea(
                pagina=entity.pagina,
                x0=pos.get("x", 0),
                y0=pos.get("y", 0),
                x1=pos.get("x", 0) + pos.get("width", 0),
                y1=pos.get("y", 0) + pos.get("height", 0),
                tipo=entity.tipo,
                valor_original=entity.valor
            ))

        # Termos customizados: buscar e adicionar posições via PyMuPDF
        if body.custom_terms:
            import fitz
            doc = fitz.open(str(input_path))
            for page_num, page in enumerate(doc, start=1):
                for term_item in body.custom_terms:
                    # Support legacy string or new CustomTermItem
                    if isinstance(term_item, str):
                        term = term_item.strip()
                        tipo = "OUTRO"
                    else:
                        term = term_item.termo.strip()
                        tipo = term_item.tipo

                    if not term:
                        continue

                    instances = page.search_for(term)
                    for rect in instances:
                        areas.append(RedactionArea(
                            pagina=page_num,
                            x0=rect.x0,
                            y0=rect.y0,
                            x1=rect.x1,
                            y1=rect.y1,
                            tipo=tipo,
                            valor_original=term
                        ))
            doc.close()

        # Aplicar anonimização (bloqueante → thread pool)
        if areas:
            if mode == "pseudonymize":
                await _run_pipeline_in_executor(redactor.pseudonymize_pdf, input_path, output_path, areas, job_id)
            else:
                await _run_pipeline_in_executor(redactor.redact_pdf, input_path, output_path, areas)
        else:
            from app.core.pdf_handler import pdf_handler
            await _run_pipeline_in_executor(pdf_handler.remove_metadata, input_path, output_path)

        # Calcular hashes
        hash_original = audit_logger.calculate_hash(input_path)
        hash_anonimizado = audit_logger.calculate_hash(output_path)

        # Registrar auditoria
        regras_aplicadas = list(set(e.tipo for e in body.entities))
        if body.custom_terms:
            regras_aplicadas.append("OUTRO")

        audit_logger.log_anonymization(
            job_id=job_id,
            arquivo_original=input_path,
            arquivo_anonimizado=output_path,
            total_redacoes=len(areas),
            regras_aplicadas=regras_aplicadas,
            dados_anonimizados=[
                {'tipo': a.tipo, 'hash': audit_logger.calculate_hash_bytes(a.valor_original.encode())[:16]}
                for a in areas
            ],
            tempo_processamento_ms=0,
            usuario=None,
            ip_origem=request.client.host if request.client else None
        )

        # Retornar arquivo anonimizado
        return FileResponse(
            path=output_path,
            filename=output_path.name,
            media_type="application/pdf",
            headers={
                "X-Job-ID": job_id,
                "X-Total-Redactions": str(len(areas)),
                "X-Original-Hash": hash_original,
                "X-Anonymized-Hash": hash_anonimizado,
                "X-Anonymization-Mode": mode
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao anonimizar seletivo job={job_id}: {type(e).__name__}: {e}")
        raise HTTPException(500, f"Erro ao anonimizar documento: {type(e).__name__}")


@router.post("/anonymize")
@limiter.limit(settings.RATE_LIMIT)
async def anonymize_document(
    request: Request,
    file: UploadFile = File(...),
    classe_processual: Optional[str] = Form(None),
    vara: Optional[str] = Form(None),
    comarca: Optional[str] = Form(None),
    mode: Optional[str] = Form(None),  # 'redact' | 'pseudonymize'
    ner_mode: Optional[str] = Form(None),  # 'standard' | 'deep' | 'legacy'
):
    """
    Anonimiza um documento e retorna o PDF processado.

    Modos:
    - redact: Aplica tarjas pretas (padrão)
    - pseudonymize: Substitui por dados fake consistentes
    """
    file_content = await file.read()
    validate_file(file, content_bytes=file_content)
    safe_name = sanitize_filename(file.filename or "upload")
    job_id = str(uuid.uuid4())

    # Salvar arquivo
    input_path = settings.UPLOAD_DIR / f"{job_id}_{safe_name}"
    output_dir = settings.UPLOAD_DIR

    try:
        with open(input_path, "wb") as f:
            f.write(file_content)

        # Processar documento (bloqueante → thread pool)
        import functools
        result = await _run_pipeline_in_executor(
            functools.partial(
                get_pipeline().process,
                output_dir=output_dir,
                usuario=None,
                ip_origem=request.client.host if request.client else None,
                mode=mode,
                ner_mode=ner_mode,
            ),
            input_path,
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
                "X-Processing-Time-Ms": str(result.tempo_processamento_ms),
                "X-Anonymization-Mode": mode or settings.ANONYMIZATION_MODE
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao processar documento job={job_id}: {type(e).__name__}: {e}")
        raise HTTPException(500, f"Erro ao processar documento: {type(e).__name__}")

    finally:
        # Limpar arquivo de input (output mantido para auditoria com TTL externo)
        if input_path.exists():
            try:
                input_path.unlink()
            except OSError:
                pass


@router.post("/anonymize/json", response_model=AnonymizeResponse)
@limiter.limit(settings.RATE_LIMIT)
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
    # FIX: ler conteúdo antes para validar magic bytes corretamente
    content = await file.read()
    validate_file(file, content_bytes=content)
    safe_name = sanitize_filename(file.filename or "upload")
    job_id = str(uuid.uuid4())

    # Salvar arquivo
    input_path = settings.UPLOAD_DIR / f"{job_id}_{safe_name}"
    output_dir = settings.UPLOAD_DIR

    try:
        with open(input_path, "wb") as f:
            f.write(content)

        import functools
        result = await _run_pipeline_in_executor(
            functools.partial(
                get_pipeline().process,
                output_dir=output_dir,
                usuario=None,
                ip_origem=request.client.host if request.client else None,
            ),
            input_path,
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao processar JSON job={job_id}: {type(e).__name__}: {e}")
        raise HTTPException(500, f"Erro ao processar documento: {type(e).__name__}")

    finally:
        if input_path.exists():
            try:
                input_path.unlink()
            except OSError:
                pass


@router.get("/download/{job_id}")
async def download_anonymized(job_id: str):
    """
    Baixa um arquivo anonimizado pelo job_id.
    Busca pelo job_id no log de auditoria e depois no disco.
    """
    # FIX: buscar via audit log index (O(1)) e localizar arquivo por job_id no nome
    log = audit_logger.get_log(job_id)
    if not log:
        raise HTTPException(404, "Job não encontrado no log de auditoria")

    # Procurar arquivo pelo nome registrado no log
    file_path = settings.UPLOAD_DIR / log.arquivo_anonimizado
    if not file_path.exists():
        # Tentar encontrar por glob (nome pode ter sufixo diferente)
        candidates = list(settings.UPLOAD_DIR.glob(f"{job_id}*_anonimizado.pdf")) + \
                     list(settings.UPLOAD_DIR.glob(f"{job_id}*_pseudonimizado.pdf"))
        if not candidates:
            raise HTTPException(404, "Arquivo anonimizado não encontrado em disco")
        file_path = candidates[0]

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/pdf"
    )


# FIX: /audit/stats DEVE vir ANTES de /audit/{job_id} para não ser interpretado como job_id
@router.get("/audit/stats")
async def get_audit_stats():
    """
    Retorna estatísticas gerais de auditoria.
    """
    return audit_logger.get_statistics()


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


@router.get("/progress/{job_id}")
async def stream_progress(job_id: str):
    """
    Stream de progresso em tempo real (Server-Sent Events).

    Uso no frontend:
        const evtSource = new EventSource('/api/progress/{job_id}');
        evtSource.onmessage = (e) => { console.log(JSON.parse(e.data)); };
    """
    async def event_generator():
        queue = progress_manager.register_listener(job_id)
        try:
            while True:
                try:
                    # Aguardar update com timeout de 30s
                    update = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(update.to_dict())}\n\n"

                    # Se chegou a 100%, finalizar stream
                    if update.porcentagem >= 100:
                        yield f"data: {json.dumps({'done': True})}\n\n"
                        break
                except asyncio.TimeoutError:
                    # Enviar heartbeat para manter conexão viva
                    yield f": heartbeat\n\n"
        finally:
            progress_manager.unregister_listener(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/progress/{job_id}/status")
async def get_progress_status(job_id: str):
    """
    Obtém status atual do progresso (polling alternativo ao SSE).
    """
    progress = progress_manager.get(job_id)
    if not progress:
        return {"status": "not_found", "job_id": job_id}
    return progress.to_dict()
