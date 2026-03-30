## ---- Stage 1: Build React frontend ----
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

## ---- Stage 2: Python backend ----
FROM python:3.11-slim

# Evitar que o Python gere arquivos .pyc
ENV PYTHONDONTWRITEBYTECODE=1
# Saída do console sem buffer
ENV PYTHONUNBUFFERED=1
# Otimizações de memória para containers (reduz fragmentação glibc + threads PyTorch)
ENV MALLOC_ARENA_MAX=2
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1

# Instalar dependências de sistema
# Tesseract mantido como OCR para PDFs escaneados (ativado condicionalmente pelo pipeline)
RUN apt-get update && apt-get install -y \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-por \
    poppler-utils \
    libmagic1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar CPU-only PyTorch + Transformers PRIMEIRO
# (antes do requirements.txt para que nenhum outro pacote puxe o torch com CUDA)
COPY requirements-transformers.txt .
RUN pip install --no-cache-dir -r requirements-transformers.txt

# Instalar dependências Python core (sem GLiNER, sem Surya)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Baixar modelo SpaCy para português (fallback do BERTimbau)
RUN pip install --no-cache-dir https://github.com/explosion/spacy-models/releases/download/pt_core_news_lg-3.7.0/pt_core_news_lg-3.7.0-py3-none-any.whl

# Copiar código da aplicação
COPY . .

# Pré-baixar BERTimbau (NER primário) durante o build
RUN python -c "from transformers import pipeline; pipeline('ner', model='pierreguillou/bert-base-cased-pt-lenerbr', aggregation_strategy='simple')" \
    || echo "Aviso: BERTimbau será baixado na primeira execução"

# Copiar build do frontend
COPY --from=frontend-build /frontend/dist ./frontend/dist

# Criar diretórios necessários
RUN mkdir -p logs data/uploads data/allowlist

# Usuário não-root por segurança
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expor porta (apenas documentação, Railway injeta PORT)
EXPOSE 8000

# Comando de execução
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
