"""
Configurações de treinamento para fine-tuning do BERTimbau no TJMG.

Todas as decisões de hiperparâmetros estão centralizadas aqui para
reprodutibilidade e rastreabilidade de experimentos.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class LabelSchema:
    """
    Esquema de labels IOB2 para anonimização TJMG.

    Apenas entidades que requerem NER. CPF, CNPJ, e-mail e telefone
    são tratados por regex com precisão ~1.0 e não entram no modelo.
    """

    # Labels IOB2 — ordem fixa para reprodutibilidade
    LABELS: list[str] = field(default_factory=lambda: [
        "O",
        "B-PESSOA",
        "I-PESSOA",
        "B-ORGANIZACAO",
        "I-ORGANIZACAO",
        "B-LOCAL",
        "I-LOCAL",
    ])

    # Label ignorada no cálculo de loss (subwords não-primeiro, padding, [CLS], [SEP])
    IGNORE_INDEX: int = -100

    @property
    def label2id(self) -> dict[str, int]:
        return {label: i for i, label in enumerate(self.LABELS)}

    @property
    def id2label(self) -> dict[int, str]:
        return {i: label for i, label in enumerate(self.LABELS)}

    @property
    def num_labels(self) -> int:
        return len(self.LABELS)

    @property
    def entity_types(self) -> list[str]:
        """Tipos de entidade sem prefixo IOB."""
        return sorted({l.split("-", 1)[1] for l in self.LABELS if l != "O"})


@dataclass
class TrainingConfig:
    """Hiperparâmetros e caminhos para o pipeline de treinamento."""

    # ── Modelo ───────────────────────────────────────────────────
    base_model: str = "pierreguillou/bert-base-cased-pt-lenerbr"
    # Diretório onde o melhor checkpoint será salvo
    output_dir: Path = Path("training/output")
    # Diretório com o dataset HuggingFace em disco
    dataset_dir: Path = Path("training/dataset")
    # Diretório com JSONs anotados
    annotations_dir: Path = Path("training/annotations")

    # ── Tokenização ──────────────────────────────────────────────
    max_seq_length: int = 512
    # Sliding window: stride em tokens para documentos longos
    doc_stride: int = 128

    # ── Treinamento ──────────────────────────────────────────────
    num_train_epochs: int = 15
    per_device_train_batch_size: int = 8
    per_device_eval_batch_size: int = 16
    gradient_accumulation_steps: int = 4  # batch efetivo = 8 * 4 = 32
    learning_rate: float = 2e-5
    weight_decay: float = 0.01
    warmup_ratio: float = 0.1
    fp16: bool = True  # Desligado automaticamente se não houver GPU
    seed: int = 42

    # ── Early stopping ───────────────────────────────────────────
    # Métrica para early stopping: recall (não F1) — missing PII = violação
    metric_for_best_model: str = "eval_recall"
    greater_is_better: bool = True
    early_stopping_patience: int = 4
    eval_strategy: str = "epoch"
    save_strategy: str = "epoch"
    load_best_model_at_end: bool = True

    # ── Class imbalance ──────────────────────────────────────────
    # Peso para falsos negativos vs falsos positivos.
    # FN (miss PII) é ~3x pior que FP (anonimizar demais) para o TJMG.
    fn_weight: float = 3.0
    # Pesos por label (O recebe peso baixo por ser majoritário).
    # Calculados automaticamente em train.py a partir das frequências,
    # mas estes são os defaults mínimos.
    label_weights: Optional[dict[str, float]] = None

    # ── Split ────────────────────────────────────────────────────
    train_ratio: float = 0.70
    dev_ratio: float = 0.15
    test_ratio: float = 0.15

    # ── Logging ──────────────────────────────────────────────────
    logging_steps: int = 10
    report_to: str = "none"  # "wandb" se tiver wandb instalado

    @property
    def labels(self) -> LabelSchema:
        return LabelSchema()

    def to_dict(self) -> dict:
        """Serializa config para JSON (para reprodutibilidade)."""
        import json

        d = {}
        for k, v in self.__dict__.items():
            if isinstance(v, Path):
                d[k] = str(v)
            else:
                d[k] = v
        # Adicionar labels
        d["labels"] = self.labels.LABELS
        return d

    def save(self, path: Optional[Path] = None):
        """Salva config em JSON."""
        import json

        path = path or (self.output_dir / "training_config.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path) -> "TrainingConfig":
        """Carrega config de JSON."""
        import json

        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        d.pop("labels", None)
        for k in ("output_dir", "dataset_dir", "annotations_dir"):
            if k in d:
                d[k] = Path(d[k])
        return cls(**d)
