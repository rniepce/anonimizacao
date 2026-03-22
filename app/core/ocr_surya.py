"""
Motor OCR baseado no Surya — SOTA em OCR open source (2024/2025)

Surya supera o Tesseract de forma significativa em documentos jurídicos:
- Reconhecimento neural end-to-end (sem pipeline de pré-processamento manual)
- Multilingual nativo (incluindo português com acentuação)
- Layout-aware: detecta colunas, tabelas e orientações
- Sem necessidade de binarização, deskew ou denoising manual

Requisito: pip install surya-ocr
Compatível com surya-ocr >= 0.4.0
"""
import logging
from pathlib import Path

from PIL import Image

from app.core.ocr_engine import OCRBox
from app.config import settings

logger = logging.getLogger(__name__)


class SuryaOCREngine:
    """
    Motor OCR usando Surya — melhor OCR open source disponível em 2024/2025.

    Substitui Tesseract e PaddleOCR para documentos escaneados. A cada 1% de
    melhoria na acurácia do OCR há ganho de ~1.5-3% no F1 do NER subsequente,
    tornando esta a troca de maior impacto prático no pipeline.

    A carga dos modelos é lazy (primeira chamada). Em CPU, a inicialização
    demora ~10-30s; chamadas subsequentes são rápidas.
    """

    def __init__(
        self,
        languages: list[str] = None,
        confidence_threshold: float = None,
        dpi: int = None,
    ):
        self.languages = languages or ["pt"]
        self.confidence_threshold = confidence_threshold or (settings.OCR_CONFIDENCE_THRESHOLD / 100.0)
        self.dpi = dpi or settings.OCR_DPI

        # Modelos carregados sob demanda
        self._det_model = None
        self._det_processor = None
        self._rec_model = None
        self._rec_processor = None
        self._api_version: str | None = None  # 'classic' | 'modern'

        self.is_available = self._check_import()

    # ------------------------------------------------------------------
    # Verificação de disponibilidade
    # ------------------------------------------------------------------

    def _check_import(self) -> bool:
        """Verifica se surya-ocr está instalado sem carregar os modelos."""
        try:
            import surya  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "surya-ocr não instalado. "
                "Instale com: pip install surya-ocr  "
                "ou pip install -r requirements-surya.txt"
            )
            return False

    # ------------------------------------------------------------------
    # Carregamento de modelos (lazy)
    # ------------------------------------------------------------------

    def _load_models(self) -> None:
        """Carrega os modelos Surya na primeira chamada (lazy loading)."""
        if self._api_version is not None:
            return  # já carregados

        logger.info("Carregando modelos Surya OCR (primeira execução — pode demorar)...")

        # Tentar API moderna (surya >= 0.7)
        try:
            from surya.recognition import RecognitionPredictor  # type: ignore
            from surya.detection import DetectionPredictor      # type: ignore

            self._det_predictor = DetectionPredictor()
            self._rec_predictor = RecognitionPredictor()
            self._api_version = "modern"
            logger.info("Surya carregado — API moderna (>= 0.7)")
            return
        except (ImportError, AttributeError):
            pass

        # Fallback API clássica (surya 0.4 – 0.6)
        try:
            from surya.model.detection.segformer import (  # type: ignore
                load_model as load_det_model,
                load_processor as load_det_processor,
            )
            from surya.model.recognition.model import load_model as load_rec_model      # type: ignore
            from surya.model.recognition.processor import load_processor as load_rec_proc  # type: ignore

            self._det_processor = load_det_processor()
            self._det_model = load_det_model()
            self._rec_model = load_rec_model()
            self._rec_processor = load_rec_proc()
            self._api_version = "classic"
            logger.info("Surya carregado — API clássica (0.4-0.6)")
            return
        except (ImportError, AttributeError):
            pass

        # Nenhuma API disponível
        logger.error(
            "surya-ocr instalado mas não foi possível carregar os modelos. "
            "Verifique a versão com: pip show surya-ocr"
        )
        self.is_available = False

    # ------------------------------------------------------------------
    # Inferência OCR em uma imagem
    # ------------------------------------------------------------------

    def _run_on_image(self, image: Image.Image) -> list:
        """
        Executa OCR em uma imagem PIL, compatível com múltiplas versões da API.

        Returns:
            Lista de objetos TextLine com atributos .text e .bbox
        """
        if self._api_version == "modern":
            det_result = self._det_predictor([image])
            rec_result = self._rec_predictor([image], [self.languages], det_result)
            return rec_result[0].text_lines if rec_result else []

        # API clássica
        from surya.ocr import run_ocr  # type: ignore
        predictions = run_ocr(
            [image],
            [self.languages],
            self._det_model,
            self._det_processor,
            self._rec_model,
            self._rec_processor,
        )
        return predictions[0].text_lines if predictions else []

    # ------------------------------------------------------------------
    # Interface pública (mesma que OCREngine e PaddleOCREngine)
    # ------------------------------------------------------------------

    def process_pdf(self, pdf_path: Path) -> list[OCRBox]:
        """
        Processa todas as páginas de um PDF escaneado com Surya OCR.

        Args:
            pdf_path: Caminho para o arquivo PDF

        Returns:
            Lista de OCRBox com texto e posições em pixels
        """
        if not self.is_available:
            return []

        self._load_models()
        if not self.is_available:
            return []

        from pdf2image import convert_from_path

        images = convert_from_path(str(pdf_path), dpi=self.dpi)

        results: list[OCRBox] = []
        for page_num, image in enumerate(images, start=1):
            logger.info(f"Surya OCR — página {page_num}/{len(images)}")
            page_boxes = self.process_image(image, page_num)
            results.extend(page_boxes)

        return results

    def process_image(self, image: Image.Image, page_num: int = 1) -> list[OCRBox]:
        """
        Processa uma única imagem PIL.

        Args:
            image: Imagem PIL (RGB ou L)
            page_num: Número da página (1-based)

        Returns:
            Lista de OCRBox
        """
        if not self.is_available:
            return []

        self._load_models()
        if not self.is_available:
            return []

        # Surya aceita RGB diretamente — sem necessidade de pré-processamento
        if image.mode != "RGB":
            image = image.convert("RGB")

        try:
            text_lines = self._run_on_image(image)
        except Exception as exc:
            logger.error(f"Surya OCR falhou na página {page_num}: {exc}")
            return []

        boxes: list[OCRBox] = []
        for line in text_lines:
            text = line.text.strip() if hasattr(line, "text") else ""
            confidence = float(getattr(line, "confidence", 1.0))

            if not text or confidence < self.confidence_threshold:
                continue

            # bbox = [x1, y1, x2, y2] em pixels (canto superior esquerdo → inferior direito)
            bbox = line.bbox
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])

            boxes.append(OCRBox(
                texto=text,
                pagina=page_num,
                x=x1,
                y=y1,
                largura=max(1, x2 - x1),
                altura=max(1, y2 - y1),
                confianca=confidence,
            ))

        return boxes

    def get_full_text(self, boxes: list[OCRBox]) -> str:
        """
        Reconstrói o texto completo a partir dos OCRBoxes, ordenados por
        página e posição vertical/horizontal.

        Args:
            boxes: Lista de OCRBox

        Returns:
            Texto completo do documento
        """
        pages: dict[int, list[OCRBox]] = {}
        for box in boxes:
            pages.setdefault(box.pagina, []).append(box)

        lines: list[str] = []
        for page_num in sorted(pages):
            page_boxes = sorted(pages[page_num], key=lambda b: (b.y, b.x))
            lines.extend(box.texto for box in page_boxes)

        return "\n".join(lines)

    def pixels_to_pdf_points(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        page_height_pixels: int,
    ) -> tuple[float, float, float, float]:
        """
        Converte coordenadas de pixels (origem no canto superior esquerdo)
        para pontos PDF (origem no canto inferior esquerdo).

        Fórmula: ponto_PDF = (pixel / DPI) * 72

        Returns:
            (pdf_x, pdf_y, pdf_width, pdf_height)
        """
        scale = 72.0 / self.dpi
        pdf_x = x * scale
        pdf_y = (page_height_pixels - y - height) * scale
        pdf_width = width * scale
        pdf_height = height * scale
        return (pdf_x, pdf_y, pdf_width, pdf_height)
