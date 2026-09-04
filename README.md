# 🔍 CPF Validador

> Valide CPFs, descubra a quem pertencem e encontre o CPF correto a partir de dígitos parciais ou ilegíveis — com resolução automática de CAPTCHA via rede neural treinada localmente.

Expõe as mesmas operações como **MCP tools** (para agentes AI) e **REST API** (para integrações diretas), com interface web incluída.

---

## 💡 O que este projeto faz

| | |
|--|--|
| ✅ | Valida se um CPF é matematicamente correto |
| 👤 | Confirma a quem um CPF pertence pelo nome |
| 🔎 | Descobre o CPF completo a partir de dígitos parciais ou ilegíveis |
| 👥 | Processa dezenas de CPFs em paralelo |
| 🤖 | Integra com qualquer agente AI via protocolo MCP |

Para confirmar a titularidade de um CPF, o sistema consulta o **TRT3** — que emite certidões públicas associando CPF e nome. A resolução de CAPTCHA é feita por uma **CRNN (Convolutional Recurrent Neural Network)** treinada especificamente para isso, atingindo **~99% de acurácia** sem depender de nenhum serviço externo.

---

## 🤖 MCP Tools

| Tool | Descrição |
| ---- | --------- |
| `validate_cpf` | Valida matematicamente um CPF pelo algoritmo módulo-11 |
| `generate_valid_variations` | Gera todas as variações válidas de um CPF com dígitos errados ou ilegíveis |
| `check_feitos_trabalhistas` | Confirma titularidade de um CPF consultando o TRT3 |
| `find_cpf_by_mask` | Descobre o CPF completo a partir de uma máscara com `*` nos dígitos desconhecidos |
| `find_cpf_by_variations` | Dado um CPF parcial ou errado, encontra o correto filtrando pelo nome |
| `check_multiple_cpfs` | Valida e confirma titularidade de uma lista de CPFs em paralelo |

---

## 🌐 REST API

| Método | Rota | Rate limit | Descrição |
| ------ | ---- | ---------- | --------- |
| `GET`  | `/` | — | Interface web |
| `POST` | `/cpf/validate` | — | Valida um CPF matematicamente |
| `POST` | `/cpf/variations` | — | Gera variações válidas de um CPF |
| `POST` | `/trt3/feitos` | 10/min por IP | Confirma titularidade de um CPF via TRT3 |
| `POST` | `/trt3/feitos-multiplos` | 5/min por IP | Confirma lista de CPFs em paralelo |
| `POST` | `/trt3/buscar-por-mascara` | 3/min por IP | Descobre CPF por máscara com curingas |
| `POST` | `/trt3/buscar-por-variacoes` | 3/min por IP | Descobre CPF correto a partir de variações |
| `GET`  | `/auth/check` | — | Valida o token — `401` se ausente/incorreto, `200` se válido |
| `GET`  | `/health` | — | Health check — retorna `{"status": "ok"}` |

Documentação interativa: `http://localhost:8000/docs` (disponível apenas em `ENV=development`).

### 📂 Histórico de consultas

O histórico é **local ao navegador** — fica no `localStorage` da interface web e nunca sai do cliente. O servidor não persiste CPFs consultados.

- **Interface web:** o toggle na aba Histórico ativa ou desativa o salvamento automático; a preferência também é salva no `localStorage`.
- **REST API / MCP:** não gravam histórico — cada cliente registra o que quiser do seu lado.

---

## 🏗️ Arquitetura

FastAPI com FastMCP 3.0 montado em `/mcp` (streamable-http). A camada `services/` não tem dependência de framework — a mesma lógica é consumida pelos routers REST e pelo MCP server.

```
app/
├── main.py             # FastAPI — routers + mcp.http_app() em /mcp + rate limiter
├── config.py           # Lê todas as variáveis de ambiente com defaults
├── mcp_server.py       # FastMCP("cpf-validador") — 6 tools
├── auth.py             # TokenMiddleware — autenticação via API_TOKEN + controle prod/dev
├── services/
│   ├── cpf.py          # Validação, variações e geração por máscara (zero deps de framework)
│   └── trt3.py         # Consulta TRT3: curl_cffi + CAPTCHA solver + pypdf
├── routers/
│   ├── cpf.py          # POST /cpf/validate, POST /cpf/variations
│   ├── trt3.py         # POST /trt3/feitos, /feitos-multiplos, /buscar-por-mascara, /buscar-por-variacoes
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

## ⚙️ Configuração

Todas as opções são lidas de variáveis de ambiente ou do arquivo `.env` na raiz do projeto.

### Referência completa de variáveis

| Variável | Padrão | Descrição |
| -------- | ------ | --------- |
| `API_TOKEN` | *(vazio — sem auth)* | Token Bearer. Se vazio, todos os endpoints ficam abertos |
| `ENV` | `development` | `development` ou `production` — controla quais rotas ficam abertas sem token |
| `TRT3_BASE_URL` | `https://certidao.trt3.jus.br` | URL base do site do TRT3 |
| `TRT3_FORM_PATH` | `/certidao/feitosTrabalhistas/aba1.emissao.htm` | Path do formulário de consulta |
| `HTTP_TIMEOUT` | `30` | Timeout (segundos) para requisições HTTP ao TRT3 |
| `CAPTCHA_TIMEOUT` | `15` | Timeout (segundos) para download da imagem CAPTCHA |
| `MAX_CAPTCHA_ATTEMPTS` | `20` | Tentativas máximas de resolver o CAPTCHA antes de desistir |
| `RETRY_DELAY` | `1.0` | Segundos de espera entre tentativas de CAPTCHA |
| `DEFAULT_WORKERS` | `8` | Threads paralelas padrão nas consultas em lote |
| `MAX_WORKERS` | `20` | Limite máximo de `workers` que o cliente pode solicitar |
| `TASK_TIMEOUT` | `60` | Timeout (segundos) por CPF individual em consultas paralelas |
| `MAX_WILDCARDS_IN_MASK` | `5` | Máximo de curingas na parte base da máscara (evita explosão combinatória) |
| `RATE_LIMIT_FEITOS` | `10/minute` | Rate limit de `/trt3/feitos` por IP |
| `RATE_LIMIT_MULTIPLOS` | `5/minute` | Rate limit de `/trt3/feitos-multiplos` por IP |
| `RATE_LIMIT_MASK` | `3/minute` | Rate limit de `/trt3/buscar-por-mascara` por IP |
| `RATE_LIMIT_VARIACOES` | `3/minute` | Rate limit de `/trt3/buscar-por-variacoes` por IP |
| `CAPTCHA_MODEL_PATH` | *(vazio — usa `app/captcha/captcha_model.pt`)* | Path absoluto para o modelo `.pt` (útil para montar modelo externo) |
| `METRICS_PUBLIC` | `false` | `true` abre `/metrics` sem token também em `production` |

### 🔒 Rotas abertas por ambiente

| Rota | `development` | `production` |
| ---- | :-----------: | :----------: |
| `/` | ✅ aberta | ✅ aberta |
| `/health` | ✅ aberta | ✅ aberta |
| `/docs` | ✅ aberta | 🔒 token |
| `/redoc` | ✅ aberta | 🔒 token |
| `/openapi.json` | ✅ aberta | 🔒 token |
| `/metrics` | ✅ aberta | 🔒 token *(ou `METRICS_PUBLIC=true`)* |
| `/mcp` | 🔒 token | 🔒 token |
| demais | 🔒 token | 🔒 token |

> Se `API_TOKEN` estiver vazio, o middleware ignora autenticação em qualquer ambiente.

---

## 🔐 Autenticação

Com `API_TOKEN` configurado, todas as requisições protegidas precisam enviar:

```
Authorization: Bearer meu-token-secreto
```

**REST:**

```bash
curl -X POST http://localhost:8000/trt3/feitos \
  -H "Authorization: Bearer meu-token-secreto" \
  -H "Content-Type: application/json" \
  -d '{"cpf": "111.444.777-35"}'
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

A interface web (`/`) exibe um **gate de autenticação** quando `API_TOKEN` está definido — o token é validado contra o servidor e salvo no navegador.

---

## 🚀 Instalação

### Docker (recomendado)

```bash
git clone https://github.com/opastorello/cpf-validador.git
cd cpf-validador
cp .env.example .env   # edite se quiser definir API_TOKEN
docker compose up --build -d
```

### Local

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Após iniciar:
- Interface web: `http://localhost:8000/`
- REST docs: `http://localhost:8000/docs` *(apenas em `ENV=development`)*
- MCP endpoint: `http://localhost:8000/mcp`

---

## 📋 Exemplos de uso

### Validar um CPF

```bash
curl -X POST http://localhost:8000/cpf/validate \
  -H "Content-Type: application/json" \
  -d '{"cpf": "111.444.777-35"}'
```

### Confirmar titularidade

```bash
curl -X POST http://localhost:8000/trt3/feitos \
  -H "Content-Type: application/json" \
  -d '{"cpf": "111.444.777-35"}'
```

```json
{
  "cpf": "111.444.777-35",
  "encontrado": true,
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

O servidor gera todas as combinações válidas para as posições curinga, consulta em paralelo e retorna apenas os matches com o nome informado.

**Formatos de máscara aceitos.** Os curingas `*`, `X`, `x`, `?`, `_` e `#` são equivalentes, os separadores `.`, `-`, `/` e espaços são ignorados (inclusive nenhum separador), e os dígitos verificadores podem ser omitidos. Todas estas máscaras são a mesma coisa:

```
***.444.777-**      ← mascaramento LGPD de documento público
***444777**         ← sem separador
*** 444 777 **      ← separado por espaço
XXX.444.777-XX      ← anotação manual
???.444.777-??
___.444.777-__      ← campo de formulário
###.444.777-##      ← planilha
***.444.777         ← dígitos verificadores omitidos
```

Um caractere que não seja dígito, curinga ou separador é rejeitado com `422` apontando qual é — em vez de ser descartado silenciosamente e virar erro de tamanho.

> Máximo de 5 wildcards na parte base (posições 0–8) = até 100.000 combinações. Configurável via `MAX_WILDCARDS_IN_MASK`.

### Recuperar CPF com erros ou dígito faltando

```bash
curl -X POST http://localhost:8000/trt3/buscar-por-variacoes \
  -H "Content-Type: application/json" \
  -d '{"cpf_parcial": "1114447773", "nome": "joao"}'
```

### Consulta em lote

```bash
curl -X POST http://localhost:8000/trt3/feitos-multiplos \
  -H "Content-Type: application/json" \
  -d '{"cpfs": ["111.444.777-35", "123.456.789-09"], "workers": 4}'
```

---

## 🧠 Modelo de CAPTCHA

### Arquitetura CRNN

```
Input (1×60×160)
    → Conv2D ×4 + BatchNorm + ReLU + MaxPool   (extração de features visuais)
    → BiLSTM ×2 (128 hidden, bidirectional)    (modelagem de sequência)
    → Linear → CTC Loss                         (decode sem segmentação)
Output: string de 5 caracteres [0-9a-z]
```

### Bootstrapping em 3 rodadas

| Rodada | Amostras | Rotulador | Acurácia dos labels | Acurácia do modelo |
| ------ | -------- | --------- | :-----------------: | :----------------: |
| 1 | 15.000 | ddddocr (OCR genérico) | ~43% | **98.70%** |
| 2 | 20.000 | Modelo R1 | ~96% | **98.80%** |
| 3 | 20.000 | Modelo R2 | ~99.3% | **98.55%** |

**Total: 55.000 amostras.** O modelo final (v1) convergiu na época 106/120 com `val_loss=0.0072`.

### Hiperparâmetros

- **Optimizer:** AdamW | **LR:** 1e-3 com CosineAnnealingLR
- **Epochs:** 120 com early stopping (patience: 20)
- **Batch size:** 128 | **Treino:** GPU com AMP float16 via `torch.amp.autocast`
- **Inferência:** CPU-only (Docker)
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

## 📦 Dependências principais

| Pacote | Uso |
| ------ | --- |
| [FastMCP](https://github.com/jlowin/fastmcp) | Framework MCP server |
| [FastAPI](https://github.com/fastapi/fastapi) | REST API |
| [slowapi](https://github.com/laurentS/slowapi) | Rate limiting por IP |
| [curl-cffi](https://github.com/yifeikong/curl-cffi) | HTTP com impersonação TLS Chrome-124 |
| [PyTorch](https://github.com/pytorch/pytorch) | Rede neural CRNN para CAPTCHA |
| [torchvision](https://github.com/pytorch/vision) | Transforms e augmentation de imagem |
| [pypdf](https://github.com/py-pdf/pypdf) | Extração de dados do PDF de certidão |
| [Pillow](https://github.com/python-pillow/Pillow) | Processamento de imagem |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | Carregamento de variáveis do `.env` |

---

## 🗺️ Roadmap

Ideias e melhorias planejadas para versões futuras.

### Escalabilidade
- **Worker distribuído** — arquitetura de fila (Redis + worker nodes) onde cada nó é uma VPS com IP próprio contribuindo com slots de conexão ao TRT3. Escala horizontalmente: 1 worker = 20 slots, 5 workers = 100 slots, IPs diferentes reduzem risco de throttling.
- **Cache de resultados** — CPFs já consultados recentemente retornam resultado armazenado sem nova requisição ao TRT3. Reduz latência e carga no tribunal.

### Multi-usuário
- **Quota de consultas por token** — cada token teria um limite mensal/diário de consultas configurável independentemente do rate limit por IP. Ex: token A = 1.000 consultas/dia, token B = 10.000/dia.
- **Workers por token** — cada token teria um número máximo de workers simultâneos ao TRT3. Ex: token gratuito = 2 workers, token premium = 20 workers. Garante que um único cliente não monopoliza a capacidade do servidor enquanto outros aguardam.

### Cobertura
- **Suporte a outros tribunais** — expandir para TRT1 (RJ), TRT2 (SP) e demais regiões, consolidando resultados em uma única consulta.
- **Consulta à Receita Federal** — validar situação cadastral do CPF diretamente na base da RF.

### Observabilidade
- **Dashboard de uso** — visualizar volume de consultas, taxa de acerto do CAPTCHA e latência média por endpoint.
- **Alerta de bloqueio** — detectar automaticamente quando o TRT3 começa a retornar erros acima do normal e notificar.

---

## ⚖️ Responsabilidade de Uso

Este projeto consulta exclusivamente o sistema público do **TRT3** ([certidao.trt3.jus.br](https://certidao.trt3.jus.br)) — os mesmos dados acessíveis por qualquer pessoa pelo navegador, sem login ou cadastro. As certidões emitidas são documentos públicos por determinação legal.

**Usos adequados:**
- Due diligence em processos de contratação
- Verificação de titularidade em contextos jurídicos ou de compliance
- Integração com agentes AI para automação de processos legítimos

**O projeto não se destina a:**
- Varredura em massa sem finalidade específica
- Coleta de dados para fins não autorizados pela LGPD
- Qualquer uso que viole a legislação brasileira vigente

O código é aberto e auditável. A responsabilidade pelo uso é inteiramente do operador que implanta e utiliza o serviço. Rate limiting está configurado por padrão para desincentivar abuso.

---

## 📄 Licença

[MIT](LICENSE) © 2026 Nícolas Pastorello
