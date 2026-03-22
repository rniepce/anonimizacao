"""
Exporta documentos para anotação humana com pré-anotações automáticas.

Fluxo de weak supervision:
1. Lê PDFs de data/uploads/ (ou diretório especificado)
2. Extrai texto com o pipeline existente
3. Roda NER (BERTimbau + regex) para gerar pré-anotações
4. Exporta como JSON no formato esperado por prepare_dataset.py
5. Anotador humano revisa: corrige, remove FP, adiciona FN

Isso reduz drasticamente o tempo de anotação (revisar >> anotar do zero).

Uso:
    python -m training.export_for_annotation
    python -m training.export_for_annotation --input_dir data/uploads --output_dir training/annotations
    python -m training.export_for_annotation --limit 50
"""
import argparse
import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# Mapeamento de tipos do pipeline para labels de treinamento
TIPO_TO_LABEL = {
    "PESSOA": "PESSOA",
    "ENDERECO": "LOCAL",
    "LOCAL": "LOCAL",
    "ORGANIZACAO": "ORGANIZACAO",
}

# Tipos que são tratados por regex (não precisam de NER)
REGEX_ONLY_TYPES = {"CPF", "CNPJ", "EMAIL", "TELEFONE", "OAB", "PROCESSO", "DATA", "VALOR"}


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extrai texto de um PDF usando PyMuPDF."""
    try:
        import fitz

        doc = fitz.open(str(pdf_path))
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n".join(pages)
    except Exception as e:
        logger.error(f"Erro ao extrair texto de {pdf_path.name}: {e}")
        return ""


def generate_pre_annotations(text: str) -> list[dict]:
    """
    Gera pré-anotações usando o pipeline NER existente.

    Usa o NERTransformerEngine diretamente para obter entidades
    com posições no texto.
    """
    entities = []

    try:
        from app.core.ner_transformer import NERTransformerEngine

        engine = NERTransformerEngine()
        if engine.is_available:
            ner_entities = engine.extract_entities(text)
            for ent in ner_entities:
                label = TIPO_TO_LABEL.get(ent.tipo)
                if label is None:
                    continue

                # Verificar que as posições batem com o texto
                expected = text[ent.inicio : ent.fim]
                if expected.strip() and ent.texto.strip():
                    entities.append({
                        "start": ent.inicio,
                        "end": ent.fim,
                        "label": label,
                        "text": expected,
                        "confidence": ent.score,
                        "source": "bertimbau",
                    })
        else:
            logger.warning(
                "BERTimbau não disponível. Instale: pip install transformers torch"
            )
    except ImportError:
        logger.warning("transformers não instalado — pré-anotações NER indisponíveis")

    # Fallback: regex para nomes em contexto jurídico (heurística simples)
    try:
        _add_regex_name_hints(text, entities)
    except Exception as e:
        logger.warning(f"Heurística regex falhou: {e}")

    # Deduplicar por posição
    seen = set()
    unique = []
    for ent in entities:
        key = (ent["start"], ent["end"])
        if key not in seen:
            seen.add(key)
            unique.append(ent)

    return sorted(unique, key=lambda e: e["start"])


def _add_regex_name_hints(text: str, entities: list[dict]):
    """
    Heurísticas regex para capturar nomes em contexto jurídico
    que o NER pode ter perdido.

    Padrões como "Autor: NOME", "Réu: NOME", "Requerente: NOME".
    """
    import re

    # Padrões de contexto jurídico
    patterns = [
        (r"(?:Autor|Autora|Requerente|Reclamante|Impetrante|Apelante|Agravante)"
         r"\s*[:]\s*([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,5})"),
        (r"(?:Réu|Ré|Requerido|Requerida|Reclamado|Reclamada|Impetrado|Apelado|Agravado)"
         r"\s*[:]\s*([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,5})"),
        (r"(?:Vítima|Ofendido|Ofendida|Paciente|Interessado|Interessada)"
         r"\s*[:]\s*([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,5})"),
    ]

    existing_spans = {(e["start"], e["end"]) for e in entities}

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            start = match.start(1)
            end = match.end(1)
            # Não adicionar se já existe entidade nesta posição
            overlap = any(
                start < e_end and end > e_start for e_start, e_end in existing_spans
            )
            if not overlap:
                entities.append({
                    "start": start,
                    "end": end,
                    "label": "PESSOA",
                    "text": match.group(1),
                    "confidence": 0.70,
                    "source": "regex_hint",
                })


def export_document(
    pdf_path: Path,
    output_dir: Path,
    doc_id: Optional[str] = None,
) -> Optional[Path]:
    """
    Exporta um PDF como JSON para anotação.

    Returns:
        Path do arquivo JSON criado, ou None se falhou.
    """
    doc_id = doc_id or pdf_path.stem

    # Extrair texto
    text = extract_text_from_pdf(pdf_path)
    if not text.strip():
        logger.warning(f"Texto vazio em {pdf_path.name} — documento escaneado?")
        return None

    # Gerar pré-anotações
    entities = generate_pre_annotations(text)

    # Montar JSON
    annotation = {
        "doc_id": doc_id,
        "text": text,
        "entities": entities,
        "metadata": {
            "source_file": pdf_path.name,
            "source": "pre_annotation",
            "annotator": None,
            "reviewed": False,
            "notes": (
                "PRE-ANOTACAO AUTOMATICA. Revise todas as entidades:\n"
                "- Corrija entidades com posições erradas\n"
                "- Remova falsos positivos (entidades que nao sao PII)\n"
                "- Adicione entidades que o modelo perdeu (falsos negativos)\n"
                "- Marque 'reviewed': true quando finalizar"
            ),
        },
    }

    # Salvar
    output_path = output_dir / f"{doc_id}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(annotation, f, indent=2, ensure_ascii=False)

    logger.info(
        f"  {pdf_path.name} → {output_path.name} "
        f"({len(entities)} pré-anotações, {len(text)} chars)"
    )
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Exporta documentos para anotação com pré-anotações"
    )
    parser.add_argument(
        "--input_dir",
        type=Path,
        default=Path("data/uploads"),
        help="Diretório com PDFs de entrada",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=Path("training/annotations"),
        help="Diretório de saída para JSONs",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Número máximo de documentos a processar",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="*.pdf",
        help="Padrão glob para filtrar PDFs (default: *.pdf)",
    )
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_dir.exists():
        logger.error(f"Diretório de entrada não existe: {input_dir}")
        sys.exit(1)

    pdf_files = sorted(input_dir.glob(args.pattern))
    if not pdf_files:
        logger.error(f"Nenhum PDF encontrado em {input_dir}")
        sys.exit(1)

    if args.limit:
        pdf_files = pdf_files[: args.limit]

    logger.info(f"Processando {len(pdf_files)} documentos de {input_dir}")
    logger.info(f"Saída: {output_dir}")

    exported = 0
    for pdf_path in pdf_files:
        result = export_document(pdf_path, output_dir)
        if result:
            exported += 1

    logger.info(f"\nExportados: {exported}/{len(pdf_files)} documentos")
    logger.info(f"Diretório de anotações: {output_dir}")
    logger.info(
        "\nPróximo passo: revise os JSONs em um editor de texto ou ferramenta de anotação.\n"
        "Quando finalizar, marque 'reviewed': true no metadata de cada arquivo.\n"
        "Depois execute: python -m training.prepare_dataset"
    )


if __name__ == "__main__":
    main()
