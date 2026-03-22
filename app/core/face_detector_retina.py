"""
Detector de rostos usando RetinaFace (InsightFace) — SOTA 2024/2025.

Substitui o OpenCV DNN (SSD ResNet-10 de 2017) por uma abordagem
neural moderna com F1 > 0.95 no benchmark WIDER FACE.

Vantagens sobre o detector anterior:
- Detecta rostos pequenos e parcialmente ocluídos (comum em fotos 3x4 de documentos)
- Robusto a baixa resolução e digitalização com ruído
- Modelos ONNX — sem dependência de Caffe/TensorFlow
- Detecta também pontos de referência faciais (olhos, nariz, boca)

Requisito: pip install insightface onnxruntime
           (ou pip install -r requirements-visual.txt)
"""
import logging

import numpy as np
from PIL import Image

from app.core.face_detector import FaceArea
from app.config import settings

logger = logging.getLogger(__name__)


class RetinaFaceDetector:
    """
    Detector de rostos usando RetinaFace via InsightFace.

    A carga do modelo é lazy (primeira chamada). O modelo `buffalo_sc`
    (~85MB, baixado automaticamente) é otimizado para CPU e documentos
    com fotos de tamanho passaporte/3x4.
    """

    def __init__(
        self,
        confidence_threshold: float = None,
        det_size: tuple[int, int] = (640, 640),
    ):
        self.confidence_threshold = confidence_threshold or settings.FACE_CONFIDENCE
        self.det_size = det_size
        self._app = None
        self.is_available = self._check_import()

    # ------------------------------------------------------------------
    # Verificação de disponibilidade
    # ------------------------------------------------------------------

    def _check_import(self) -> bool:
        """Verifica se insightface e onnxruntime estão instalados."""
        try:
            import insightface  # noqa: F401
            import onnxruntime  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "insightface não instalado — usando OpenCV DNN como fallback. "
                "Para RetinaFace: pip install insightface onnxruntime"
            )
            return False

    # ------------------------------------------------------------------
    # Carregamento de modelo (lazy)
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Carrega o modelo RetinaFace na primeira chamada."""
        if self._app is not None:
            return

        logger.info("Carregando modelo RetinaFace (buffalo_sc, ~85MB)...")
        try:
            from insightface.app import FaceAnalysis

            self._app = FaceAnalysis(
                name="buffalo_sc",
                # Carregar apenas o módulo de detecção (sem reconhecimento)
                allowed_modules=["detection"],
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            self._app.prepare(ctx_id=0, det_size=self.det_size)
            logger.info("RetinaFace carregado com sucesso")
        except Exception as exc:
            logger.error(f"Erro ao carregar RetinaFace: {exc}")
            self.is_available = False

    # ------------------------------------------------------------------
    # Detecção
    # ------------------------------------------------------------------

    def detect_faces(
        self,
        image: np.ndarray,
        page_num: int = 1,
    ) -> list[FaceArea]:
        """
        Detecta rostos em uma imagem numpy (RGB).

        Args:
            image: Array numpy em formato RGB (H, W, 3)
            page_num: Número da página para preencher FaceArea.pagina

        Returns:
            Lista de FaceArea com bounding boxes e scores
        """
        if not self.is_available:
            return []

        self._load_model()
        if not self.is_available:
            return []

        # Garantir RGB
        if len(image.shape) == 2:
            image = np.stack([image] * 3, axis=-1)
        elif image.shape[2] == 4:
            image = image[:, :, :3]

        h, w = image.shape[:2]

        try:
            detected = self._app.get(image)
        except Exception as exc:
            logger.error(f"RetinaFace falhou na página {page_num}: {exc}")
            return []

        faces: list[FaceArea] = []
        for face in detected:
            score = float(face.det_score)
            if score < self.confidence_threshold:
                continue

            x1, y1, x2, y2 = face.bbox.astype(int)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if x2 > x1 and y2 > y1:
                faces.append(FaceArea(
                    pagina=page_num,
                    x=x1,
                    y=y1,
                    largura=x2 - x1,
                    altura=y2 - y1,
                    confianca=score,
                ))

        return faces

    def detect_in_pdf_images(self, images: list[Image.Image]) -> list[FaceArea]:
        """
        Detecta rostos em todas as páginas de um PDF (lista de imagens PIL).

        Args:
            images: Uma imagem PIL por página

        Returns:
            Lista de FaceArea de todas as páginas
        """
        all_faces: list[FaceArea] = []

        for page_num, pil_image in enumerate(images, start=1):
            img_np = np.array(pil_image.convert("RGB"))
            faces = self.detect_faces(img_np, page_num)
            if faces:
                logger.info(
                    f"Página {page_num}: {len(faces)} rosto(s) — RetinaFace"
                )
            all_faces.extend(faces)

        return all_faces
