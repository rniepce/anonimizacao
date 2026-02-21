"""
Detector de Assinaturas Manuscritas em Documentos Escaneados
Usa análise de contornos com OpenCV (sem modelo ML extra).
"""
import logging
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class SignatureArea:
    """Região de assinatura detectada"""
    pagina: int
    x: int
    y: int
    largura: int
    altura: int
    confianca: float  # Score heurístico (0-1)


class SignatureDetector:
    """
    Detector de assinaturas manuscritas via análise de contornos.
    
    Heurísticas utilizadas:
    1. Região com alta densidade de traços curvos (muitos contornos pequenos)
    2. Aspect ratio típico de assinatura (largo e baixo, ~3:1 a 6:1)
    3. Localização preferencial: metade inferior da página
    4. Densidade de pixels escuros na região (tinta)
    
    Não requer modelo ML — usa apenas OpenCV.
    """
    
    # Parâmetros de detecção
    MIN_CONTOUR_AREA = 50        # Área mínima de contorno individual
    MAX_CONTOUR_AREA = 50000     # Área máxima (evitar blocos de texto)
    MIN_REGION_WIDTH = 80        # Largura mínima da assinatura (px)
    MIN_REGION_HEIGHT = 15       # Altura mínima
    MAX_REGION_HEIGHT = 200      # Altura máxima (evitar parágrafos)
    MIN_ASPECT_RATIO = 1.5       # Assinaturas são mais largas que altas
    MAX_ASPECT_RATIO = 10.0
    MIN_CONTOURS_IN_REGION = 3   # Mínimo de traços na região
    CLUSTER_DISTANCE = 30        # Distância para agrupar contornos (px)
    
    def __init__(self, min_confidence: float = 0.4):
        self.min_confidence = min_confidence
    
    def detect_signatures(
        self,
        image: np.ndarray,
        page_num: int = 1
    ) -> list[SignatureArea]:
        """
        Detecta regiões de assinatura em uma imagem.
        
        Args:
            image: Imagem numpy (BGR ou escala de cinza)
            page_num: Número da página
            
        Returns:
            Lista de SignatureArea
        """
        h, w = image.shape[:2]
        
        # 1. Converter para escala de cinza
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # 2. Binarizar (inverso: tinta branca em fundo preto)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # 3. Encontrar contornos
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        # 4. Filtrar contornos candidatos (traços de assinatura)
        candidate_contours = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if self.MIN_CONTOUR_AREA <= area <= self.MAX_CONTOUR_AREA:
                # Verificar complexidade do contorno (assinaturas são curvas)
                perimeter = cv2.arcLength(cnt, True)
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    # Assinaturas têm baixa circularidade (não são círculos nem quadrados)
                    if circularity < 0.5:
                        candidate_contours.append(cnt)
        
        if not candidate_contours:
            return []
        
        # 5. Agrupar contornos próximos em regiões
        regions = self._cluster_contours(candidate_contours, h, w)
        
        # 6. Avaliar cada região
        signatures = []
        for region in regions:
            x, y, rw, rh, num_contours = region
            
            # Filtros de tamanho
            if rw < self.MIN_REGION_WIDTH or rh < self.MIN_REGION_HEIGHT:
                continue
            if rh > self.MAX_REGION_HEIGHT:
                continue
            
            # Aspect ratio
            aspect_ratio = rw / max(rh, 1)
            if not (self.MIN_ASPECT_RATIO <= aspect_ratio <= self.MAX_ASPECT_RATIO):
                continue
            
            # Mínimo de traços
            if num_contours < self.MIN_CONTOURS_IN_REGION:
                continue
            
            # Calcular score de confiança
            confidence = self._calculate_confidence(
                aspect_ratio, num_contours, y, h, rw, rh, gray[y:y+rh, x:x+rw]
            )
            
            if confidence >= self.min_confidence:
                signatures.append(SignatureArea(
                    pagina=page_num,
                    x=x,
                    y=y,
                    largura=rw,
                    altura=rh,
                    confianca=confidence,
                ))
        
        return signatures
    
    def _cluster_contours(
        self,
        contours: list,
        page_h: int,
        page_w: int,
    ) -> list[tuple]:
        """
        Agrupa contornos próximos em regiões candidatas.
        
        Returns:
            Lista de tuplas (x, y, width, height, num_contours)
        """
        # Bounding boxes de cada contorno
        boxes = [cv2.boundingRect(c) for c in contours]
        
        # Agrupar por proximidade vertical e horizontal
        used = [False] * len(boxes)
        regions = []
        
        for i, (bx, by, bw, bh) in enumerate(boxes):
            if used[i]:
                continue
            
            # Iniciar cluster com este contorno
            cluster_boxes = [(bx, by, bw, bh)]
            used[i] = True
            
            # Buscar vizinhos
            for j, (bx2, by2, bw2, bh2) in enumerate(boxes):
                if used[j]:
                    continue
                
                # Verificar proximidade
                dist_x = min(
                    abs(bx - (bx2 + bw2)),
                    abs(bx2 - (bx + bw)),
                    abs((bx + bw // 2) - (bx2 + bw2 // 2))
                )
                dist_y = abs((by + bh // 2) - (by2 + bh2 // 2))
                
                if dist_x < self.CLUSTER_DISTANCE and dist_y < self.CLUSTER_DISTANCE:
                    cluster_boxes.append((bx2, by2, bw2, bh2))
                    used[j] = True
            
            # Calcular bounding box do cluster
            min_x = min(b[0] for b in cluster_boxes)
            min_y = min(b[1] for b in cluster_boxes)
            max_x = max(b[0] + b[2] for b in cluster_boxes)
            max_y = max(b[1] + b[3] for b in cluster_boxes)
            
            regions.append((
                min_x, min_y,
                max_x - min_x, max_y - min_y,
                len(cluster_boxes)
            ))
        
        return regions
    
    def _calculate_confidence(
        self,
        aspect_ratio: float,
        num_contours: int,
        y: int,
        page_h: int,
        rw: int,
        rh: int,
        roi: np.ndarray,
    ) -> float:
        """
        Calcula score de confiança baseado em múltiplas heurísticas.
        
        Returns:
            Score entre 0 e 1
        """
        scores = []
        
        # 1. Aspect ratio ideal (~3:1 a 5:1)
        if 2.5 <= aspect_ratio <= 5.5:
            scores.append(0.9)
        elif 1.5 <= aspect_ratio <= 7.0:
            scores.append(0.5)
        else:
            scores.append(0.2)
        
        # 2. Posição na página (assinaturas geralmente na parte inferior)
        relative_y = y / max(page_h, 1)
        if relative_y > 0.6:
            scores.append(0.8)
        elif relative_y > 0.4:
            scores.append(0.5)
        else:
            scores.append(0.3)
        
        # 3. Número de traços (assinaturas têm vários traços)
        if num_contours >= 8:
            scores.append(0.9)
        elif num_contours >= 5:
            scores.append(0.7)
        else:
            scores.append(0.4)
        
        # 4. Densidade de pixels escuros (tinta)
        if roi.size > 0:
            dark_ratio = np.sum(roi < 128) / max(roi.size, 1)
            if 0.05 <= dark_ratio <= 0.4:
                scores.append(0.8)  # Densidade típica de assinatura
            else:
                scores.append(0.3)
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def detect_in_pdf_images(
        self,
        images: list[Image.Image],
    ) -> list[SignatureArea]:
        """
        Detecta assinaturas em imagens de páginas de PDF.
        
        Args:
            images: Lista de imagens PIL (uma por página)
            
        Returns:
            Lista de SignatureArea
        """
        all_signatures = []
        
        for page_num, pil_image in enumerate(images, start=1):
            img_np = np.array(pil_image)
            if len(img_np.shape) == 3 and img_np.shape[2] == 3:
                img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            else:
                img_bgr = img_np
            
            sigs = self.detect_signatures(img_bgr, page_num)
            
            if sigs:
                logger.info(
                    f"Página {page_num}: {len(sigs)} assinatura(s) detectada(s)"
                )
            
            all_signatures.extend(sigs)
        
        return all_signatures


# Singleton
signature_detector = SignatureDetector()
