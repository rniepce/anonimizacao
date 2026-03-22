"""
Benchmark do pipeline completo de anonimização TJMG.

Avalia o sistema END-TO-END — não apenas o modelo NER isolado,
mas o pipeline completo: regex + NER (primário + suplementar) + detecção visual.

Diferença em relação a training/evaluate.py:
  training/evaluate.py  → avalia o modelo NER em tokens isolados
  benchmark/run_benchmark.py → avalia o que chegou até o anotador:
    "o sistema encontrou os dados sensíveis que um humano marcaria?"

Formato de entrada: mesmo JSON de training/annotations/
  {
    "doc_id": "proc_001",
    "text": "...",
    "entities": [{"start": 9, "end": 23, "label": "PESSOA", "text": "João da Silva"}],
    "metadata": {"reviewed": true}
  }

Métricas reportadas:
  1. Por tipo de entidade: precision, recall, F1
  2. Zero-leak rate: % de documentos onde NENHUMA entidade foi perdida
     → Métrica principal para anonimização judicial
  3. False positive rate: % de redações desnecessárias
  4. Comparação por fonte: regex vs NER vs NER suplementar

Uso:
    python -m benchmark.run_benchmark
    python -m benchmark.run_benchmark --annotations_dir training/annotations
    python -m benchmark.run_benchmark --only_reviewed
    python -m benchmark.run_benchmark --verbose
"""
import argparse
import json
import logging
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ─── Estruturas de dados ─────────────────────────────────────────────────────


@dataclass
class AnnotatedEntity:
    """Entidade anotada por humano (ground truth)."""
    start: int
    end: int
    label: str   # PESSOA | ORGANIZACAO | LOCAL
    text: str


@dataclass
class DetectedEntity:
    """Entidade detectada pelo pipeline."""
    start: int
    end: int
    tipo: str
    valor: str
    confianca: float
    fonte: str   # regex | ner | ner_gliner | header_analysis


@dataclass
class DocumentResult:
    """Resultado da avaliação de um documento."""
    doc_id: str
    true_positives: list[tuple[AnnotatedEntity, DetectedEntity]] = field(default_factory=list)
    false_negatives: list[AnnotatedEntity] = field(default_factory=list)   # perdidos
    false_positives: list[DetectedEntity] = field(default_factory=list)    # extras
    processing_ms: int = 0

    @property
    def zero_leak(self) -> bool:
        """True se nenhuma entidade anotada foi perdida."""
        return len(self.false_negatives) == 0

    @property
    def precision(self) -> float:
        tp = len(self.true_positives)
        fp = len(self.false_positives)
        return tp / (tp + fp) if (tp + fp) > 0 else 1.0

    @property
    def recall(self) -> float:
        tp = len(self.true_positives)
        fn = len(self.false_negatives)
        return tp / (tp + fn) if (tp + fn) > 0 else 1.0


# ─── Carregamento de anotações ────────────────────────────────────────────────


def load_annotated_docs(
    annotations_dir: Path,
    only_reviewed: bool = False,
) -> list[dict]:
    """Carrega JSONs de anotação do diretório."""
    json_files = sorted(annotations_dir.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(
            f"Nenhum JSON encontrado em {annotations_dir}. "
            "Execute: python -m training.export_for_annotation"
        )

    docs = []
    skipped = 0
    for path in json_files:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)

        if only_reviewed and not doc.get("metadata", {}).get("reviewed", False):
            skipped += 1
            continue

        if "doc_id" not in doc:
            doc["doc_id"] = path.stem

        docs.append(doc)

    logger.info(
        f"Carregados {len(docs)} documentos"
        + (f" ({skipped} não revisados ignorados)" if skipped else "")
    )
    return docs


def parse_ground_truth(doc: dict) -> list[AnnotatedEntity]:
    """Converte entidades do JSON para AnnotatedEntity."""
    valid_labels = {"PESSOA", "ORGANIZACAO", "LOCAL"}
    entities = []
    for ent in doc.get("entities", []):
        if ent.get("label") not in valid_labels:
            continue
        text = doc["text"][ent["start"]:ent["end"]]
        entities.append(AnnotatedEntity(
            start=ent["start"],
            end=ent["end"],
            label=ent["label"],
            text=text,
        ))
    return entities


# ─── Execução do pipeline ─────────────────────────────────────────────────────


LABEL_TO_TIPO = {
    "PESSOA": "PESSOA",
    "ORGANIZACAO": "ORGANIZACAO",
    "LOCAL": "ENDERECO",
}

TIPO_TO_LABEL = {v: k for k, v in LABEL_TO_TIPO.items()}
TIPO_TO_LABEL["LOCAL"] = "LOCAL"


def run_pipeline_on_text(text: str) -> list[DetectedEntity]:
    """
    Executa o pipeline de detecção de texto (regex + NER) sobre um texto puro.

    Não executa a parte visual (rostos/assinaturas) pois o benchmark
    de texto usa anotações de entidades textuais.

    Returns:
        Lista de DetectedEntity com posições no texto
    """
    from app.core.regex_matcher import regex_matcher
    from app.core.pipeline import pipeline as p
    from app.core.context_validator import context_validator

    detected: list[DetectedEntity] = []

    # --- Regex ---
    TIPO_MAP = {"PESSOA_CONTEXTO": "PESSOA"}
    for match in regex_matcher.find_all(text):
        tipo = TIPO_MAP.get(match.tipo, match.tipo)
        # Localizar posição no texto
        pos = text.find(match.valor)
        if pos == -1:
            continue
        detected.append(DetectedEntity(
            start=pos,
            end=pos + len(match.valor),
            tipo=tipo,
            valor=match.valor,
            confianca=1.0,
            fonte="regex",
        ))

    # --- NER primário ---
    primary_entities = p._ner_engine.extract_entities(text)
    for ent in primary_entities:
        if ent.tipo not in ("PESSOA", "ENDERECO", "ORGANIZACAO", "LOCAL"):
            continue
        if ent.tipo in ("PESSOA", "ORGANIZACAO", "ORG", "PER"):
            decision = context_validator.validate(
                text=text,
                entity_text=ent.texto,
                start_char=ent.inicio,
                end_char=ent.fim,
                entity_label=ent.tipo,
            )
            if not decision.should_anonymize:
                continue
        detected.append(DetectedEntity(
            start=ent.inicio,
            end=ent.fim,
            tipo=ent.tipo,
            valor=ent.texto,
            confianca=getattr(ent, "score", getattr(ent, "confianca", 0.85)),
            fonte="ner",
        ))

    # --- NER suplementar (GLiNER) ---
    if p._ner_supplementary is not None:
        primary_spans = [(e.inicio, e.fim) for e in primary_entities]
        supp_entities = p._ner_supplementary.extract_entities(text)
        for ent in supp_entities:
            if ent.tipo not in ("PESSOA", "ENDERECO", "ORGANIZACAO"):
                continue
            overlaps = any(
                ent.inicio < p_fim and ent.fim > p_ini
                for (p_ini, p_fim) in primary_spans
            )
            if overlaps:
                continue
            if ent.tipo in ("PESSOA", "ORGANIZACAO"):
                decision = context_validator.validate(
                    text=text,
                    entity_text=ent.texto,
                    start_char=ent.inicio,
                    end_char=ent.fim,
                    entity_label=ent.tipo,
                )
                if not decision.should_anonymize:
                    continue
            detected.append(DetectedEntity(
                start=ent.inicio,
                end=ent.fim,
                tipo=ent.tipo,
                valor=ent.texto,
                confianca=ent.confianca,
                fonte="ner_gliner",
            ))

    return detected


# ─── Matching ground truth ↔ detecções ───────────────────────────────────────


def _spans_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and a_end > b_start


def _overlap_ratio(gt: AnnotatedEntity, det: DetectedEntity) -> float:
    """Proporção de sobreposição entre ground truth e detecção."""
    overlap = max(0, min(gt.end, det.end) - max(gt.start, det.start))
    union = max(gt.end, det.end) - min(gt.start, det.start)
    return overlap / union if union > 0 else 0.0


def match_entities(
    ground_truth: list[AnnotatedEntity],
    detected: list[DetectedEntity],
    overlap_threshold: float = 0.5,
) -> DocumentResult:
    """
    Faz o matching entre entidades anotadas e detectadas.

    Uma detecção é TP se:
    - Há sobreposição >= overlap_threshold com uma anotação
    - Os tipos são compatíveis (PESSOA↔PESSOA, LOCAL↔ENDERECO, etc.)

    Args:
        overlap_threshold: Mínimo de sobreposição para considerar match (0.5 = IoU >= 0.5)
    """
    matched_gt = set()
    matched_det = set()
    true_positives = []

    # Normalizar tipos para comparação
    def normalize_tipo(tipo: str) -> str:
        mapping = {"ENDERECO": "LOCAL", "LOCAL": "LOCAL",
                   "ORG": "ORGANIZACAO", "PER": "PESSOA"}
        return mapping.get(tipo, tipo)

    for i, gt in enumerate(ground_truth):
        for j, det in enumerate(detected):
            if j in matched_det:
                continue
            if not _spans_overlap(gt.start, gt.end, det.start, det.end):
                continue
            if normalize_tipo(gt.label) != normalize_tipo(det.tipo):
                continue
            if _overlap_ratio(gt, det) < overlap_threshold:
                continue
            # Match encontrado
            true_positives.append((gt, det))
            matched_gt.add(i)
            matched_det.add(j)
            break

    false_negatives = [gt for i, gt in enumerate(ground_truth) if i not in matched_gt]
    false_positives = [det for j, det in enumerate(detected) if j not in matched_det]

    return DocumentResult(
        doc_id="",
        true_positives=true_positives,
        false_negatives=false_negatives,
        false_positives=false_positives,
    )


# ─── Relatório ────────────────────────────────────────────────────────────────


def print_report(
    results: list[DocumentResult],
    verbose: bool = False,
) -> dict:
    """
    Imprime relatório completo e retorna métricas como dict.
    """
    total_tp = sum(len(r.true_positives) for r in results)
    total_fn = sum(len(r.false_negatives) for r in results)
    total_fp = sum(len(r.false_positives) for r in results)

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    zero_leak_docs = [r for r in results if r.zero_leak]
    zero_leak_rate = len(zero_leak_docs) / len(results) if results else 0.0

    avg_ms = sum(r.processing_ms for r in results) / len(results) if results else 0

    # Métricas por tipo de entidade
    by_type: dict[str, dict] = defaultdict(lambda: {"tp": 0, "fn": 0, "fp": 0})
    for r in results:
        for gt, _ in r.true_positives:
            by_type[gt.label]["tp"] += 1
        for gt in r.false_negatives:
            by_type[gt.label]["fn"] += 1
        for det in r.false_positives:
            label = TIPO_TO_LABEL.get(det.tipo, det.tipo)
            by_type[label]["fp"] += 1

    # Métricas por fonte de detecção
    by_source: dict[str, int] = defaultdict(int)
    for r in results:
        for _, det in r.true_positives:
            by_source[det.fonte] += 1

    print("\n" + "=" * 60)
    print("  BENCHMARK — PIPELINE COMPLETO TJMG")
    print("=" * 60)
    print(f"\n  Documentos avaliados : {len(results)}")
    print(f"  Total de anotações   : {total_tp + total_fn}")
    print(f"  Tempo médio/doc      : {avg_ms:.0f}ms")

    print("\n── Métricas gerais ──────────────────────────────────────")
    print(f"  Precision      : {precision:.4f}  ({total_tp} TP / {total_tp + total_fp} detectados)")
    print(f"  Recall         : {recall:.4f}  ({total_tp} TP / {total_tp + total_fn} anotados)")
    print(f"  F1             : {f1:.4f}")
    print(f"\n  ★ Zero-leak rate : {zero_leak_rate:.1%}  ({len(zero_leak_docs)}/{len(results)} docs sem PII perdido)")

    print("\n── Por tipo de entidade ─────────────────────────────────")
    for label, counts in sorted(by_type.items()):
        tp, fn, fp = counts["tp"], counts["fn"], counts["fp"]
        p_ = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        r_ = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f_ = 2 * p_ * r_ / (p_ + r_) if (p_ + r_) > 0 else 0.0
        print(f"  {label:<15}  P={p_:.3f}  R={r_:.3f}  F1={f_:.3f}  "
              f"(TP={tp} FN={fn} FP={fp})")

    print("\n── Por fonte de detecção (TPs) ──────────────────────────")
    total_tp_all = sum(by_source.values())
    for source, count in sorted(by_source.items(), key=lambda x: -x[1]):
        pct = count / total_tp_all * 100 if total_tp_all > 0 else 0
        print(f"  {source:<20}  {count:4d}  ({pct:.1f}%)")

    if verbose:
        print("\n── Documentos com PII perdido ───────────────────────────")
        leaking = [r for r in results if not r.zero_leak]
        if not leaking:
            print("  Nenhum — zero-leak rate = 100%!")
        for r in leaking:
            print(f"\n  [{r.doc_id}]  {len(r.false_negatives)} entidade(s) perdida(s):")
            for gt in r.false_negatives:
                print(f"    ✗ {gt.label}: '{gt.text}' (chars {gt.start}-{gt.end})")

    print("=" * 60 + "\n")

    return {
        "documentos": len(results),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "zero_leak_rate": round(zero_leak_rate, 4),
        "tp": total_tp,
        "fn": total_fn,
        "fp": total_fp,
        "avg_processing_ms": round(avg_ms),
        "by_type": {
            label: {
                "precision": round(c["tp"] / (c["tp"] + c["fp"]) if (c["tp"] + c["fp"]) > 0 else 1.0, 4),
                "recall": round(c["tp"] / (c["tp"] + c["fn"]) if (c["tp"] + c["fn"]) > 0 else 1.0, 4),
                "tp": c["tp"], "fn": c["fn"], "fp": c["fp"],
            }
            for label, c in by_type.items()
        },
        "by_source": dict(by_source),
    }


# ─── Main ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark end-to-end do pipeline de anonimização TJMG"
    )
    parser.add_argument(
        "--annotations_dir",
        type=Path,
        default=Path("training/annotations"),
        help="Diretório com JSONs anotados (default: training/annotations)",
    )
    parser.add_argument(
        "--only_reviewed",
        action="store_true",
        help="Usar apenas documentos com metadata.reviewed=true",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Salvar métricas em JSON (ex: benchmark/results.json)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Listar documentos com PII perdido",
    )
    parser.add_argument(
        "--overlap_threshold",
        type=float,
        default=0.5,
        help="IoU mínimo para considerar detecção correta (default: 0.5)",
    )
    args = parser.parse_args()

    # Carregar documentos anotados
    docs = load_annotated_docs(args.annotations_dir, only_reviewed=args.only_reviewed)
    if not docs:
        logger.error("Nenhum documento encontrado para avaliação.")
        sys.exit(1)

    logger.info("Inicializando pipeline...")
    from app.core.pipeline import pipeline  # noqa — inicializa engines

    results: list[DocumentResult] = []

    for doc in docs:
        ground_truth = parse_ground_truth(doc)

        if not ground_truth:
            logger.debug(f"[{doc['doc_id']}] Sem anotações — pulando")
            continue

        logger.info(f"[{doc['doc_id']}]  {len(ground_truth)} anotações")

        t0 = time.time()
        try:
            detected = run_pipeline_on_text(doc["text"])
        except Exception as exc:
            logger.error(f"[{doc['doc_id']}] Pipeline falhou: {exc}")
            detected = []
        elapsed_ms = int((time.time() - t0) * 1000)

        doc_result = match_entities(
            ground_truth, detected, overlap_threshold=args.overlap_threshold
        )
        doc_result.doc_id = doc["doc_id"]
        doc_result.processing_ms = elapsed_ms
        results.append(doc_result)

    if not results:
        logger.error("Nenhum documento com anotações processado.")
        sys.exit(1)

    metrics = print_report(results, verbose=args.verbose)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        logger.info(f"Métricas salvas em {args.output}")


if __name__ == "__main__":
    main()
