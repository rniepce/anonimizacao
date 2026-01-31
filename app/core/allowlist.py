"""
Sistema de Allowlist (Lista Branca)
Gerencia lista de juízes, promotores e advogados que não devem ser anonimizados
"""
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from app.config import settings


@dataclass
class AllowlistItem:
    """Item da lista branca"""
    nome: str
    tipo: str  # 'juiz', 'promotor', 'advogado', 'servidor'
    registro: Optional[str] = None  # OAB ou matrícula
    ativo: bool = True


class AllowlistManager:
    """
    Gerenciador de lista branca para excluir da anonimização.
    Juízes, promotores e advogados públicos não devem ser anonimizados.
    """
    
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or settings.ALLOWLIST_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Arquivos de dados
        self.juizes_file = self.data_dir / "juizes.json"
        self.promotores_file = self.data_dir / "promotores.json"
        self.advogados_file = self.data_dir / "advogados.json"
        self.servidores_file = self.data_dir / "servidores.json"
        
        # Cache em memória
        self._cache: dict[str, list[AllowlistItem]] = {}
        self._names_set: set[str] = set()
        
        # Carregar dados
        self._load_all()
    
    def _load_file(self, filepath: Path) -> list[AllowlistItem]:
        """Carrega um arquivo JSON de allowlist"""
        if not filepath.exists():
            return []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [AllowlistItem(**item) for item in data]
        except Exception:
            return []
    
    def _save_file(self, filepath: Path, items: list[AllowlistItem]) -> None:
        """Salva lista em arquivo JSON"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump([asdict(item) for item in items], f, ensure_ascii=False, indent=2)
    
    def _load_all(self) -> None:
        """Carrega todos os arquivos de allowlist"""
        self._cache = {
            'juiz': self._load_file(self.juizes_file),
            'promotor': self._load_file(self.promotores_file),
            'advogado': self._load_file(self.advogados_file),
            'servidor': self._load_file(self.servidores_file),
        }
        
        # Construir set de nomes para busca rápida
        self._names_set = set()
        for items in self._cache.values():
            for item in items:
                if item.ativo:
                    # Normalizar nome para comparação
                    nome_normalizado = self._normalize_name(item.nome)
                    self._names_set.add(nome_normalizado)
    
    def _normalize_name(self, nome: str) -> str:
        """Normaliza nome para comparação (minúsculo, sem acentos extras)"""
        return nome.lower().strip()
    
    def is_allowed(self, nome: str) -> bool:
        """
        Verifica se um nome está na lista branca.
        
        Args:
            nome: Nome a verificar
            
        Returns:
            True se está na lista branca (não deve ser anonimizado)
        """
        nome_normalizado = self._normalize_name(nome)
        
        # Busca exata
        if nome_normalizado in self._names_set:
            return True
        
        # Busca parcial (nome contido em algum item)
        for nome_lista in self._names_set:
            if nome_normalizado in nome_lista or nome_lista in nome_normalizado:
                return True
        
        return False
    
    def get_match(self, nome: str) -> Optional[AllowlistItem]:
        """
        Retorna o item da allowlist que corresponde ao nome.
        
        Args:
            nome: Nome a buscar
            
        Returns:
            AllowlistItem se encontrado, None caso contrário
        """
        nome_normalizado = self._normalize_name(nome)
        
        for items in self._cache.values():
            for item in items:
                if item.ativo:
                    item_normalizado = self._normalize_name(item.nome)
                    if (nome_normalizado in item_normalizado or 
                        item_normalizado in nome_normalizado):
                        return item
        
        return None
    
    def add_item(self, item: AllowlistItem) -> None:
        """
        Adiciona item à lista branca.
        
        Args:
            item: Item a adicionar
        """
        tipo = item.tipo.lower()
        if tipo not in self._cache:
            self._cache[tipo] = []
        
        self._cache[tipo].append(item)
        
        if item.ativo:
            self._names_set.add(self._normalize_name(item.nome))
        
        # Persistir
        file_map = {
            'juiz': self.juizes_file,
            'promotor': self.promotores_file,
            'advogado': self.advogados_file,
            'servidor': self.servidores_file,
        }
        
        if tipo in file_map:
            self._save_file(file_map[tipo], self._cache[tipo])
    
    def remove_item(self, nome: str) -> bool:
        """
        Remove item da lista branca.
        
        Args:
            nome: Nome a remover
            
        Returns:
            True se removido, False se não encontrado
        """
        nome_normalizado = self._normalize_name(nome)
        
        for tipo, items in self._cache.items():
            for i, item in enumerate(items):
                if self._normalize_name(item.nome) == nome_normalizado:
                    del self._cache[tipo][i]
                    self._names_set.discard(nome_normalizado)
                    
                    # Persistir
                    file_map = {
                        'juiz': self.juizes_file,
                        'promotor': self.promotores_file,
                        'advogado': self.advogados_file,
                        'servidor': self.servidores_file,
                    }
                    
                    if tipo in file_map:
                        self._save_file(file_map[tipo], self._cache[tipo])
                    
                    return True
        
        return False
    
    def list_all(self, tipo: Optional[str] = None) -> list[AllowlistItem]:
        """
        Lista todos os itens da allowlist.
        
        Args:
            tipo: Filtrar por tipo (opcional)
            
        Returns:
            Lista de itens
        """
        if tipo:
            return self._cache.get(tipo.lower(), [])
        
        all_items = []
        for items in self._cache.values():
            all_items.extend(items)
        return all_items
    
    def import_csv(self, csv_path: Path, tipo: str) -> int:
        """
        Importa lista de um arquivo CSV.
        Formato: nome,registro
        
        Args:
            csv_path: Caminho do arquivo CSV
            tipo: Tipo dos itens (juiz, promotor, advogado)
            
        Returns:
            Número de itens importados
        """
        import csv
        
        count = 0
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 1:
                    nome = row[0].strip()
                    registro = row[1].strip() if len(row) > 1 else None
                    
                    if nome:
                        item = AllowlistItem(
                            nome=nome,
                            tipo=tipo,
                            registro=registro,
                            ativo=True
                        )
                        self.add_item(item)
                        count += 1
        
        return count
    
    def get_stats(self) -> dict:
        """
        Retorna estatísticas da allowlist.
        
        Returns:
            Dicionário com contagens por tipo
        """
        return {
            tipo: len([i for i in items if i.ativo])
            for tipo, items in self._cache.items()
        }


# Singleton para uso global
allowlist_manager = AllowlistManager()
