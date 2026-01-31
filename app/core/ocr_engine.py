"""
Motor OCR para documentos digitalizados
Usa Tesseract com pré-processamento OpenCV
"""
import cv2
import numpy as np
import pytesseract
from dataclasses import dataclass
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image
from typing import Optional

from app.config import settings


@dataclass
class OCRBox:
    """Resultado do OCR com coordenadas"""
    texto: str
    pagina: int
    x: int
    y: int
    largura: int
    altura: int
    confianca: float


class OCREngine:
    """
    Motor de OCR otimizado para documentos jurídicos escaneados.
    Inclui pré-processamento para melhorar qualidade da extração.
    """
    
    def __init__(
        self,
        language: str = None,
        dpi: int = None,
        confidence_threshold: int = None
    ):
        self.language = language or settings.OCR_LANGUAGE
        self.dpi = dpi or settings.OCR_DPI
        self.confidence_threshold = confidence_threshold or settings.OCR_CONFIDENCE_THRESHOLD
        
        # Configuração do Tesseract
        self.tesseract_config = f'--oem 3 --psm 3 -l {self.language}'
    
    def process_pdf(self, pdf_path: Path) -> list[OCRBox]:
        """
        Processa um PDF escaneado e extrai texto com coordenadas.
        
        Args:
            pdf_path: Caminho para o arquivo PDF
            
        Returns:
            Lista de OCRBox com texto e posições
        """
        # Converter PDF para imagens
        images = convert_from_path(str(pdf_path), dpi=self.dpi)
        
        results = []
        for page_num, image in enumerate(images, start=1):
            # Pré-processar imagem
            processed = self._preprocess_image(image)
            
            # Extrair texto com coordenadas
            page_results = self._extract_with_boxes(processed, page_num)
            results.extend(page_results)
        
        return results
    
    def process_image(self, image: Image.Image, page_num: int = 1) -> list[OCRBox]:
        """
        Processa uma única imagem.
        
        Args:
            image: Imagem PIL
            page_num: Número da página
            
        Returns:
            Lista de OCRBox
        """
        processed = self._preprocess_image(image)
        return self._extract_with_boxes(processed, page_num)
    
    def _preprocess_image(self, image: Image.Image) -> np.ndarray:
        """
        Pré-processa imagem para melhorar qualidade do OCR.
        Aplica: conversão para cinza, binarização, correção de rotação.
        
        Args:
            image: Imagem PIL original
            
        Returns:
            Imagem numpy processada
        """
        # Converter para numpy array
        img_np = np.array(image)
        
        # Converter para escala de cinza
        if len(img_np.shape) == 3:
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_np
        
        # Correção de rotação (deskew)
        gray = self._deskew(gray)
        
        # Binarização adaptativa (Otsu)
        thresh = cv2.threshold(
            gray, 0, 255, 
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )[1]
        
        # Remoção de ruído
        denoised = cv2.medianBlur(thresh, 3)
        
        return denoised
    
    def _deskew(self, image: np.ndarray) -> np.ndarray:
        """
        Corrige rotação de documentos escaneados tortos.
        
        Args:
            image: Imagem em escala de cinza
            
        Returns:
            Imagem corrigida
        """
        # Detectar ângulo de rotação usando Tesseract OSD
        try:
            osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
            angle = osd.get('rotate', 0)
            
            if angle != 0:
                # Rotacionar imagem
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                image = cv2.warpAffine(
                    image, M, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE
                )
        except Exception:
            # Se falhar a detecção, retorna imagem original
            pass
        
        return image
    
    def _extract_with_boxes(
        self, 
        image: np.ndarray, 
        page_num: int
    ) -> list[OCRBox]:
        """
        Extrai texto com bounding boxes usando Tesseract.
        
        Args:
            image: Imagem pré-processada
            page_num: Número da página
            
        Returns:
            Lista de OCRBox
        """
        # Extrair dados com coordenadas
        data = pytesseract.image_to_data(
            image,
            config=self.tesseract_config,
            output_type=pytesseract.Output.DICT
        )
        
        results = []
        n_boxes = len(data['text'])
        
        for i in range(n_boxes):
            conf = int(data['conf'][i])
            text = data['text'][i].strip()
            
            # Filtrar por confiança e texto não vazio
            if conf >= self.confidence_threshold and text:
                results.append(OCRBox(
                    texto=text,
                    pagina=page_num,
                    x=data['left'][i],
                    y=data['top'][i],
                    largura=data['width'][i],
                    altura=data['height'][i],
                    confianca=conf / 100.0
                ))
        
        return results
    
    def get_full_text(self, boxes: list[OCRBox]) -> str:
        """
        Concatena o texto de todos os boxes em uma string.
        
        Args:
            boxes: Lista de OCRBox
            
        Returns:
            Texto completo
        """
        # Agrupar por página e linha
        pages = {}
        for box in boxes:
            if box.pagina not in pages:
                pages[box.pagina] = []
            pages[box.pagina].append(box)
        
        # Ordenar por posição Y e então X
        lines = []
        for page_num in sorted(pages.keys()):
            page_boxes = pages[page_num]
            # Ordenar por Y (linha) e então X (coluna)
            page_boxes.sort(key=lambda b: (b.y // 20, b.x))
            
            current_line = []
            current_y = -100
            
            for box in page_boxes:
                # Nova linha se Y mudou significativamente
                if abs(box.y - current_y) > 15:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [box.texto]
                    current_y = box.y
                else:
                    current_line.append(box.texto)
            
            if current_line:
                lines.append(' '.join(current_line))
        
        return '\n'.join(lines)
    
    def pixels_to_pdf_points(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        page_height_pixels: int
    ) -> tuple[float, float, float, float]:
        """
        Converte coordenadas de pixels para pontos PDF.
        
        Fórmula: Ponto_PDF = (Pixel / DPI) * 72
        
        Args:
            x, y, width, height: Coordenadas em pixels
            page_height_pixels: Altura total da página em pixels
            
        Returns:
            Tupla (x, y, width, height) em pontos PDF
        """
        scale = 72.0 / self.dpi
        
        # PDF usa sistema de coordenadas com origem no canto inferior esquerdo
        # OCR usa origem no canto superior esquerdo
        pdf_x = x * scale
        pdf_y = (page_height_pixels - y - height) * scale
        pdf_width = width * scale
        pdf_height = height * scale
        
        return (pdf_x, pdf_y, pdf_width, pdf_height)


# Singleton para uso global
ocr_engine = OCREngine()
