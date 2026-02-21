"""
Handler de PDFs para manipulação de documentos
Detecta tipo de PDF, extrai texto e converte formatos
"""
import fitz  # PyMuPDF
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TextBlock:
    """Bloco de texto extraído do PDF"""
    texto: str
    pagina: int
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class PDFInfo:
    """Informações sobre um PDF"""
    caminho: Path
    total_paginas: int
    tipo: str  # 'nativo' ou 'imagem'
    tem_texto: bool
    metadados: dict


class PDFHandler:
    """
    Handler para manipulação de arquivos PDF.
    Suporta extração de texto, detecção de tipo e metadados.
    """
    
    # Threshold mínimo de texto por página para considerar "nativo"
    MIN_TEXT_CHARS_PER_PAGE = 100
    
    def __init__(self):
        pass
    
    def get_info(self, pdf_path: Path) -> PDFInfo:
        """
        Obtém informações sobre um PDF.
        
        Args:
            pdf_path: Caminho para o PDF
            
        Returns:
            PDFInfo com detalhes do documento
        """
        doc = fitz.open(str(pdf_path))
        
        # Extrair metadados
        metadata = doc.metadata or {}
        
        # Verificar se tem texto nativo
        total_text = 0
        for page in doc:
            total_text += len(page.get_text())
        
        avg_text_per_page = total_text / len(doc) if len(doc) > 0 else 0
        tem_texto = avg_text_per_page >= self.MIN_TEXT_CHARS_PER_PAGE
        tipo = 'nativo' if tem_texto else 'imagem'
        
        info = PDFInfo(
            caminho=pdf_path,
            total_paginas=len(doc),
            tipo=tipo,
            tem_texto=tem_texto,
            metadados=metadata
        )
        
        doc.close()
        return info
    
    def is_native_pdf(self, pdf_path: Path) -> bool:
        """
        Verifica se é um PDF com texto nativo (copiável).
        
        Args:
            pdf_path: Caminho para o PDF
            
        Returns:
            True se nativo, False se imagem/escaneado
        """
        return self.get_info(pdf_path).tipo == 'nativo'
    
    def extract_text(self, pdf_path: Path) -> str:
        """
        Extrai todo o texto de um PDF nativo.
        
        Args:
            pdf_path: Caminho para o PDF
            
        Returns:
            Texto completo do documento
        """
        doc = fitz.open(str(pdf_path))
        text_parts = []
        
        for page in doc:
            text_parts.append(page.get_text())
        
        doc.close()
        return '\n'.join(text_parts)
    
    def extract_text_with_positions(self, pdf_path: Path) -> list[TextBlock]:
        """
        Extrai texto com coordenadas (bounding boxes).
        
        Args:
            pdf_path: Caminho para o PDF
            
        Returns:
            Lista de TextBlock com posições
        """
        doc = fitz.open(str(pdf_path))
        blocks = []
        
        for page_num, page in enumerate(doc, start=1):
            # Extrair blocos de texto com posições
            text_dict = page.get_text("dict")
            
            for block in text_dict.get("blocks", []):
                if block.get("type") == 0:  # Bloco de texto
                    # Concatenar linhas do bloco
                    block_text = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            block_text += span.get("text", "")
                        block_text += "\n"
                    
                    if block_text.strip():
                        bbox = block["bbox"]
                        blocks.append(TextBlock(
                            texto=block_text.strip(),
                            pagina=page_num,
                            x0=bbox[0],
                            y0=bbox[1],
                            x1=bbox[2],
                            y1=bbox[3]
                        ))
        
        doc.close()
        return blocks
    
    def extract_words_with_positions(self, pdf_path: Path) -> list[TextBlock]:
        """
        Extrai palavras individuais com suas posições.
        Útil para anonimização precisa.
        
        Args:
            pdf_path: Caminho para o PDF
            
        Returns:
            Lista de TextBlock para cada palavra
        """
        doc = fitz.open(str(pdf_path))
        words = []
        
        for page_num, page in enumerate(doc, start=1):
            # Extrair palavras com posições
            word_list = page.get_text("words")
            
            for word in word_list:
                # word = (x0, y0, x1, y1, "word", block_no, line_no, word_no)
                if len(word) >= 5 and word[4].strip():
                    words.append(TextBlock(
                        texto=word[4],
                        pagina=page_num,
                        x0=word[0],
                        y0=word[1],
                        x1=word[2],
                        y1=word[3]
                    ))
        
        doc.close()
        return words
    
    def get_page_dimensions(self, pdf_path: Path) -> list[tuple[float, float]]:
        """
        Obtém dimensões de cada página do PDF.
        
        Args:
            pdf_path: Caminho para o PDF
            
        Returns:
            Lista de tuplas (largura, altura) em pontos PDF
        """
        doc = fitz.open(str(pdf_path))
        dimensions = []
        
        for page in doc:
            rect = page.rect
            dimensions.append((rect.width, rect.height))
        
        doc.close()
        return dimensions
    
    def remove_metadata(self, pdf_path: Path, output_path: Path) -> None:
        """
        Remove metadados sensíveis do PDF.
        
        Args:
            pdf_path: Caminho do PDF original
            output_path: Caminho para salvar PDF limpo
        """
        doc = fitz.open(str(pdf_path))
        
        # Limpar metadados
        doc.set_metadata({
            'author': '',
            'creator': 'TJMG Anonymizer',
            'producer': 'TJMG Anonymizer',
            'title': '',
            'subject': '',
            'keywords': ''
        })
        
        doc.save(str(output_path))
        doc.close()
    
    def convert_to_pdfa(self, pdf_path: Path, output_path: Path) -> None:
        """
        Converte PDF para formato PDF/A (arquivístico).
        
        Args:
            pdf_path: Caminho do PDF original
            output_path: Caminho para salvar PDF/A
        """
        # PyMuPDF não suporta conversão nativa para PDF/A
        # Por enquanto, apenas copia e limpa metadados
        # Para PDF/A completo, seria necessário usar pikepdf ou ghostscript
        doc = fitz.open(str(pdf_path))
        
        # Configurações para melhor compatibilidade
        doc.set_metadata({
            'author': '',
            'creator': 'TJMG Anonymizer',
            'producer': 'TJMG Anonymizer Pipeline',
        })
        
        doc.save(
            str(output_path),
            garbage=4,  # Máxima compressão
            deflate=True,  # Comprimir streams
            clean=True,  # Limpar conteúdo desnecessário
        )
        doc.close()


# Singleton para uso global
pdf_handler = PDFHandler()
