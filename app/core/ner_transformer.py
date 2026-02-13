"""
Motor NER com Transformers (BERTimbau)
Usa modelo BERT treinado em português para melhor detecção de entidades.
Fallback automático para SpaCy se transformers não disponível.
"""
import logging
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class TransformerEntity:
    """Entidade identificada pelo modelo transformer"""
    texto: str
    tipo: str  # PER, LOC, ORG, MISC
    inicio: int
    fim: int
    score: float
    label_original: str


class NERTransformerEngine:
    """
    Motor NER usando BERTimbau (neuralmind/bert-base-portuguese-cased).
    
    Vantagens sobre SpaCy:
    - Maior precisão (~95% F1 vs ~85%)
    - Melhor captura de contexto
    - Entidades mais complexas
    
    Modelo usado: neuralmind/bert-base-portuguese-cased
    Fine-tuned para NER: lener_br ou harem
    """
    
    # Mapeamento de labels do modelo para tipos do sistema
    LABEL_MAP = {
        'PER': 'PESSOA',
        'PESSOA': 'PESSOA',
        'LOC': 'ENDERECO',
        'LOCAL': 'ENDERECO',
        'ORG': 'ORGANIZACAO',
        'ORGANIZACAO': 'ORGANIZACAO',
        'MISC': 'OUTRO',
        'TEMPO': 'DATA',
        'VALOR': 'VALOR',
        # Labels do LeNER-Br (jurídico brasileiro)
        'JURISPRUDENCIA': 'OUTRO',
        'LEGISLACAO': 'OUTRO',
    }
    
    def __init__(
        self, 
        model_name: str = "pierreguillou/bert-base-cased-pt-lenerbr",
        device: str = "cpu"
    ):
        """
        Inicializa o motor NER com transformers.
        
        Args:
            model_name: Nome do modelo no HuggingFace Hub
                        Opções recomendadas:
                        - pierreguillou/bert-base-cased-pt-lenerbr (jurídico)
                        - neuralmind/bert-base-portuguese-cased (geral)
            device: 'cpu' ou 'cuda'
        """
        self.model_name = model_name
        self.device = device
        self._pipeline = None
        self._available = None
    
    @property
    def is_available(self) -> bool:
        """Verifica se transformers está disponível"""
        if self._available is None:
            try:
                import transformers
                import torch
                self._available = True
            except ImportError:
                self._available = False
                logger.warning(
                    "Transformers não disponível. "
                    "Instale com: pip install transformers torch"
                )
        return self._available
    
    @property
    def pipeline(self):
        """Lazy loading do pipeline NER"""
        if self._pipeline is None and self.is_available:
            try:
                from transformers import pipeline
                
                logger.info(f"Carregando modelo NER: {self.model_name}")
                self._pipeline = pipeline(
                    "ner",
                    model=self.model_name,
                    tokenizer=self.model_name,
                    aggregation_strategy="simple",
                    device=-1 if self.device == "cpu" else 0
                )
                logger.info("Modelo NER carregado com sucesso")
            except Exception as e:
                logger.error(f"Erro ao carregar modelo NER: {e}")
                self._available = False
                self._pipeline = None
        
        return self._pipeline
    
    def extract_entities(self, texto: str) -> List[TransformerEntity]:
        """
        Extrai entidades nomeadas do texto usando BERT.
        
        Args:
            texto: Texto para analisar
            
        Returns:
            Lista de entidades identificadas
        """
        if not self.is_available or self.pipeline is None:
            return []
        
        try:
            # Limitar tamanho do texto por performance
            # BERT tem limite de 512 tokens, processamos em chunks
            max_chunk_size = 4000  # ~500 tokens aprox
            
            entities = []
            
            # Processar em chunks se texto muito grande
            for chunk_start in range(0, len(texto), max_chunk_size):
                chunk = texto[chunk_start:chunk_start + max_chunk_size]
                
                results = self.pipeline(chunk)
                
                for result in results:
                    # Ajustar posições para o texto completo
                    start = result['start'] + chunk_start
                    end = result['end'] + chunk_start
                    
                    # Mapear label
                    label = result['entity_group'].upper()
                    tipo = self.LABEL_MAP.get(label, 'OUTRO')
                    
                    entities.append(TransformerEntity(
                        texto=result['word'],
                        tipo=tipo,
                        inicio=start,
                        fim=end,
                        score=result['score'],
                        label_original=label
                    ))
            
            return entities
            
        except Exception as e:
            logger.error(f"Erro na extração de entidades: {e}")
            return []
    
    def find_persons(self, texto: str) -> List[TransformerEntity]:
        """Encontra apenas nomes de pessoas"""
        entities = self.extract_entities(texto)
        return [e for e in entities if e.tipo == 'PESSOA']
    
    def find_locations(self, texto: str) -> List[TransformerEntity]:
        """Encontra endereços e localizações"""
        entities = self.extract_entities(texto)
        return [e for e in entities if e.tipo == 'ENDERECO']
    
    def find_organizations(self, texto: str) -> List[TransformerEntity]:
        """Encontra organizações"""
        entities = self.extract_entities(texto)
        return [e for e in entities if e.tipo == 'ORGANIZACAO']
    
    def analyze_full_document(self, texto: str) -> dict:
        """
        Análise completa do documento.
        
        Args:
            texto: Texto do documento
            
        Returns:
            Dicionário com todas as entidades agrupadas
        """
        entities = self.extract_entities(texto)
        
        # Agrupar por tipo
        by_type = {}
        for ent in entities:
            if ent.tipo not in by_type:
                by_type[ent.tipo] = []
            by_type[ent.tipo].append({
                'texto': ent.texto,
                'inicio': ent.inicio,
                'fim': ent.fim,
                'score': ent.score
            })
        
        # Calcular estatísticas
        high_confidence = [e for e in entities if e.score > 0.9]
        
        return {
            'entidades': by_type,
            'total_entidades': len(entities),
            'alta_confianca': len(high_confidence),
            'modelo': self.model_name,
            'engine': 'transformer'
        }


# Factory function para escolher o melhor motor disponível
def get_best_ner_engine():
    """
    Retorna o melhor motor NER disponível.
    Prioridade: Transformer > SpaCy
    """
    transformer_engine = NERTransformerEngine()
    
    if transformer_engine.is_available:
        # Testar se consegue carregar o modelo
        try:
            _ = transformer_engine.pipeline
            if transformer_engine.pipeline is not None:
                logger.info("Usando NER com Transformers (BERTimbau)")
                return transformer_engine
        except Exception:
            pass
    
    # Fallback para SpaCy
    logger.info("Usando NER com SpaCy (fallback)")
    from app.core.ner_engine import ner_engine
    return ner_engine


# Singleton - tenta usar transformer, fallback para spacy
try:
    ner_transformer = NERTransformerEngine()
except Exception:
    ner_transformer = None
