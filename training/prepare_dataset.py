"""
Prepara dataset HuggingFace a partir de anotações JSON para fine-tuning.

Formato de entrada (JSON por documento):
{
  "doc_id": "proc_001",
  "text": "O autor João da Silva, residente em Belo Horizonte...",
  "entities": [
    {"start": 9, "end": 23, "label": "PESSOA", "text": "João da Silva"},
    {"start": 38, "end": 53, "label": "LOCAL", "text": "Belo Horizonte"}
  ],
  "metadata": {
    "source": "manual" | "pre_annotation" | "corrected",
    "annotator": "nome_anotador",
    "reviewed": true
  }
}

Uso:
    python -m training.prepare_dataset \\
        --annotations_dir training/annotations \\
        --output_dir training/dataset \\
        --model pierreguillou/bert-base-cased-pt-lenerbr
"""
import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np
from datasets import Dataset, DatasetDict, Features, Sequence, Value
from transformers import AutoTokenizer

# Adicionar raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).parent.parent))
from training.config import TrainingConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_annotations(annotations_dir: Path) -> list[dict]:
    """
    Carrega todos os arquivos JSON de anotação do diretório.

    Valida formato mínimo e reporta documentos inválidos.
    """
    docs = []
    json_files = sorted(annotations_dir.glob("*.json"))

    if not json_files:
        raise FileNotFoundError(
            f"Nenhum arquivo .json encontrado em {annotations_dir}. "
            f"Execute export_for_annotation.py primeiro."
        )

    for path in json_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)

            # Validação mínima
            assert "text" in doc, "Campo 'text' obrigatório"
            assert "entities" in doc, "Campo 'entities' obrigatório"
            assert isinstance(doc["entities"], list), "'entities' deve ser lista"

            if "doc_id" not in doc:
                doc["doc_id"] = path.stem

            # Validar entidades
            valid_labels = {"PESSOA", "ORGANIZACAO", "LOCAL"}
            filtered = []
            for ent in doc["entities"]:
                assert "start" in ent and "end" in ent and "label" in ent, (
                    f"Entidade incompleta: {ent}"
                )
                if ent["label"] not in valid_labels:
                    logger.warning(
                        f"Label '{ent['label']}' ignorada em {path.name} "
                        f"(válidas: {valid_labels})"
                    )
                    continue
                # Verificar que o texto bate com as posições
                expected = doc["text"][ent["start"]:ent["end"]]
                if "text" in ent and ent["text"] != expected:
                    logger.warning(
                        f"Texto da entidade não bate com posição em {path.name}: "
                        f"esperado='{expected}', encontrado='{ent['text']}'. "
                        f"Usando texto da posição."
                    )
                ent["text"] = expected
                filtered.append(ent)

            doc["entities"] = filtered
            docs.append(doc)

        except Exception as e:
            logger.error(f"Erro ao carregar {path.name}: {e}")

    logger.info(f"Carregados {len(docs)} documentos de {annotations_dir}")
    return docs


def text_to_words_and_labels(
    text: str,
    entities: list[dict],
) -> tuple[list[str], list[str]]:
    """
    Converte texto + span annotations em listas word-level com labels IOB2.

    Tokenização word-level usa whitespace + pontuação como delimitadores,
    consistente com o que o BERTimbau WordPiece espera.
    """
    # Tokenização simples por whitespace preservando posições
    words = []
    word_starts = []
    word_ends = []

    i = 0
    while i < len(text):
        # Pular whitespace
        if text[i].isspace():
            i += 1
            continue

        # Coletar word
        start = i
        while i < len(text) and not text[i].isspace():
            i += 1
        words.append(text[start:i])
        word_starts.append(start)
        word_ends.append(i)

    # Ordenar entidades por posição
    entities_sorted = sorted(entities, key=lambda e: e["start"])

    # Atribuir labels IOB2
    labels = ["O"] * len(words)

    for ent in entities_sorted:
        ent_start = ent["start"]
        ent_end = ent["end"]
        label = ent["label"]
        is_beginning = True

        for w_idx, (ws, we) in enumerate(zip(word_starts, word_ends)):
            # Word está dentro do span da entidade?
            # Critério: sobreposição significativa (>50% da word)
            overlap_start = max(ws, ent_start)
            overlap_end = min(we, ent_end)
            overlap = max(0, overlap_end - overlap_start)
            word_len = we - ws

            if overlap > word_len * 0.5:
                if is_beginning:
                    labels[w_idx] = f"B-{label}"
                    is_beginning = False
                else:
                    labels[w_idx] = f"I-{label}"

    return words, labels


def tokenize_and_align_labels(
    words: list[str],
    labels: list[str],
    tokenizer,
    label2id: dict[str, int],
    max_length: int = 512,
    doc_stride: int = 128,
) -> list[dict]:
    """
    Tokeniza com BPE e alinha labels word-level para subword-level.

    Para documentos longos (>max_length tokens), usa sliding window
    com sobreposição de doc_stride tokens.

    Retorna lista de exemplos (1 por window) com:
      - input_ids, attention_mask, labels (subword-aligned)
    """
    # Tokenizar preservando alinhamento word → subwords
    tokenized = tokenizer(
        words,
        is_split_into_words=True,
        return_offsets_mapping=False,
        add_special_tokens=False,
        # Não truncar aqui — vamos fazer sliding window manual
        truncation=False,
    )

    # Mapear cada subword token para seu word index
    word_ids = tokenized.word_ids()
    all_input_ids = tokenized["input_ids"]

    # Alinhar labels: primeiro subword de cada word recebe o label,
    # subwords subsequentes recebem IGNORE_INDEX (-100)
    aligned_labels = []
    previous_word_idx = None
    for word_idx in word_ids:
        if word_idx is None:
            aligned_labels.append(-100)
        elif word_idx != previous_word_idx:
            # Primeiro subword desta word
            label_str = labels[word_idx]
            aligned_labels.append(label2id.get(label_str, label2id["O"]))
        else:
            # Subword continuação — ignorar no loss
            aligned_labels.append(-100)
        previous_word_idx = word_idx

    # Sliding window para documentos longos
    # Reservar 2 tokens para [CLS] e [SEP]
    effective_length = max_length - 2
    examples = []

    if len(all_input_ids) <= effective_length:
        # Documento cabe em uma janela
        input_ids = [tokenizer.cls_token_id] + all_input_ids + [tokenizer.sep_token_id]
        label_ids = [-100] + aligned_labels + [-100]
        attention_mask = [1] * len(input_ids)

        # Padding
        pad_len = max_length - len(input_ids)
        input_ids += [tokenizer.pad_token_id] * pad_len
        label_ids += [-100] * pad_len
        attention_mask += [0] * pad_len

        examples.append({
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": label_ids,
        })
    else:
        # Sliding window
        start = 0
        while start < len(all_input_ids):
            end = min(start + effective_length, len(all_input_ids))

            chunk_ids = all_input_ids[start:end]
            chunk_labels = aligned_labels[start:end]

            input_ids = [tokenizer.cls_token_id] + chunk_ids + [tokenizer.sep_token_id]
            label_ids = [-100] + chunk_labels + [-100]
            attention_mask = [1] * len(input_ids)

            # Padding
            pad_len = max_length - len(input_ids)
            input_ids += [tokenizer.pad_token_id] * pad_len
            label_ids += [-100] * pad_len
            attention_mask += [0] * pad_len

            examples.append({
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "labels": label_ids,
            })

            if end == len(all_input_ids):
                break
            start += effective_length - doc_stride

    return examples


def split_documents(
    docs: list[dict],
    train_ratio: float = 0.70,
    dev_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Split document-level (não sentence-level) para evitar data leakage.

    Usa hash determinístico do doc_id para split reprodutível
    independente da ordem dos arquivos.
    """
    assert abs(train_ratio + dev_ratio + test_ratio - 1.0) < 1e-6

    # Hash determinístico para cada documento
    def doc_hash(doc: dict) -> float:
        h = hashlib.md5(doc["doc_id"].encode()).hexdigest()
        return int(h[:8], 16) / 0xFFFFFFFF

    train, dev, test = [], [], []
    for doc in docs:
        h = doc_hash(doc)
        if h < train_ratio:
            train.append(doc)
        elif h < train_ratio + dev_ratio:
            dev.append(doc)
        else:
            test.append(doc)

    logger.info(
        f"Split: train={len(train)}, dev={len(dev)}, test={len(test)} "
        f"(total={len(docs)})"
    )

    # Verificar se algum split ficou vazio
    if len(train) == 0:
        raise ValueError("Split de treino vazio. Adicione mais documentos.")
    if len(dev) == 0:
        logger.warning("Split de dev vazio. Considere adicionar mais documentos.")
    if len(test) == 0:
        logger.warning("Split de test vazio. Considere adicionar mais documentos.")

    return train, dev, test


def build_dataset(
    docs: list[dict],
    tokenizer,
    config: TrainingConfig,
) -> Dataset:
    """
    Converte lista de documentos anotados em HuggingFace Dataset.
    """
    label2id = config.labels.label2id

    all_input_ids = []
    all_attention_mask = []
    all_labels = []
    all_doc_ids = []

    for doc in docs:
        words, word_labels = text_to_words_and_labels(doc["text"], doc["entities"])

        examples = tokenize_and_align_labels(
            words=words,
            labels=word_labels,
            tokenizer=tokenizer,
            label2id=label2id,
            max_length=config.max_seq_length,
            doc_stride=config.doc_stride,
        )

        for ex in examples:
            all_input_ids.append(ex["input_ids"])
            all_attention_mask.append(ex["attention_mask"])
            all_labels.append(ex["labels"])
            all_doc_ids.append(doc["doc_id"])

    features = Features({
        "input_ids": Sequence(Value("int32")),
        "attention_mask": Sequence(Value("int8")),
        "labels": Sequence(Value("int32")),
        "doc_id": Value("string"),
    })

    dataset = Dataset.from_dict(
        {
            "input_ids": all_input_ids,
            "attention_mask": all_attention_mask,
            "labels": all_labels,
            "doc_id": all_doc_ids,
        },
        features=features,
    )

    return dataset


def compute_label_frequencies(dataset: Dataset, config: TrainingConfig) -> dict[str, int]:
    """
    Conta frequência de cada label no dataset para cálculo de pesos.
    """
    id2label = config.labels.id2label
    counts = {label: 0 for label in config.labels.LABELS}

    for example in dataset:
        for label_id in example["labels"]:
            if label_id >= 0:  # Ignorar -100
                label = id2label[label_id]
                counts[label] += 1

    logger.info("Frequência de labels:")
    total = sum(counts.values())
    for label, count in sorted(counts.items(), key=lambda x: -x[1]):
        pct = count / total * 100 if total > 0 else 0
        logger.info(f"  {label}: {count:,} ({pct:.1f}%)")

    return counts


def main():
    parser = argparse.ArgumentParser(
        description="Prepara dataset HuggingFace a partir de anotações JSON"
    )
    parser.add_argument(
        "--annotations_dir",
        type=Path,
        default=None,
        help="Diretório com JSONs anotados",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=None,
        help="Diretório de saída para o dataset HF",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Nome do modelo no HuggingFace Hub (para tokenizer)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Caminho para training_config.json",
    )
    args = parser.parse_args()

    # Carregar ou criar config
    if args.config and args.config.exists():
        config = TrainingConfig.load(args.config)
    else:
        config = TrainingConfig()

    # Overrides da CLI
    if args.annotations_dir:
        config.annotations_dir = args.annotations_dir
    if args.output_dir:
        config.dataset_dir = args.output_dir
    if args.model:
        config.base_model = args.model

    logger.info(f"Modelo: {config.base_model}")
    logger.info(f"Anotações: {config.annotations_dir}")
    logger.info(f"Saída: {config.dataset_dir}")

    # 1. Carregar anotações
    docs = load_annotations(config.annotations_dir)

    # 2. Carregar tokenizer
    logger.info(f"Carregando tokenizer de {config.base_model}...")
    tokenizer = AutoTokenizer.from_pretrained(config.base_model)

    # 3. Split document-level
    train_docs, dev_docs, test_docs = split_documents(
        docs,
        train_ratio=config.train_ratio,
        dev_ratio=config.dev_ratio,
        test_ratio=config.test_ratio,
        seed=config.seed,
    )

    # 4. Construir datasets
    logger.info("Construindo dataset de treino...")
    train_dataset = build_dataset(train_docs, tokenizer, config)
    logger.info(f"  {len(train_dataset)} exemplos de treino")

    dev_dataset = None
    if dev_docs:
        logger.info("Construindo dataset de dev...")
        dev_dataset = build_dataset(dev_docs, tokenizer, config)
        logger.info(f"  {len(dev_dataset)} exemplos de dev")

    test_dataset = None
    if test_docs:
        logger.info("Construindo dataset de test...")
        test_dataset = build_dataset(test_docs, tokenizer, config)
        logger.info(f"  {len(test_dataset)} exemplos de test")

    # 5. Montar DatasetDict e salvar
    dd = {"train": train_dataset}
    if dev_dataset:
        dd["validation"] = dev_dataset
    if test_dataset:
        dd["test"] = test_dataset

    dataset_dict = DatasetDict(dd)

    config.dataset_dir.mkdir(parents=True, exist_ok=True)
    dataset_dict.save_to_disk(str(config.dataset_dir))
    logger.info(f"Dataset salvo em {config.dataset_dir}")

    # 6. Estatísticas de labels
    compute_label_frequencies(train_dataset, config)

    # 7. Salvar config para reprodutibilidade
    config.save()
    logger.info(f"Config salva em {config.output_dir / 'training_config.json'}")

    # 8. Salvar metadados do split
    split_meta = {
        "train_docs": [d["doc_id"] for d in train_docs],
        "dev_docs": [d["doc_id"] for d in dev_docs],
        "test_docs": [d["doc_id"] for d in test_docs],
        "train_examples": len(train_dataset),
        "dev_examples": len(dev_dataset) if dev_dataset else 0,
        "test_examples": len(test_dataset) if test_dataset else 0,
    }
    meta_path = config.dataset_dir / "split_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(split_meta, f, indent=2, ensure_ascii=False)
    logger.info(f"Metadados do split salvos em {meta_path}")


if __name__ == "__main__":
    main()
