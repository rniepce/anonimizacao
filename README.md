# TJMG Anonymizer Pipeline

Pipeline de anonimização de documentos judiciais para o Tribunal de Justiça de Minas Gerais, em conformidade com a Resolução 615 do CNJ.

## 🚀 Quick Start

```bash
# 1. Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Instalar modelo SpaCy
python -m spacy download pt_core_news_lg

# 4. Instalar Tesseract OCR (macOS)
brew install tesseract tesseract-lang poppler

# 5. Executar servidor
uvicorn app.main:app --reload --port 8000
```

## 📁 Estrutura do Projeto

```
anonimizacao/
├── app/                    # Backend FastAPI
│   ├── api/               # Endpoints REST
│   ├── core/              # Motores de processamento
│   └── audit/             # Sistema de auditoria
├── data/                  # Dados (allowlist, uploads)
├── logs/                  # Logs de auditoria
├── frontend/              # Interface web
└── tests/                 # Testes automatizados
```

## 🔧 Funcionalidades

- **Upload**: PDF/DOCX via API REST
- **OCR**: Tesseract com pré-processamento OpenCV
- **Identificação**: Regex + NLP (SpaCy)
- **Anonimização**: Tarjas sobre dados sensíveis
- **Auditoria**: Logs imutáveis com hashes SHA-256

## 📡 API Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/anonymize` | Anonimiza documento |
| POST | `/api/analyze` | Preview de dados sensíveis |
| GET | `/api/audit/{job_id}` | Consulta auditoria |

## 📄 Licença

Desenvolvido para uso interno do TJMG.
