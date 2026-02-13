# TJMG Anonymizer - Resumo Executivo

> **Apresentação para Setor de TI**  
> Fevereiro 2026

---

## 🎯 O que é?

Sistema de **anonimização automática** de documentos judiciais que:
- Detecta dados sensíveis (CPF, nomes, endereços, etc.)
- Remove ou substitui informações de forma irreversível
- Cumpre LGPD e Resolução CNJ 615/2024

---

## ✅ Principais Benefícios

| Benefício | Impacto |
|-----------|---------|
| **Automação** | Reduz tempo de anonimização manual de horas para segundos |
| **Precisão** | Até 95% de acurácia na detecção (modo BERTimbau) |
| **Compliance** | LGPD e CNJ 615 built-in |
| **Auditoria** | Logs imutáveis com hashes SHA-256 |
| **Escalabilidade** | Suporta arquivos até 200MB |

---

## 🏗️ Arquitetura Resumida

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│   FastAPI    │────▶│   Pipeline   │
│   (HTML/JS)  │     │   (REST)     │     │   (Python)   │
└──────────────┘     └──────────────┘     └──────────────┘
                                                 │
                     ┌───────────────────────────┼───────────────────────┐
                     ▼                           ▼                       ▼
              ┌────────────┐              ┌────────────┐          ┌────────────┐
              │   Regex    │              │    NER     │          │    OCR     │
              │  Matcher   │              │  (SpaCy/   │          │ (Tesseract/│
              │            │              │  BERT)     │          │  Paddle)   │
              └────────────┘              └────────────┘          └────────────┘
```

---

## 📊 Requisitos de Infraestrutura

### Mínimo
| Recurso | Especificação |
|---------|---------------|
| CPU | 2 cores |
| RAM | 4 GB |
| Disco | 10 GB |
| OS | Linux/Windows/macOS |

### Recomendado (Produção)
| Recurso | Especificação |
|---------|---------------|
| CPU | 4+ cores |
| RAM | 8 GB (16 GB com BERTimbau) |
| Disco | 50 GB SSD |
| Container | Docker |

---

## 🔐 Segurança

| Camada | Implementação |
|--------|---------------|
| Entrada | Validação de tipos, limite de tamanho |
| Processamento | Container non-root, timeout |
| Anonimização | True Redaction (remove bytes) |
| Auditoria | Logs append-only, hashes encadeados |

---

## 📡 Integração

### API REST
```bash
# Anonimizar documento
curl -X POST http://servidor:8000/api/anonymize \
  -F "file=@processo.pdf" \
  -o processo_anonimizado.pdf
```

### Modos de Operação
| Modo | Uso |
|------|-----|
| `redact` | Tarjas pretas (publicação) |
| `pseudonymize` | Dados fake (análise estatística) |

---

## 🚀 Deploy

```bash
# Docker (recomendado)
docker-compose up -d

# Ou Railway
railway up
```

---

## 📈 Roadmap Futuro

- [ ] Integração com e-SAJ/PJe
- [ ] API de batch processing (ZIP)
- [ ] Dashboard de métricas
- [ ] Classificação via LLM (Gemini/Claude)

---

## 📞 Próximos Passos

1. **Homologação** — Testar em ambiente controlado
2. **Piloto** — Selecionar vara para teste real
3. **Treinamento** — Capacitar usuários
4. **Deploy** — Produção gradual

---

**Documentação Completa:** `DOCUMENTACAO_TI.md`  
**Código Fonte:** `/anonimizacao/`
