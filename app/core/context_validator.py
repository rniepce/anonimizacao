"""
Validador de Contexto Jurídico
Decide se uma entidade deve ou não ser anonimizada com base em:
1. Allowlist (Lista Branca)
2. Contexto Posicional (Cargo antes do nome)
3. Papéis Processuais (Autor, Réu, etc.)
"""
import re
from typing import Optional
from dataclasses import dataclass

from app.core.allowlist import allowlist_manager
from app.core.pdf_handler import TextBlock

@dataclass
class ContextDecision:
    should_anonymize: bool
    reason: str


class ContextoJuridicoValidator:
    """
    Validador heurístico para contexto jurídico brasileiro.
    Análise BIDIRECIONAL: verifica contexto ANTES e DEPOIS do nome.
    """
    
    def __init__(self):
        # ==== PREFIXOS (Texto ANTES do nome) ====
        
        # Cargos públicos que BLINDAM o nome (Manter visível)
        self.cargos_publicos_prefixo = re.compile(
            r"(?:Juiz|Juíza|Desembargador|Desembargadora|Escrivã|Escrivão|"
            r"Promotor|Promotora|Defensor|Defensora|Advogado|Advogada|Dr\.|Dra\.|"
            r"Perito|Perita|Conciliador|Conciliadora|Magistrado|Magistrada|"
            r"Exmo\.?\s*Sr\.?|Exma\.?\s*Sra\.?|MM\.?\s*Juiz|"
            r"Relator|Relatora|Revisor|Revisora|Vogal)\s*(?:de Direito|Substituto|Federal|Titular)?",
            re.IGNORECASE
        )
        
        # Papéis processuais que FORÇAM anonimização (Polo Ativo/Passivo)
        self.papeis_privados_prefixo = re.compile(
            r"(?:Autor|Autora|Réu|Ré|Requerente|Requerido|Requerida|Vítima|"
            r"Testemunha|Depoente|Agravante|Agravado|Agravada|Impetrante|Impetrado|"
            r"Exequente|Executado|Reclamante|Reclamado|Apelante|Apelado|"
            r"Embargante|Embargado|Querelante|Querelado)\s*:?",
            re.IGNORECASE
        )
        
        # ==== SUFIXOS (Texto DEPOIS do nome) ====
        
        # Cargos públicos após o nome (Ex: "João Carlos, magistrado")
        self.cargos_publicos_sufixo = re.compile(
            r"(?:,\s*)?(?:juiz|juíza|desembargador|desembargadora|magistrado|magistrada|"
            r"promotor|promotora|defensor|defensora|procurador|procuradora|"
            r"advogado|advogada|perito|perita|escrivão|escrivã|"
            r"relator|relatora|revisor|revisora|presidente|vice-presidente)",
            re.IGNORECASE
        )
        
        # Qualificações públicas após o nome
        self.qualificacoes_publicas_sufixo = re.compile(
            r"(?:,\s*)?(?:OAB[/-]?[A-Z]{2}[/-]?\d+|"
            r"matrícula\s*n?\.?\s*\d+|"
            r"inscrito\s*na\s*OAB|"
            r"membro\s*d[oa]\s*(?:MP|Ministério Público|Defensoria)|"
            r"titular\s*d[ao]?\s*\d+[ªºa]?\s*(?:Vara|Câmara|Turma))",
            re.IGNORECASE
        )
        
        # Papéis privados após o nome (Ex: "Maria, autora da ação")
        self.papeis_privados_sufixo = re.compile(
            r"(?:,\s*)?(?:autor[a]?\s*d[ao]|réu|ré\s*d[ao]|"
            r"requerente|requerido|vítima\s*d[ao]|"
            r"parte\s*(?:autora|ré|requerente)|"
            r"testemunha\s*d[ao]|"
            r"qualificad[oa]\s*nos\s*autos)",
            re.IGNORECASE
        )
        
    def validate(
        self, 
        text: str, 
        entity_text: str, 
        start_char: int, 
        end_char: int,
        entity_label: str
    ) -> ContextDecision:
        """
        Avalia se a entidade deve ser anonimizada.
        ANÁLISE BIDIRECIONAL: verifica contexto antes E depois do nome.
        
        Args:
            text: Texto completo do documento (ou fragmento grande)
            entity_text: Texto da entidade (o nome)
            start_char: Índice inicial no texto
            end_char: Índice final no texto
            entity_label: Label do NER (PESSOA, ORG, etc.)
            
        Returns:
            ContextDecision
        """
        name_clean = entity_text.strip()
        
        # REGRA 1: Allowlist (Banco de Dados / JSON)
        if allowlist_manager.is_allowed(name_clean):
            return ContextDecision(False, "Allowlist: Encontrado na base de autoridades")
            
        # REGRA 2: Padrão OAB no próprio nome
        if "OAB" in name_clean.upper():
            return ContextDecision(False, "Padrão OAB detectado no nome")
            
        # REGRA 3: Análise de Contexto BIDIRECIONAL
        
        # 3.1 Contexto ANTERIOR (100 chars antes)
        window_start = max(0, start_char - 100)
        previous_text = text[window_start:start_char]
        last_chunk_before = previous_text[-60:]  # Últimos 60 chars
        
        # 3.2 Contexto POSTERIOR (100 chars depois)
        window_end = min(len(text), end_char + 100)
        next_text = text[end_char:window_end]
        first_chunk_after = next_text[:60]  # Primeiros 60 chars
        
        # ==== VERIFICAR CARGOS PÚBLICOS (NÃO ANONIMIZAR) ====
        
        # Cargo público ANTES do nome
        if self.cargos_publicos_prefixo.search(last_chunk_before):
            return ContextDecision(False, "Contexto Público: Cargo detectado ANTES do nome")
        
        # Cargo público DEPOIS do nome (Ex: "João Carlos, magistrado")
        if self.cargos_publicos_sufixo.search(first_chunk_after):
            return ContextDecision(False, "Contexto Público: Cargo detectado APÓS o nome")
        
        # Qualificação pública DEPOIS (Ex: "OAB/MG 123456")
        if self.qualificacoes_publicas_sufixo.search(first_chunk_after):
            return ContextDecision(False, "Contexto Público: Qualificação profissional detectada")
        
        # ==== VERIFICAR PAPÉIS PRIVADOS (ANONIMIZAR) ====
        
        # Papel privado ANTES do nome
        if self.papeis_privados_prefixo.search(last_chunk_before):
            return ContextDecision(True, "Contexto Privado: Papel processual ANTES do nome")
        
        # Papel privado DEPOIS do nome (Ex: "Maria, autora da ação")
        if self.papeis_privados_sufixo.search(first_chunk_after):
            return ContextDecision(True, "Contexto Privado: Papel processual APÓS o nome")
            
        # REGRA 4: Safety Net (Padrão)
        if entity_label in ["PESSOA", "PER", "PERSON"]:
            return ContextDecision(True, "Default: Pessoa não identificada como pública")
            
        # Verificar entes públicos para ORG
        if entity_label in ["ORG", "ORGANIZACAO"]:
            entes_publicos = ["ESTADO", "UNIÃO", "MUNICIPIO", "MINISTÉRIO", "TRIBUNAL", "DEFENSORIA", "POLÍCIA"]
            upper_name = name_clean.upper()
            if any(ente in upper_name for ente in entes_publicos):
                return ContextDecision(False, "Ente Público detectado")
        
        return ContextDecision(False, "Default: Não anonimizar")

    def analyze_header(self, text: str) -> list[str]:
        """
        Extrai nomes do cabeçalho que DEVEM ser anonimizados (Autor, Réu).
        Retorna lista de nomes para anonimização agressiva.
        """
        # Limita a análise às primeiras 2000 caracteres (início do doc)
        header_text = text[:3000]
        
        names_to_hide = []
        
        # Padrões comuns de cabeçalho
        patterns = [
            r"(?:Autor|Requerente|Impetrante|Exequente|Agravante)es?\s*[:.]\s*([^\n]+)",
            r"(?:Réu|Ré|Requerido|Impetrado|Executado|Agravado)s?\s*[:.]\s*([^\n]+)",
        ]
        
        for pat in patterns:
            matches = re.finditer(pat, header_text, re.IGNORECASE)
            for match in matches:
                # O grupo 1 captura o nome (ou lista de nomes)
                content = match.group(1).strip()
                # Limpar ruídos comuns (ex: "e outros", "qualificados nos autos")
                content = re.split(r"[,;]|\be\b|\bqualificad", content)[0]
                name = content.strip()
                
                if len(name) > 3 and name.upper() not in ["A", "O", "OS", "AS"]:
                    names_to_hide.append(name)
                    
        return names_to_hide


# Singleton
context_validator = ContextoJuridicoValidator()
