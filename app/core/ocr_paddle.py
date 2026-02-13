"""
Motor OCR com PaddleOCR
Melhor detecção de layouts complexos, tabelas e colunas.
"""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PaddleOCRBox:
    """Resultado do PaddleOCR com coordenadas"""
    texto: str
    pagina: int
    x: int
    y: int
    largura: int
    altura: int
    confianca: float
    # Coordenadas do polígono (4 pontos)
    polygon: Optional[List[List[int]]] = None


class PaddleOCREngine:
    """
    Motor OCR usando PaddleOCR.
    
    Vantagens sobre Tesseract:
    - Melhor detecção de layouts complexos
    - Suporte nativo a tabelas
    - Detecção de texto em múltiplas orientações
    - Melhor pré-processamento automático
    """
    
    def __init__(
        self,
        lang: str = "pt",
        use_gpu: bool = False,
        det_model_dir: str = None,
        rec_model_dir: str = None
    ):
        """
        Inicializa o PaddleOCR.
        
        Args:
            lang: Idioma ('pt' para português, 'latin' para multilíngue)
            use_gpu: Usar GPU (requer paddlepaddle-gpu)
            det_model_dir: Diretório do modelo de detecção (opcional)
            rec_model_dir: Diretório do modelo de reconhecimento (opcional)
        """
        self.lang = lang
        self.use_gpu = use_gpu
        self.det_model_dir = det_model_dir
        self.rec_model_dir = rec_model_dir
        self._ocr = None
        self._available = None
    
    @property
    def is_available(self) -> bool:
        """Verifica se PaddleOCR está disponível"""
        if self._available is None:
            try:
                from paddleocr import PaddleOCR
                self._available = True
            except ImportError:
                self._available = False
                logger.warning(
                    "PaddleOCR não disponível. "
                    "Instale com: pip install paddlepaddle paddleocr"
                )
        return self._available
    
    @property
    def ocr(self):
        """Lazy loading do PaddleOCR"""
        if self._ocr is None and self.is_available:
            try:
                from paddleocr import PaddleOCR
                
                logger.info("Inicializando PaddleOCR...")
                self._ocr = PaddleOCR(
                    lang=self.lang,
                    use_gpu=self.use_gpu,
                    show_log=False,
                    det_model_dir=self.det_model_dir,
                    rec_model_dir=self.rec_model_dir,
                )
                logger.info("PaddleOCR inicializado com sucesso")
            except Exception as e:
                logger.error(f"Erro ao inicializar PaddleOCR: {e}")
                self._available = False
        
        return self._ocr
    
    def process_image(
        self, 
        image: Image.Image, 
        page_num: int = 1
    ) -> List[PaddleOCRBox]:
        """
        Processa uma imagem e extrai texto com coordenadas.
        
        Args:
            image: Imagem PIL
            page_num: Número da página
            
        Returns:
            Lista de PaddleOCRBox
        """
        if not self.is_available or self.ocr is None:
            return []
        
        try:
            # Converter PIL para numpy array
            img_np = np.array(image)
            
            # Executar OCR
            results = self.ocr.ocr(img_np, cls=True)
            
            boxes = []
            
            if results and results[0]:
                for line in results[0]:
                    # line = [polygon, (text, confidence)]
                    polygon = line[0]
                    text, confidence = line[1]
                    
                    # Calcular bounding box do polígono
                    xs = [p[0] for p in polygon]
                    ys = [p[1] for p in polygon]
                    
                    x = int(min(xs))
                    y = int(min(ys))
                    width = int(max(xs) - min(xs))
                    height = int(max(ys) - min(ys))
                    
                    boxes.append(PaddleOCRBox(
                        texto=text.strip(),
                        pagina=page_num,
                        x=x,
                        y=y,
                        largura=width,
                        altura=height,
                        confianca=confidence,
                        polygon=[[int(p[0]), int(p[1])] for p in polygon]
                    ))
            
            return boxes
            
        except Exception as e:
            logger.error(f"Erro no OCR: {e}")
            return []
    
    def process_pdf(self, pdf_path: Path, dpi: int = 300) -> List[PaddleOCRBox]:
        """
        Processa um PDF escaneado.
        
        Args:
            pdf_path: Caminho do PDF
            dpi: Resolução para conversão
            
        Returns:
            Lista de PaddleOCRBox de todas as páginas
        """
        if not self.is_available:
            return []
        
        try:
            from pdf2image import convert_from_path
            
            # Converter PDF para imagens
            images = convert_from_path(str(pdf_path), dpi=dpi)
            
            all_boxes = []
            
            for page_num, image in enumerate(images, start=1):
                logger.info(f"Processando página {page_num}/{len(images)} com PaddleOCR")
                boxes = self.process_image(image, page_num)
                all_boxes.extend(boxes)
            
            return all_boxes
            
        except Exception as e:
            logger.error(f"Erro ao processar PDF: {e}")
            return []
    
    def get_full_text(self, boxes: List[PaddleOCRBox]) -> str:
        """
        Concatena texto de todos os boxes.
        
        Args:
            boxes: Lista de PaddleOCRBox
            
        Returns:
            Texto completo
        """
        # Agrupar por página
        pages = {}
        for box in boxes:
            if box.pagina not in pages:
                pages[box.pagina] = []
            pages[box.pagina].append(box)
        
        # Ordenar por posição e concatenar
        lines = []
        for page_num in sorted(pages.keys()):
            page_boxes = pages[page_num]
            # Ordenar por Y (linha) e então X (coluna)
            page_boxes.sort(key=lambda b: (b.y // 15, b.x))
            
            current_line = []
            current_y = -100
            
            for box in page_boxes:
                if abs(box.y - current_y) > 12:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [box.texto]
                    current_y = box.y
                else:
                    current_line.append(box.texto)
            
            if current_line:
                lines.append(' '.join(current_line))
        
        return '\n'.join(lines)


# Singleton
try:
    paddle_ocr = PaddleOCREngine()
except Exception:
    paddle_ocr = None
