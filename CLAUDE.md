# CLAUDE.md

Guia para o Claude Code ao trabalhar neste repositório.

## Comandos

```bash
# Instalar dependências
pip install -r requirements.txt

# Rodar localmente (FastAPI + FastMCP na porta 8000)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Docker (porta 8002 conforme docker-compose.yaml)
docker compose up --build -d
docker compose down
```

Testes automatizados (mockam o TRT3, rodam no CI):

```bash
pip install -r requirements-dev.txt
ruff check app/
pytest tests/ -v
```

Testes manuais via:
- Interface web: `http://localhost:8000/`
- FastAPI docs (apenas `ENV=development`): `http://localhost:8000/docs`
- MCP transport: `http://localhost:8000/mcp` (streamable-http)

## Arquitetura

FastAPI (`app/main.py`) com routers REST + FastMCP 3.0 montado em `/mcp`. A camada `services/` não tem dependência de framework.

```
app/
├── main.py           # FastAPI — routers + rate limiter + mcp.http_app() em /mcp
├── config.py         # Lê todas as variáveis de ambiente com defaults
├── mcp_server.py     # FastMCP("cpf-validador") — 6 tools wrapping services
├── auth.py           # TokenMiddleware — autenticação via API_TOKEN + controle prod/dev via ENV
├── services/
│   ├── cpf.py        # Lógica pura de CPF (zero deps de framework)
│   └── trt3.py       # Web scraping TRT3: curl_cffi + CAPTCHA CRNN + pypdf + ThreadPoolExecutor
├── routers/
│   ├── cpf.py        # POST /cpf/validate, POST /cpf/variations
│   ├── trt3.py       # POST /trt3/feitos, /feitos-multiplos, /buscar-por-mascara, /buscar-por-variacoes
│   └── ui.py         # GET / — interface web com gate de autenticação
└── captcha/
    ├── model.py       # Arquitetura CRNN (CNN + BiLSTM + CTC Loss)
    ├── predictor.py   # Inferência — carrega captcha_model.pt
    ├── dataset.py     # CaptchaDataset com data augmentation
    ├── train.py       # Loop de treino com early stopping + AMP + registry
    ├── collector.py   # Coleta amostras rotuladas do TRT3 (--workers N)
    ├── registry.py    # Versionamento de modelos (models/vN/model.pt + meta.json)
    └── models/        # Histórico de versões treinadas
```

### Regras de camada
- `services/` — zero imports de FastAPI ou FastMCP; puro Python
- `routers/` e `mcp_server.py` importam apenas de `services/` — mesma lógica de negócio, duas interfaces
- I/O bloqueante em `services/trt3.py` sempre executado via `run_in_threadpool`
- Consultas paralelas usam `ThreadPoolExecutor` dentro de `services/trt3.py` (não nos routers)

### MCP tools (6)
| Tool | Descrição |
|------|-----------|
| `validate_cpf` | Validação matemática via algoritmo módulo-11 |
| `generate_valid_variations` | Gera variações válidas: recalcula dígitos, troca 1 dígito, transpõe pares adjacentes |
| `check_feitos_trabalhistas` | Consulta TRT3 — valida CPF, resolve CAPTCHA (CRNN), retorna resultado estruturado |
| `find_cpf_by_mask` | Descobre CPF completo a partir de máscara com `*` — consulta TRT3 em paralelo |
| `find_cpf_by_variations` | Gera candidatos de CPF parcial/errado e consulta TRT3 em paralelo, filtra por nome |
| `check_multiple_cpfs` | Consulta lista de CPFs em paralelo, agrupa erros de validação separadamente |

### REST endpoints
| Método | Rota | Rate limit | Descrição |
|--------|------|------------|-----------|
| GET | `/` | — | Interface web |
| POST | `/cpf/validate` | — | Valida um CPF |
| POST | `/cpf/variations` | — | Gera variações válidas |
| POST | `/trt3/feitos` | 10/min por IP | Consulta feitos de um CPF |
| POST | `/trt3/feitos-multiplos` | 5/min por IP | Consulta lista de CPFs em paralelo |
| POST | `/trt3/buscar-por-mascara` | 3/min por IP | Consulta CPFs por máscara com `*` |
| POST | `/trt3/buscar-por-variacoes` | 3/min por IP | Consulta variações de CPF parcial |
| GET | `/auth/check` | — | Valida o token (401 se inválido) — usado pelo gate da UI |
| GET | `/health` | — | Health check (sempre aberto — healthcheck do Docker) |
| GET | `/metrics` | — | Métricas Prometheus (token em `production`) |

### Autenticação
- `API_TOKEN` vazio → servidor sem autenticação
- `API_TOKEN` definido → todas as rotas exigem `Authorization: Bearer <token>`, exceto `/` e `/health`
- `ENV=development` → `/docs`, `/redoc`, `/openapi.json`, `/metrics` também ficam abertos
- `ENV=production` → apenas `/` e `/health` ficam abertos sem token (`/health` é o healthcheck do Docker)
- `METRICS_PUBLIC=true` → abre `/metrics` sem token também em `production`
- Interface web (`/`) tem gate: exige token no browser quando `API_TOKEN` está configurado. O gate valida contra `/auth/check` — **nunca** contra uma rota aberta como `/health`, senão qualquer token passa
- O histórico da UI vive no `localStorage` do navegador; o servidor não persiste consultas

### Fluxo de scraping TRT3
1. GET página do formulário → extrai JSF `ViewState` e URL do CAPTCHA
2. Download da imagem CAPTCHA → resolve com **modelo CRNN local** (PyTorch, ~99% acurácia)
3. POST do formulário com impersonação Chrome-124 via **curl_cffi** (bypass TLS fingerprint)
4. Retry até 20× em falha de CAPTCHA
5. Parse da resposta: se PDF retornado, extrai nome/CPF/validade via **pypdf** + regex

### Modelo CAPTCHA
- Arquitetura: CRNN (4× Conv2D + BatchNorm + BiLSTM × 2 + CTC Loss)
- Treinamento: 3 rodadas bootstrapping, 55k amostras, val_accuracy 98.55%
- Modelo ativo: `app/captcha/captcha_model.pt` (registry v1)
- Para retreinar: `python -m app.captcha.train --epochs 120 --batch 128 --lr 1e-3`
