# Como Treinar o Modelo de Anonimização TJMG

Guia passo a passo para fine-tuning do BERTimbau em dados do TJMG.

## Pré-requisitos

- Python 3.9+
- GPU com CUDA (recomendado, mas funciona em CPU)
- ~4GB de RAM para GPU, ~16GB de RAM para CPU
- Documentos PDF do TJMG para anotação

## 1. Instalar dependências

```bash
pip install -r training/requirements.txt
```

## 2. Preparar documentos para anotação

Coloque os PDFs do TJMG em `data/uploads/` e execute:

```bash
python -m training.export_for_annotation \
    --input_dir data/uploads \
    --output_dir training/annotations \
    --limit 100
```

Isso gera arquivos JSON em `training/annotations/` com **pré-anotações automáticas** do modelo atual. O formato de cada arquivo é:

```json
{
  "doc_id": "nome_do_documento",
  "text": "texto completo do documento...",
  "entities": [
    {
      "start": 9,
      "end": 23,
      "label": "PESSOA",
      "text": "João da Silva",
      "confidence": 0.95,
      "source": "bertimbau"
    }
  ],
  "metadata": {
    "reviewed": false
  }
}
```

## 3. Revisar anotações

Abra cada JSON e revise as entidades:

- **Corrigir** entidades com posições erradas
- **Remover** falsos positivos (nomes de leis, tribunais que foram marcados como PESSOA, etc.)
- **Adicionar** entidades que o modelo perdeu (nomes de partes, enderecos, etc.)
- Marcar `"reviewed": true` quando finalizar

**Labels disponíveis:**
| Label | Descrição | Exemplos |
|-------|-----------|----------|
| `PESSOA` | Nomes de pessoas | partes, testemunhas, peritos, advogados |
| `ORGANIZACAO` | Organizações | empresas, órgãos públicos |
| `LOCAL` | Endereços e locais | ruas, bairros, cidades, CEPs |

**Não anotar:** CPF, CNPJ, e-mail, telefone (tratados por regex).

**Quantidade recomendada:** mínimo 100 documentos, ideal 300+.

## 4. Preparar dataset

```bash
python -m training.prepare_dataset \
    --annotations_dir training/annotations \
    --output_dir training/dataset
```

O script:
- Converte anotações para formato HuggingFace
- Alinha labels com tokenização BPE (subwords)
- Aplica sliding window para documentos longos
- Divide em treino/dev/teste (70/15/15) por documento
- Salva em `training/dataset/`

## 5. Treinar

```bash
python -m training.train
```

Opções:
```bash
# Mais épocas
python -m training.train --epochs 20

# Learning rate diferente
python -m training.train --lr 3e-5

# Sem FP16 (se der erro de precisão)
python -m training.train --no_fp16

# Batch size menor (se falta GPU RAM)
python -m training.train --batch_size 4
```

O treinamento:
- Parte do modelo `pierreguillou/bert-base-cased-pt-lenerbr` (warm start)
- Usa loss ponderada que penaliza falsos negativos 3x mais
- Para automaticamente quando recall no dev set parar de melhorar
- Salva melhor checkpoint em `training/output/best_model/`

## 6. Avaliar

```bash
# Avaliação no test set
python -m training.evaluate

# Comparar com modelo original (baseline)
python -m training.evaluate --compare

# Avaliar em split específico
python -m training.evaluate --split validation
```

Métricas reportadas:
- **Precision/Recall/F1** por tipo de entidade
- **Zero-leak rate**: % de documentos sem nenhuma entidade perdida (métrica principal)
- **Confusion matrix**: quais tipos são confundidos entre si
- **Comparação com baseline**: delta vs modelo original

## 7. Usar o modelo treinado

Para usar o modelo fine-tuned no sistema de anonimização, atualize `app/config.py`:

```python
# Antes
NER_TRANSFORMER_MODEL: str = "pierreguillou/bert-base-cased-pt-lenerbr"

# Depois
NER_TRANSFORMER_MODEL: str = "training/output/best_model"
```

Ou via variável de ambiente:
```bash
export TJMG_NER_TRANSFORMER_MODEL=training/output/best_model
```

## Estrutura de arquivos

```
training/
├── annotations/        # JSONs para anotação humana
│   ├── proc_001.json
│   └── proc_002.json
├── dataset/            # Dataset HuggingFace processado
│   ├── train/
│   ├── validation/
│   └── test/
├── output/             # Resultados do treinamento
│   ├── best_model/     # Melhor checkpoint
│   ├── training_config.json
│   ├── train_metrics.json
│   └── evaluation_results.json
├── config.py
├── prepare_dataset.py
├── train.py
├── evaluate.py
├── export_for_annotation.py
└── requirements.txt
```

## Dicas

1. **Qualidade > quantidade**: 100 documentos bem anotados valem mais que 1000 mal anotados.
2. **Foque nos erros**: após a primeira rodada, anote documentos onde o modelo erra mais.
3. **Itere**: treine, avalie, anote mais documentos difíceis, treine de novo.
4. **Zero-leak rate** é a métrica que importa: o modelo pode anonimizar demais (falso positivo), mas nunca pode perder PII (falso negativo).
5. **GPU**: treinamento em CPU funciona mas demora ~10x mais. Use Google Colab se não tiver GPU local.
