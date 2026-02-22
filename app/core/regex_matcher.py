"""
Motor de Regex para identificação de dados sensíveis
Padrões específicos para o contexto jurídico brasileiro
"""
import re
from dataclasses import dataclass
from typing import Iterator


@dataclass
class RegexMatch:
    """Resultado de um match de regex"""
    tipo: str
    valor: str
    inicio: int
    fim: int


class RegexMatcher:
    """
    Motor de busca por padrões regex para dados sensíveis brasileiros.
    Otimizado para documentos jurídicos do TJMG.
    """
    
    def __init__(self):
        self.patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> dict[str, re.Pattern]:
        """Compila todos os padrões regex"""
        return {
            # CPF (Com ou sem pontuação) - Evita falsos positivos com \b
            "CPF": re.compile(
                r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"
            ),
            
            # CNPJ (Com ou sem pontuação)
            "CNPJ": re.compile(
                r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"
            ),
            
            # Numeração Única CNJ (NNNNNNN-DD.AAAA.J.TR.OOOO)
            "PROC_CNJ": re.compile(
                r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b"
            ),
            
            # OAB (Variações: OAB/MG 123.456, OAB-MG 123456, OAB 123456)
            "OAB": re.compile(
                r"\bOAB[ /-]?(?:[A-Z]{2})?[ .]?\d{1,7}[A-Z]?\b",
                re.IGNORECASE
            ),
            
            # E-mails
            "EMAIL": re.compile(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
            ),
            
            # Telefones (Fixo e Celular, com ou sem DDD, com ou sem +55)
            "TELEFONE": re.compile(
                r"(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?(?:9\d{4}|\d{4})[-.\s]?\d{4}\b"
            ),
            
            # CEP
            "CEP": re.compile(
                r"\b\d{2}\.?\d{3}-?\d{3}\b"
            ),
            
            # RG com contexto (palavra "RG" ou "CI" antes)
            "RG": re.compile(
                r"(?:R\.?G\.?|C\.?I\.?|Identidade|Registro\s+Geral)\s*[:º]?\s*([\w\d\.-]+)",
                re.IGNORECASE
            ),
            
            # Data de nascimento com contexto
            "DATA_NASCIMENTO": re.compile(
                r"(?:nascido|nascida|nasc\.?|data\s+de\s+nascimento|DN)\s*[:.]?\s*"
                r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                re.IGNORECASE
            ),
            
            # Endereço (padrão brasileiro comum)
            "ENDERECO": re.compile(
                r"(?:Rua|Av\.?|Avenida|Alameda|Travessa|Praça|Rodovia|BR-\d+)\s+"
                r"[A-Za-zÀ-ÿ\s]+,?\s*(?:n[º°]?\.?\s*)?\d+",
                re.IGNORECASE
            ),
            
            # Carteira de Trabalho (CTPS)
            "CTPS": re.compile(
                r"(?:CTPS|Carteira\s+de\s+Trabalho)\s*[:.]?\s*(\d{5,7})",
                re.IGNORECASE
            ),
            
            # PIS/PASEP
            "PIS_PASEP": re.compile(
                r"(?:PIS|PASEP|NIS|NIT)\s*[:.]?\s*(\d{3}\.?\d{5}\.?\d{2}-?\d)",
                re.IGNORECASE
            ),
            
            # Título de Eleitor
            "TITULO_ELEITOR": re.compile(
                r"(?:Título\s+(?:de\s+)?Eleitor|TE)\s*[:.]?\s*(\d{4}\s?\d{4}\s?\d{4})",
                re.IGNORECASE
            ),
            
            # CNH
            "CNH": re.compile(
                r"(?:CNH|Carteira\s+(?:Nacional\s+)?(?:de\s+)?Habilitação)\s*[:.]?\s*(\d{9,11})",
                re.IGNORECASE
            ),
            
            # Conta bancária (padrão genérico)
            "CONTA_BANCARIA": re.compile(
                r"(?:Conta|C/?C|Conta\s+Corrente|Poupança)\s*[:.]?\s*(\d{4,12}[-.]?\d?)",
                re.IGNORECASE
            ),
            
            # Agência bancária
            "AGENCIA": re.compile(
                r"(?:Agência|Ag\.?)\s*[:.]?\s*(\d{4}[-.]?\d?)",
                re.IGNORECASE
            ),
            
            # Nomes de pessoas em contexto jurídico
            # Captura nomes completos após palavras-chave comuns
            "PESSOA_CONTEXTO": re.compile(
                r"(?:Autor(?:a)?|Réu|Ré|Requerente|Requerido(?:a)?|Indiciado(?:a)?|"
                r"Vítima|Investigado(?:a)?|Apelante|Apelado(?:a)?|Agravante|"
                r"Agravado(?:a)?|Impetrante|Impetrado(?:a)?|Reclamante|"
                r"Reclamado(?:a)?|Exequente|Executado(?:a)?|Paciente|"
                r"Denunciado(?:a)?|Querelante|Querelado(?:a)?|"
                r"(?:Menor|Criança|Adolescente)|"
                r"(?:Sr\.?|Sra\.?|Dr\.?|Dra\.?)|"
                r"Nome(?:\s+completo)?|"
                r"Genitor(?:a)?|Pai|Mãe|Filho(?:a)?)"
                r"\s*[:.]?\s*"
                r"([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:d[aoe]s?|e|D[aoe]s?)\s+)?(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,6})",
                re.UNICODE
            ),
        }
    
    def find_all(self, texto: str) -> list[RegexMatch]:
        """
        Encontra todos os dados sensíveis no texto.
        
        Args:
            texto: Texto para analisar
            
        Returns:
            Lista de matches encontrados
        """
        matches = []
        
        for tipo, pattern in self.patterns.items():
            for match in pattern.finditer(texto):
                # Para padrões com grupos, pega o grupo capturado
                valor = match.group(1) if match.lastindex else match.group(0)
                matches.append(RegexMatch(
                    tipo=tipo,
                    valor=valor,
                    inicio=match.start(),
                    fim=match.end()
                ))
        
        # Ordenar por posição no texto
        matches.sort(key=lambda m: m.inicio)
        
        return matches
    
    def find_by_type(self, texto: str, tipo: str) -> list[RegexMatch]:
        """
        Encontra dados sensíveis de um tipo específico.
        
        Args:
            texto: Texto para analisar
            tipo: Tipo de dado (ex: 'CPF', 'CNPJ')
            
        Returns:
            Lista de matches do tipo especificado
        """
        if tipo not in self.patterns:
            raise ValueError(f"Tipo desconhecido: {tipo}")
        
        pattern = self.patterns[tipo]
        matches = []
        
        for match in pattern.finditer(texto):
            valor = match.group(1) if match.lastindex else match.group(0)
            matches.append(RegexMatch(
                tipo=tipo,
                valor=valor,
                inicio=match.start(),
                fim=match.end()
            ))
        
        return matches
    
    def validate_cpf(self, cpf: str) -> bool:
        """
        Valida um CPF usando dígitos verificadores.
        
        Args:
            cpf: CPF para validar (com ou sem pontuação)
            
        Returns:
            True se válido, False caso contrário
        """
        # Remove pontuação
        cpf = re.sub(r'\D', '', cpf)
        
        if len(cpf) != 11:
            return False
        
        # CPFs inválidos conhecidos
        if cpf == cpf[0] * 11:
            return False
        
        # Calcula primeiro dígito verificador
        soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
        resto = soma % 11
        digito1 = 0 if resto < 2 else 11 - resto
        
        if int(cpf[9]) != digito1:
            return False
        
        # Calcula segundo dígito verificador
        soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
        resto = soma % 11
        digito2 = 0 if resto < 2 else 11 - resto
        
        return int(cpf[10]) == digito2
    
    def validate_cnpj(self, cnpj: str) -> bool:
        """
        Valida um CNPJ usando dígitos verificadores.
        
        Args:
            cnpj: CNPJ para validar (com ou sem pontuação)
            
        Returns:
            True se válido, False caso contrário
        """
        # Remove pontuação
        cnpj = re.sub(r'\D', '', cnpj)
        
        if len(cnpj) != 14:
            return False
        
        # CNPJs inválidos conhecidos
        if cnpj == cnpj[0] * 14:
            return False
        
        # Cálculo dos dígitos verificadores
        def calc_digito(cnpj: str, peso: list) -> int:
            soma = sum(int(cnpj[i]) * peso[i] for i in range(len(peso)))
            resto = soma % 11
            return 0 if resto < 2 else 11 - resto
        
        peso1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        peso2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        
        digito1 = calc_digito(cnpj, peso1)
        digito2 = calc_digito(cnpj, peso2)
        
        return int(cnpj[12]) == digito1 and int(cnpj[13]) == digito2
    
    def get_context(self, texto: str, inicio: int, fim: int, janela: int = 50) -> str:
        """
        Extrai contexto ao redor de um match.
        
        Args:
            texto: Texto completo
            inicio: Posição inicial do match
            fim: Posição final do match
            janela: Número de caracteres de contexto
            
        Returns:
            Texto do entorno com o match destacado
        """
        ctx_inicio = max(0, inicio - janela)
        ctx_fim = min(len(texto), fim + janela)
        
        prefixo = texto[ctx_inicio:inicio]
        match = texto[inicio:fim]
        sufixo = texto[fim:ctx_fim]
        
        return f"...{prefixo}[{match}]{sufixo}..."


# Singleton para uso global
regex_matcher = RegexMatcher()
