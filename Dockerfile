FROM python:3.11-slim

# Evitar que o Python gere arquivos .pyc
ENV PYTHONDONTWRITEBYTECODE=1
# Saída do console sem buffer
ENV PYTHONUNBUFFERED=1

# Instalar dependências de sistema
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

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Baixar modelo SpaCy
RUN python -m spacy download pt_core_news_lg

# Copiar código da aplicação
COPY . .

# Criar diretórios necessários
RUN mkdir -p logs data/uploads data/allowlist

# Usuário não-root por segurança
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expor porta (apenas documentação, Railway injeta PORT)
EXPOSE 8000

# Comando de execução
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
