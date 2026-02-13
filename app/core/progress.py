"""
Gerenciador de Progresso para processamento de documentos
Permite acompanhamento em tempo real via SSE
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable
from collections import defaultdict


@dataclass
class ProgressUpdate:
    """Atualização de progresso"""
    job_id: str
    etapa: str  # 'upload', 'extraction', 'detection', 'redaction', 'finalization'
    pagina_atual: int
    total_paginas: int
    porcentagem: float
    mensagem: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    dados_encontrados: int = 0
    
    def to_dict(self) -> dict:
        return {
            'job_id': self.job_id,
            'etapa': self.etapa,
            'pagina_atual': self.pagina_atual,
            'total_paginas': self.total_paginas,
            'porcentagem': self.porcentagem,
            'mensagem': self.mensagem,
            'timestamp': self.timestamp,
            'dados_encontrados': self.dados_encontrados
        }


class ProgressManager:
    """
    Gerenciador centralizado de progresso.
    Mantém estado de progresso por job_id e notifica listeners.
    """
    
    def __init__(self):
        self._progress: dict[str, ProgressUpdate] = {}
        self._queues: dict[str, list[asyncio.Queue]] = defaultdict(list)
    
    def update(self, progress: ProgressUpdate) -> None:
        """Atualiza progresso e notifica listeners"""
        self._progress[progress.job_id] = progress
        
        # Notificar todas as queues registradas para esse job
        for queue in self._queues.get(progress.job_id, []):
            try:
                queue.put_nowait(progress)
            except asyncio.QueueFull:
                pass  # Ignorar se a queue está cheia
    
    def get(self, job_id: str) -> Optional[ProgressUpdate]:
        """Obtém último progresso de um job"""
        return self._progress.get(job_id)
    
    def register_listener(self, job_id: str) -> asyncio.Queue:
        """Registra um listener para receber atualizações de um job"""
        queue = asyncio.Queue(maxsize=100)
        self._queues[job_id].append(queue)
        return queue
    
    def unregister_listener(self, job_id: str, queue: asyncio.Queue) -> None:
        """Remove um listener"""
        if job_id in self._queues:
            try:
                self._queues[job_id].remove(queue)
            except ValueError:
                pass
            if not self._queues[job_id]:
                del self._queues[job_id]
    
    def cleanup(self, job_id: str) -> None:
        """Limpa dados de um job concluído"""
        self._progress.pop(job_id, None)
        self._queues.pop(job_id, None)
    
    def create_callback(self, job_id: str, total_paginas: int) -> Callable:
        """
        Cria callback para uso no pipeline.
        
        Uso:
            callback = progress_manager.create_callback(job_id, total_paginas)
            callback('extraction', pagina=1, mensagem='Extraindo página 1')
        """
        def callback(
            etapa: str,
            pagina: int = 0,
            mensagem: str = "",
            dados_encontrados: int = 0
        ):
            # Calcular porcentagem baseada na etapa e página
            etapa_pesos = {
                'upload': 5,
                'extraction': 40,
                'detection': 40,
                'redaction': 10,
                'finalization': 5
            }
            
            peso_etapa = etapa_pesos.get(etapa, 0)
            peso_anterior = sum(etapa_pesos[e] for e in list(etapa_pesos.keys())[:list(etapa_pesos.keys()).index(etapa)])
            
            if total_paginas > 0 and pagina > 0:
                progresso_na_etapa = (pagina / total_paginas) * peso_etapa
            else:
                progresso_na_etapa = peso_etapa
                
            porcentagem = peso_anterior + progresso_na_etapa
            
            update = ProgressUpdate(
                job_id=job_id,
                etapa=etapa,
                pagina_atual=pagina,
                total_paginas=total_paginas,
                porcentagem=min(porcentagem, 100),
                mensagem=mensagem,
                dados_encontrados=dados_encontrados
            )
            self.update(update)
        
        return callback


# Singleton global
progress_manager = ProgressManager()
