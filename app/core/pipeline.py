"""
Pipeline principal de anonimização
Orquestra todos os componentes do sistema
"""
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.config import settings
from app.core.pdf_handler import pdf_handler, TextBlock
from app.core.ocr_engine import ocr_engine, OCRBox
from app.core.regex_matcher import regex_matcher, RegexMatch
from app.core.ner_engine import ner_engine, NEREntity
from app.core.allowlist import allowlist_manager
from app.core.redactor import redactor, RedactionArea
from app.audit.logger import audit_logger

logger = logging.getLogger(__name__)


@dataclass
class SensitiveDataItem:
    """Item de dado sensível identificado"""
    tipo: str
    valor: str
    pagina: int
    x0: float
    y0: float
    x1: float
    y1: float
    confianca: float
    fonte: str  # 'regex', 'ner', 'gliner', 'face', 'signature'


@dataclass
class AnonymizationResult:
    """Resultado da anonimização"""
    job_id: str
    arquivo_original: Path
    arquivo_anonimizado: Path
    tipo_pdf: str
    total_paginas: int
    dados_identificados: list[SensitiveDataItem]
    dados_anonimizados: list[SensitiveDataItem]
    dados_ignorados: list[SensitiveDataItem]  # Na allowlist
    tempo_processamento_ms: int
    hash_original: str
    hash_anonimizado: str


class AnonymizationPipeline:
    """
    Pipeline completo de anonimização de documentos.
    
    Fluxo:
    1. Ingestão: Recebe PDF/DOCX
    2. Triagem: Detecta se é nativo ou imagem
    3. Extração: Extrai texto com posições (direta ou OCR)
    4. Identificação: Regex + NER
    5. Filtro: Remove itens da allowlist
    6. Anonimização: Aplica tarjas ou pseudonimização
    7. Auditoria: Registra operação
    """
    
    def __init__(self):
        # Inicializar engines baseado nas configurações
        self._ner_engine = None        # engine primário
        self._ner_supplementary = None  # engine suplementar (GLiNER sobre o primário)
        self._ocr_engine = None
        self._current_ner_mode = None
        self._init_engines()
    
    def _init_engines(self, ner_mode: Optional[str] = None):
        """
        Inicializa os engines de NER e OCR baseado nas configurações.

        Arquitetura NER (ordem de prioridade recomendada pelo SOTA):
          1. Transformer (BERTimbau) — engine primário, maior F1 em entidades definidas
          2. GLiNER — engine suplementar, captura entidades de cauda longa não cobertas pelo primário
          3. SpaCy — fallback final, sempre disponível

        Para modos legados (gliner, gliner_deep), o GLiNER age como primário (backward compat).
        """
        effective_ner = ner_mode or settings.NER_ENGINE
        self._current_ner_mode = effective_ner
        self._ner_engine = None
        self._ner_supplementary = None

        # --- LLM (Ollama) — modo especial, sem suplementar ---
        if effective_ner == 'llm':
            try:
                from app.core.ner_llm import NERLLMEngine
                engine = NERLLMEngine(
                    model_name=settings.LLM_MODEL,
                    ollama_url=settings.LLM_OLLAMA_URL,
                    timeout=settings.LLM_TIMEOUT,
                    temperature=settings.LLM_TEMPERATURE,
                )
                if engine.is_available:
                    self._ner_engine = engine
                    logger.info(f"NER primário: LLM ({settings.LLM_MODEL} via Ollama)")
                else:
                    logger.warning("Ollama não disponível, usando fallback")
            except Exception as e:
                logger.warning(f"LLM NER não disponível: {e}")

        # --- Transformer (BERTimbau) — primário recomendado ---
        elif effective_ner == 'transformer':
            try:
                from app.core.ner_transformer import NERTransformerEngine
                engine = NERTransformerEngine(model_name=settings.NER_TRANSFORMER_MODEL)
                if engine.is_available:
                    self._ner_engine = engine
                    logger.info(f"NER primário: BERTimbau ({settings.NER_TRANSFORMER_MODEL})")
                else:
                    logger.warning("BERTimbau não disponível, usando fallback")
            except ImportError:
                logger.warning("Transformers não instalado — execute: pip install -r requirements-transformers.txt")

            # GLiNER como camada suplementar (se habilitado e primário disponível)
            if self._ner_engine is not None and settings.NER_GLINER_SUPPLEMENTARY:
                try:
                    from app.core.ner_gliner import GLiNEREngine
                    supp = GLiNEREngine(
                        mode='standard',
                        model_name=settings.GLINER_MODEL,
                        confidence_threshold=settings.GLINER_CONFIDENCE,
                    )
                    if supp.is_available:
                        self._ner_supplementary = supp
                        logger.info("NER suplementar: GLiNER (captura entidades de cauda longa)")
                except ImportError:
                    logger.warning("GLiNER não disponível para camada suplementar")

        # --- GLiNER como primário (modos legados, backward compat) ---
        elif effective_ner in ('gliner', 'gliner_deep'):
            try:
                from app.core.ner_gliner import GLiNEREngine
                mode = 'deep' if effective_ner == 'gliner_deep' else 'standard'
                model = settings.GLINER_DEEP_MODEL if mode == 'deep' else settings.GLINER_MODEL
                engine = GLiNEREngine(
                    mode=mode,
                    model_name=model,
                    confidence_threshold=settings.GLINER_CONFIDENCE,
                )
                if engine.is_available:
                    self._ner_engine = engine
                    logger.info(f"NER primário: GLiNER ({mode})")
                else:
                    logger.warning("GLiNER não disponível, usando fallback")
            except ImportError:
                logger.warning("GLiNER não instalado")

            # Fallback para Transformer se GLiNER indisponível
            if self._ner_engine is None:
                try:
                    from app.core.ner_transformer import NERTransformerEngine
                    engine = NERTransformerEngine(model_name=settings.NER_TRANSFORMER_MODEL)
                    if engine.is_available:
                        self._ner_engine = engine
                        logger.info("NER primário: BERTimbau (fallback do GLiNER)")
                except ImportError:
                    pass

        # --- SpaCy — fallback final ---
        if self._ner_engine is None:
            self._ner_engine = ner_engine
            logger.info("NER primário: SpaCy (fallback)")
        
        # OCR Engine — prioridade: surya > paddle > tesseract
        if settings.OCR_ENGINE == "surya":
            try:
                from app.core.ocr_surya import SuryaOCREngine
                self._ocr_engine = SuryaOCREngine()
                if self._ocr_engine.is_available:
                    logger.info("Usando OCR com Surya (SOTA)")
                else:
                    self._ocr_engine = None
            except ImportError:
                logger.warning("surya-ocr não instalado, tentando fallback")

        if self._ocr_engine is None and settings.OCR_ENGINE == "paddle":
            try:
                from app.core.ocr_paddle import PaddleOCREngine
                self._ocr_engine = PaddleOCREngine()
                if self._ocr_engine.is_available:
                    logger.info("Usando OCR com PaddleOCR")
                else:
                    self._ocr_engine = None
            except ImportError:
                logger.warning("PaddleOCR não disponível, usando Tesseract")

        if self._ocr_engine is None:
            self._ocr_engine = ocr_engine
            logger.info("Usando OCR com Tesseract")
    
    def process(
        self,
        input_path: Path,
        output_dir: Optional[Path] = None,
        usuario: Optional[str] = None,
        ip_origem: Optional[str] = None,
        mode: Optional[str] = None,  # 'redact' | 'pseudonymize'
        ner_mode: Optional[str] = None,  # 'standard' | 'deep' | 'legacy'
    ) -> AnonymizationResult:
        """
        Processa um documento completo.
        
        Args:
            input_path: Caminho do arquivo de entrada
            output_dir: Diretório de saída (default: mesmo do input)
            usuario: Usuário executando (para auditoria)
            ip_origem: IP de origem (para auditoria)
            mode: Modo de anonimização ('redact' ou 'pseudonymize')
            
        Returns:
            AnonymizationResult com detalhes do processamento
        """
        start_time = time.time()
        job_id = str(uuid.uuid4())
        
        # Reinicializar NER se modo diferente do atual
        if ner_mode:
            ner_mode_map = {'standard': 'transformer', 'deep': 'gliner_deep', 'legacy': 'spacy', 'llm': 'llm'}
            effective_ner = ner_mode_map.get(ner_mode, ner_mode)
            if effective_ner != self._current_ner_mode:
                self._init_engines(ner_mode=effective_ner)
        
        # Definir modo de anonimização
        anonymization_mode = mode or settings.ANONYMIZATION_MODE
        
        # Definir caminho de saída
        if output_dir is None:
            output_dir = input_path.parent
        
        suffix = "_pseudonimizado" if anonymization_mode == "pseudonymize" else "_anonimizado"
        output_path = output_dir / f"{input_path.stem}{suffix}.pdf"
        
        # 1. Obter informações do PDF
        pdf_info = pdf_handler.get_info(input_path)
        
        # 2. Extrair texto com posições
        if pdf_info.tipo == 'nativo':
            text_items = self._extract_native(input_path)
            texto_completo = '\n'.join(item.texto for item in text_items)
        else:
            try:
                text_items = self._extract_ocr(input_path)
                texto_completo = self._ocr_engine.get_full_text(
                    [OCRBox(
                        texto=item.texto,
                        pagina=item.pagina,
                        x=int(item.x0),
                        y=int(item.y0),
                        largura=int(item.x1 - item.x0),
                        altura=int(item.y1 - item.y0),
                        confianca=0.9
                    ) for item in text_items]
                )
            except Exception as ocr_err:
                logger.warning(
                    f"OCR falhou ({ocr_err}), usando extração nativa como fallback"
                )
                text_items = self._extract_native(input_path)
                texto_completo = '\n'.join(item.texto for item in text_items)
        
        # 3. Identificar dados sensíveis (texto)
        dados_identificados = self._identify_sensitive_data(
            texto_completo, text_items
        )
        
        # 3b. Detecção visual (rostos e assinaturas em scans)
        if pdf_info.tipo == 'imagem':
            visual_areas = self._detect_visual_pii(input_path)
            dados_identificados.extend(visual_areas)
        
        # 4. Filtrar allowlist
        dados_anonimizar = []
        dados_ignorados = []
        
        for item in dados_identificados:
            if item.tipo == 'PESSOA' and allowlist_manager.is_allowed(item.valor):
                dados_ignorados.append(item)
            else:
                dados_anonimizar.append(item)
        
        # 5. Aplicar anonimização (redact ou pseudonymize)
        areas = [
            RedactionArea(
                pagina=item.pagina,
                x0=item.x0,
                y0=item.y0,
                x1=item.x1,
                y1=item.y1,
                tipo=item.tipo,
                valor_original=item.valor
            )
            for item in dados_anonimizar
        ]
        
        if areas:
            if anonymization_mode == "pseudonymize":
                stats = redactor.pseudonymize_pdf(input_path, output_path, areas, job_id)
            else:
                stats = redactor.redact_pdf(input_path, output_path, areas)
        else:
            # Se não há nada a anonimizar, apenas copiar e limpar metadados
            pdf_handler.remove_metadata(input_path, output_path)
            stats = {'total_redacoes': 0, 'por_tipo': {}, 'por_pagina': {}}
        
        # 6. Calcular tempo e hashes
        tempo_ms = int((time.time() - start_time) * 1000)
        hash_original = audit_logger.calculate_hash(input_path)
        hash_anonimizado = audit_logger.calculate_hash(output_path)
        
        # 7. Registrar auditoria
        regras_aplicadas = list(set(item.tipo for item in dados_anonimizar))
        
        audit_logger.log_anonymization(
            job_id=job_id,
            arquivo_original=input_path,
            arquivo_anonimizado=output_path,
            total_redacoes=len(dados_anonimizar),
            regras_aplicadas=regras_aplicadas,
            dados_anonimizados=[
                {'tipo': item.tipo, 'valor': item.valor[:3] + '***'}
                for item in dados_anonimizar
            ],
            tempo_processamento_ms=tempo_ms,
            usuario=usuario,
            ip_origem=ip_origem
        )
        
        return AnonymizationResult(
            job_id=job_id,
            arquivo_original=input_path,
            arquivo_anonimizado=output_path,
            tipo_pdf=pdf_info.tipo,
            total_paginas=pdf_info.total_paginas,
            dados_identificados=dados_identificados,
            dados_anonimizados=dados_anonimizar,
            dados_ignorados=dados_ignorados,
            tempo_processamento_ms=tempo_ms,
            hash_original=hash_original,
            hash_anonimizado=hash_anonimizado
        )
    
    def analyze_only(
        self,
        input_path: Path,
        ner_mode: Optional[str] = None,
    ) -> list[SensitiveDataItem]:
        """
        Apenas identifica dados sensíveis sem anonimizar.
        Útil para preview.
        
        Args:
            input_path: Caminho do arquivo
            ner_mode: Override do modo NER ('standard', 'deep', 'legacy')
            
        Returns:
            Lista de dados sensíveis identificados
        """
        # Reinicializar NER se modo diferente
        if ner_mode:
            ner_mode_map = {'standard': 'transformer', 'deep': 'gliner_deep', 'legacy': 'spacy', 'llm': 'llm'}
            effective_ner = ner_mode_map.get(ner_mode, ner_mode)
            self._init_engines(ner_mode=effective_ner)
        pdf_info = pdf_handler.get_info(input_path)
        
        if pdf_info.tipo == 'nativo':
            text_items = self._extract_native(input_path)
            texto_completo = '\n'.join(item.texto for item in text_items)
        else:
            try:
                text_items = self._extract_ocr(input_path)
                texto_completo = self._ocr_engine.get_full_text(
                    [OCRBox(
                        texto=item.texto,
                        pagina=item.pagina,
                        x=int(item.x0),
                        y=int(item.y0),
                        largura=int(item.x1 - item.x0),
                        altura=int(item.y1 - item.y0),
                        confianca=0.9
                    ) for item in text_items]
                )
            except Exception as ocr_err:
                logger.warning(
                    f"OCR falhou ({ocr_err}), usando extração nativa como fallback"
                )
                text_items = self._extract_native(input_path)
                texto_completo = '\n'.join(item.texto for item in text_items)
        
        dados = self._identify_sensitive_data(texto_completo, text_items)
        
        # Detecção visual em scans
        if pdf_info.tipo == 'imagem':
            visual_areas = self._detect_visual_pii(input_path)
            dados.extend(visual_areas)
        
        return dados
    
    def _extract_native(self, pdf_path: Path) -> list[TextBlock]:
        """Extrai texto de PDF nativo com posições"""
        return pdf_handler.extract_words_with_positions(pdf_path)
    
    def _extract_ocr(self, pdf_path: Path) -> list[TextBlock]:
        """Extrai texto via OCR com posições"""
        ocr_results = self._ocr_engine.process_pdf(pdf_path)
        
        # Converter OCRBox para TextBlock
        # Precisamos das dimensões da página para conversão de coordenadas
        dimensions = pdf_handler.get_page_dimensions(pdf_path)
        
        text_blocks = []
        for box in ocr_results:
            page_idx = box.pagina - 1
            if page_idx < len(dimensions):
                # Calcular altura da página em pixels
                # Assumindo DPI padrão do OCR
                page_height_pixels = int(dimensions[page_idx][1] * settings.OCR_DPI / 72)
                
                # Converter coordenadas
                pdf_x, pdf_y, pdf_w, pdf_h = self._ocr_engine.pixels_to_pdf_points(
                    box.x, box.y, box.largura, box.altura, page_height_pixels
                )
                
                text_blocks.append(TextBlock(
                    texto=box.texto,
                    pagina=box.pagina,
                    x0=pdf_x,
                    y0=pdf_y,
                    x1=pdf_x + pdf_w,
                    y1=pdf_y + pdf_h
                ))
        
        return text_blocks
    
    def _detect_visual_pii(self, pdf_path: Path) -> list[SensitiveDataItem]:
        """
        Detecta PII visual em documentos escaneados (rostos e assinaturas).
        
        Args:
            pdf_path: Caminho do PDF escaneado
            
        Returns:
            Lista de SensitiveDataItem para áreas visuais detectadas
        """
        visual_items = []
        
        try:
            from pdf2image import convert_from_path
            
            images = convert_from_path(pdf_path, dpi=settings.OCR_DPI)
            dimensions = pdf_handler.get_page_dimensions(pdf_path)
            
            # Detecção de rostos
            if settings.DETECT_FACES:
                try:
                    faces = self._get_face_detector().detect_in_pdf_images(images)
                    visual_items.extend(
                        self._scale_visual_items(faces, images, dimensions, 'ROSTO', 'face')
                    )
                except Exception as e:
                    logger.warning(f"Erro na detecção de rostos: {e}")

            # Detecção de assinaturas e carimbos
            if settings.DETECT_SIGNATURES:
                try:
                    sigs = self._get_signature_detector().detect_in_pdf_images(images)
                    # SignatureYOLOArea tem .tipo; SignatureArea usa 'ASSINATURA' fixo
                    for sig in sigs:
                        tipo = getattr(sig, 'tipo', 'ASSINATURA')
                        visual_items.extend(
                            self._scale_visual_items(
                                [sig], images, dimensions, tipo, 'signature'
                            )
                        )
                except Exception as e:
                    logger.warning(f"Erro na detecção de assinaturas/carimbos: {e}")
        
        except ImportError:
            logger.warning("pdf2image não disponível para detecção visual")
        except Exception as e:
            logger.warning(f"Erro na detecção visual: {e}")
        
        return visual_items
    
    # ------------------------------------------------------------------
    # Detectores visuais — factory com fallback
    # ------------------------------------------------------------------

    def _get_face_detector(self):
        """
        Retorna o melhor detector de rostos disponível.
        Prioridade: RetinaFace (InsightFace) → OpenCV DNN
        """
        if settings.FACE_DETECTOR == "retina":
            try:
                from app.core.face_detector_retina import RetinaFaceDetector
                det = RetinaFaceDetector(
                    confidence_threshold=settings.FACE_CONFIDENCE
                )
                if det.is_available:
                    return det
                logger.info("RetinaFace indisponível — usando OpenCV DNN como fallback")
            except ImportError:
                pass

        from app.core.face_detector import FaceDetector
        det = FaceDetector(confidence_threshold=settings.FACE_CONFIDENCE)
        return det

    def _get_signature_detector(self):
        """
        Retorna o melhor detector de assinaturas/carimbos disponível.
        Prioridade: YOLOv8 (se modelo configurado) → heurístico por contornos
        """
        if settings.SIGNATURE_DETECTOR == "yolo":
            try:
                from app.core.signature_detector_yolo import SignatureDetectorYOLO
                det = SignatureDetectorYOLO(
                    model_path=settings.SIGNATURE_YOLO_MODEL or None,
                    confidence_threshold=0.4,
                )
                if det.is_available:
                    return det
                # is_available=False quando modelo não está configurado — fallback silencioso
            except ImportError:
                logger.info("ultralytics não instalado — usando detector por contornos")

        from app.core.signature_detector import signature_detector
        return signature_detector

    def _scale_visual_items(
        self,
        detections: list,
        images: list,
        dimensions: list[tuple[float, float]],
        tipo: str,
        fonte: str,
    ) -> list[SensitiveDataItem]:
        """
        Converte detecções visuais (coordenadas em pixels) para
        SensitiveDataItem (coordenadas em PDF points).

        Args:
            detections: Lista de FaceArea, SignatureArea ou SignatureYOLOArea
            images: Imagens PIL das páginas
            dimensions: Dimensões de cada página em PDF points
            tipo: Tipo para SensitiveDataItem (ex: 'ROSTO', 'ASSINATURA')
            fonte: Fonte para SensitiveDataItem (ex: 'face', 'signature')
        """
        items: list[SensitiveDataItem] = []
        for det in detections:
            page_idx = det.pagina - 1
            if page_idx >= len(dimensions) or page_idx >= len(images):
                continue

            img_w, img_h = images[page_idx].size
            pdf_w, pdf_h = dimensions[page_idx]

            scale_x = pdf_w / img_w
            scale_y = pdf_h / img_h

            items.append(SensitiveDataItem(
                tipo=tipo,
                valor=f"[{tipo} DETECTADO]",
                pagina=det.pagina,
                x0=det.x * scale_x,
                y0=det.y * scale_y,
                x1=(det.x + det.largura) * scale_x,
                y1=(det.y + det.altura) * scale_y,
                confianca=det.confianca,
                fonte=fonte,
            ))
        return items

    def _identify_sensitive_data(
        self,
        texto: str,
        text_items: list[TextBlock]
    ) -> list[SensitiveDataItem]:
        """
        Identifica dados sensíveis usando Regex + NER primário + NER suplementar.

        Fluxo:
          0. Header parsing — nomes de partes identificados no cabeçalho
          1. Regex — CPF, CNPJ, e-mail, telefone, etc. (precisão ~1.0)
          2. NER primário (BERTimbau) — nomes, endereços, organizações
          3. NER suplementar (GLiNER) — entidades não cobertas pelo primário
        """
        from app.core.context_validator import context_validator

        results = []

        # 0. Análise de Cabeçalho — partes processuais (Autor/Réu)
        priority_names = context_validator.analyze_header(texto)
        for name in priority_names:
            position = self._find_position_for_text(name, text_items)
            if position:
                results.append(SensitiveDataItem(
                    tipo='PESSOA',
                    valor=name,
                    pagina=position.pagina,
                    x0=position.x0, y0=position.y0,
                    x1=position.x1, y1=position.y1,
                    confianca=0.95,
                    fonte='header_analysis',
                ))

        # 1. Regex — dados estruturados (CPF, CNPJ, OAB, e-mail, telefone…)
        TIPO_MAP = {'PESSOA_CONTEXTO': 'PESSOA'}
        for match in regex_matcher.find_all(texto):
            tipo_normalizado = TIPO_MAP.get(match.tipo, match.tipo)
            position = self._find_position_for_text(match.valor, text_items)
            if position:
                results.append(SensitiveDataItem(
                    tipo=tipo_normalizado,
                    valor=match.valor,
                    pagina=position.pagina,
                    x0=position.x0, y0=position.y0,
                    x1=position.x1, y1=position.y1,
                    confianca=1.0,
                    fonte='regex',
                ))

        # 2. NER primário (BERTimbau / GLiNER / SpaCy)
        primary_entities = self._ner_engine.extract_entities(texto)
        results.extend(
            self._process_ner_entities(primary_entities, texto, text_items, fonte='ner')
        )

        # 3. NER suplementar (GLiNER) — adiciona apenas o que o primário não cobriu
        if self._ner_supplementary is not None:
            supp_entities = self._ner_supplementary.extract_entities(texto)

            # Excluir entidades que sobrepõem spans já detectados pelo primário
            primary_spans = [(e.inicio, e.fim) for e in primary_entities]
            non_overlapping = [
                e for e in supp_entities
                if not any(
                    e.inicio < p_fim and e.fim > p_inicio
                    for (p_inicio, p_fim) in primary_spans
                )
            ]

            if non_overlapping:
                logger.debug(
                    f"GLiNER suplementar adicionou {len(non_overlapping)} entidades "
                    f"não cobertas pelo primário"
                )
            results.extend(
                self._process_ner_entities(
                    non_overlapping, texto, text_items, fonte='ner_gliner'
                )
            )

        return self._deduplicate_results(results)

    def _process_ner_entities(
        self,
        entities: list,
        texto: str,
        text_items: list[TextBlock],
        fonte: str = 'ner',
    ) -> list[SensitiveDataItem]:
        """
        Aplica validação de contexto jurídico e localização de posição
        a uma lista de entidades NER (compatível com qualquer engine).

        Args:
            entities: Lista de entidades (NEREntity, TransformerEntity ou GLiNEREntity)
            texto: Texto completo do documento
            text_items: Blocos de texto com posições para localização
            fonte: Identificador da origem ('ner', 'ner_gliner', etc.)

        Returns:
            Lista de SensitiveDataItem prontos para redação
        """
        from app.core.context_validator import context_validator

        results = []
        for entity in entities:
            # Validação de contexto para pessoas e organizações
            if entity.tipo in ('PESSOA', 'ORGANIZACAO', 'ORG', 'PER'):
                decision = context_validator.validate(
                    text=texto,
                    entity_text=entity.texto,
                    start_char=entity.inicio,
                    end_char=entity.fim,
                    entity_label=entity.tipo,
                )
                if not decision.should_anonymize:
                    continue

            # Filtrar apenas tipos que o sistema anonimiza via NER
            if entity.tipo not in ('PESSOA', 'ENDERECO', 'ORGANIZACAO'):
                continue

            position = self._find_position_for_text(entity.texto, text_items)
            if position:
                results.append(SensitiveDataItem(
                    tipo=entity.tipo,
                    valor=entity.texto,
                    pagina=position.pagina,
                    x0=position.x0, y0=position.y0,
                    x1=position.x1, y1=position.y1,
                    confianca=0.85,
                    fonte=fonte,
                ))

        return results

    def _deduplicate_results(self, results: list[SensitiveDataItem]) -> list[SensitiveDataItem]:
        """Remove duplicatas baseadas em posição e valor"""
        seen = set()
        unique = []
        for item in results:
            # Chave única aproximada (valor + pagina + coordenadas arredondadas)
            key = (
                item.valor.lower(), 
                item.pagina, 
                round(item.x0), 
                round(item.y0)
            )
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique
    
    def _find_position_for_text(
        self,
        search_text: str,
        text_items: list[TextBlock]
    ) -> Optional[TextBlock]:
        """
        Encontra a posição de um texto nos itens extraídos.
        
        Args:
            search_text: Texto a buscar
            text_items: Itens de texto com posições
            
        Returns:
            TextBlock com a posição, ou None se não encontrado
        """
        search_lower = search_text.lower().strip()
        
        # Busca exata
        for item in text_items:
            if item.texto.lower().strip() == search_lower:
                return item
        
        # Busca parcial (texto contido)
        for item in text_items:
            if search_lower in item.texto.lower():
                return item
        
        # Busca por partes (para textos quebrados em múltiplos blocos)
        words = search_text.split()
        if len(words) > 1:
            first_word = words[0].lower()
            for item in text_items:
                if item.texto.lower().startswith(first_word):
                    return item
        
        return None


# Singleton para uso global
pipeline = AnonymizationPipeline()
