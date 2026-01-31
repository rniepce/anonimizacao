"""
Pydantic schemas para a API
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Tipo de documento"""
    PDF = "pdf"
    DOCX = "docx"


class SensitiveDataType(str, Enum):
    """Tipos de dados sensíveis identificados"""
    CPF = "CPF"
    CNPJ = "CNPJ"
    PROC_CNJ = "PROC_CNJ"
    OAB = "OAB"
    EMAIL = "EMAIL"
    TELEFONE = "TELEFONE"
    CEP = "CEP"
    RG = "RG"
    PESSOA = "PESSOA"  # Nome de pessoa (NER)
    ENDERECO = "ENDERECO"  # Endereço (NER)
    DATA_NASCIMENTO = "DATA_NASCIMENTO"


class DocumentMetadata(BaseModel):
    """Metadados do documento para processamento"""
    classe_processual: Optional[str] = Field(None, description="Classe processual (ex: Ação Civil)")
    vara: Optional[str] = Field(None, description="Vara (ex: 1ª Vara Cível)")
    comarca: Optional[str] = Field(None, description="Comarca (ex: Belo Horizonte)")
    numero_processo: Optional[str] = Field(None, description="Número do processo CNJ")


class SensitiveData(BaseModel):
    """Dado sensível identificado"""
    tipo: SensitiveDataType
    valor: str
    pagina: int
    posicao: Optional[dict] = Field(None, description="Coordenadas {x, y, width, height}")
    confianca: float = Field(ge=0, le=1, description="Nível de confiança da detecção")
    contexto: Optional[str] = Field(None, description="Texto ao redor para contexto")


class AnalyzeResponse(BaseModel):
    """Resposta da análise de dados sensíveis"""
    job_id: str
    arquivo: str
    total_paginas: int
    tipo_pdf: str = Field(description="'nativo' ou 'imagem'")
    dados_sensiveis: list[SensitiveData]
    total_identificados: int
    tempo_processamento_ms: int


class AnonymizeResponse(BaseModel):
    """Resposta da anonimização"""
    job_id: str
    arquivo_original: str
    arquivo_anonimizado: str
    hash_original: str
    hash_anonimizado: str
    total_redacoes: int
    dados_anonimizados: list[SensitiveData]
    tempo_processamento_ms: int


class AuditLog(BaseModel):
    """Registro de auditoria"""
    job_id: str
    timestamp: datetime
    arquivo_original: str
    hash_original: str
    hash_anonimizado: str
    total_redacoes: int
    regras_aplicadas: list[str]
    usuario: Optional[str] = None
    ip_origem: Optional[str] = None


class AllowlistEntry(BaseModel):
    """Entrada na lista branca"""
    nome: str
    tipo: str = Field(description="'juiz', 'promotor', 'advogado'")
    registro: Optional[str] = Field(None, description="OAB ou matrícula")
    ativo: bool = True
