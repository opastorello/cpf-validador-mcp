# cpf-validador-mcp

> MCP server para consulta de feitos trabalhistas no **TRT3 (3ª Região)** com resolução automática de CAPTCHA via rede neural treinada localmente — sem APIs externas, sem serviços pagos.

Expõe as mesmas operações como **MCP tools** (para agentes AI) e **REST API** (para integrações diretas), usando a mesma lógica de negócio internamente.

---

## Por que este projeto existe

O site do TRT3 ([certidao.trt3.jus.br](https://certidao.trt3.jus.br)) exige resolução de CAPTCHA para cada consulta. Este projeto resolve isso com uma CRNN (Convolutional Recurrent Neural Network) treinada especificamente nas imagens do site, atingindo **~99% de acurácia** sem depender de nenhum serviço externo.

---

## MCP Tools

| Tool                        | Descrição |
| --------------------------- | --------- |
| `validate_cpf`              | Valida matematicamente um CPF pelo algoritmo módulo-11 |
| `generate_valid_variations` | Gera todas as variações válidas de um CPF possivelmente errado: recalcula dígitos, troca 1 dígito, transpõe pares adjacentes |
| `check_feitos_trabalhistas` | Consulta feitos trabalhistas no TRT3 — valida CPF, resolve CAPTCHA e retorna resultado estruturado |
| `find_cpf_by_mask`          | Descobre o CPF completo a partir de uma máscara com `*` nos dígitos desconhecidos — consulta o TRT3 em paralelo filtrando pelo nome |
| `find_cpf_by_variations`    | Dado um CPF parcial ou com erros (10 ou 11 dígitos), gera candidatos válidos e consulta o TRT3 em paralelo |
| `check_multiple_cpfs`       | Consulta uma lista de CPFs em paralelo, agrupando erros de validação separadamente |

---

## REST API

| Método | Rota                         | Rate limit     | Descrição |
| ------ | ---------------------------- | -------------- | --------- |
| `POST` | `/cpf/validate`              | —              | Valida um CPF |
| `POST` | `/cpf/variations`            | —              | Gera variações válidas de um CPF |
| `POST` | `/trt3/feitos`               | 10/min por IP  | Consulta feitos trabalhistas de um CPF |
| `POST` | `/trt3/feitos-multiplos`     | 5/min por IP   | Consulta uma lista de CPFs em paralelo |
| `POST` | `/trt3/buscar-por-mascara`   | 3/min por IP   | Consulta CPFs que encaixam em máscara com `*` |
| `POST` | `/trt3/buscar-por-variacoes` | 3/min por IP   | Consulta variações de CPF parcial em paralelo |
| `GET`  | `/health`                    | —              | Health check — retorna `{"status": "ok"}` |
| `GET`  | `/`                          | —              | Interface web para consultas manuais |

Documentação interativa: `http://localhost:8000/docs` (disponível apenas em `ENV=development`).

---

## Arquitetura

FastAPI com FastMCP 3.0 montado em `/mcp` (streamable-http). A camada `services/` não tem dependência de framework — a mesma lógica é consumida pelos routers REST e pelo MCP server.

```
app/
├── main.py             # FastAPI — routers + mcp.http_app() em /mcp + rate limiter
├── config.py           # Lê todas as variáveis de ambiente com defaults
├── mcp_server.py       # FastMCP("cpf-validador") — 6 tools
├── auth.py             # TokenMiddleware — autenticação via API_TOKEN + controle prod/dev
├── services/
│   ├── cpf.py          # Validação, variações e geração por máscara (zero deps de framework)
│   └── trt3.py         # Web scraping TRT3: curl_cffi + CAPTCHA solver + pypdf
├── routers/
│   ├── cpf.py          # POST /cpf/validate, POST /cpf/variations
│   ├── trt3.py         # POST /trt3/feitos, /feitos-multiplos, /buscar-por-mascara, /buscar-por-variacoes
│   ├── history.py      # GET/POST/DELETE /history/ — histórico de consultas
│   └── ui.py           # GET / — interface web
└── captcha/
    ├── model.py        # Arquitetura CRNN (CNN + BiLSTM + CTC Loss)
    ├── predictor.py    # Inferência: carrega captcha_model.pt e prediz
    ├── dataset.py      # CaptchaDataset com data augmentation
    ├── train.py        # Loop de treino com early stopping + AMP + registry
    ├── collector.py    # Coleta amostras rotuladas direto do TRT3
    ├── registry.py     # Versionamento de modelos (models/vN/model.pt + meta.json)
    └── models/         # Histórico de versões treinadas
```

**Regras de camada:**
- `services/` — zero imports de FastAPI ou FastMCP
- `routers/` e `mcp_server.py` — importam apenas de `services/`
- I/O bloqueante em `services/trt3.py` é sempre executado via `run_in_threadpool`

---

## Configuração

Todas as opções são lidas de variáveis de ambiente ou do arquivo `.env` na raiz do projeto.

### Referência completa de variáveis

| Variável                  | Padrão                                            | Descrição |
| ------------------------- | ------------------------------------------------- | --------- |
| `API_TOKEN`               | *(vazio — sem auth)*                              | Token Bearer. Se vazio, todos os endpoints ficam abertos |
| `ENV`                     | `development`                                     | `development` ou `production` — controla quais rotas ficam abertas sem token (ver abaixo) |
| `TRT3_BASE_URL`           | `https://certidao.trt3.jus.br`                   | URL base do site do TRT3 |
| `TRT3_FORM_PATH`          | `/certidao/feitosTrabalhistas/aba1.emissao.htm`  | Path do formulário de consulta |
| `HTTP_TIMEOUT`            | `30`                                              | Timeout (segundos) para requisições HTTP ao TRT3 |
| `CAPTCHA_TIMEOUT`         | `15`                                              | Timeout (segundos) para download da imagem CAPTCHA |
| `MAX_CAPTCHA_ATTEMPTS`    | `20`                                              | Tentativas máximas de resolver o CAPTCHA antes de desistir |
| `RETRY_DELAY`             | `1.0`                                             | Segundos de espera entre tentativas de CAPTCHA |
| `DEFAULT_WORKERS`         | `8`                                               | Threads paralelas padrão nas consultas em lote |
| `MAX_WORKERS`             | `20`                                              | Limite máximo de `workers` que o cliente pode solicitar |
| `TASK_TIMEOUT`            | `60`                                              | Timeout (segundos) por CPF individual em consultas paralelas |
| `MAX_WILDCARDS_IN_MASK`   | `5`                                               | Máximo de `*` na parte base da máscara (evita explosão combinatória) |
| `RATE_LIMIT_FEITOS`       | `10/minute`                                       | Rate limit de `/trt3/feitos` por IP |
| `RATE_LIMIT_MULTIPLOS`    | `5/minute`                                        | Rate limit de `/trt3/feitos-multiplos` por IP |
| `RATE_LIMIT_MASK`         | `3/minute`                                        | Rate limit de `/trt3/buscar-por-mascara` por IP |
| `RATE_LIMIT_VARIACOES`    | `3/minute`                                        | Rate limit de `/trt3/buscar-por-variacoes` por IP |
| `CAPTCHA_MODEL_PATH`      | *(vazio — usa `app/captcha/captcha_model.pt`)*   | Path absoluto para o modelo `.pt` (útil para montar modelo externo) |
| `HISTORY_RETENTION_DAYS`  | `90`                                              | Dias de retenção do histórico (LGPD). `0` = sem limite |
| `APP_TIMEZONE`            | `America/Sao_Paulo`                               | Timezone para timestamps do histórico |

### Rotas abertas por ambiente

| Rota           | `development` | `production` |
| -------------- | :-----------: | :----------: |
| `/`            | ✅ aberta     | ✅ aberta    |
| `/health`      | ✅ aberta     | 🔒 token     |
| `/docs`        | ✅ aberta     | 🔒 token     |
| `/redoc`       | ✅ aberta     | 🔒 token     |
| `/openapi.json`| ✅ aberta     | 🔒 token     |
| `/mcp`         | 🔒 token     | 🔒 token     |
| demais         | 🔒 token     | 🔒 token     |

> Se `API_TOKEN` estiver vazio, o middleware ignora autenticação em qualquer ambiente.

---

## Autenticação

Com `API_TOKEN` configurado, todas as requisições protegidas precisam enviar:

```
Authorization: Bearer meu-token-secreto
```

**REST:**

```bash
curl -X POST http://localhost:8000/trt3/feitos \
  -H "Authorization: Bearer meu-token-secreto" \
  -H "Content-Type: application/json" \
  -d '{"cpf": "529.982.247-25"}'
```

**Claude Desktop / Claude Code (`claude_desktop_config.json`):**

```json
{
  "mcpServers": {
    "cpf-validador": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8000/mcp", "--allow-http"],
      "env": {
        "MCP_REMOTE_HEADER_AUTHORIZATION": "Bearer meu-token-secreto"
      }
    }
  }
}
```

---

## Instalação

### Pré-requisito: modelo de CAPTCHA

O arquivo `app/captcha/captcha_model.pt` não está incluso no repositório. Baixe via [GitHub Releases](https://github.com/opastorello/cpf-validador-mcp/releases) e coloque em `app/captcha/captcha_model.pt` — ou treine do zero (ver [Treinar o modelo](#treinar-o-modelo)).

### Docker (recomendado)

```bash
# Copie e ajuste o .env
cp .env.example .env

# Suba o container (porta 8002 → 8000 interno)
docker compose up -d

# Para produção
ENV=production docker compose up -d
```

### Local

```bash
git clone https://github.com/opastorello/cpf-validador-mcp
cd cpf-validador-mcp
pip install -r requirements.txt
cp .env.example .env   # ajuste as variáveis

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Após iniciar:
- Web UI: `http://localhost:8000/`
- REST docs: `http://localhost:8000/docs` *(apenas em `ENV=development`)*
- MCP endpoint: `http://localhost:8000/mcp`

---

## Exemplos de uso

### Consulta simples

```bash
curl -X POST http://localhost:8000/trt3/feitos \
  -H "Content-Type: application/json" \
  -d '{"cpf": "529.982.247-25"}'
```

```json
{
  "cpf": "529.982.247-25",
  "encontrado": true,
  "tipo_certidao": "NEGATIVA",
  "tem_feitos": false,
  "nome_certidao": "JOAO DA SILVA",
  "valida_ate": "18/04/2026",
  "numero_certidao": "2026/123456"
}
```

### Descobrir CPF por máscara

Quando você conhece apenas parte dos dígitos — substitua os desconhecidos por `*`:

```bash
curl -X POST http://localhost:8000/trt3/buscar-por-mascara \
  -H "Content-Type: application/json" \
  -d '{"mascara": "***.123.456-**", "nome": "João Silva"}'
```

O servidor gera todas as combinações válidas para as posições com `*` (recalculando os dígitos verificadores), consulta o TRT3 em paralelo e retorna apenas os matches com o nome informado.

> Máximo de 5 wildcards na parte base (posições 0–8) = até 100.000 combinações. Configurável via `MAX_WILDCARDS_IN_MASK`.

### Recuperar CPF com erros ou dígito faltando

```bash
curl -X POST http://localhost:8000/trt3/buscar-por-variacoes \
  -H "Content-Type: application/json" \
  -d '{"cpf_parcial": "5299824725", "nome": "joao"}'
```

Gera todos os candidatos válidos e filtra pelo nome na certidão emitida pelo TRT3.

### Consulta em lote

```bash
curl -X POST http://localhost:8000/trt3/feitos-multiplos \
  -H "Content-Type: application/json" \
  -d '{"cpfs": ["529.982.247-25", "111.444.777-35"], "workers": 4}'
```

---

## Fluxo de consulta TRT3

```
1. GET página           → extrai JSF ViewState + URL do CAPTCHA
2. GET imagem CAPTCHA   → resolve com CRNN local (PyTorch, CPU)
3. POST formulário      → impersonação Chrome-124 via curl_cffi (bypass TLS fingerprint)
4. Retry até 20×        → CAPTCHA inválido: reutiliza sessão / sessão expirada: refaz GET
5. Parse resultado      → PDF: extrai campos via pypdf + regex / HTML: parse direto
```

---

## Modelo de CAPTCHA

### Arquitetura CRNN

```
Input (1×60×160)
    → Conv2D ×4 + BatchNorm + ReLU + MaxPool   (extração de features visuais)
    → BiLSTM ×2 (128 hidden, bidirectional)    (modelagem de sequência)
    → Linear → CTC Loss                         (decode sem segmentação)
Output: string de 5 caracteres [0-9a-z]
```

### Bootstrapping em 3 rodadas

| Rodada | Amostras | Rotulador              | Acurácia dos labels | Acurácia do modelo |
| ------ | -------- | ---------------------- | :-----------------: | :----------------: |
| 1      | 15.000   | ddddocr (OCR genérico) | ~43%                | **98.70%**         |
| 2      | 20.000   | Modelo R1              | ~96%                | **98.80%**         |
| 3      | 20.000   | Modelo R2              | ~99.3%              | **98.55%**         |

**Total: 55.000 amostras.** O modelo final (v1) convergiu na época 106/120 com `val_loss=0.0072`.

### Hiperparâmetros

- **Optimizer:** AdamW | **LR:** 1e-3 com CosineAnnealingLR
- **Epochs:** 120 com early stopping (patience: 20)
- **Batch size:** 128 | **AMP:** float16 via `torch.amp.autocast`
- **Augmentation:** rotação, shear, translate, color jitter, gaussian blur, random erasing

---

## Treinar o modelo

**1. Coletar amostras**

```bash
python -m app.captcha.collector --cpf 000.000.000-00 --target 15000 --workers 4
```

**2. Treinar**

```bash
python -m app.captcha.train --epochs 120 --batch 128 --lr 1e-3
```

O melhor modelo (menor `val_loss`) é salvo em `app/captcha/captcha_model.pt`.

**3. Bootstrap (melhora qualidade dos labels)**

```bash
rm -rf app/captcha/data/
python -m app.captcha.collector --cpf 000.000.000-00 --target 20000 --workers 4
python -m app.captcha.train --epochs 120 --batch 128 --lr 1e-3
```

Repita 2–3 rodadas até a acurácia estabilizar. Para consultar o histórico de versões:

```bash
python -m app.captcha.registry
```

---

## Dependências principais

| Pacote | Uso |
| ------ | --- |
| [FastMCP](https://github.com/jlowin/fastmcp) | Framework MCP server |
| [FastAPI](https://fastapi.tiangolo.com/) | REST API |
| [slowapi](https://github.com/laurentS/slowapi) | Rate limiting por IP |
| [curl-cffi](https://github.com/yifeikong/curl-cffi) | HTTP com impersonação TLS Chrome-124 |
| [PyTorch](https://pytorch.org/) | Rede neural CRNN para CAPTCHA |
| [torchvision](https://pytorch.org/vision/) | Transforms e augmentation de imagem |
| [pypdf](https://github.com/py-pdf/pypdf) | Extração de dados do PDF de certidão |
| [Pillow](https://python-pillow.org/) | Processamento de imagem |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | Carregamento de variáveis do `.env` |
