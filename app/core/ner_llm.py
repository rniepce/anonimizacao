"""
Motor NER com LLM (Qwen 3.5 via Ollama)
Usa uma LLM local para extração inteligente de entidades sensíveis
em documentos jurídicos brasileiros.
"""
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMEntity:
    """Entidade identificada pela LLM"""
    texto: str
    tipo: str       # Tipo normalizado do sistema (PESSOA, CPF, etc.)
    inicio: int
    fim: int
    confianca: float
    label_original: str  # Label original retornada pela LLM


# Prompt do sistema especializado para extração de PII em docs jurídicos
SYSTEM_PROMPT = """Você é um especialista em identificação de dados pessoais sensíveis (PII) em documentos jurídicos brasileiros.

Sua tarefa é extrair TODAS as entidades sensíveis do texto fornecido.

## Categorias de entidades a identificar:

- PESSOA: Nomes completos de pessoas físicas (partes, testemunhas, etc.)
- CPF: Números de CPF (formato XXX.XXX.XXX-XX)
- CNPJ: Números de CNPJ (formato XX.XXX.XXX/XXXX-XX)
- RG: Números de RG/Identidade
- EMAIL: Endereços de email
- TELEFONE: Números de telefone
- ENDERECO: Endereços completos ou parciais (ruas, bairros, etc.)
- OAB: Registros OAB de advogados
- DATA_NASCIMENTO: Datas de nascimento
- CEP: Códigos postais (formato XXXXX-XXX)
- CONTA_BANCARIA: Números de conta bancária
- AGENCIA: Números de agência bancária
- CNH: Números de CNH
- TITULO_ELEITOR: Números de título de eleitor
- PIS_PASEP: Números PIS/PASEP
- CTPS: Números de CTPS
- ORGANIZACAO: Nomes de empresas ou organizações privadas

## Regras:
1. NÃO identifique nomes de autoridades públicas (juízes, desembargadores, promotores) como PESSOA — esses devem ser mantidos visíveis.
2. Identifique TODAS as ocorrências, não apenas a primeira.
3. Retorne APENAS as entidades encontradas, não invente dados.
4. Para cada entidade, informe o texto exato como aparece no documento.

## Formato de resposta:
Responda APENAS com um JSON array, sem explicações:
[
  {"texto": "João da Silva", "tipo": "PESSOA"},
  {"texto": "123.456.789-00", "tipo": "CPF"}
]

Se não encontrar nenhuma entidade, responda: []"""


class NERLLMEngine:
    """
    Motor NER usando LLM local via Ollama.
    
    Vantagens sobre os outros engines:
    - Compreensão contextual profunda do texto
    - Entende o contexto jurídico brasileiro
    - Pode identificar entidades implícitas e contextuais
    - Não precisa de treinamento específico
    
    Limitações:
    - Mais lento (especialmente em CPU)
    - Requer Ollama rodando localmente
    - Resultados podem variar entre execuções
    """
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        ollama_url: Optional[str] = None,
        timeout: int = 120,
        temperature: float = 0.1,
    ):
        """
        Inicializa o motor NER com LLM.
        
        Args:
            model_name: Nome do modelo no Ollama (ex: 'qwen3.5:9b')
            ollama_url: URL base do Ollama (ex: 'http://localhost:11434')
            timeout: Timeout em segundos para cada chamada
            temperature: Temperatura da LLM (0-1, menor = mais determinístico)
        """
        self.model_name = model_name or getattr(settings, 'LLM_MODEL', 'qwen3.5:9b')
        self.ollama_url = ollama_url or getattr(settings, 'LLM_OLLAMA_URL', 'http://localhost:11434')
        self.timeout = timeout
        self.temperature = temperature
        self._available = None
    
    @property
    def is_available(self) -> bool:
        """Verifica se o Ollama está acessível e o modelo está disponível."""
        if self._available is None:
            try:
                response = httpx.get(
                    f"{self.ollama_url}/api/tags",
                    timeout=5.0
                )
                if response.status_code == 200:
                    data = response.json()
                    models = [m.get('name', '') for m in data.get('models', [])]
                    # Verificar se o modelo está disponível
                    if any(self.model_name in m for m in models):
                        self._available = True
                        logger.info(f"Ollama disponível com modelo {self.model_name}")
                    else:
                        logger.warning(
                            f"Ollama acessível mas modelo '{self.model_name}' não encontrado. "
                            f"Modelos disponíveis: {models}. "
                            f"Execute: ollama pull {self.model_name}"
                        )
                        self._available = False
                else:
                    self._available = False
            except Exception as e:
                logger.warning(
                    f"Ollama não acessível em {self.ollama_url}: {e}. "
                    "Execute: ollama serve"
                )
                self._available = False
        return self._available
    
    def _call_llm(self, user_prompt: str) -> str:
        """
        Faz uma chamada ao Ollama e retorna a resposta.
        
        Args:
            user_prompt: Prompt do usuário
            
        Returns:
            Texto da resposta da LLM
        """
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": 4096,
            },
            "format": "json",
        }
        
        response = httpx.post(
            f"{self.ollama_url}/api/chat",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get("message", {}).get("content", "[]")
    
    def _parse_llm_response(self, response_text: str, original_text: str) -> list[LLMEntity]:
        """
        Faz o parse da resposta JSON da LLM e localiza as entidades no texto original.
        
        Args:
            response_text: Resposta da LLM (JSON string)
            original_text: Texto original para localizar posições
            
        Returns:
            Lista de LLMEntity com posições corretas
        """
        entities = []
        
        try:
            # Tentar parsear o JSON diretamente
            parsed = json.loads(response_text)
            
            # Se a LLM retornou um dict com uma chave contendo a lista
            if isinstance(parsed, dict):
                # Procurar a primeira chave que contém uma lista
                for key in parsed:
                    if isinstance(parsed[key], list):
                        parsed = parsed[key]
                        break
                else:
                    parsed = []
            
            if not isinstance(parsed, list):
                logger.warning(f"Resposta da LLM não é uma lista: {type(parsed)}")
                return []
            
        except json.JSONDecodeError:
            # Tentar extrair JSON de dentro da resposta
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                except json.JSONDecodeError:
                    logger.error(f"Não foi possível parsear resposta da LLM: {response_text[:200]}")
                    return []
            else:
                logger.error(f"Nenhum JSON encontrado na resposta da LLM: {response_text[:200]}")
                return []
        
        # Tipos válidos do sistema
        VALID_TYPES = {
            'PESSOA', 'CPF', 'CNPJ', 'RG', 'EMAIL', 'TELEFONE',
            'ENDERECO', 'OAB', 'DATA_NASCIMENTO', 'CEP',
            'CONTA_BANCARIA', 'AGENCIA', 'CNH', 'TITULO_ELEITOR',
            'PIS_PASEP', 'CTPS', 'ORGANIZACAO', 'OUTRO',
        }
        
        for item in parsed:
            if not isinstance(item, dict):
                continue
                
            texto = item.get('texto', '').strip()
            tipo = item.get('tipo', 'OUTRO').upper().strip()
            
            if not texto:
                continue
            
            # Normalizar tipo
            if tipo not in VALID_TYPES:
                tipo = 'OUTRO'
            
            # Encontrar todas as ocorrências no texto original
            search_pos = 0
            while True:
                idx = original_text.find(texto, search_pos)
                if idx == -1:
                    # Tentar busca case-insensitive
                    idx_lower = original_text.lower().find(texto.lower(), search_pos)
                    if idx_lower == -1:
                        break
                    idx = idx_lower
                    # Usar o texto exato do documento
                    texto = original_text[idx:idx + len(texto)]
                
                entities.append(LLMEntity(
                    texto=texto,
                    tipo=tipo,
                    inicio=idx,
                    fim=idx + len(texto),
                    confianca=0.80,  # Confiança padrão para LLM
                    label_original=tipo,
                ))
                
                search_pos = idx + len(texto)
                break  # Por padrão, pegar apenas a primeira ocorrência
                       # Cada ocorrência será encontrada pelo pipeline ao buscar posição
        
        return entities
    
    def extract_entities(self, texto: str) -> list[LLMEntity]:
        """
        Extrai entidades PII do texto via LLM.
        
        Args:
            texto: Texto para analisar
            
        Returns:
            Lista de entidades PII identificadas
        """
        if not self.is_available:
            return []
        
        try:
            # Chunking para textos longos
            # Qwen 3.5 9B suporta ~32K tokens, mas para CPU ser mais rápido usamos chunks menores
            max_chunk_chars = 6000  # ~1500 tokens aprox
            overlap = 300
            
            all_entities = []
            
            if len(texto) <= max_chunk_chars:
                # Texto cabe em um único chunk
                response = self._call_llm(
                    f"Extraia todas as entidades sensíveis do seguinte texto jurídico:\n\n{texto}"
                )
                all_entities = self._parse_llm_response(response, texto)
            else:
                # Processar em chunks
                for chunk_start in range(0, len(texto), max_chunk_chars - overlap):
                    chunk_end = min(chunk_start + max_chunk_chars, len(texto))
                    chunk = texto[chunk_start:chunk_end]
                    
                    logger.info(
                        f"LLM NER: processando chunk {chunk_start}-{chunk_end} "
                        f"de {len(texto)} chars"
                    )
                    
                    response = self._call_llm(
                        f"Extraia todas as entidades sensíveis do seguinte trecho de documento jurídico:\n\n{chunk}"
                    )
                    
                    chunk_entities = self._parse_llm_response(response, chunk)
                    
                    # Ajustar posições para o texto completo
                    for entity in chunk_entities:
                        entity.inicio += chunk_start
                        entity.fim += chunk_start
                    
                    all_entities.extend(chunk_entities)
            
            # Deduplicar
            return self._deduplicate(all_entities)
            
        except httpx.TimeoutException:
            logger.error(
                f"Timeout ao chamar Ollama ({self.timeout}s). "
                "A LLM está rodando em CPU e pode ser lenta."
            )
            return []
        except Exception as e:
            logger.error(f"Erro na extração LLM: {e}")
            return []
    
    def _deduplicate(self, entities: list[LLMEntity]) -> list[LLMEntity]:
        """Remove duplicatas geradas pelo overlap de chunks."""
        seen = set()
        unique = []
        for ent in entities:
            key = (ent.texto.lower(), ent.tipo, ent.inicio)
            if key not in seen:
                seen.add(key)
                unique.append(ent)
        return unique
    
    def find_persons(self, texto: str) -> list[LLMEntity]:
        """Encontra apenas nomes de pessoas."""
        return [e for e in self.extract_entities(texto) if e.tipo == 'PESSOA']
    
    def find_pii_by_type(self, texto: str, tipo: str) -> list[LLMEntity]:
        """Encontra PII de um tipo específico."""
        return [e for e in self.extract_entities(texto) if e.tipo == tipo]
    
    def analyze_full_document(self, texto: str) -> dict:
        """Análise completa do documento."""
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
        
        return {
            'entidades': by_type,
            'total_entidades': len(entities),
            'modelo': self.model_name,
            'engine': 'llm',
        }
