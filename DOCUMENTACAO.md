# 📋 TJMG Anonymizer Pipeline

**Pipeline de Anonimização de Documentos Judiciais para o Tribunal de Justiça de Minas Gerais**

> ✅ Em conformidade com a **Resolução 615 do CNJ**

---

## 📖 Índice

1. [Visão Geral](#-visão-geral)
2. [Arquitetura](#-arquitetura)
3. [Funcionalidades](#-funcionalidades)
4. [Stack Tecnológico](#️-stack-tecnológico)
5. [Instalação](#-instalação)
6. [API Reference](#-api-reference)
7. [Interface Web](#-interface-web)
8. [Extensão Chrome](#-extensão-chrome)
9. [Sistema de Auditoria](#-sistema-de-auditoria)
10. [Deploy](#-deploy)

---

## 🎯 Visão Geral

O **TJMG Anonymizer** é uma solução completa para anonimização automática de documentos judiciais. A ferramenta identifica e redige dados sensíveis em PDFs, garantindo conformidade com a LGPD e a Resolução 615/CNJ.

### Principais Características

| Característica | Descrição |
|----------------|-----------|
| 🔍 **Detecção Inteligente** | Combina Regex + NLP (SpaCy) + OCR |
| 📄 **Suporte a PDF/DOCX** | PDFs nativos e digitalizados |
| 🔒 **Anonimização Irreversível** | Tarjas que removem texto subjacente |
| 📊 **Auditoria Completa** | Logs imutáveis com hashes SHA-256 |
| 🌐 **API REST** | Integração fácil com outros sistemas |
| 🧩 **Extensão Chrome** | Anonimização direta do navegador |

---

## 🏗 Arquitetura

```
┌─────────────────────────────────────────────────────────────────────┐
│                          TJMG Anonymizer                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐ │
│  │   Frontend  │    │  Chrome     │    │      API REST           │ │
│  │   (Web UI)  │───▶│  Extension  │───▶│     (FastAPI)           │ │
│  └─────────────┘    └─────────────┘    └───────────┬─────────────┘ │
│                                                     │               │
│  ┌──────────────────────────────────────────────────▼─────────────┐ │
│  │                    PIPELINE DE PROCESSAMENTO                   │ │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │ │
│  │  │ PDF     │─▶│ OCR     │─▶│ Regex   │─▶│ NER     │─┐         │ │
│  │  │ Handler │  │ Engine  │  │ Matcher │  │ Engine  │ │         │ │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘ │         │ │
│  │                                                      │         │ │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────────────────┐  │         │ │
│  │  │Allowlist│◀─│Context  │◀─│      Redactor       │◀─┘         │ │
│  │  │ Manager │  │Validator│  │  (Aplica Tarjas)    │            │ │
│  │  └─────────┘  └─────────┘  └──────────┬──────────┘            │ │
│  │                                        │                       │ │
│  └────────────────────────────────────────│───────────────────────┘ │
│                                           │                         │
│  ┌────────────────────────────────────────▼───────────────────────┐ │
│  │                    SISTEMA DE AUDITORIA                        │ │
│  │         Logs Imutáveis • Hashes SHA-256 • JSONL                │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Estrutura de Diretórios

```
anonimizacao/
├── app/                          # 🧠 Backend FastAPI
│   ├── api/                      # Endpoints REST
│   │   ├── routes.py             # Rotas da API
│   │   └── schemas.py            # Schemas Pydantic
│   ├── core/                     # Motores de Processamento
│   │   ├── pipeline.py           # Orquestrador principal
│   │   ├── pdf_handler.py        # Manipulação de PDFs
│   │   ├── ocr_engine.py         # Motor OCR (Tesseract)
│   │   ├── regex_matcher.py      # Padrões regex brasileiros
│   │   ├── ner_engine.py         # NLP com SpaCy
│   │   ├── context_validator.py  # Validação contextual
│   │   ├── allowlist.py          # Lista branca
│   │   └── redactor.py           # Aplicação de tarjas
│   ├── audit/                    # Sistema de Auditoria
│   │   └── logger.py             # Logs imutáveis
│   ├── config.py                 # Configurações
│   └── main.py                   # Entry point
├── frontend/                     # 🌐 Interface Web
│   ├── index.html                # Página principal
│   ├── style.css                 # Estilos
│   └── app.js                    # Lógica do frontend
├── chrome_extension/             # 🧩 Extensão Chrome
│   ├── manifest.json             # Configuração MV3
│   ├── popup.html/js             # Interface popup
│   ├── background.js             # Service worker
│   └── content.js                # Script de conteúdo
├── data/                         # 📁 Dados
│   ├── uploads/                  # Arquivos temporários
│   └── allowlist/                # Listas brancas
├── logs/                         # 📝 Logs de auditoria
├── tests/                        # 🧪 Testes automatizados
├── Dockerfile                    # 🐳 Configuração Docker
└── requirements.txt              # 📦 Dependências Python
```

---

## 🔧 Funcionalidades

### 1. Detecção de Dados Sensíveis

O sistema utiliza **três camadas** de detecção:

#### 🔢 Regex Matcher
Padrões otimizados para o contexto jurídico brasileiro:

| Tipo | Padrão | Exemplo |
|------|--------|---------|
| CPF | `\d{3}\.\d{3}\.\d{3}-\d{2}` | 123.456.789-00 |
| CNPJ | `\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}` | 12.345.678/0001-90 |
| RG | `\d{2}\.\d{3}\.\d{3}-[\dX]` | 12.345.678-9 |
| OAB | `OAB[/-]?[A-Z]{2}[/-]?\d+` | OAB/MG 123456 |
| Telefone | `\(\d{2}\)\s?\d{4,5}-?\d{4}` | (31) 99999-9999 |
| E-mail | Padrão RFC-compliant | email@dominio.com |
| CEP | `\d{5}-\d{3}` | 30130-000 |
| Processo CNJ | `\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}` | 1234567-89.2024.8.13.0000 |
| Data | Múltiplos formatos | 01/01/2024 |

**Validação de Dígitos Verificadores:** CPF e CNPJ são validados matematicamente.

#### 🤖 NER Engine (SpaCy)
Reconhecimento de entidades nomeadas:

- **PESSOA**: Nomes de pessoas
- **ENDEREÇO**: Logradouros, cidades, CEPs
- **ORGANIZAÇÃO**: Empresas, instituições

**Detecção de Contexto Sensível:**
- Saúde: `doença`, `diagnóstico`, `tratamento`, `hospital`...
- Família: `menor`, `criança`, `adoção`, `guarda`...
- Violência: `agressão`, `estupro`, `assédio`...

#### 📋 Allowlist (Lista Branca)
Exceções configuráveis para termos que não devem ser anonimizados:
- Nomes de autoridades públicas
- Números de processos públicos
- Organizações governamentais

---

### 2. OCR para Documentos Digitalizados

O **OCR Engine** processa PDFs escaneados com:

| Etapa | Técnica | Biblioteca |
|-------|---------|------------|
| Conversão | PDF → Imagens | pdf2image |
| Pré-processamento | Binarização Otsu | OpenCV |
| Correção de Rotação | Deskew automático | Tesseract OSD |
| Remoção de Ruído | Filtro mediano | OpenCV |
| Extração + Posições | OCR com bounding boxes | Tesseract |

**Configurações:**
- **DPI**: 300 (configurável)
- **Idioma**: Português (por)
- **Confiança Mínima**: 60%

---

### 3. Anonimização (Redactor)

O **Redactor** aplica tarjas de forma irreversível:

```python
# Estratégias disponíveis:
redactor.redact_pdf()           # Tarjas sobre coordenadas
redactor.redact_text_blocks()   # Anonimiza blocos de texto
redactor.redact_by_text_search() # Busca e anonimiza textos
redactor.redact_via_rasterization() # "Nuclear" - rasteriza PDF inteiro
```

| Modo | Uso | Segurança |
|------|-----|-----------|
| **Normal** | Tarjas sobre dados identificados | ⭐⭐⭐⭐ |
| **Rasterização** | Converte para imagens | ⭐⭐⭐⭐⭐ |

**Nota:** A rasterização garante que NENHUM texto ou metadado oculto sobreviva.

---

### 4. Comparação Visual

Geração de PDF lado-a-lado para conferência:

```python
redactor.create_comparison_pdf(
    original_path="documento.pdf",
    redacted_path="documento_anonimizado.pdf",
    output_path="comparacao.pdf"
)
```

---

## 🛠️ Stack Tecnológico

### Backend

| Tecnologia | Versão | Função |
|------------|--------|--------|
| **Python** | 3.9+ | Linguagem base |
| **FastAPI** | 0.109 | Framework web |
| **Uvicorn** | 0.27 | Servidor ASGI |
| **Pydantic** | 2.5 | Validação de dados |

### Processamento de PDF

| Biblioteca | Versão | Função |
|------------|--------|--------|
| **PyMuPDF (fitz)** | 1.23 | Manipulação de PDFs |
| **pdf2image** | 1.16 | Conversão PDF → Imagem |
| **pikepdf** | 8.11 | Operações avançadas em PDF |

### OCR

| Biblioteca | Versão | Função |
|------------|--------|--------|
| **Tesseract** | - | Motor OCR |
| **pytesseract** | 0.3 | Wrapper Python |
| **OpenCV** | 4.9 | Pré-processamento de imagens |
| **Pillow** | 10.2 | Manipulação de imagens |

### NLP

| Biblioteca | Versão | Modelo |
|------------|--------|--------|
| **SpaCy** | 3.7 | pt_core_news_lg |

---

## 🚀 Instalação

### Pré-requisitos

- Python 3.9+
- Tesseract OCR
- Poppler (para pdf2image)

### Instalação Local

```bash
# 1. Clonar repositório
git clone https://github.com/tjmg/anonimizacao.git
cd anonimizacao

# 2. Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Instalar dependências Python
pip install -r requirements.txt

# 4. Instalar modelo SpaCy
python -m spacy download pt_core_news_lg

# 5. Instalar Tesseract OCR
# macOS:
brew install tesseract tesseract-lang poppler

# Ubuntu/Debian:
sudo apt-get install tesseract-ocr tesseract-ocr-por poppler-utils

# 6. Executar servidor
uvicorn app.main:app --reload --port 8000
```

### Docker

```bash
# Build
docker build -t tjmg-anonymizer .

# Run
docker run -p 8000:8000 tjmg-anonymizer
```

---

## 📡 API Reference

**Base URL:** `http://localhost:8000/api`

### POST /api/analyze

Analisa documento e retorna preview dos dados sensíveis identificados.

**Request:**
```http
POST /api/analyze
Content-Type: multipart/form-data

file: documento.pdf
classe_processual: "Ação Civil Pública" (opcional)
vara: "1ª Vara Cível" (opcional)
comarca: "Belo Horizonte" (opcional)
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "analyzed",
  "total_pages": 5,
  "sensitive_data": [
    {
      "type": "CPF",
      "value": "123.456.789-00",
      "page": 1,
      "confidence": 0.95,
      "source": "regex"
    }
  ]
}
```

---

### POST /api/anonymize

Anonimiza documento e retorna o PDF processado.

**Request:**
```http
POST /api/anonymize
Content-Type: multipart/form-data

file: documento.pdf
```

**Response:** Arquivo PDF anonimizado (binário)

---

### POST /api/anonymize/json

Anonimiza documento e retorna metadados JSON.

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "total_pages": 5,
  "identified": 12,
  "redacted": 10,
  "ignored": 2,
  "processing_time_ms": 3500,
  "hash_original": "sha256:a1b2c3...",
  "hash_anonymized": "sha256:d4e5f6...",
  "download_url": "/api/download/550e8400..."
}
```

---

### GET /api/download/{job_id}

Baixa arquivo anonimizado.

**Response:** Arquivo PDF (application/pdf)

---

### GET /api/audit/{job_id}

Consulta log de auditoria.

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:00Z",
  "original_file": "documento.pdf",
  "hash_original": "sha256:a1b2c3...",
  "hash_anonymized": "sha256:d4e5f6...",
  "total_redactions": 10,
  "rules_applied": ["CPF", "PESSOA", "ENDERECO"],
  "processing_time_ms": 3500,
  "user": "admin",
  "ip_origin": "192.168.1.100"
}
```

---

### GET /api/audit/stats

Retorna estatísticas gerais.

**Response:**
```json
{
  "total_jobs": 1250,
  "total_redactions": 15000,
  "by_type": {
    "CPF": 5000,
    "PESSOA": 4500,
    "ENDERECO": 3000,
    "CNPJ": 2500
  },
  "average_time_ms": 2800
}
```

---

### Allowlist (Lista Branca)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/allowlist` | Adiciona item |
| GET | `/api/allowlist` | Lista itens |
| DELETE | `/api/allowlist/{name}` | Remove item |
| GET | `/api/allowlist/stats` | Estatísticas |

---

## 🖥 Interface Web

A interface web oferece uma experiência intuitiva:

### Funcionalidades

1. **Upload Drag & Drop**
   - Suporte a PDF e DOCX
   - Preview do arquivo selecionado

2. **Metadados do Processo** (opcional)
   - Classe Processual
   - Vara
   - Comarca

3. **Análise (Preview)**
   - Visualiza dados identificados antes de anonimizar
   - Tabela com tipo, valor mascarado, página e confiança

4. **Anonimização**
   - Processamento com barra de progresso
   - Download do PDF anonimizado
   - Exibição de hashes para verificação

### Estatísticas Exibidas

| Métrica | Descrição |
|---------|-----------|
| 📄 Páginas | Total de páginas |
| 🎯 Identificados | Dados sensíveis encontrados |
| 🔒 Anonimizados | Dados efetivamente redatados |
| ⏱️ Tempo | Tempo de processamento |

### Acesso

```
http://localhost:8000/
```

---

## 🧩 Extensão Chrome

A extensão permite anonimizar documentos diretamente do navegador.

### Instalação

1. Acesse `chrome://extensions/`
2. Ative "Modo do desenvolvedor"
3. Clique em "Carregar sem compactação"
4. Selecione a pasta `chrome_extension/`

### Funcionalidades

- **Popup**: Interface para upload e configuração
- **Content Script**: Captura de PDFs da página
- **Background Worker**: Comunicação com a API

### Manifest V3

A extensão utiliza o Manifest V3, o padrão mais recente do Chrome.

---

## 📊 Sistema de Auditoria

### Características

| Aspecto | Implementação |
|---------|---------------|
| **Formato** | JSON Lines (.jsonl) |
| **Integridade** | Hash SHA-256 |
| **Imutabilidade** | Append-only |
| **Rastreabilidade** | Job ID, usuário, IP |

### Estrutura do Log

```json
{
  "job_id": "uuid",
  "timestamp": "2024-01-15T10:30:00Z",
  "arquivo_original": "documento.pdf",
  "hash_original": "sha256:...",
  "arquivo_anonimizado": "documento_anon.pdf",
  "hash_anonimizado": "sha256:...",
  "total_redacoes": 10,
  "regras_aplicadas": ["CPF", "PESSOA"],
  "dados_anonimizados": [...],
  "tempo_processamento_ms": 3500,
  "usuario": "admin",
  "ip_origem": "192.168.1.100"
}
```

### Verificação de Integridade

```python
from app.audit.logger import audit_logger

# Verificar se arquivo foi alterado
result = audit_logger.verify_integrity(
    job_id="550e8400...",
    file_path=Path("documento_anon.pdf")
)

# Resultado:
# {"valido": True, "tipo": "anonimizado", "hash": "sha256:..."}
```

---

## 🚀 Deploy

### Railway (Recomendado)

O projeto está pronto para deploy no Railway:

1. **Conecte o repositório**
2. Railway detecta o `Dockerfile` automaticamente
3. A variável `PORT` é injetada pelo Railway

**Configurações no Dockerfile:**
- ✅ Tesseract OCR + idioma português
- ✅ Poppler para pdf2image
- ✅ Modelo SpaCy baixado no build
- ✅ Usuário não-root por segurança

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `PORT` | 8000 | Porta do servidor |
| `OCR_LANGUAGE` | por | Idioma do Tesseract |
| `OCR_DPI` | 300 | Resolução do OCR |
| `SPACY_MODEL` | pt_core_news_lg | Modelo NLP |

---

## 📄 Conformidade Legal

### Resolução 615/CNJ

Esta ferramenta foi desenvolvida em conformidade com a **Resolução Nº 615 do CNJ** (15/02/2024), que regulamenta:

> Art 2º: "Os documentos judiciais deverão ter os dados pessoais sensíveis protegidos antes da disponibilização pública."

### LGPD (Lei 13.709/2018)

Atende aos requisitos de:
- **Anonimização** (Art. 5º, III)
- **Segurança** (Art. 46)
- **Rastreabilidade** (Art. 37)

---

## 🔒 Segurança

| Medida | Implementação |
|--------|---------------|
| **Execução** | Container com usuário não-root |
| **Dados** | Arquivos temporários são removidos |
| **Auditoria** | Logs imutáveis com hashes |
| **Validação** | Input sanitization via Pydantic |

---

## 📞 Suporte

**Desenvolvido para uso interno do TJMG**

- 📧 Email: suporte@tjmg.jus.br
- 📖 Documentação: Este documento
- 🐛 Issues: GitHub Issues

---

## 📝 Changelog

### v1.0.0 (2024)
- ✅ Pipeline completo de anonimização
- ✅ OCR com Tesseract + OpenCV
- ✅ NER com SpaCy
- ✅ API REST FastAPI
- ✅ Interface Web responsiva
- ✅ Extensão Chrome (MV3)
- ✅ Sistema de auditoria
- ✅ Docker + Railway ready

---

<div align="center">

**TJMG Anonymizer Pipeline v1.0.0**

Desenvolvido com ❤️ para o Tribunal de Justiça de Minas Gerais

Em conformidade com a **Resolução 615/CNJ** e **LGPD**

</div>
