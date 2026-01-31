"""
Pipeline principal de anonimização
Orquestra todos os componentes do sistema
"""
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
    fonte: str  # 'regex' ou 'ner'


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
    6. Anonimização: Aplica tarjas
    7. Auditoria: Registra operação
    """
    
    def __init__(self):
        pass
    
    def process(
        self,
        input_path: Path,
        output_dir: Optional[Path] = None,
        usuario: Optional[str] = None,
        ip_origem: Optional[str] = None
    ) -> AnonymizationResult:
        """
        Processa um documento completo.
        
        Args:
            input_path: Caminho do arquivo de entrada
            output_dir: Diretório de saída (default: mesmo do input)
            usuario: Usuário executando (para auditoria)
            ip_origem: IP de origem (para auditoria)
            
        Returns:
            AnonymizationResult com detalhes do processamento
        """
        start_time = time.time()
        job_id = str(uuid.uuid4())
        
        # Definir caminho de saída
        if output_dir is None:
            output_dir = input_path.parent
        
        output_path = output_dir / f"{input_path.stem}_anonimizado.pdf"
        
        # 1. Obter informações do PDF
        pdf_info = pdf_handler.get_info(input_path)
        
        # 2. Extrair texto com posições
        if pdf_info.tipo == 'nativo':
            text_items = self._extract_native(input_path)
            texto_completo = '\n'.join(item.texto for item in text_items)
        else:
            text_items = self._extract_ocr(input_path)
            texto_completo = ocr_engine.get_full_text(
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
        
        # 3. Identificar dados sensíveis
        dados_identificados = self._identify_sensitive_data(
            texto_completo, text_items
        )
        
        # 4. Filtrar allowlist
        dados_anonimizar = []
        dados_ignorados = []
        
        for item in dados_identificados:
            if item.tipo == 'PESSOA' and allowlist_manager.is_allowed(item.valor):
                dados_ignorados.append(item)
            else:
                dados_anonimizar.append(item)
        
        # 5. Aplicar anonimização
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
    
    def analyze_only(self, input_path: Path) -> list[SensitiveDataItem]:
        """
        Apenas identifica dados sensíveis sem anonimizar.
        Útil para preview.
        
        Args:
            input_path: Caminho do arquivo
            
        Returns:
            Lista de dados sensíveis identificados
        """
        pdf_info = pdf_handler.get_info(input_path)
        
        if pdf_info.tipo == 'nativo':
            text_items = self._extract_native(input_path)
            texto_completo = '\n'.join(item.texto for item in text_items)
        else:
            text_items = self._extract_ocr(input_path)
            texto_completo = ocr_engine.get_full_text(
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
        
        return self._identify_sensitive_data(texto_completo, text_items)
    
    def _extract_native(self, pdf_path: Path) -> list[TextBlock]:
        """Extrai texto de PDF nativo com posições"""
        return pdf_handler.extract_words_with_positions(pdf_path)
    
    def _extract_ocr(self, pdf_path: Path) -> list[TextBlock]:
        """Extrai texto via OCR com posições"""
        ocr_results = ocr_engine.process_pdf(pdf_path)
        
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
    
    def _identify_sensitive_data(
        self,
        texto: str,
        text_items: list[TextBlock]
    ) -> list[SensitiveDataItem]:
        """
        Identifica dados sensíveis usando Regex e NER.
        
        Args:
            texto: Texto completo do documento
            text_items: Itens de texto com posições
            
        Returns:
            Lista de dados sensíveis com posições
        """
        results = []
        
        # 1. Busca por Regex
        regex_matches = regex_matcher.find_all(texto)
        
        for match in regex_matches:
            # Encontrar posição no documento
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
                    confianca=1.0,  # Regex tem alta confiança
                    fonte='regex'
                ))
        
        # 2. Busca por NER (nomes, endereços)
        ner_entities = ner_engine.extract_entities(texto)
        
        for entity in ner_entities:
            if entity.tipo in ('PESSOA', 'ENDERECO'):
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
                        confianca=0.85,  # NER tem confiança menor
                        fonte='ner'
                    ))
        
        # Remover duplicatas (mesmo valor na mesma posição)
        seen = set()
        unique_results = []
        for item in results:
            key = (item.valor, item.pagina, round(item.x0), round(item.y0))
            if key not in seen:
                seen.add(key)
                unique_results.append(item)
        
        return unique_results
    
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
