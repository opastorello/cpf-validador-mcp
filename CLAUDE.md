# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run server locally (FastAPI + FastMCP on port 8000)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Docker
docker build -t cpf-validador .
docker run -p 8000:8000 cpf-validador
```

There are no automated tests. Manual testing via:
- FastAPI docs: `http://localhost:8000/docs`
- MCP transport: `http://localhost:8000/mcp` (streamable-http)

## Architecture

FastAPI app (`app/main.py`) that includes REST routers **and** mounts a FastMCP 3.0 server at `/mcp`.

```
app/
├── main.py           # FastAPI app — includes routers, mounts mcp.http_app() at /mcp
├── mcp_server.py     # FastMCP("cpf-validador") — 4 tools wrapping services
├── auth.py           # TokenMiddleware — optional auth via API_TOKEN env var
├── services/
│   ├── cpf.py        # Pure CPF logic (no framework deps)
│   └── trt3.py       # TRT3 web scraping (curl_cffi + CRNN captcha + pypdf) + parallel lookup
├── routers/
│   ├── cpf.py        # POST /cpf/validate, POST /cpf/variations
│   └── trt3.py       # POST /trt3/feitos, POST /trt3/buscar-por-variacoes
└── captcha/
    ├── model.py       # CRNN architecture (CNN + BiLSTM + CTC Loss)
    ├── predictor.py   # Inference — loads captcha_model.pt
    ├── dataset.py     # CaptchaDataset with augmentation
    ├── train.py       # Training loop with early stopping + AMP + registry
    ├── collector.py   # Collects labeled samples from TRT3 (--workers N)
    ├── registry.py    # Model versioning (models/vN/model.pt + meta.json)
    └── models/        # Versioned model history
```

### Layer rules
- `services/` has **no FastAPI or FastMCP imports** — pure Python callable from anywhere
- `routers/` and `mcp_server.py` both import from `services/` — same business logic, two interfaces
- Blocking I/O in `services/trt3.py` is always wrapped with `run_in_threadpool` before awaiting
- Parallel TRT3 queries use `ThreadPoolExecutor` inside `services/trt3.py` (not in routers)

### MCP tools
| Tool | Description |
|------|-------------|
| `validate_cpf` | Mathematical validation via modulo-11 check-digit algorithm |
| `generate_valid_variations` | Returns all valid CPF variants: recalc digits, single-digit swap, adjacent transposition |
| `check_feitos_trabalhistas` | Queries TRT3 labor court — validates CPF, solves CAPTCHA (CRNN), parses PDF result |
| `find_cpf_by_variations` | Generates all valid candidates from a partial CPF and queries TRT3 in parallel — filters by name in the PDF certidão |

### REST endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/cpf/validate` | Validate a CPF |
| POST | `/cpf/variations` | Generate valid variations |
| POST | `/trt3/feitos` | Query TRT3 labor records for one CPF |
| POST | `/trt3/buscar-por-variacoes` | Query all valid variants of a partial CPF in parallel, filter by name |
| GET | `/health` | Health check |

### TRT3 scraping flow
1. GET form page → extract JSF `ViewState` and CAPTCHA URL
2. Download CAPTCHA image → solve with **CRNN local model** (PyTorch, ~98.5% accuracy); fallback to ddddocr
3. POST form with Chrome-124 impersonation via **curl_cffi** (required to bypass TLS fingerprint)
4. Retry up to 20× on CAPTCHA failure
5. Parse response: if PDF returned, extract name/CPF/validity via **pypdf** regex

### CAPTCHA model
- Architecture: CRNN (4× Conv2D + BatchNorm + BiLSTM × 2 + CTC Loss)
- Training: 3 rounds bootstrapping, 55k samples total, val_accuracy 98.55%
- Active model: `app/captcha/captcha_model.pt` (registry v1)
- To retrain: `python -m app.captcha.train --epochs 120 --batch 128 --lr 1e-3`
