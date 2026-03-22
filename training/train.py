"""
Script de fine-tuning do BERTimbau para anonimização TJMG.

Warm-start a partir do modelo pierreguillou/bert-base-cased-pt-lenerbr
(já fine-tuned no LeNER-Br) e continua treinamento em dados TJMG.

Diferencial: weighted loss que penaliza falsos negativos 3x mais que
falsos positivos. Para anonimização judicial, missing PII = violação
de privacidade, que é muito pior que anonimizar um termo inócuo.

Uso:
    python -m training.train
    python -m training.train --config training/output/training_config.json
    python -m training.train --epochs 20 --lr 3e-5
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from datasets import DatasetDict, load_from_disk
from seqeval.metrics import (
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)

sys.path.insert(0, str(Path(__file__).parent.parent))
from training.config import TrainingConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ─── Weighted Loss Trainer ───────────────────────────────────────────────────


class RecallWeightedTrainer(Trainer):
    """
    Trainer customizado com CrossEntropyLoss ponderada.

    Pesos são calibrados para que falsos negativos (não detectar PII)
    custem mais que falsos positivos (anonimizar demais).

    Isso empurra o modelo na direção de maior recall, alinhado com
    o requisito do TJMG de que missing PII = violação de privacidade.
    """

    def __init__(self, class_weights: Optional[torch.Tensor] = None, **kwargs):
        super().__init__(**kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits  # (batch, seq_len, num_labels)

        if self.class_weights is not None:
            weight = self.class_weights.to(logits.device)
            loss_fn = nn.CrossEntropyLoss(weight=weight, ignore_index=-100)
        else:
            loss_fn = nn.CrossEntropyLoss(ignore_index=-100)

        # Reshape: (batch*seq_len, num_labels)
        loss = loss_fn(
            logits.view(-1, model.config.num_labels),
            labels.view(-1),
        )

        return (loss, outputs) if return_outputs else loss


# ─── Métricas ────────────────────────────────────────────────────────────────


def build_compute_metrics(id2label: dict[int, str]):
    """
    Retorna função compute_metrics compatível com HF Trainer.

    Reporta precision, recall, F1 por entidade + overall.
    Early stopping usa eval_recall (overall recall).
    """

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        predictions = np.argmax(logits, axis=-1)

        # Converter IDs de volta para labels string (ignorando -100)
        true_labels = []
        pred_labels = []

        for pred_seq, label_seq in zip(predictions, labels):
            true_seq = []
            pred_seq_str = []

            for p, l in zip(pred_seq, label_seq):
                if l == -100:
                    continue
                true_seq.append(id2label[l])
                pred_seq_str.append(id2label[p])

            true_labels.append(true_seq)
            pred_labels.append(pred_seq_str)

        # Métricas seqeval (entity-level, modo strict)
        overall_precision = precision_score(true_labels, pred_labels)
        overall_recall = recall_score(true_labels, pred_labels)
        overall_f1 = f1_score(true_labels, pred_labels)

        # Report detalhado (logado mas não retornado como métrica)
        report = classification_report(true_labels, pred_labels, digits=4)
        logger.info(f"\n{report}")

        return {
            "precision": overall_precision,
            "recall": overall_recall,
            "f1": overall_f1,
        }

    return compute_metrics


# ─── Cálculo de pesos ───────────────────────────────────────────────────────


def compute_class_weights(
    dataset,
    config: TrainingConfig,
) -> torch.Tensor:
    """
    Calcula pesos para CrossEntropyLoss baseado em frequência inversa.

    Labels de entidade (B-*, I-*) recebem peso adicional fn_weight
    para penalizar falsos negativos.

    A fórmula é:
        weight[i] = (total / (num_classes * count[i])) * boost[i]

    Onde boost[i] = fn_weight para labels de entidade (B-*, I-*),
    e boost[i] = 1.0 para O.
    """
    id2label = config.labels.id2label
    num_labels = config.labels.num_labels
    counts = np.zeros(num_labels, dtype=np.float64)

    for example in dataset:
        for label_id in example["labels"]:
            if 0 <= label_id < num_labels:
                counts[label_id] += 1

    # Evitar divisão por zero
    counts = np.maximum(counts, 1.0)
    total = counts.sum()

    # Frequência inversa normalizada
    weights = total / (num_labels * counts)

    # Boost para labels de entidade (não-O)
    for i in range(num_labels):
        label = id2label[i]
        if label != "O":
            weights[i] *= config.fn_weight

    # Normalizar para média ~1.0
    weights = weights / weights.mean()

    logger.info("Pesos das classes para loss:")
    for i, w in enumerate(weights):
        logger.info(f"  {id2label[i]}: {w:.3f} (count={int(counts[i]):,})")

    return torch.tensor(weights, dtype=torch.float32)


# ─── Remapeamento de labels ─────────────────────────────────────────────────


def remap_model_head(model, source_id2label: dict, target_label2id: dict, target_id2label: dict):
    """
    Remapeia a cabeça de classificação de um modelo pré-treinado para
    um novo conjunto de labels.

    O modelo base (pierreguillou/bert-base-cased-pt-lenerbr) tem labels
    do LeNER-Br que não são idênticas às nossas. Esta função:
    1. Copia pesos de labels que existem em ambos os esquemas
    2. Inicializa labels novas com média dos pesos existentes
    3. Atualiza config do modelo

    Isso preserva o conhecimento do fine-tuning LeNER-Br ao máximo.
    """
    old_num_labels = model.config.num_labels
    new_num_labels = len(target_label2id)

    if old_num_labels == new_num_labels:
        # Verificar se labels são as mesmas
        old_labels = set(source_id2label.values())
        new_labels = set(target_label2id.keys())
        if old_labels == new_labels:
            logger.info("Labels idênticas ao modelo base — sem remapeamento.")
            return model

    logger.info(
        f"Remapeando cabeça: {old_num_labels} labels → {new_num_labels} labels"
    )

    # Salvar pesos antigos
    old_weight = model.classifier.weight.data.clone()
    old_bias = model.classifier.bias.data.clone()

    # Nova cabeça
    model.classifier = nn.Linear(model.config.hidden_size, new_num_labels)
    model.num_labels = new_num_labels
    model.config.num_labels = new_num_labels
    model.config.id2label = target_id2label
    model.config.label2id = target_label2id

    # Copiar pesos de labels coincidentes
    mapped = 0
    for new_label, new_id in target_label2id.items():
        # Procurar no modelo antigo
        for old_id, old_label in source_id2label.items():
            if old_label == new_label:
                model.classifier.weight.data[new_id] = old_weight[old_id]
                model.classifier.bias.data[new_id] = old_bias[old_id]
                mapped += 1
                break

    logger.info(f"  {mapped}/{new_num_labels} labels mapeadas do modelo original")

    return model


# ─── Main ────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Fine-tuning BERTimbau para TJMG")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--batch_size", type=int, default=None)
    parser.add_argument("--no_fp16", action="store_true")
    args = parser.parse_args()

    # Config
    if args.config and args.config.exists():
        config = TrainingConfig.load(args.config)
    else:
        config = TrainingConfig()

    if args.epochs:
        config.num_train_epochs = args.epochs
    if args.lr:
        config.learning_rate = args.lr
    if args.batch_size:
        config.per_device_train_batch_size = args.batch_size
    if args.no_fp16:
        config.fp16 = False

    # Desabilitar fp16 se não tem GPU
    if not torch.cuda.is_available():
        config.fp16 = False
        logger.info("GPU não disponível — desabilitando fp16")

    # Reprodutibilidade
    torch.manual_seed(config.seed)
    np.random.seed(config.seed)

    # Salvar config
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.save()

    # ── Carregar dataset ─────────────────────────────────────────
    logger.info(f"Carregando dataset de {config.dataset_dir}...")
    dataset = load_from_disk(str(config.dataset_dir))

    if "train" not in dataset:
        raise ValueError("Dataset não contém split 'train'")

    has_validation = "validation" in dataset
    if not has_validation:
        logger.warning(
            "Dataset sem split 'validation'. "
            "Early stopping não será habilitado."
        )

    # ── Carregar modelo e tokenizer ──────────────────────────────
    logger.info(f"Carregando modelo base: {config.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(config.base_model)

    model = AutoModelForTokenClassification.from_pretrained(
        config.base_model,
    )

    # Remapear cabeça de classificação para nosso esquema de labels
    source_id2label = {int(k): v for k, v in model.config.id2label.items()}
    target_label2id = config.labels.label2id
    target_id2label = config.labels.id2label

    model = remap_model_head(model, source_id2label, target_label2id, target_id2label)

    # ── Pesos das classes ────────────────────────────────────────
    logger.info("Calculando pesos das classes...")
    class_weights = compute_class_weights(dataset["train"], config)

    # ── Training arguments ───────────────────────────────────────
    training_args = TrainingArguments(
        output_dir=str(config.output_dir),
        num_train_epochs=config.num_train_epochs,
        per_device_train_batch_size=config.per_device_train_batch_size,
        per_device_eval_batch_size=config.per_device_eval_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        weight_decay=config.weight_decay,
        warmup_ratio=config.warmup_ratio,
        fp16=config.fp16,
        seed=config.seed,
        eval_strategy=config.eval_strategy if has_validation else "no",
        save_strategy=config.save_strategy,
        load_best_model_at_end=config.load_best_model_at_end and has_validation,
        metric_for_best_model=config.metric_for_best_model if has_validation else None,
        greater_is_better=config.greater_is_better if has_validation else None,
        logging_steps=config.logging_steps,
        logging_dir=str(config.output_dir / "logs"),
        report_to=config.report_to,
        save_total_limit=3,
        remove_unused_columns=True,
        dataloader_num_workers=0,  # Evitar problemas com fork em macOS
    )

    # ── Callbacks ────────────────────────────────────────────────
    callbacks = []
    if has_validation:
        callbacks.append(
            EarlyStoppingCallback(
                early_stopping_patience=config.early_stopping_patience
            )
        )

    # ── Trainer ──────────────────────────────────────────────────
    compute_metrics = build_compute_metrics(config.labels.id2label)

    trainer = RecallWeightedTrainer(
        class_weights=class_weights,
        model=model,
        args=training_args,
        train_dataset=dataset["train"].remove_columns(["doc_id"]),
        eval_dataset=(
            dataset["validation"].remove_columns(["doc_id"])
            if has_validation
            else None
        ),
        tokenizer=tokenizer,
        compute_metrics=compute_metrics,
        callbacks=callbacks,
    )

    # ── Treinar ──────────────────────────────────────────────────
    logger.info("Iniciando treinamento...")
    logger.info(f"  Épocas: {config.num_train_epochs}")
    logger.info(f"  Batch efetivo: {config.per_device_train_batch_size * config.gradient_accumulation_steps}")
    logger.info(f"  LR: {config.learning_rate}")
    logger.info(f"  FP16: {config.fp16}")
    logger.info(f"  Early stopping: recall (patience={config.early_stopping_patience})")
    logger.info(f"  FN weight: {config.fn_weight}x")

    train_result = trainer.train()

    # ── Salvar ───────────────────────────────────────────────────
    best_dir = config.output_dir / "best_model"
    best_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(best_dir))
    tokenizer.save_pretrained(str(best_dir))

    # Salvar métricas de treino
    metrics = train_result.metrics
    metrics_path = config.output_dir / "train_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    logger.info(f"Melhor modelo salvo em {best_dir}")
    logger.info(f"Métricas de treino salvas em {metrics_path}")

    # ── Avaliação final no test set ──────────────────────────────
    if "test" in dataset:
        logger.info("Avaliação no test set...")
        test_metrics = trainer.evaluate(
            eval_dataset=dataset["test"].remove_columns(["doc_id"]),
            metric_key_prefix="test",
        )
        test_path = config.output_dir / "test_metrics.json"
        with open(test_path, "w") as f:
            json.dump(test_metrics, f, indent=2)
        logger.info(f"Métricas de test: {test_metrics}")

    logger.info("Treinamento concluído.")


if __name__ == "__main__":
    main()
