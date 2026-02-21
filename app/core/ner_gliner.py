"""
Motor NER com GLiNER-PII
Detecção zero-shot de 60+ categorias de PII (dados pessoais).
Suporta dois modos: standard e deep.
"""
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GLiNEREntity:
    """Entidade PII identificada pelo GLiNER"""
    texto: str
    tipo: str       # Tipo normalizado do sistema (PESSOA, EMAIL, etc.)
    inicio: int
    fim: int
    confianca: float
    label_original: str  # Label original do GLiNER


class GLiNEREngine:
    """
    Motor NER usando GLiNER-PII — detecção zero-shot de dados pessoais.
    
    Vantagens sobre SpaCy:
    - Zero-shot: detecta 60+ tipos de PII sem retreinar
    - Multilíngue: funciona em português nativamente
    - PII-específico: foca em dados sensíveis, não NER genérico
    - Leve: roda em CPU (~500MB de modelo)
    """
    
    # Mapeamento de labels GLiNER-PII para tipos do sistema
    LABEL_MAP = {
        # Pessoas
        'person': 'PESSOA',
        'name': 'PESSOA',
        'first_name': 'PESSOA',
        'last_name': 'PESSOA',
        'username': 'PESSOA',
        # Documentos
        'social_security_number': 'CPF',
        'tax_id': 'CPF',
        'national_id': 'RG',
        'passport_number': 'RG',
        'driver_license': 'CNH',
        'license_plate': 'OUTRO',
        # Contato
        'email': 'EMAIL',
        'email_address': 'EMAIL',
        'phone_number': 'TELEFONE',
        'telephone': 'TELEFONE',
        # Endereço
        'address': 'ENDERECO',
        'street_address': 'ENDERECO',
        'city': 'ENDERECO',
        'state': 'ENDERECO',
        'zip_code': 'CEP',
        'postal_code': 'CEP',
        'country': 'ENDERECO',
        # Financeiro
        'credit_card_number': 'CONTA_BANCARIA',
        'bank_account': 'CONTA_BANCARIA',
        'iban': 'CONTA_BANCARIA',
        'swift_code': 'AGENCIA',
        # Datas
        'date_of_birth': 'DATA_NASCIMENTO',
        'date': 'DATA_NASCIMENTO',
        'age': 'DATA_NASCIMENTO',
        # Organizações
        'organization': 'ORGANIZACAO',
        'company': 'ORGANIZACAO',
        # Outros
        'ip_address': 'OUTRO',
        'url': 'OUTRO',
        'medical_record': 'OUTRO',
        'health_info': 'OUTRO',
    }
    
    # Labels PII a solicitar ao GLiNER (modo standard)
    PII_LABELS_STANDARD = [
        "person", "email", "phone_number", "address",
        "date_of_birth", "social_security_number", "national_id",
        "organization", "credit_card_number", "bank_account",
        "driver_license", "passport_number", "zip_code",
        "ip_address", "url", "username",
    ]
    
    # Labels PII expandidas (modo deep)
    PII_LABELS_DEEP = PII_LABELS_STANDARD + [
        "medical_record", "health_info", "tax_id",
        "license_plate", "swift_code", "iban",
        "first_name", "last_name", "street_address",
        "city", "state", "country", "age", "company",
    ]
    
    # Modelos disponíveis
    MODELS = {
        'standard': 'urchade/gliner_multi_pii-v1',
        'deep': 'Ai4Privacy/star-pii-gliner-multi-v1',
    }
    
    def __init__(
        self,
        mode: str = 'standard',
        model_name: Optional[str] = None,
        confidence_threshold: float = 0.5,
    ):
        """
        Inicializa o motor GLiNER-PII.
        
        Args:
            mode: 'standard' ou 'deep'
            model_name: Override do modelo (opcional)
            confidence_threshold: Limiar de confiança (0-1)
        """
        self.mode = mode
        self.model_name = model_name or self.MODELS.get(mode, self.MODELS['standard'])
        self.confidence_threshold = confidence_threshold
        self._model = None
        self._available = None
    
    @property
    def is_available(self) -> bool:
        """Verifica se GLiNER está instalado"""
        if self._available is None:
            try:
                from gliner import GLiNER
                self._available = True
            except ImportError:
                self._available = False
                logger.warning(
                    "GLiNER não disponível. "
                    "Instale com: pip install gliner"
                )
        return self._available
    
    @property
    def model(self):
        """Lazy loading do modelo GLiNER"""
        if self._model is None and self.is_available:
            try:
                from gliner import GLiNER
                
                logger.info(f"Carregando modelo GLiNER: {self.model_name}")
                self._model = GLiNER.from_pretrained(self.model_name)
                logger.info("Modelo GLiNER carregado com sucesso")
            except Exception as e:
                logger.error(f"Erro ao carregar GLiNER: {e}")
                self._available = False
                self._model = None
        
        return self._model
    
    def extract_entities(self, texto: str) -> list[GLiNEREntity]:
        """
        Extrai entidades PII do texto via GLiNER.
        
        Args:
            texto: Texto para analisar
            
        Returns:
            Lista de entidades PII identificadas
        """
        if not self.is_available or self.model is None:
            return []
        
        try:
            labels = (
                self.PII_LABELS_DEEP if self.mode == 'deep'
                else self.PII_LABELS_STANDARD
            )
            
            # GLiNER tem limite de ~1024 tokens, processar em chunks
            max_chunk = 3500  # ~800 tokens aprox
            overlap = 200     # Overlap para não perder entidades na borda
            
            all_entities = []
            
            for chunk_start in range(0, len(texto), max_chunk - overlap):
                chunk_end = min(chunk_start + max_chunk, len(texto))
                chunk = texto[chunk_start:chunk_end]
                
                # Predição zero-shot
                predictions = self.model.predict_entities(
                    chunk,
                    labels,
                    threshold=self.confidence_threshold,
                )
                
                for pred in predictions:
                    # Ajustar posições para o texto completo
                    start = pred['start'] + chunk_start
                    end = pred['end'] + chunk_start
                    
                    # Mapear label para tipo do sistema
                    label = pred['label'].lower().replace(' ', '_')
                    tipo = self.LABEL_MAP.get(label, 'OUTRO')
                    
                    all_entities.append(GLiNEREntity(
                        texto=pred['text'],
                        tipo=tipo,
                        inicio=start,
                        fim=end,
                        confianca=pred['score'],
                        label_original=pred['label'],
                    ))
            
            # Deduplicar entidades do overlap
            return self._deduplicate(all_entities)
            
        except Exception as e:
            logger.error(f"Erro na extração GLiNER: {e}")
            return []
    
    def _deduplicate(self, entities: list[GLiNEREntity]) -> list[GLiNEREntity]:
        """Remove duplicatas geradas pelo overlap de chunks"""
        seen = set()
        unique = []
        for ent in entities:
            key = (ent.texto.lower(), ent.tipo, ent.inicio)
            if key not in seen:
                seen.add(key)
                unique.append(ent)
        return unique
    
    def find_persons(self, texto: str) -> list[GLiNEREntity]:
        """Encontra apenas nomes de pessoas"""
        return [e for e in self.extract_entities(texto) if e.tipo == 'PESSOA']
    
    def find_pii_by_type(self, texto: str, tipo: str) -> list[GLiNEREntity]:
        """Encontra PII de um tipo específico"""
        return [e for e in self.extract_entities(texto) if e.tipo == tipo]
    
    def analyze_full_document(self, texto: str) -> dict:
        """Análise completa do documento"""
        entities = self.extract_entities(texto)
        
        by_type = {}
        for ent in entities:
            if ent.tipo not in by_type:
                by_type[ent.tipo] = []
            by_type[ent.tipo].append({
                'texto': ent.texto,
                'inicio': ent.inicio,
                'fim': ent.fim,
                'confianca': ent.confianca,
                'label_original': ent.label_original,
            })
        
        high_confidence = [e for e in entities if e.confianca > 0.8]
        
        return {
            'entidades': by_type,
            'total_entidades': len(entities),
            'alta_confianca': len(high_confidence),
            'modelo': self.model_name,
            'modo': self.mode,
            'engine': 'gliner',
        }
