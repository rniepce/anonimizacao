"""
Detector de Assinaturas e Carimbos usando YOLOv8.

Substitui a detecção heurística por contornos (OpenCV) por um modelo
de object detection treinável para o domínio específico de documentos
jurídicos brasileiros.

Classes detectadas:
  0: assinatura  — traços manuscritos de assinatura
  1: carimbo     — selos, carimbos circulares/retangulares

Estado do modelo:
  Não existe modelo pré-treinado público para assinaturas de documentos
  jurídicos brasileiros. Este arquivo estrutura a integração YOLOv8
  para quando um modelo for treinado (ver COMO_TREINAR.md para o
  processo de anotação e treinamento).

  Enquanto não houver modelo treinado em TJMG_SIGNATURE_YOLO_MODEL,
  o sistema usa automaticamente o detector heurístico por contornos
  (signature_detector.py) como fallback.

Requisito: pip install ultralytics  (ou pip install -r requirements-visual.txt)

Como treinar:
  1. Anote assinaturas/carimbos em documentos usando Roboflow ou Label Studio
  2. Exporte no formato YOLOv8 (YOLO txt)
  3. Treine: yolo train model=yolov8n.pt data=signatures.yaml epochs=100
  4. Aponte TJMG_SIGNATURE_YOLO_MODEL para o best.pt gerado
"""
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)

# Mapeamento de índice de classe YOLOv8 → tipo do sistema
CLASS_TO_TIPO = {
    0: "ASSINATURA",
    1: "CARIMBO",
}


@dataclass
class SignatureYOLOArea:
    """Região de assinatura ou carimbo detectada pelo YOLOv8."""
    pagina: int
    x: int
    y: int
    largura: int
    altura: int
    confianca: float
    tipo: str  # 'ASSINATURA' | 'CARIMBO'


class SignatureDetectorYOLO:
    """
    Detector de assinaturas e carimbos usando YOLOv8.

    Quando o modelo personalizado não está disponível, retorna lista vazia
    e o pipeline faz fallback automático para o detector por contornos.

    O modelo esperado deve ser treinado com estas classes:
      0: assinatura
      1: carimbo

    Exemplo de uso com modelo treinado:
        detector = SignatureDetectorYOLO(model_path="data/models/signatures.pt")
        areas = detector.detect_in_pdf_images(images)
    """

    def __init__(
        self,
        model_path: str | Path = None,
        confidence_threshold: float = 0.4,
    ):
        self.model_path = Path(model_path) if model_path else None
        self.confidence_threshold = confidence_threshold
        self._model = None
        self.is_available = self._check_availability()

    # ------------------------------------------------------------------
    # Verificação de disponibilidade
    # ------------------------------------------------------------------

    def _check_availability(self) -> bool:
        """
        Verifica se YOLOv8 está instalado e o modelo existe.

        Ambas as condições são necessárias — sem modelo treinado,
        a detecção não tem utilidade.
        """
        try:
            import ultralytics  # noqa: F401
        except ImportError:
            logger.warning(
                "ultralytics não instalado — detector YOLO indisponível. "
                "Instale com: pip install ultralytics"
            )
            return False

        if not self.model_path or not self.model_path.exists():
            logger.info(
                "Modelo YOLOv8 para assinaturas não configurado. "
                "Defina TJMG_SIGNATURE_YOLO_MODEL com o caminho para um modelo treinado. "
                "Usando detector heurístico por contornos como fallback."
            )
            return False

        return True

    # ------------------------------------------------------------------
    # Carregamento de modelo (lazy)
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Carrega o modelo YOLOv8 na primeira chamada."""
        if self._model is not None:
            return

        logger.info(f"Carregando modelo YOLOv8 de {self.model_path}...")
        try:
            from ultralytics import YOLO
            self._model = YOLO(str(self.model_path))
            logger.info("Modelo YOLOv8 de assinaturas/carimbos carregado")
        except Exception as exc:
            logger.error(f"Erro ao carregar modelo YOLO: {exc}")
            self.is_available = False

    # ------------------------------------------------------------------
    # Detecção
    # ------------------------------------------------------------------

    def detect(
        self,
        image: np.ndarray,
        page_num: int = 1,
    ) -> list[SignatureYOLOArea]:
        """
        Detecta assinaturas e carimbos em uma imagem numpy (RGB).

        Args:
            image: Array numpy em formato RGB (H, W, 3)
            page_num: Número da página

        Returns:
            Lista de SignatureYOLOArea
        """
        if not self.is_available:
            return []

        self._load_model()
        if not self.is_available:
            return []

        h, w = image.shape[:2]

        try:
            results = self._model.predict(
                image,
                conf=self.confidence_threshold,
                verbose=False,
            )
        except Exception as exc:
            logger.error(f"YOLOv8 falhou na página {page_num}: {exc}")
            return []

        areas: list[SignatureYOLOArea] = []
        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                tipo = CLASS_TO_TIPO.get(cls_id, "ASSINATURA")

                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)

                if x2 > x1 and y2 > y1:
                    areas.append(SignatureYOLOArea(
                        pagina=page_num,
                        x=x1,
                        y=y1,
                        largura=x2 - x1,
                        altura=y2 - y1,
                        confianca=conf,
                        tipo=tipo,
                    ))

        return areas

    def detect_in_pdf_images(
        self,
        images: list[Image.Image],
    ) -> list[SignatureYOLOArea]:
        """
        Detecta assinaturas e carimbos em todas as páginas de um PDF.

        Args:
            images: Uma imagem PIL por página

        Returns:
            Lista de SignatureYOLOArea de todas as páginas
        """
        all_areas: list[SignatureYOLOArea] = []

        for page_num, pil_image in enumerate(images, start=1):
            img_np = np.array(pil_image.convert("RGB"))
            areas = self.detect(img_np, page_num)
            if areas:
                tipos = [a.tipo for a in areas]
                logger.info(
                    f"Página {page_num}: {len(areas)} região(ões) detectada(s) — "
                    f"YOLOv8 {tipos}"
                )
            all_areas.extend(areas)

        return all_areas
