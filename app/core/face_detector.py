"""
Detector de Rostos em Documentos Escaneados
Usa OpenCV DNN para detectar e marcar rostos para anonimização.
Importante para LGPD: rosto é dado biométrico (Art. 5°, II).
"""
import logging
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


# Diretório para cachear modelos DNN
MODELS_DIR = Path(__file__).parent.parent.parent / "data" / "models"


@dataclass
class FaceArea:
    """Região de rosto detectada"""
    pagina: int
    x: int
    y: int
    largura: int
    altura: int
    confianca: float


class FaceDetector:
    """
    Detector de rostos usando OpenCV DNN (SSD ResNet-10).
    
    Modelo: res10_300x300_ssd — pré-treinado, ~10MB.
    Funciona em CPU sem dependências extras além do OpenCV.
    """
    
    # URLs dos arquivos do modelo (hospedados pelo OpenCV)
    PROTOTXT_URL = (
        "https://raw.githubusercontent.com/opencv/opencv/master/"
        "samples/dnn/face_detector/deploy.prototxt"
    )
    MODEL_URL = (
        "https://raw.githubusercontent.com/opencv/opencv_3rdparty/"
        "dnn_samples_face_detector_20170830/"
        "res10_300x300_ssd_iter_140000.caffemodel"
    )
    
    def __init__(self, confidence_threshold: float = 0.5):
        """
        Args:
            confidence_threshold: Limiar de confiança para detecção (0-1)
        """
        self.confidence_threshold = confidence_threshold
        self._net = None
        self._available = None
    
    @property
    def is_available(self) -> bool:
        """Verifica se o detector está disponível"""
        if self._available is None:
            try:
                self._ensure_model_files()
                self._available = True
            except Exception as e:
                logger.warning(f"Face detector não disponível: {e}")
                self._available = False
        return self._available
    
    def _ensure_model_files(self) -> tuple[Path, Path]:
        """Baixa arquivos do modelo se necessário"""
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        
        prototxt_path = MODELS_DIR / "deploy.prototxt"
        model_path = MODELS_DIR / "res10_300x300_ssd_iter_140000.caffemodel"
        
        if not prototxt_path.exists():
            logger.info("Baixando modelo de detecção de rostos (prototxt)...")
            urllib.request.urlretrieve(self.PROTOTXT_URL, str(prototxt_path))
        
        if not model_path.exists():
            logger.info("Baixando modelo de detecção de rostos (caffemodel ~10MB)...")
            urllib.request.urlretrieve(self.MODEL_URL, str(model_path))
        
        return prototxt_path, model_path
    
    @property
    def net(self):
        """Lazy loading da rede neural"""
        if self._net is None and self.is_available:
            try:
                prototxt_path, model_path = self._ensure_model_files()
                self._net = cv2.dnn.readNetFromCaffe(
                    str(prototxt_path), str(model_path)
                )
                logger.info("Modelo de detecção de rostos carregado")
            except Exception as e:
                logger.error(f"Erro ao carregar modelo de rostos: {e}")
                self._available = False
        return self._net
    
    def detect_faces(
        self,
        image: np.ndarray,
        page_num: int = 1
    ) -> list[FaceArea]:
        """
        Detecta rostos em uma imagem.
        
        Args:
            image: Imagem numpy (BGR ou RGB)
            page_num: Número da página
            
        Returns:
            Lista de FaceArea com bounding boxes dos rostos
        """
        if self.net is None:
            return []
        
        h, w = image.shape[:2]
        
        # Preparar blob para a rede DNN
        blob = cv2.dnn.blobFromImage(
            cv2.resize(image, (300, 300)),
            scalefactor=1.0,
            size=(300, 300),
            mean=(104.0, 177.0, 123.0),
        )
        
        self.net.setInput(blob)
        detections = self.net.forward()
        
        faces = []
        for i in range(detections.shape[2]):
            confidence = float(detections[0, 0, i, 2])
            
            if confidence >= self.confidence_threshold:
                # Coordenadas normalizadas → pixels
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = box.astype(int)
                
                # Garantir limites válidos
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(w, x2)
                y2 = min(h, y2)
                
                if x2 > x1 and y2 > y1:
                    faces.append(FaceArea(
                        pagina=page_num,
                        x=x1,
                        y=y1,
                        largura=x2 - x1,
                        altura=y2 - y1,
                        confianca=confidence,
                    ))
        
        return faces
    
    def detect_in_pdf_images(
        self,
        images: list[Image.Image],
    ) -> list[FaceArea]:
        """
        Detecta rostos em imagens de páginas de PDF.
        
        Args:
            images: Lista de imagens PIL (uma por página)
            
        Returns:
            Lista de FaceArea de todas as páginas
        """
        all_faces = []
        
        for page_num, pil_image in enumerate(images, start=1):
            # Converter PIL → numpy BGR
            img_np = np.array(pil_image)
            if len(img_np.shape) == 3 and img_np.shape[2] == 3:
                img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            else:
                img_bgr = img_np
            
            faces = self.detect_faces(img_bgr, page_num)
            
            if faces:
                logger.info(
                    f"Página {page_num}: {len(faces)} rosto(s) detectado(s)"
                )
            
            all_faces.extend(faces)
        
        return all_faces


# Singleton
face_detector = FaceDetector()
