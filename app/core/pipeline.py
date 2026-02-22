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
        self._ner_engine = None
        self._ocr_engine = None
        self._init_engines()
    
    def _init_engines(self, ner_mode: Optional[str] = None):
        """Inicializa os engines de NER e OCR baseado nas configurações."""
        # NER Engine — resolver modo
        effective_ner = ner_mode or settings.NER_ENGINE
        self._ner_engine = None
        
        # Tentar GLiNER (standard ou deep)
        if effective_ner in ('gliner', 'gliner_deep'):
            try:
                from app.core.ner_gliner import GLiNEREngine
                mode = 'deep' if effective_ner == 'gliner_deep' else 'standard'
                model = (
                    settings.GLINER_DEEP_MODEL if mode == 'deep'
                    else settings.GLINER_MODEL
                )
                self._ner_engine = GLiNEREngine(
                    mode=mode,
                    model_name=model,
                    confidence_threshold=settings.GLINER_CONFIDENCE,
                )
                if self._ner_engine.is_available:
                    logger.info(f"Usando NER com GLiNER ({mode})")
                else:
                    logger.warning("GLiNER não disponível, tentando fallback")
                    self._ner_engine = None
            except ImportError:
                logger.warning("GLiNER não instalado, tentando fallback")
        
        # Fallback para Transformer
        if self._ner_engine is None and effective_ner in ('transformer', 'gliner', 'gliner_deep'):
            try:
                from app.core.ner_transformer import NERTransformerEngine
                self._ner_engine = NERTransformerEngine(
                    model_name=settings.NER_TRANSFORMER_MODEL
                )
                if self._ner_engine.is_available:
                    logger.info("Usando NER com Transformers (BERTimbau)")
                else:
                    self._ner_engine = None
            except ImportError:
                logger.warning("Transformers não disponível")
        
        # Fallback final para SpaCy
        if self._ner_engine is None:
            self._ner_engine = ner_engine
            logger.info("Usando NER com SpaCy")
        
        # OCR Engine
        if settings.OCR_ENGINE == "paddle":
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
        
        # Reinicializar NER se modo diferente do padrão
        if ner_mode:
            ner_mode_map = {'standard': 'gliner', 'deep': 'gliner_deep', 'legacy': 'spacy'}
            effective_ner = ner_mode_map.get(ner_mode, ner_mode)
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
            ner_mode_map = {'standard': 'gliner', 'deep': 'gliner_deep', 'legacy': 'spacy'}
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
                pdf_x, pdf_y, pdf_w, pdf_h = ocr_engine.pixels_to_pdf_points(
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
                    from app.core.face_detector import face_detector
                    
                    face_detector.confidence_threshold = settings.FACE_CONFIDENCE
                    faces = face_detector.detect_in_pdf_images(images)
                    
                    for face in faces:
                        page_idx = face.pagina - 1
                        if page_idx < len(dimensions) and page_idx < len(images):
                            img_w, img_h = images[page_idx].size
                            pdf_w, pdf_h = dimensions[page_idx]
                            
                            # Converter pixels → PDF points
                            scale_x = pdf_w / img_w
                            scale_y = pdf_h / img_h
                            
                            x0 = face.x * scale_x
                            y0 = face.y * scale_y
                            x1 = (face.x + face.largura) * scale_x
                            y1 = (face.y + face.altura) * scale_y
                            
                            visual_items.append(SensitiveDataItem(
                                tipo='ROSTO',
                                valor='[ROSTO DETECTADO]',
                                pagina=face.pagina,
                                x0=x0, y0=y0, x1=x1, y1=y1,
                                confianca=face.confianca,
                                fonte='face',
                            ))
                except Exception as e:
                    logger.warning(f"Erro na detecção de rostos: {e}")
            
            # Detecção de assinaturas
            if settings.DETECT_SIGNATURES:
                try:
                    from app.core.signature_detector import signature_detector
                    
                    signatures = signature_detector.detect_in_pdf_images(images)
                    
                    for sig in signatures:
                        page_idx = sig.pagina - 1
                        if page_idx < len(dimensions) and page_idx < len(images):
                            img_w, img_h = images[page_idx].size
                            pdf_w, pdf_h = dimensions[page_idx]
                            
                            scale_x = pdf_w / img_w
                            scale_y = pdf_h / img_h
                            
                            x0 = sig.x * scale_x
                            y0 = sig.y * scale_y
                            x1 = (sig.x + sig.largura) * scale_x
                            y1 = (sig.y + sig.altura) * scale_y
                            
                            visual_items.append(SensitiveDataItem(
                                tipo='ASSINATURA',
                                valor='[ASSINATURA DETECTADA]',
                                pagina=sig.pagina,
                                x0=x0, y0=y0, x1=x1, y1=y1,
                                confianca=sig.confianca,
                                fonte='signature',
                            ))
                except Exception as e:
                    logger.warning(f"Erro na detecção de assinaturas: {e}")
        
        except ImportError:
            logger.warning("pdf2image não disponível para detecção visual")
        except Exception as e:
            logger.warning(f"Erro na detecção visual: {e}")
        
        return visual_items
    
    def _identify_sensitive_data(
        self,
        texto: str,
        text_items: list[TextBlock]
    ) -> list[SensitiveDataItem]:
        """
        Identifica dados sensíveis usando Regex, NER e Contexto Jurídico.
        """
        results = []
        
        # 0. Análise de Cabeçalho (Header Parsing)
        # Identifica partes (Autor/Réu) para anonimização agressiva
        from app.core.context_validator import context_validator
        priority_names = context_validator.analyze_header(texto)
        
        # Adicionar nomes do cabeçalho como alvos
        for name in priority_names:
            # Buscar ocorrências desse nome no texto
            position = self._find_position_for_text(name, text_items)
            if position:
                # Tentar encontrar todas as ocorrências (simples busca textual aqui)
                # Na implementação real, seria ideal um search_all nos text_items
                results.append(SensitiveDataItem(
                    tipo='PESSOA', # Assumimos pessoa/parte
                    valor=name,
                    pagina=position.pagina,
                    x0=position.x0,
                    y0=position.y0,
                    x1=position.x1,
                    y1=position.y1,
                    confianca=0.95,
                    fonte='header_analysis'
                ))

        # 1. Busca por Regex (CPF, CNPJ, OAB, etc)
        regex_matches = regex_matcher.find_all(texto)
        
        for match in regex_matches:
            # Se for OAB, verificamos contexto (geralmente publico)
            if match.tipo == 'OAB':
                # OAB geralmente não se anonimiza, exceto se solicitado especificamente
                # Vamos manter como detectado, mas o filtro posterior decide
                pass 
                
            position = self._find_position_for_text(match.valor, text_items)
            if position:
                results.append(SensitiveDataItem(
                    tipo=match.tipo,
                    valor=match.valor,
                    pagina=position.pagina,
                    x0=position.x0,
                    y0=position.y0,
                    x1=position.x1,
                    y1=position.y1,
                    confianca=1.0,
                    fonte='regex'
                ))
        
        # 2. Busca por NER (nomes, endereços)
        ner_entities = self._ner_engine.extract_entities(texto)
        
        for entity in ner_entities:
            # Validar contexto para Pessoas e Organizações
            if entity.tipo in ('PESSOA', 'ORGANIZACAO', 'ORG', 'PER'):
                # Usar o validador de contexto
                decision = context_validator.validate(
                    text=texto,
                    entity_text=entity.texto,
                    start_char=entity.inicio,
                    end_char=entity.fim,
                    entity_label=entity.tipo
                )
                
                if not decision.should_anonymize:
                    continue # Pula se o validador disse para manter visível
                
            # Se chegou aqui, é candidato a anonimização
            if entity.tipo in ('PESSOA', 'ENDERECO', 'ORGANIZACAO'):
                position = self._find_position_for_text(entity.texto, text_items)
                if position:
                    results.append(SensitiveDataItem(
                        tipo=entity.tipo,
                        valor=entity.texto,
                        pagina=position.pagina,
                        x0=position.x0,
                        y0=position.y0,
                        x1=position.x1,
                        y1=position.y1,
                        confianca=0.85,
                        fonte='ner'
                    ))
        
        # Remover duplicatas e sobreposições
        return self._deduplicate_results(results)

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
