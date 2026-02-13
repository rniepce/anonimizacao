"""
Motor de Anonimização (Redactor)
Aplica tarjas sobre dados sensíveis em PDFs
"""
import fitz  # PyMuPDF
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.config import settings
from app.core.pdf_handler import TextBlock, pdf_handler


@dataclass
class RedactionArea:
    """Área a ser anonimizada"""
    pagina: int
    x0: float
    y0: float
    x1: float
    y1: float
    tipo: str  # Tipo de dado (CPF, NOME, etc.)
    valor_original: str


class Redactor:
    """
    Motor de anonimização que aplica tarjas sobre dados sensíveis.
    Suporta tarjas visuais e remoção de texto subjacente.
    """
    
    def __init__(
        self,
        redaction_color: tuple = None,
        redaction_text: str = None
    ):
        self.color = redaction_color or settings.REDACTION_COLOR
        self.text = redaction_text or settings.REDACTION_TEXT
    
    def redact_pdf(
        self,
        input_path: Path,
        output_path: Path,
        areas: list[RedactionArea]
    ) -> dict:
        """
        Aplica anonimização em um PDF.
        
        Args:
            input_path: Caminho do PDF original
            output_path: Caminho para salvar PDF anonimizado
            areas: Lista de áreas a anonimizar
            
        Returns:
            Dicionário com estatísticas da redação
        """
        doc = fitz.open(str(input_path))
        
        stats = {
            'total_redacoes': 0,
            'por_tipo': {},
            'por_pagina': {}
        }
        
        # Agrupar áreas por página
        areas_por_pagina = {}
        for area in areas:
            if area.pagina not in areas_por_pagina:
                areas_por_pagina[area.pagina] = []
            areas_por_pagina[area.pagina].append(area)
        
        # Aplicar redações
        for page_num, page_areas in areas_por_pagina.items():
            if page_num < 1 or page_num > len(doc):
                continue
            
            page = doc[page_num - 1]  # fitz usa índice 0-based
            
            for area in page_areas:
                # Criar retângulo de redação
                rect = fitz.Rect(area.x0, area.y0, area.x1, area.y1)
                
                # Adicionar anotação de redação (True Redaction)
                # fill=preto, text=" " para garantir que não haja vazamento visual
                annot = page.add_redact_annot(
                    rect,
                    text=" ", 
                    fill=(0, 0, 0)
                )

                # Atualizar estatísticas
                stats['total_redacoes'] += 1
                
                if area.tipo not in stats['por_tipo']:
                    stats['por_tipo'][area.tipo] = 0
                stats['por_tipo'][area.tipo] += 1
                
                if page_num not in stats['por_pagina']:
                    stats['por_pagina'][page_num] = 0
                stats['por_pagina'][page_num] += 1
                
            # Aplicar as redações (remove o texto e desenha retângulo)
            # images=2 remove partes de imagens sob a tarja (crucial para assinaturas)
            # graphics=2 remove vetores/linhas sob a tarja
            page.apply_redactions(images=2, graphics=2)
        
        # Limpar metadados totalmente (Metadata Scrubbing)
        doc.set_metadata({})
        
        # Salvar documento com Garbage Collection agressivo
        doc.save(
            str(output_path),
            garbage=4,     # Reescreve eliminando objetos não utilizados
            deflate=True,  # Comprime o arquivo
            clean=True,    # Limpa estrutura interna
        )
        doc.close()
        
        return stats

    def pseudonymize_pdf(
        self,
        input_path: Path,
        output_path: Path,
        areas: list[RedactionArea],
        job_id: str = None
    ) -> dict:
        """
        Substitui dados sensíveis por dados fake consistentes.
        
        Diferente de redact_pdf que aplica tarjas pretas, este método
        substitui CPF por CPF fake, nome por nome fake, etc.
        
        Args:
            input_path: Caminho do PDF original
            output_path: Caminho para salvar PDF pseudonimizado
            areas: Lista de áreas a pseudonimizar
            job_id: ID do job para garantir consistência
            
        Returns:
            Dicionário com estatísticas e mapeamentos
        """
        from app.core.pseudonymizer import Pseudonymizer
        
        doc = fitz.open(str(input_path))
        pseudonymizer = Pseudonymizer(seed=job_id or "default")
        
        stats = {
            'total_pseudonimizacoes': 0,
            'por_tipo': {},
            'por_pagina': {},
            'mapeamentos': []  # Para auditoria
        }
        
        # Agrupar áreas por página
        areas_por_pagina = {}
        for area in areas:
            if area.pagina not in areas_por_pagina:
                areas_por_pagina[area.pagina] = []
            areas_por_pagina[area.pagina].append(area)
        
        for page_num, page_areas in areas_por_pagina.items():
            if page_num < 1 or page_num > len(doc):
                continue
            
            page = doc[page_num - 1]
            
            for area in page_areas:
                rect = fitz.Rect(area.x0, area.y0, area.x1, area.y1)
                
                # Gerar pseudônimo
                pseudonimo = pseudonymizer.pseudonymize(
                    area.tipo, 
                    area.valor_original
                )
                
                # 1. Adicionar redação para remover texto original
                page.add_redact_annot(rect, text=" ", fill=(1, 1, 1))  # Fundo branco
                
                # Atualizar estatísticas
                stats['total_pseudonimizacoes'] += 1
                
                if area.tipo not in stats['por_tipo']:
                    stats['por_tipo'][area.tipo] = 0
                stats['por_tipo'][area.tipo] += 1
                
                if page_num not in stats['por_pagina']:
                    stats['por_pagina'][page_num] = 0
                stats['por_pagina'][page_num] += 1
            
            # Aplicar redações (remove texto original)
            page.apply_redactions(images=0, graphics=0)
            
            # 2. Inserir pseudônimos no lugar
            for area in page_areas:
                rect = fitz.Rect(area.x0, area.y0, area.x1, area.y1)
                pseudonimo = pseudonymizer.pseudonymize(
                    area.tipo, 
                    area.valor_original
                )
                
                # Calcular tamanho da fonte baseado na altura do rect
                font_size = min(12, max(8, (rect.height - 2) * 0.8))
                
                # Inserir texto pseudonimizado
                page.insert_text(
                    (rect.x0 + 1, rect.y1 - 2),  # Posição ajustada
                    pseudonimo,
                    fontsize=font_size,
                    color=(0, 0, 0)  # Preto
                )
                
                stats['mapeamentos'].append({
                    'tipo': area.tipo,
                    'pseudonimo': pseudonimo,
                    'pagina': page_num
                })
        
        # Limpar metadados
        doc.set_metadata({})
        
        # Salvar
        doc.save(
            str(output_path),
            garbage=4,
            deflate=True,
            clean=True,
        )
        doc.close()
        
        return stats

    def redact_via_rasterization(
        self,
        input_path: Path,
        output_path: Path
    ) -> None:
        """
        Estratégia "Nuclear": Rasteriza o PDF inteiro (transforma em imagens).
        Garante que NENHUM texto ou metadado oculto sobreviva.
        
        Args:
            input_path: Caminho do PDF a ser rasterizado
            output_path: Caminho de saída
        """
        doc = fitz.open(str(input_path))
        # Zoom de 2.0 = 200% de resolução (mantém legibilidade)
        mat = fitz.Matrix(2.0, 2.0)
        
        pdf_novo = fitz.open()

        for page in doc:
            # 1. Renderiza a página como imagem (Pixmap)
            pix = page.get_pixmap(matrix=mat)
            
            # 2. Cria nova página no PDF de destino
            nova_pagina = pdf_novo.new_page(
                width=page.rect.width, 
                height=page.rect.height
            )
            
            # 3. Insere a imagem "achatada" (flat)
            img_bytes = pix.tobytes("png")
            nova_pagina.insert_image(nova_pagina.rect, stream=img_bytes)

        # Salvar o novo PDF (puramente imagem)
        pdf_novo.save(str(output_path))
        doc.close()
        pdf_novo.close()
        
        return stats
    
    def redact_text_blocks(
        self,
        input_path: Path,
        output_path: Path,
        blocks_to_redact: list[TextBlock]
    ) -> dict:
        """
        Anonimiza blocos de texto específicos.
        
        Args:
            input_path: Caminho do PDF original
            output_path: Caminho para salvar PDF anonimizado
            blocks_to_redact: Blocos de texto a anonimizar
            
        Returns:
            Estatísticas da redação
        """
        areas = [
            RedactionArea(
                pagina=block.pagina,
                x0=block.x0,
                y0=block.y0,
                x1=block.x1,
                y1=block.y1,
                tipo='TEXTO',
                valor_original=block.texto
            )
            for block in blocks_to_redact
        ]
        
        return self.redact_pdf(input_path, output_path, areas)
    
    def redact_by_text_search(
        self,
        input_path: Path,
        output_path: Path,
        search_terms: list[tuple[str, str]]  # (texto, tipo)
    ) -> dict:
        """
        Busca e anonimiza textos específicos no PDF.
        
        Args:
            input_path: Caminho do PDF original
            output_path: Caminho para salvar PDF anonimizado
            search_terms: Lista de tuplas (texto_a_buscar, tipo_dado)
            
        Returns:
            Estatísticas da redação
        """
        doc = fitz.open(str(input_path))
        areas = []
        
        for page_num, page in enumerate(doc, start=1):
            for search_text, tipo in search_terms:
                # Buscar todas as ocorrências
                text_instances = page.search_for(search_text)
                
                for rect in text_instances:
                    areas.append(RedactionArea(
                        pagina=page_num,
                        x0=rect.x0,
                        y0=rect.y0,
                        x1=rect.x1,
                        y1=rect.y1,
                        tipo=tipo,
                        valor_original=search_text
                    ))
        
        doc.close()
        
        return self.redact_pdf(input_path, output_path, areas)
    
    def add_overlay_boxes(
        self,
        input_path: Path,
        output_path: Path,
        areas: list[RedactionArea],
        color: tuple = None
    ) -> None:
        """
        Adiciona caixas coloridas sobre áreas (para visualização/preview).
        Não remove o texto subjacente.
        
        Args:
            input_path: Caminho do PDF original
            output_path: Caminho para salvar PDF com overlays
            areas: Áreas a destacar
            color: Cor do overlay (RGB 0-1)
        """
        doc = fitz.open(str(input_path))
        overlay_color = color or (1, 1, 0)  # Amarelo por padrão
        
        # Agrupar por página
        areas_por_pagina = {}
        for area in areas:
            if area.pagina not in areas_por_pagina:
                areas_por_pagina[area.pagina] = []
            areas_por_pagina[area.pagina].append(area)
        
        for page_num, page_areas in areas_por_pagina.items():
            if page_num < 1 or page_num > len(doc):
                continue
            
            page = doc[page_num - 1]
            
            for area in page_areas:
                rect = fitz.Rect(area.x0, area.y0, area.x1, area.y1)
                
                # Desenhar retângulo semi-transparente
                shape = page.new_shape()
                shape.draw_rect(rect)
                shape.finish(
                    color=overlay_color,
                    fill=overlay_color,
                    fill_opacity=0.3,
                    stroke_opacity=1,
                    width=1
                )
                shape.commit()
        
        doc.save(str(output_path))
        doc.close()
    
    def create_comparison_pdf(
        self,
        original_path: Path,
        redacted_path: Path,
        output_path: Path
    ) -> None:
        """
        Cria PDF lado a lado para comparação (antes/depois).
        
        Args:
            original_path: PDF original
            redacted_path: PDF anonimizado
            output_path: PDF de comparação
        """
        original = fitz.open(str(original_path))
        redacted = fitz.open(str(redacted_path))
        output = fitz.open()
        
        for i in range(min(len(original), len(redacted))):
            # Criar página maior para caber dois lados
            orig_page = original[i]
            rect = orig_page.rect
            
            new_width = rect.width * 2 + 20  # Espaço entre
            new_height = rect.height
            
            new_page = output.new_page(width=new_width, height=new_height)
            
            # Inserir original à esquerda
            new_page.show_pdf_page(
                fitz.Rect(0, 0, rect.width, rect.height),
                original,
                i
            )
            
            # Inserir redacted à direita
            new_page.show_pdf_page(
                fitz.Rect(rect.width + 20, 0, new_width, rect.height),
                redacted,
                i
            )
            
            # Adicionar labels
            new_page.insert_text(
                (10, 15),
                "ORIGINAL",
                fontsize=12,
                color=(1, 0, 0)
            )
            new_page.insert_text(
                (rect.width + 30, 15),
                "ANONIMIZADO",
                fontsize=12,
                color=(0, 0.5, 0)
            )
        
        output.save(str(output_path))
        output.close()
        original.close()
        redacted.close()


# Singleton para uso global
redactor = Redactor()
