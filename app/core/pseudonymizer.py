"""
Sistema de Pseudonimização Consistente
Substitui dados sensíveis por dados fake, mas mantém consistência.
Ex: Mesmo CPF sempre gera o mesmo CPF fake no documento.
"""
import hashlib
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable


@dataclass
class PseudonymMapping:
    """Mapeamento de valor real para pseudônimo"""
    tipo: str
    valor_original: str
    valor_pseudonimo: str
    hash_original: str


class Pseudonymizer:
    """
    Gerador de pseudônimos consistentes.
    
    Garante que:
    - Mesmo valor original → mesmo pseudônimo
    - Pseudônimos são sintaticamente válidos
    - Não há vazamento do valor original
    """
    
    # Primeiros nomes comuns brasileiros
    PRIMEIRO_NOMES_M = [
        "João", "José", "Carlos", "Paulo", "Pedro", "Lucas", "Marcos", 
        "Antonio", "Francisco", "Rafael", "Gabriel", "Bruno", "Thiago",
        "Felipe", "Gustavo", "Rodrigo", "Fernando", "Ricardo", "Eduardo"
    ]
    
    PRIMEIRO_NOMES_F = [
        "Maria", "Ana", "Juliana", "Fernanda", "Patricia", "Camila",
        "Adriana", "Luciana", "Mariana", "Carolina", "Beatriz", "Larissa",
        "Amanda", "Gabriela", "Renata", "Vanessa", "Leticia", "Priscila"
    ]
    
    SOBRENOMES = [
        "Silva", "Santos", "Oliveira", "Souza", "Lima", "Pereira",
        "Costa", "Ferreira", "Rodrigues", "Almeida", "Nascimento",
        "Carvalho", "Araújo", "Ribeiro", "Martins", "Gomes", "Barbosa",
        "Rocha", "Dias", "Moreira", "Alves", "Monteiro", "Mendes"
    ]
    
    def __init__(self, seed: str = None):
        """
        Inicializa o pseudonymizer.
        
        Args:
            seed: Semente para consistência entre execuções.
                  Use o job_id para consistência dentro do mesmo job.
        """
        self.seed = seed or "default_seed"
        self._cache: Dict[str, PseudonymMapping] = {}
        self._generators: Dict[str, Callable] = {
            'CPF': self._generate_cpf,
            'CNPJ': self._generate_cnpj,
            'PESSOA': self._generate_nome,
            'NOME': self._generate_nome,
            'EMAIL': self._generate_email,
            'TELEFONE': self._generate_telefone,
            'ENDERECO': self._generate_endereco,
            'DATA': self._generate_data,
            'CEP': self._generate_cep,
            'RG': self._generate_rg,
        }
    
    def _get_deterministic_random(self, valor: str) -> random.Random:
        """
        Cria um gerador random determinístico baseado no valor.
        Mesmo valor + seed → mesma sequência random.
        """
        combined = f"{self.seed}:{valor}"
        hash_bytes = hashlib.sha256(combined.encode()).digest()
        seed_int = int.from_bytes(hash_bytes[:8], 'big')
        return random.Random(seed_int)
    
    def pseudonymize(self, tipo: str, valor: str) -> str:
        """
        Gera pseudônimo para um valor.
        
        Args:
            tipo: Tipo do dado (CPF, PESSOA, EMAIL, etc.)
            valor: Valor original
            
        Returns:
            Valor pseudonimizado
        """
        # Verificar cache
        cache_key = f"{tipo}:{valor}"
        if cache_key in self._cache:
            return self._cache[cache_key].valor_pseudonimo
        
        # Gerar pseudônimo
        tipo_upper = tipo.upper()
        generator = self._generators.get(tipo_upper)
        
        if generator:
            pseudonimo = generator(valor)
        else:
            # Fallback: substituir por placeholder
            pseudonimo = f"[{tipo_upper}_ANON]"
        
        # Cachear
        self._cache[cache_key] = PseudonymMapping(
            tipo=tipo,
            valor_original=valor,
            valor_pseudonimo=pseudonimo,
            hash_original=hashlib.sha256(valor.encode()).hexdigest()[:16]
        )
        
        return pseudonimo
    
    def _generate_cpf(self, valor: str) -> str:
        """Gera CPF fake válido"""
        rng = self._get_deterministic_random(valor)
        
        # Gerar 9 primeiros dígitos
        cpf = [rng.randint(0, 9) for _ in range(9)]
        
        # Calcular primeiro dígito verificador
        soma = sum((10 - i) * cpf[i] for i in range(9))
        resto = soma % 11
        cpf.append(0 if resto < 2 else 11 - resto)
        
        # Calcular segundo dígito verificador
        soma = sum((11 - i) * cpf[i] for i in range(10))
        resto = soma % 11
        cpf.append(0 if resto < 2 else 11 - resto)
        
        # Formatar
        cpf_str = ''.join(map(str, cpf))
        return f"{cpf_str[:3]}.{cpf_str[3:6]}.{cpf_str[6:9]}-{cpf_str[9:]}"
    
    def _generate_cnpj(self, valor: str) -> str:
        """Gera CNPJ fake válido"""
        rng = self._get_deterministic_random(valor)
        
        # Gerar 8 primeiros dígitos + 4 fixos (0001)
        cnpj = [rng.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]
        
        # Calcular primeiro dígito verificador
        pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        soma = sum(pesos1[i] * cnpj[i] for i in range(12))
        resto = soma % 11
        cnpj.append(0 if resto < 2 else 11 - resto)
        
        # Calcular segundo dígito verificador
        pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        soma = sum(pesos2[i] * cnpj[i] for i in range(13))
        resto = soma % 11
        cnpj.append(0 if resto < 2 else 11 - resto)
        
        # Formatar
        cnpj_str = ''.join(map(str, cnpj))
        return f"{cnpj_str[:2]}.{cnpj_str[2:5]}.{cnpj_str[5:8]}/{cnpj_str[8:12]}-{cnpj_str[12:]}"
    
    def _generate_nome(self, valor: str) -> str:
        """Gera nome fake"""
        rng = self._get_deterministic_random(valor)
        
        # Determinar gênero baseado no nome original (heurística simples)
        is_female = valor.strip().split()[0].lower().endswith('a') if valor else False
        
        primeiro_nomes = self.PRIMEIRO_NOMES_F if is_female else self.PRIMEIRO_NOMES_M
        
        primeiro = rng.choice(primeiro_nomes)
        sobrenome1 = rng.choice(self.SOBRENOMES)
        sobrenome2 = rng.choice(self.SOBRENOMES)
        
        return f"{primeiro} {sobrenome1} {sobrenome2}"
    
    def _generate_email(self, valor: str) -> str:
        """Gera email fake"""
        rng = self._get_deterministic_random(valor)
        
        nome = rng.choice(self.PRIMEIRO_NOMES_M + self.PRIMEIRO_NOMES_F).lower()
        sobrenome = rng.choice(self.SOBRENOMES).lower()
        numero = rng.randint(1, 999)
        dominio = rng.choice(['email.com', 'mail.com', 'correio.com.br', 'exemplo.com'])
        
        return f"{nome}.{sobrenome}{numero}@{dominio}"
    
    def _generate_telefone(self, valor: str) -> str:
        """Gera telefone fake"""
        rng = self._get_deterministic_random(valor)
        
        ddd = rng.randint(11, 99)
        prefixo = rng.choice(['9', '98', '99'])
        numero = ''.join([str(rng.randint(0, 9)) for _ in range(8 - len(prefixo))])
        
        return f"({ddd}) {prefixo}{numero[:4]}-{numero[4:]}"
    
    def _generate_endereco(self, valor: str) -> str:
        """Gera endereço fake"""
        rng = self._get_deterministic_random(valor)
        
        tipos = ["Rua", "Avenida", "Alameda", "Travessa", "Praça"]
        nomes = ["das Flores", "Brasil", "Principal", "Central", "do Comércio", "da Paz"]
        
        tipo = rng.choice(tipos)
        nome = rng.choice(nomes)
        numero = rng.randint(1, 9999)
        
        return f"{tipo} {nome}, {numero}"
    
    def _generate_data(self, valor: str) -> str:
        """Gera data fake (mantém formato similar)"""
        rng = self._get_deterministic_random(valor)
        
        # Gerar data aleatória entre 1950 e 2010
        start = datetime(1950, 1, 1)
        end = datetime(2010, 12, 31)
        delta = end - start
        random_days = rng.randint(0, delta.days)
        data = start + timedelta(days=random_days)
        
        # Detectar formato original
        if '/' in valor:
            return data.strftime("%d/%m/%Y")
        elif '-' in valor:
            return data.strftime("%Y-%m-%d")
        else:
            return data.strftime("%d/%m/%Y")
    
    def _generate_cep(self, valor: str) -> str:
        """Gera CEP fake"""
        rng = self._get_deterministic_random(valor)
        
        # CEPs começam com 01000 a 99999
        parte1 = rng.randint(10000, 99999)
        parte2 = rng.randint(0, 999)
        
        return f"{parte1:05d}-{parte2:03d}"
    
    def _generate_rg(self, valor: str) -> str:
        """Gera RG fake"""
        rng = self._get_deterministic_random(valor)
        
        numeros = ''.join([str(rng.randint(0, 9)) for _ in range(8)])
        digito = rng.choice(['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'X'])
        
        return f"{numeros[:2]}.{numeros[2:5]}.{numeros[5:8]}-{digito}"
    
    def get_mapping_report(self) -> Dict[str, list]:
        """
        Retorna relatório de todos os mapeamentos feitos.
        
        Returns:
            Dict com mapeamentos por tipo (valores são hasheados)
        """
        report = {}
        for mapping in self._cache.values():
            if mapping.tipo not in report:
                report[mapping.tipo] = []
            report[mapping.tipo].append({
                'hash_original': mapping.hash_original,
                'pseudonimo': mapping.valor_pseudonimo
            })
        return report
    
    def clear_cache(self):
        """Limpa o cache de mapeamentos"""
        self._cache.clear()


# Factory para criar pseudonymizer por job
def create_pseudonymizer(job_id: str) -> Pseudonymizer:
    """
    Cria um pseudonymizer para um job específico.
    
    Args:
        job_id: ID do job para garantir consistência
        
    Returns:
        Instância de Pseudonymizer
    """
    return Pseudonymizer(seed=job_id)
