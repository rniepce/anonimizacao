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
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
            ),

            # Telefones (Fixo e Celular) — requer DDD obrigatório para reduzir falsos positivos
            # Formatos: (31) 99999-0000 | (31)99999-0000 | 31 99999-0000 | +55 31 99999-0000
            "TELEFONE": re.compile(
                r"(?:\+?55[\s-]?)?(?:\(?\d{2}\)?[\s-])"
                r"(?:9\d{4}|\d{4})[-.\s]?\d{4}\b"
            ),

            # CEP — requer palavra-chave de contexto para evitar falsos positivos
            "CEP": re.compile(
                r"(?:CEP|C\.E\.P\.?)\s*[:.]?\s*(\d{2}\.?\d{3}-?\d{3})",
                re.IGNORECASE
            ),

            # RG com contexto (palavra "RG" ou "CI" antes)
            "RG": re.compile(
                r"(?:R\.?G\.?|C\.?I\.?|Identidade|Registro\s+Geral)\s*[:º]?\s*([\w\d\.-]+)",
                re.IGNORECASE
            ),

            # Passaporte brasileiro (letra + 6-7 dígitos, ou dois letras + 6 dígitos)
            "PASSAPORTE": re.compile(
                r"(?:Passaporte|Pass\.?)\s*[:.]?\s*([A-Z]{1,2}\d{6,7})\b",
                re.IGNORECASE
            ),

            # Data de nascimento com contexto
            "DATA_NASCIMENTO": re.compile(
                r"(?:nascido|nascida|nasc\.?|data\s+de\s+nascimento|DN)\s*[:.]?\s*"
                r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                re.IGNORECASE
            ),

            # Endereço (padrão brasileiro) com complemento opcional
            "ENDERECO": re.compile(
                r"(?:Rua|Av\.?|Avenida|Alameda|Travessa|Praça|Rodovia|Estrada|Viela|"
                r"Largo|Quadra|BR-\d+)\s+"
                r"[A-Za-zÀ-ÿ0-9\s]+,?\s*(?:n[º°]?\.?\s*)?\d+"
                r"(?:\s*,?\s*(?:Apto?\.?|Ap\.?|Bloco?\.?|Bl\.?|Casa|Sala|Loja|Conjunto|Cj\.?)"
                r"\s*[\w\d-]+)?",
                re.IGNORECASE
            ),

            # Carteira de Trabalho (CTPS)
            "CTPS": re.compile(
                r"(?:CTPS|Carteira\s+de\s+Trabalho(?:\s+e\s+Previdência\s+Social)?)"
                r"\s*[:.]?\s*(?:n[º°]?\.?\s*)?(\d{5,8})",
                re.IGNORECASE
            ),

            # PIS/PASEP/NIS/NIT
            "PIS_PASEP": re.compile(
                r"(?:PIS|PASEP|NIS|NIT)\s*[:.]?\s*(\d{3}\.?\d{5}\.?\d{2}-?\d)",
                re.IGNORECASE
            ),

            # Título de Eleitor
            "TITULO_ELEITOR": re.compile(
                r"(?:Título\s+(?:de\s+)?Eleitor|T\.?\s*E\.?)\s*[:.]?\s*(\d{4}\s?\d{4}\s?\d{4})",
                re.IGNORECASE
            ),

            # CNH
            "CNH": re.compile(
                r"(?:CNH|Carteira\s+(?:Nacional\s+)?(?:de\s+)?Habilitação|Permissão\s+para\s+Dirigir)"
                r"\s*[:.]?\s*(?:n[º°]?\.?\s*)?(\d{9,11})",
                re.IGNORECASE
            ),

            # RENAVAM (11 dígitos, comum em processos de trânsito)
            "RENAVAM": re.compile(
                r"(?:RENAVAM)\s*[:.]?\s*(\d{9,11})",
                re.IGNORECASE
            ),

            # Placa de veículo — formato antigo (ABC-1234) e Mercosul (ABC1D23)
            "PLACA_VEICULO": re.compile(
                r"\b(?:placa|veículo|veículo\s+de\s+placa|placa\s+de\s+prefixo)?\s*"
                r"([A-Z]{3}[-\s]?(?:\d{4}|\d[A-Z]\d{2}))\b",
                re.IGNORECASE
            ),

            # Conta bancária (padrão genérico)
            "CONTA_BANCARIA": re.compile(
                r"(?:Conta|C/?C|Conta\s+Corrente|Conta\s+Poupança|Poupança)\s*"
                r"(?:n[º°]?\.?)?\s*[:.]?\s*(\d{4,12}[-.]?\d{0,2})",
                re.IGNORECASE
            ),

            # Agência bancária
            "AGENCIA": re.compile(
                r"(?:Agência|Ag\.?)\s*(?:n[º°]?\.?)?\s*[:.]?\s*(\d{3,5}[-.]?\d?)",
                re.IGNORECASE
            ),

            # Chave PIX aleatória (UUID: 8-4-4-4-12 hex)
            "CHAVE_PIX": re.compile(
                r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
                re.IGNORECASE
            ),

            # Número de benefício INSS (10 dígitos)
            "BENEFICIO_INSS": re.compile(
                r"(?:benefício|beneficio|NB|nb|n\.?\s*b\.?)\s*[:.]?\s*"
                r"(\d{3}\.?\d{3}\.?\d{3}-?\d)",
                re.IGNORECASE
            ),

            # CNS — Cartão Nacional de Saúde (15 dígitos, começa com 1, 2, 7, 8 ou 9)
            "CNS": re.compile(
                r"(?:CNS|Cartão\s+(?:Nacional\s+de\s+)?Saúde|SUS)\s*[:.]?\s*"
                r"([12789]\d{14})",
                re.IGNORECASE
            ),

            # Matrícula SIAPE — servidores federais (7 dígitos)
            "SIAPE": re.compile(
                r"(?:SIAPE|matrícula\s+SIAPE|mat\.?\s*SIAPE)\s*[:.]?\s*(\d{7})",
                re.IGNORECASE
            ),

            # Registros profissionais (CRM, CREA, CRP, CRO, COREN, CRF, CRC)
            "REGISTRO_PROFISSIONAL": re.compile(
                r"\b(CRM|CREA|CRP|CRO|COREN|CRF|CRC|CREFITO|CFM)"
                r"[ /-]?(?:[A-Z]{2})?[ .]?\d{3,8}[A-Z]?\b",
                re.IGNORECASE
            ),

            # Nomes de pessoas em contexto jurídico
            "PESSOA_CONTEXTO": re.compile(
                r"(?:Autor(?:a)?|Réu|Ré|Requerente|Requerido(?:a)?|Indiciado(?:a)?|"
                r"Vítima|Investigado(?:a)?|Apelante|Apelado(?:a)?|Agravante|"
                r"Agravado(?:a)?|Impetrante|Impetrado(?:a)?|Reclamante|"
                r"Reclamado(?:a)?|Exequente|Executado(?:a)?|Paciente|"
                r"Denunciado(?:a)?|Querelante|Querelado(?:a)?|"
                r"Testemunha|Depoente|Informante|"
                r"Fiador(?:a)?|Avalista|Devedor(?:a)?|Credor(?:a)?|"
                r"Herdeiro(?:a)?|Inventariante|Espólio\s+de|"
                r"Terceiro(?:a)?(?:\s+Interessado(?:a)?)?|"
                r"(?:Menor|Criança|Adolescente)|"
                r"(?:Sr\.?|Sra\.?|Dr\.?|Dra\.?|Me\.?|Des\.?|Min\.?)|"
                r"Nome(?:\s+completo)?|"
                r"Genitor(?:a)?|Pai|Mãe|Filho(?:a)?|Cônjuge|Companheiro(?:a)?)"
                r"\s*[:.]?\s*"
                r"([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:d[aoe]s?|e|D[aoe]s?)\s+)?(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,6})",
                re.UNICODE
            ),
        }
    
    def find_all(self, texto: str) -> list[RegexMatch]:
        """
        Encontra todos os dados sensíveis no texto.

        Para CPF e CNPJ, valida os dígitos verificadores
        para eliminar falsos positivos.

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

                # Validação de dígitos verificadores para CPF e CNPJ
                if tipo == 'CPF':
                    cpf_digits = re.sub(r'\D', '', valor)
                    if not self.validate_cpf(cpf_digits):
                        continue
                elif tipo == 'CNPJ':
                    cnpj_digits = re.sub(r'\D', '', valor)
                    if not self.validate_cnpj(cnpj_digits):
                        continue

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
