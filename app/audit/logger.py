"""
Sistema de Auditoria e Logs
Registra todas as operações de anonimização com hashes
"""
import hashlib
import json
import threading
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from app.config import settings

# Hora Legal Brasileira (UTC-3) conforme CESEC
HLB = timezone(timedelta(hours=-3))


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

    Thread-safe (threading.Lock) e process-safe (filelock).
    Mantém índice em memória para lookups O(1) por job_id.
    """

    def __init__(self, logs_dir: Path = None):
        self.logs_dir = logs_dir or settings.LOGS_DIR
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.logs_dir / "audit.jsonl"

        # Lock in-process (threading)
        self._thread_lock = threading.Lock()

        # Índice em memória job_id → AuditEntry para lookups O(1)
        self._index: dict[str, AuditEntry] = {}

        # Carregar índice existente
        self._load_index()

    def _load_index(self) -> None:
        """Carrega índice job_id → AuditEntry a partir do arquivo em disco."""
        if not self.log_file.exists():
            return
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entry = AuditEntry(**data)
                        self._index[entry.job_id] = entry
                    except (json.JSONDecodeError, TypeError):
                        continue
        except OSError:
            pass

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
        Thread-safe e process-safe via filelock.

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

        line = json.dumps(asdict(entry), ensure_ascii=False) + '\n'

        # Escrita thread-safe + process-safe
        with self._thread_lock:
            try:
                from filelock import FileLock
                lock_path = str(self.log_file) + ".lock"
                with FileLock(lock_path, timeout=10):
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(line)
            except ImportError:
                # filelock não disponível: usar apenas thread lock (já adquirido)
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(line)

            # Atualizar índice em memória
            self._index[job_id] = entry

        return entry

    def get_log(self, job_id: str) -> Optional[AuditEntry]:
        """
        Busca um registro de auditoria por job_id.
        O(1) via índice em memória.

        Args:
            job_id: ID do job

        Returns:
            AuditEntry se encontrado, None caso contrário
        """
        return self._index.get(job_id)

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
        results = []

        with self._thread_lock:
            for entry in self._index.values():
                try:
                    timestamp = datetime.fromisoformat(
                        entry.timestamp.replace('Z', '+00:00')
                    )
                    if start_date <= timestamp <= end_date:
                        results.append(entry)
                except (ValueError, AttributeError):
                    continue

        return results

    def get_statistics(self) -> dict:
        """
        Retorna estatísticas gerais dos logs.
        O(n) sobre índice em memória (sem I/O).

        Returns:
            Dicionário com estatísticas
        """
        with self._thread_lock:
            entries = list(self._index.values())

        if not entries:
            return {
                'total_jobs': 0,
                'total_redacoes': 0,
                'por_tipo': {},
                'tempo_medio_ms': 0
            }

        total_redacoes = 0
        total_tempo = 0
        por_tipo: dict[str, int] = {}

        for entry in entries:
            total_redacoes += entry.total_redacoes
            total_tempo += entry.tempo_processamento_ms
            for regra in entry.regras_aplicadas:
                por_tipo[regra] = por_tipo.get(regra, 0) + 1

        n = len(entries)
        return {
            'total_jobs': n,
            'total_redacoes': total_redacoes,
            'por_tipo': por_tipo,
            'tempo_medio_ms': total_tempo // n if n > 0 else 0
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
