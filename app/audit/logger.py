"""
Sistema de Auditoria e Logs
Registra todas as operações de anonimização com hashes
"""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

# Hora Legal Brasileira (UTC-3) conforme CESEC
HLB = timezone(timedelta(hours=-3))

from app.config import settings


@dataclass
class AuditEntry:
    """Registro de auditoria"""
    job_id: str
    timestamp: str
    arquivo_original: str
    hash_original: str
    arquivo_anonimizado: str
    hash_anonimizado: str
    total_redacoes: int
    regras_aplicadas: list[str]
    dados_anonimizados: list[dict]
    tempo_processamento_ms: int
    usuario: Optional[str] = None
    ip_origem: Optional[str] = None


class AuditLogger:
    """
    Sistema de auditoria imutável para rastreabilidade.
    Gera hashes SHA-256 e armazena logs em formato JSON Lines.
    """
    
    def __init__(self, logs_dir: Path = None):
        self.logs_dir = logs_dir or settings.LOGS_DIR
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.logs_dir / "audit.jsonl"
    
    @staticmethod
    def calculate_hash(file_path: Path) -> str:
        """
        Calcula hash SHA-256 de um arquivo.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            Hash SHA-256 em hexadecimal
        """
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    @staticmethod
    def calculate_hash_bytes(content: bytes) -> str:
        """
        Calcula hash SHA-256 de bytes.
        
        Args:
            content: Conteúdo em bytes
            
        Returns:
            Hash SHA-256 em hexadecimal
        """
        return hashlib.sha256(content).hexdigest()
    
    def log_anonymization(
        self,
        job_id: str,
        arquivo_original: Path,
        arquivo_anonimizado: Path,
        total_redacoes: int,
        regras_aplicadas: list[str],
        dados_anonimizados: list[dict],
        tempo_processamento_ms: int,
        usuario: Optional[str] = None,
        ip_origem: Optional[str] = None
    ) -> AuditEntry:
        """
        Registra uma operação de anonimização.
        
        Args:
            job_id: ID único do job
            arquivo_original: Caminho do arquivo original
            arquivo_anonimizado: Caminho do arquivo anonimizado
            total_redacoes: Número de redações aplicadas
            regras_aplicadas: Lista de tipos de regras usadas
            dados_anonimizados: Dados que foram anonimizados
            tempo_processamento_ms: Tempo de processamento
            usuario: Usuário que executou (opcional)
            ip_origem: IP de origem (opcional)
            
        Returns:
            Entrada de auditoria criada
        """
        entry = AuditEntry(
            job_id=job_id,
            timestamp=datetime.now(HLB).isoformat(),
            arquivo_original=arquivo_original.name,
            hash_original=self.calculate_hash(arquivo_original),
            arquivo_anonimizado=arquivo_anonimizado.name,
            hash_anonimizado=self.calculate_hash(arquivo_anonimizado),
            total_redacoes=total_redacoes,
            regras_aplicadas=regras_aplicadas,
            dados_anonimizados=dados_anonimizados,
            tempo_processamento_ms=tempo_processamento_ms,
            usuario=usuario,
            ip_origem=ip_origem
        )
        
        # Append ao arquivo de log (JSON Lines)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + '\n')
        
        return entry
    
    def get_log(self, job_id: str) -> Optional[AuditEntry]:
        """
        Busca um registro de auditoria por job_id.
        
        Args:
            job_id: ID do job
            
        Returns:
            AuditEntry se encontrado, None caso contrário
        """
        if not self.log_file.exists():
            return None
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    if data.get('job_id') == job_id:
                        return AuditEntry(**data)
                except json.JSONDecodeError:
                    continue
        
        return None
    
    def get_logs_by_date(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> list[AuditEntry]:
        """
        Busca logs em um intervalo de datas.
        
        Args:
            start_date: Data inicial
            end_date: Data final
            
        Returns:
            Lista de entradas no período
        """
        if not self.log_file.exists():
            return []
        
        results = []
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    timestamp = datetime.fromisoformat(
                        data['timestamp'].replace('Z', '+00:00')
                    )
                    
                    if start_date <= timestamp <= end_date:
                        results.append(AuditEntry(**data))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        
        return results
    
    def get_statistics(self) -> dict:
        """
        Retorna estatísticas gerais dos logs.
        
        Returns:
            Dicionário com estatísticas
        """
        if not self.log_file.exists():
            return {
                'total_jobs': 0,
                'total_redacoes': 0,
                'por_tipo': {},
                'tempo_medio_ms': 0
            }
        
        total_jobs = 0
        total_redacoes = 0
        total_tempo = 0
        por_tipo = {}
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    total_jobs += 1
                    total_redacoes += data.get('total_redacoes', 0)
                    total_tempo += data.get('tempo_processamento_ms', 0)
                    
                    for regra in data.get('regras_aplicadas', []):
                        if regra not in por_tipo:
                            por_tipo[regra] = 0
                        por_tipo[regra] += 1
                except json.JSONDecodeError:
                    continue
        
        return {
            'total_jobs': total_jobs,
            'total_redacoes': total_redacoes,
            'por_tipo': por_tipo,
            'tempo_medio_ms': total_tempo // total_jobs if total_jobs > 0 else 0
        }
    
    def verify_integrity(self, job_id: str, file_path: Path) -> dict:
        """
        Verifica integridade de um arquivo comparando com hash registrado.
        
        Args:
            job_id: ID do job
            file_path: Caminho do arquivo a verificar
            
        Returns:
            Resultado da verificação
        """
        entry = self.get_log(job_id)
        
        if not entry:
            return {
                'valido': False,
                'erro': 'Job não encontrado no log de auditoria'
            }
        
        if not file_path.exists():
            return {
                'valido': False,
                'erro': 'Arquivo não encontrado'
            }
        
        hash_atual = self.calculate_hash(file_path)
        
        # Verificar se é o arquivo original ou anonimizado
        if hash_atual == entry.hash_original:
            return {
                'valido': True,
                'tipo': 'original',
                'hash': hash_atual
            }
        elif hash_atual == entry.hash_anonimizado:
            return {
                'valido': True,
                'tipo': 'anonimizado',
                'hash': hash_atual
            }
        else:
            return {
                'valido': False,
                'erro': 'Hash não corresponde aos registros',
                'hash_atual': hash_atual,
                'hash_esperado_original': entry.hash_original,
                'hash_esperado_anonimizado': entry.hash_anonimizado
            }


# Singleton para uso global
audit_logger = AuditLogger()
