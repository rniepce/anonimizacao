"""
Motor NER (Named Entity Recognition) para identificação de entidades
Usa SpaCy para reconhecimento de nomes, endereços e contexto sensível
"""
import spacy
from dataclasses import dataclass
from typing import Optional

from app.config import settings


@dataclass
class NEREntity:
    """Entidade identificada pelo NER"""
    texto: str
    tipo: str  # PER, LOC, ORG, etc.
    inicio: int
    fim: int
    label_original: str  # Label do SpaCy


class NEREngine:
    """
    Motor de NER para identificação de entidades em textos jurídicos.
    Detecta nomes de pessoas, endereços, organizações e contexto sensível.
    """
    
    # Mapeamento de labels SpaCy para tipos do sistema
    LABEL_MAP = {
        'PER': 'PESSOA',
        'PERSON': 'PESSOA',
        'LOC': 'ENDERECO',
        'GPE': 'ENDERECO',
        'ORG': 'ORGANIZACAO',
        'MISC': 'OUTRO',
    }
    
    # Palavras-chave de contexto sensível (saúde, família, etc.)
    CONTEXTO_SENSIVEL = {
        'doença', 'diagnóstico', 'tratamento', 'medicamento', 'hospital',
        'psiquiátrico', 'psicológico', 'depressão', 'ansiedade', 'câncer',
        'hiv', 'aids', 'tuberculose', 'diabetes', 'internação',
        'menor', 'criança', 'adolescente', 'infância', 'abuso',
        'violência', 'agressão', 'estupro', 'assédio',
        'adoção', 'guarda', 'pensão', 'divórcio', 'separação',
    }
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.SPACY_MODEL
        self._nlp = None
    
    @property
    def nlp(self):
        """Lazy loading do modelo SpaCy"""
        if self._nlp is None:
            try:
                self._nlp = spacy.load(self.model_name)
            except OSError:
                # Se modelo não estiver instalado, usar modelo mínimo
                self._nlp = spacy.blank("pt")
                print(f"⚠️ Modelo {self.model_name} não encontrado. "
                      f"Execute: python -m spacy download {self.model_name}")
        return self._nlp
    
    def extract_entities(self, texto: str) -> list[NEREntity]:
        """
        Extrai entidades nomeadas do texto.
        
        Args:
            texto: Texto para analisar
            
        Returns:
            Lista de entidades identificadas
        """
        doc = self.nlp(texto)
        entities = []
        
        for ent in doc.ents:
            tipo = self.LABEL_MAP.get(ent.label_, 'OUTRO')
            entities.append(NEREntity(
                texto=ent.text,
                tipo=tipo,
                inicio=ent.start_char,
                fim=ent.end_char,
                label_original=ent.label_
            ))
        
        return entities
    
    def find_persons(self, texto: str) -> list[NEREntity]:
        """
        Encontra apenas nomes de pessoas.
        
        Args:
            texto: Texto para analisar
            
        Returns:
            Lista de nomes de pessoas
        """
        entities = self.extract_entities(texto)
        return [e for e in entities if e.tipo == 'PESSOA']
    
    def find_locations(self, texto: str) -> list[NEREntity]:
        """
        Encontra endereços e localizações.
        
        Args:
            texto: Texto para analisar
            
        Returns:
            Lista de localizações
        """
        entities = self.extract_entities(texto)
        return [e for e in entities if e.tipo == 'ENDERECO']
    
    def detect_sensitive_context(self, texto: str) -> list[dict]:
        """
        Detecta menções a contextos sensíveis (saúde, família, etc.).
        
        Args:
            texto: Texto para analisar
            
        Returns:
            Lista de contextos sensíveis encontrados
        """
        texto_lower = texto.lower()
        found = []
        
        for keyword in self.CONTEXTO_SENSIVEL:
            pos = 0
            while True:
                idx = texto_lower.find(keyword, pos)
                if idx == -1:
                    break
                
                # Extrair contexto ao redor
                start = max(0, idx - 50)
                end = min(len(texto), idx + len(keyword) + 50)
                context = texto[start:end]
                
                found.append({
                    'keyword': keyword,
                    'posicao': idx,
                    'contexto': f"...{context}..."
                })
                
                pos = idx + 1
        
        return found
    
    def analyze_full_document(self, texto: str) -> dict:
        """
        Análise completa do documento.
        
        Args:
            texto: Texto do documento
            
        Returns:
            Dicionário com todas as entidades e contextos
        """
        entities = self.extract_entities(texto)
        sensitive_contexts = self.detect_sensitive_context(texto)
        
        # Agrupar por tipo
        by_type = {}
        for ent in entities:
            if ent.tipo not in by_type:
                by_type[ent.tipo] = []
            by_type[ent.tipo].append({
                'texto': ent.texto,
                'inicio': ent.inicio,
                'fim': ent.fim
            })
        
        return {
            'entidades': by_type,
            'total_entidades': len(entities),
            'contextos_sensiveis': sensitive_contexts,
            'total_contextos': len(sensitive_contexts)
        }


# Singleton para uso global
ner_engine = NEREngine()
