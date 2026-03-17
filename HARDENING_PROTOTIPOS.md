# 🛡️ Guia de Hardening para Protótipos — TJMG/Railway

Checklist e código reutilizável para aplicar segurança básica em protótipos FastAPI + React deployados no Railway.

> Baseado nas diretrizes CESEC, COARF e Conod do TJMG.

---

## 1. CORS Restritivo

**Problema**: `allow_origins=["*"]` permite que qualquer site faça requests à API.

**Solução**: Usar variável de ambiente para controlar origens.

### `config.py`
```python
# Adicionar ao Settings:
CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
RATE_LIMIT: str = "10/minute"

@property
def cors_origins_list(self) -> list[str]:
    if not self.CORS_ORIGINS:
        return ["*"]
    return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
```

### `main.py`
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,  # ← Não mais ["*"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Railway (variável de ambiente)
```
TJMG_CORS_ORIGINS=https://meu-app.up.railway.app
```

> **⚠️ Importante**: use string separada por vírgula, **não** JSON. `pydantic-settings` não parseia `list[str]` de env vars corretamente.

---

## 2. Headers de Segurança (OWASP)

**Problema**: Sem headers, o app fica vulnerável a XSS, clickjacking, MIME sniffing.

### `main.py` — Middleware
```python
from fastapi import Request, Response

@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    return response
```

> **Nota**: Ajuste a CSP conforme as fontes externas do seu projeto (CDNs, APIs externas).

---

## 3. Rate Limiting (SlowAPI)

**Problema**: Sem rate limiting, a API é vulnerável a DoS e abuso.

### Instalar
```bash
pip install slowapi
# Adicionar ao requirements.txt: slowapi==0.1.9
```

### `main.py`
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

### Nas rotas de upload
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/upload")
@limiter.limit(settings.RATE_LIMIT)
async def upload(request: Request, file: UploadFile = File(...)):
    ...
```

---

## 4. Validação de Upload (Magic Bytes)

**Problema**: Validar apenas extensão do arquivo é insuficiente — alguém pode renomear `.exe` para `.pdf`.

### Instalar
```bash
pip install python-magic
# Adicionar ao requirements.txt: python-magic==0.4.27
# No Dockerfile: apt-get install -y libmagic1
```

### Código
```python
import magic

ALLOWED_MIMES = {
    "pdf": ["application/pdf"],
    "docx": [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    ],
}

def validate_file(file: UploadFile, content_bytes: bytes | None = None):
    # ... (validar extensão e tamanho)

    # Verificar tipo real via magic bytes
    if content_bytes:
        detected_mime = magic.from_buffer(content_bytes[:2048], mime=True)
        ext = file.filename.split('.')[-1].lower()
        if detected_mime not in ALLOWED_MIMES.get(ext, []):
            raise HTTPException(400, f"Tipo de arquivo inválido: {detected_mime}")
```

### Uso na rota
```python
content = await file.read()
validate_file(file, content_bytes=content)
# Depois escrever `content` no disco
```

---

## 5. Sanitização de Filename

**Problema**: `file.filename` pode conter `../../etc/passwd` — path traversal.

```python
import os, re

def sanitize_filename(filename: str) -> str:
    filename = os.path.basename(filename)          # remove diretórios
    filename = re.sub(r'[^\w\-.]', '_', filename)  # apenas chars seguros
    return filename or "upload"

# Uso:
safe_name = sanitize_filename(file.filename or "upload")
temp_path = UPLOAD_DIR / f"{job_id}_{safe_name}"
```

---

## 6. Acessibilidade Básica (WCAG)

Adicionar `aria-label` em todos os botões que usam apenas ícones:

```tsx
<button aria-label="Página anterior" title="Página anterior">◀</button>
<button aria-label="Próxima página" title="Próxima página">▶</button>
<button aria-label="Diminuir zoom" title="Diminuir zoom">−</button>
<button aria-label="Aumentar zoom" title="Aumentar zoom">+</button>
```

Adicionar `role` em containers interativos:
```tsx
<div role="region" aria-label="Visualizador de documento">
<div role="document" aria-label={`Conteúdo da página ${page}`}>
```

---

## 7. Timestamps com Hora Legal Brasileira (HLB)

**Problema**: CESEC exige timestamps em HLB (UTC-3), não UTC.

```python
from datetime import datetime, timezone, timedelta

HLB = timezone(timedelta(hours=-3))

# Em vez de:
# timestamp = datetime.utcnow().isoformat() + 'Z'

# Usar:
timestamp = datetime.now(HLB).isoformat()
# Resultado: "2026-03-17T08:45:00-03:00"
```

---

## Checklist Rápido

Copie e cole ao iniciar cada protótipo:

```markdown
## Hardening do Protótipo
- [ ] CORS: `allow_origins` lê de variável de ambiente (não `["*"]`)
- [ ] Headers: middleware com X-Content-Type-Options, X-Frame-Options, CSP
- [ ] Rate limiting: SlowAPI nos endpoints de upload
- [ ] Upload: validar magic bytes (python-magic) + extensão + tamanho
- [ ] Filename: sanitizar com `os.path.basename()` + regex
- [ ] Acessibilidade: `aria-label` em botões de ícone, `role` em containers
- [ ] Timestamps: usar HLB (UTC-3) em logs de auditoria
- [ ] Railway: configurar `CORS_ORIGINS` nas variáveis de ambiente
```

---

## Dependências extras no `requirements.txt`
```
slowapi==0.1.9
python-magic==0.4.27
```

## No `Dockerfile`
```dockerfile
# libmagic já costuma vir com python-slim, mas garanta:
RUN apt-get update && apt-get install -y libmagic1
```
