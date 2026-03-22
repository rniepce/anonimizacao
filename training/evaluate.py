"""
Avaliação completa do modelo fine-tuned vs baseline.

Reporta:
1. Entity-level: precision, recall, F1 por tipo (PESSOA, ORGANIZACAO, LOCAL)
2. Document-level: % de docs com zero missed PII ("zero-leak rate")
3. Confusion matrix por tipo de entidade
4. Comparação head-to-head com modelo baseline (LeNER-Br)

Uso:
    python -m training.evaluate
    python -m training.evaluate --model training/output/best_model
    python -m training.evaluate --compare  # compara com baseline
"""
import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from datasets import load_from_disk
from seqeval.metrics import classification_report, f1_score, precision_score, recall_score
from seqeval.scheme import IOB2
from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline as hf_pipeline

sys.path.insert(0, str(Path(__file__).parent.parent))
from training.config import TrainingConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ─── Predição ────────────────────────────────────────────────────────────────


def predict_dataset(model, tokenizer, dataset, id2label: dict, batch_size: int = 16):
    """
    Roda predição em todo o dataset e retorna labels verdadeiros e preditos.

    Retorna:
        all_true: list[list[str]]  — labels verdadeiros por sequência
        all_pred: list[list[str]]  — labels preditos por sequência
        doc_ids: list[str]         — doc_id de cada sequência
    """
    model.eval()
    device = next(model.parameters()).device

    all_true = []
    all_pred = []
    doc_ids = []

    for i in range(0, len(dataset), batch_size):
        batch = dataset[i : i + batch_size]

        input_ids = torch.tensor(batch["input_ids"], dtype=torch.long).to(device)
        attention_mask = torch.tensor(batch["attention_mask"], dtype=torch.long).to(device)
        labels = batch["labels"]  # list of lists

        with torch.no_grad():
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            preds = torch.argmax(outputs.logits, dim=-1).cpu().numpy()

        for seq_idx in range(len(labels)):
            true_seq = []
            pred_seq = []

            for token_idx, label_id in enumerate(labels[seq_idx]):
                if label_id == -100:
                    continue
                true_seq.append(id2label[label_id])
                pred_seq.append(id2label[int(preds[seq_idx][token_idx])])

            all_true.append(true_seq)
            all_pred.append(pred_seq)

        if "doc_id" in batch:
            doc_ids.extend(
                batch["doc_id"] if isinstance(batch["doc_id"], list) else [batch["doc_id"]]
            )

    return all_true, all_pred, doc_ids


# ─── Entity-level metrics ───────────────────────────────────────────────────


def entity_level_report(
    all_true: list[list[str]],
    all_pred: list[list[str]],
) -> dict:
    """
    Calcula precision, recall, F1 por tipo de entidade (seqeval strict mode).
    """
    report_str = classification_report(all_true, all_pred, digits=4, scheme=IOB2)
    logger.info(f"\n=== Entity-Level Report ===\n{report_str}")

    overall = {
        "precision": precision_score(all_true, all_pred, scheme=IOB2),
        "recall": recall_score(all_true, all_pred, scheme=IOB2),
        "f1": f1_score(all_true, all_pred, scheme=IOB2),
    }

    # Parse per-entity from seqeval (manual — seqeval não expõe dict)
    per_entity = {}
    for line in report_str.strip().split("\n"):
        parts = line.split()
        if len(parts) >= 5 and parts[0] not in ("", "micro", "macro", "weighted"):
            entity = parts[0]
            per_entity[entity] = {
                "precision": float(parts[1]),
                "recall": float(parts[2]),
                "f1": float(parts[3]),
                "support": int(parts[4]),
            }

    return {
        "overall": overall,
        "per_entity": per_entity,
        "report_text": report_str,
    }


# ─── Document-level zero-leak rate ──────────────────────────────────────────


def extract_entities_from_bio(labels: list[str]) -> list[tuple[str, int, int]]:
    """
    Extrai entidades (tipo, start, end) de uma sequência IOB2.
    """
    entities = []
    current_type = None
    current_start = None

    for i, label in enumerate(labels):
        if label.startswith("B-"):
            if current_type is not None:
                entities.append((current_type, current_start, i))
            current_type = label[2:]
            current_start = i
        elif label.startswith("I-") and current_type == label[2:]:
            pass  # Continua entidade
        else:
            if current_type is not None:
                entities.append((current_type, current_start, i))
                current_type = None
                current_start = None

    if current_type is not None:
        entities.append((current_type, current_start, len(labels)))

    return entities


def document_level_metrics(
    all_true: list[list[str]],
    all_pred: list[list[str]],
    doc_ids: list[str],
) -> dict:
    """
    Calcula métricas document-level:
    - zero_leak_rate: % de documentos onde TODAS as entidades foram detectadas
    - missed_by_type: contagem de FN por tipo de entidade
    - false_alarm_by_type: contagem de FP por tipo de entidade

    Para o TJMG, zero_leak_rate é a métrica mais importante.
    Um documento com uma única entidade perdida é um vazamento.
    """
    # Agrupar sequências por documento
    doc_sequences = defaultdict(lambda: {"true": [], "pred": []})

    for i, (true_seq, pred_seq) in enumerate(zip(all_true, all_pred)):
        doc_id = doc_ids[i] if i < len(doc_ids) else f"doc_{i}"
        doc_sequences[doc_id]["true"].extend(true_seq)
        doc_sequences[doc_id]["pred"].extend(pred_seq)

    total_docs = len(doc_sequences)
    zero_leak_docs = 0
    missed_by_type = Counter()
    false_alarm_by_type = Counter()
    docs_with_leaks = []

    for doc_id, seqs in doc_sequences.items():
        true_entities = set(
            (t, s, e) for t, s, e in extract_entities_from_bio(seqs["true"])
        )
        pred_entities = set(
            (t, s, e) for t, s, e in extract_entities_from_bio(seqs["pred"])
        )

        # FN: entidades reais não preditas
        missed = true_entities - pred_entities
        # FP: entidades preditas que não existem
        false_alarms = pred_entities - true_entities

        if len(missed) == 0:
            zero_leak_docs += 1
        else:
            docs_with_leaks.append({
                "doc_id": doc_id,
                "missed": len(missed),
                "missed_types": [m[0] for m in missed],
            })

        for m in missed:
            missed_by_type[m[0]] += 1
        for fa in false_alarms:
            false_alarm_by_type[fa[0]] += 1

    zero_leak_rate = zero_leak_docs / total_docs if total_docs > 0 else 0.0

    result = {
        "total_documents": total_docs,
        "zero_leak_documents": zero_leak_docs,
        "zero_leak_rate": zero_leak_rate,
        "documents_with_leaks": total_docs - zero_leak_docs,
        "missed_entities_by_type": dict(missed_by_type),
        "false_alarm_entities_by_type": dict(false_alarm_by_type),
        "total_missed": sum(missed_by_type.values()),
        "total_false_alarms": sum(false_alarm_by_type.values()),
    }

    logger.info(f"\n=== Document-Level Metrics ===")
    logger.info(f"  Zero-leak rate: {zero_leak_rate:.1%} ({zero_leak_docs}/{total_docs})")
    logger.info(f"  Total missed entities: {result['total_missed']}")
    logger.info(f"  Total false alarms: {result['total_false_alarms']}")
    logger.info(f"  Missed by type: {dict(missed_by_type)}")

    if docs_with_leaks:
        logger.info(f"\n  Documentos com vazamento ({len(docs_with_leaks)}):")
        for doc in docs_with_leaks[:10]:
            logger.info(f"    {doc['doc_id']}: {doc['missed']} missed ({doc['missed_types']})")
        if len(docs_with_leaks) > 10:
            logger.info(f"    ... e mais {len(docs_with_leaks) - 10}")

    return result


# ─── Confusion matrix ───────────────────────────────────────────────────────


def confusion_matrix_report(
    all_true: list[list[str]],
    all_pred: list[list[str]],
    labels_list: list[str],
) -> dict:
    """
    Confusion matrix token-level por label.

    Útil para diagnosticar confusões sistemáticas
    (ex: LOCAL confundido com ORGANIZACAO).
    """
    # Simplificar: usar apenas o tipo (sem B-/I-)
    type_map = {}
    for label in labels_list:
        if label == "O":
            type_map[label] = "O"
        else:
            type_map[label] = label.split("-", 1)[1]

    types = sorted(set(type_map.values()))
    confusion = {t: {t2: 0 for t2 in types} for t in types}

    for true_seq, pred_seq in zip(all_true, all_pred):
        for t, p in zip(true_seq, pred_seq):
            true_type = type_map.get(t, "O")
            pred_type = type_map.get(p, "O")
            confusion[true_type][pred_type] += 1

    logger.info(f"\n=== Confusion Matrix (token-level, by entity type) ===")
    header = "True\\Pred".ljust(15) + "".join(t.ljust(15) for t in types)
    logger.info(header)
    for true_type in types:
        row = true_type.ljust(15) + "".join(
            str(confusion[true_type][pred_type]).ljust(15) for pred_type in types
        )
        logger.info(row)

    return confusion


# ─── Comparação com baseline ────────────────────────────────────────────────


def compare_with_baseline(
    finetuned_metrics: dict,
    baseline_model_name: str,
    dataset,
    config: TrainingConfig,
) -> dict:
    """
    Compara modelo fine-tuned com baseline original (LeNER-Br).

    Carrega o baseline, roda predição no mesmo test set, e reporta delta.
    """
    logger.info(f"\n=== Comparação com Baseline ({baseline_model_name}) ===")

    # Carregar baseline
    logger.info(f"Carregando baseline: {baseline_model_name}...")
    baseline_model = AutoModelForTokenClassification.from_pretrained(baseline_model_name)
    baseline_tokenizer = AutoTokenizer.from_pretrained(baseline_model_name)

    # O baseline pode ter labels diferentes — precisamos mapear
    baseline_id2label = {int(k): v for k, v in baseline_model.config.id2label.items()}
    target_id2label = config.labels.id2label

    # Verificar se labels são compatíveis
    baseline_labels = set(baseline_id2label.values())
    target_labels = set(target_id2label.values())

    # Mapear labels do baseline para o nosso esquema
    label_remap = {}
    for bl in baseline_labels:
        if bl in target_labels:
            label_remap[bl] = bl
        elif bl == "O":
            label_remap[bl] = "O"
        else:
            # Tentar mapear prefixo
            prefix = bl[:2]  # B- ou I-
            suffix = bl[2:] if len(bl) > 2 else bl
            # Mapeamentos conhecidos do LeNER-Br
            SUFFIX_MAP = {
                "PER": "PESSOA",
                "PESSOA": "PESSOA",
                "LOC": "LOCAL",
                "LOCAL": "LOCAL",
                "ORG": "ORGANIZACAO",
                "ORGANIZACAO": "ORGANIZACAO",
            }
            mapped_suffix = SUFFIX_MAP.get(suffix)
            if mapped_suffix and f"{prefix}{mapped_suffix}" in target_labels:
                label_remap[bl] = f"{prefix}{mapped_suffix}"
            else:
                label_remap[bl] = "O"  # Labels não mapeáveis viram O

    logger.info(f"  Mapeamento de labels: {label_remap}")

    # Predição com baseline — precisa re-tokenizar pois o baseline pode
    # ter vocabulário diferente. Por simplicidade, usar o pipeline HF.
    # Mas para comparação justa, vamos predizer token por token no mesmo dataset.

    # Nota: o baseline pode não ter as mesmas labels, então predizemos
    # com o baseline e mapeamos as labels.
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    baseline_model.to(device)
    baseline_model.eval()

    all_true = []
    all_pred = []

    batch_size = config.per_device_eval_batch_size

    for i in range(0, len(dataset), batch_size):
        batch = dataset[i : i + batch_size]
        input_ids = torch.tensor(batch["input_ids"], dtype=torch.long).to(device)
        attention_mask = torch.tensor(batch["attention_mask"], dtype=torch.long).to(device)
        labels = batch["labels"]

        with torch.no_grad():
            try:
                outputs = baseline_model(input_ids=input_ids, attention_mask=attention_mask)
                preds = torch.argmax(outputs.logits, dim=-1).cpu().numpy()
            except Exception:
                # Se dimensões não batem, pular batch
                continue

        for seq_idx in range(len(labels)):
            true_seq = []
            pred_seq = []

            for token_idx, label_id in enumerate(labels[seq_idx]):
                if label_id == -100:
                    continue
                true_label = target_id2label[label_id]
                pred_id = int(preds[seq_idx][token_idx])

                # Mapear label predita do baseline para nosso esquema
                if pred_id in baseline_id2label:
                    pred_label = label_remap.get(baseline_id2label[pred_id], "O")
                else:
                    pred_label = "O"

                true_seq.append(true_label)
                pred_seq.append(pred_label)

            all_true.append(true_seq)
            all_pred.append(pred_seq)

    baseline_metrics = entity_level_report(all_true, all_pred)

    # Comparação
    comparison = {
        "baseline": {
            "model": baseline_model_name,
            "precision": baseline_metrics["overall"]["precision"],
            "recall": baseline_metrics["overall"]["recall"],
            "f1": baseline_metrics["overall"]["f1"],
        },
        "finetuned": {
            "precision": finetuned_metrics["overall"]["precision"],
            "recall": finetuned_metrics["overall"]["recall"],
            "f1": finetuned_metrics["overall"]["f1"],
        },
        "delta": {
            "precision": (
                finetuned_metrics["overall"]["precision"]
                - baseline_metrics["overall"]["precision"]
            ),
            "recall": (
                finetuned_metrics["overall"]["recall"]
                - baseline_metrics["overall"]["recall"]
            ),
            "f1": (
                finetuned_metrics["overall"]["f1"]
                - baseline_metrics["overall"]["f1"]
            ),
        },
    }

    logger.info(f"\n{'Métrica':<12} {'Baseline':>10} {'Fine-tuned':>12} {'Delta':>10}")
    logger.info("-" * 46)
    for metric in ("precision", "recall", "f1"):
        b = comparison["baseline"][metric]
        f = comparison["finetuned"][metric]
        d = comparison["delta"][metric]
        sign = "+" if d >= 0 else ""
        logger.info(f"{metric:<12} {b:>10.4f} {f:>12.4f} {sign}{d:>9.4f}")

    return comparison


# ─── Main ────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Avaliação do modelo fine-tuned")
    parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="Diretório do modelo fine-tuned (default: training/output/best_model)",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="Diretório do dataset HF (default: training/dataset)",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        help="Split para avaliar (default: test)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Comparar com baseline (pierreguillou/bert-base-cased-pt-lenerbr)",
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Arquivo de saída JSON para resultados",
    )
    args = parser.parse_args()

    # Config
    if args.config and args.config.exists():
        config = TrainingConfig.load(args.config)
    else:
        config = TrainingConfig()

    model_dir = args.model or (config.output_dir / "best_model")
    dataset_dir = args.dataset or config.dataset_dir
    output_path = args.output or (config.output_dir / "evaluation_results.json")

    # Carregar dataset
    logger.info(f"Carregando dataset de {dataset_dir}...")
    dataset = load_from_disk(str(dataset_dir))

    if args.split not in dataset:
        available = list(dataset.keys())
        raise ValueError(f"Split '{args.split}' não encontrado. Disponíveis: {available}")

    eval_dataset = dataset[args.split]
    logger.info(f"Avaliando no split '{args.split}' ({len(eval_dataset)} exemplos)")

    # Carregar modelo fine-tuned
    logger.info(f"Carregando modelo de {model_dir}...")
    model = AutoModelForTokenClassification.from_pretrained(str(model_dir))
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    id2label = config.labels.id2label

    # ── Predição ─────────────────────────────────────────────────
    logger.info("Rodando predição...")
    all_true, all_pred, doc_ids = predict_dataset(
        model, tokenizer, eval_dataset, id2label
    )

    # ── 1. Entity-level metrics ──────────────────────────────────
    entity_metrics = entity_level_report(all_true, all_pred)

    # ── 2. Document-level metrics ────────────────────────────────
    doc_metrics = document_level_metrics(all_true, all_pred, doc_ids)

    # ── 3. Confusion matrix ──────────────────────────────────────
    confusion = confusion_matrix_report(all_true, all_pred, config.labels.LABELS)

    # ── 4. Comparação com baseline ───────────────────────────────
    comparison = None
    if args.compare:
        comparison = compare_with_baseline(
            finetuned_metrics=entity_metrics,
            baseline_model_name=config.base_model,
            dataset=eval_dataset,
            config=config,
        )

    # ── Salvar resultados ────────────────────────────────────────
    results = {
        "model": str(model_dir),
        "dataset": str(dataset_dir),
        "split": args.split,
        "num_examples": len(eval_dataset),
        "entity_level": {
            "overall": entity_metrics["overall"],
            "per_entity": entity_metrics["per_entity"],
        },
        "document_level": doc_metrics,
        "confusion_matrix": confusion,
    }
    if comparison:
        results["baseline_comparison"] = comparison

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(f"\nResultados salvos em {output_path}")

    # ── Resumo final ─────────────────────────────────────────────
    logger.info(f"\n{'='*50}")
    logger.info(f"RESUMO DA AVALIAÇÃO")
    logger.info(f"{'='*50}")
    logger.info(f"  Precision: {entity_metrics['overall']['precision']:.4f}")
    logger.info(f"  Recall:    {entity_metrics['overall']['recall']:.4f}")
    logger.info(f"  F1:        {entity_metrics['overall']['f1']:.4f}")
    logger.info(f"  Zero-leak: {doc_metrics['zero_leak_rate']:.1%}")
    logger.info(f"{'='*50}")


if __name__ == "__main__":
    main()
