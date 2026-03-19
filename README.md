# cpf-validador-mcp

> MCP server para consulta de feitos trabalhistas no **TRT3 (3ª Região)** com resolução automática de CAPTCHA via rede neural treinada localmente — sem APIs externas, sem serviços pagos.

Expõe as mesmas operações como **MCP tools** (para agentes AI) e **REST API** (para integrações diretas), usando a mesma lógica de negócio internamente.

---

## Por que este projeto existe

O site do TRT3 ([certidao.trt3.jus.br](https://certidao.trt3.jus.br)) exige resolução de CAPTCHA para cada consulta, tornando automação difícil. Este projeto resolve isso com uma CRNN (Convolutional Recurrent Neural Network) treinada especificamente nas imagens do site, atingindo **~99% de acurácia** sem depender de nenhum serviço externo.

---

## MCP Tools

| Tool                        | Descrição                                                                                                                                                      |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `validate_cpf`              | Valida matematicamente um CPF pelo algoritmo módulo-11 dos dígitos verificadores                                                                               |
| `generate_valid_variations` | Dado um CPF possivelmente errado, gera todas as variações matematicamente válidas: recalcula dígitos, troca 1 dígito (posições 0–8), transpõe pares adjacentes |
| `check_feitos_trabalhistas` | Consulta a certidão de feitos trabalhistas no TRT3 — valida o CPF, resolve o CAPTCHA automaticamente e retorna o resultado estruturado                         |
| `find_cpf_by_mask`          | Descobre o CPF completo a partir de uma máscara com `*` nos dígitos desconhecidos (ex: `***.123.456-**`) — gera todas as combinações válidas e consulta o TRT3 em paralelo, filtrando pelo nome na certidão |
| `find_cpf_by_variations`    | Dado um CPF parcial ou com erros (10 ou 11 dígitos), gera todos os candidatos válidos e consulta o TRT3 **em paralelo** — se `nome` for informado, filtra pelo nome na certidão (útil para recuperar CPFs errados) |

---

## REST API

| Método | Rota                         | Descrição                                                                 |
| ------ | ---------------------------- | ------------------------------------------------------------------------- |
| `POST` | `/cpf/validate`              | Valida um CPF                                                             |
| `POST` | `/cpf/variations`            | Gera variações válidas de um CPF                                          |
| `POST` | `/trt3/feitos`               | Consulta feitos trabalhistas no TRT3                                      |
| `POST` | `/trt3/buscar-por-mascara`   | Consulta todos os CPFs que encaixam em uma máscara com `*` em paralelo, filtra por nome |
| `POST` | `/trt3/buscar-por-variacoes` | Consulta todas as variações de um CPF parcial em paralelo, filtra por nome |
| `GET`  | `/health`                    | Health check                                                              |

Documentação interativa disponível em `http://localhost:8000/docs` após iniciar o servidor.

---

## Arquitetura

FastAPI com FastMCP 3.0 montado em `/mcp` (streamable-http). A camada `services/` não tem dependência de framework — a mesma lógica é consumida pelos routers REST e pelo MCP server.

```
app/
├── main.py             # FastAPI — inclui routers, monta mcp.http_app() em /mcp
├── mcp_server.py       # FastMCP("cpf-validador") — 5 tools
├── auth.py             # TokenMiddleware — autenticação opcional via API_TOKEN
├── services/
│   ├── cpf.py          # Validação, variações e geração por máscara (puro Python, sem deps)
│   └── trt3.py         # Web scraping TRT3: curl_cffi + CAPTCHA solver + pypdf
├── routers/
│   ├── cpf.py          # POST /cpf/validate, POST /cpf/variations
│   └── trt3.py         # POST /trt3/feitos, /buscar-por-mascara, /buscar-por-variacoes
└── captcha/
    ├── model.py        # Arquitetura CRNN (CNN + BiLSTM + CTC Loss)
    ├── predictor.py    # Inferência: carrega captcha_model.pt e prediz
    ├── dataset.py      # CaptchaDataset com data augmentation
    ├── train.py        # Loop de treino com early stopping + AMP + registry
    ├── collector.py    # Coleta amostras rotuladas direto do TRT3
    ├── registry.py     # Versionamento de modelos (models/vN/model.pt + meta.json)
    └── models/         # Histórico de versões treinadas
```

### Regras de camada

- `services/` — zero imports de FastAPI ou FastMCP
- `routers/` e `mcp_server.py` — importam apenas de `services/`
- I/O bloqueante em `services/trt3.py` é sempre executado via `run_in_threadpool`

---

## Autenticação

Por padrão o servidor roda sem autenticação. Para proteger todos os endpoints (REST + MCP), defina a variável de ambiente `API_TOKEN`:

```bash
API_TOKEN=meu-token-secreto uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Com o token configurado, todas as requisições (exceto `/health`, `/docs`, `/redoc`) precisam enviar o header:

```
Authorization: Bearer meu-token-secreto
```

**REST:**

```bash
curl -X POST http://localhost:8000/cpf/validate \
  -H "Authorization: Bearer meu-token-secreto" \
  -H "Content-Type: application/json" \
  -d '{"cpf": "529.982.247-25"}'
```

**Claude Desktop / Claude Code:**

```json
{
  "mcpServers": {
    "trt3": {
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer meu-token-secreto"
      }
    }
  }
}
```

**Docker:**

```bash
docker run -p 8000:8000 -e API_TOKEN=meu-token-secreto cpf-validador-mcp
```

---

## Descobrir CPF a partir de uma máscara

Quando você sabe apenas parte dos dígitos do CPF — por exemplo, apenas o miolo — use o endpoint `POST /trt3/buscar-por-mascara` (ou a tool MCP `find_cpf_by_mask`). Substitua os dígitos desconhecidos por `*`:

```bash
curl -X POST http://localhost:8000/trt3/buscar-por-mascara \
  -H "Content-Type: application/json" \
  -d '{"mascara": "***.123.456-**", "nome": "João Silva"}'
```

O servidor:
1. Gera todas as combinações válidas para as posições com `*` (recalculando os dígitos verificadores)
2. Consulta o TRT3 para cada candidato **em paralelo**
3. Retorna apenas os que contêm o nome informado na certidão

Resposta:
```json
{
  "total": 1000,
  "candidatos_gerados": 999,
  "matches": {
    "12312345600": {
      "cpf": "123.123.456-00",
      "encontrado": true,
      "tipo_certidao": "NEGATIVA",
      "tem_feitos": false,
      "nome_certidao": "JOAO SILVA",
      "valida_ate": "18/04/2026"
    }
  }
}
```

**Parâmetros:**

| Campo     | Tipo   | Descrição                                                                                  |
| --------- | ------ | ------------------------------------------------------------------------------------------ |
| `mascara` | string | CPF com `*` nos dígitos desconhecidos — deve ter 11 posições (dígitos + `*`)               |
| `nome`    | string | Parte do nome para filtrar na certidão (case-insensitive, opcional)                        |
| `workers` | int    | Threads paralelas para consultar o TRT3 (padrão: 8)                                       |

> Os dígitos verificadores (posições 10–11) são sempre recalculados, independente do que for passado na máscara.

---

## Recuperar CPF com erros ou dígitos faltando

O endpoint `POST /trt3/buscar-por-variacoes` (e a tool MCP `find_cpf_by_variations`) resolve o problema de CPFs digitados com erros ou dígitos faltando. Ele:

1. Gera todos os candidatos matematicamente válidos a partir do CPF parcial
2. Consulta o TRT3 para cada candidato **em paralelo** (ThreadPoolExecutor)
3. Filtra os resultados pelo nome extraído diretamente da certidão em PDF

```bash
# CPF com 10 dígitos (1 faltando) e 1 dígito errado — informar nome para filtrar
curl -X POST http://localhost:8000/trt3/buscar-por-variacoes \
  -H "Content-Type: application/json" \
  -d '{"cpf_parcial": "5299824725", "nome": "joao", "workers": 8}'
```

Resposta:
```json
{
  "total": 83,
  "candidatos_gerados": 83,
  "matches": {
    "52998224725": {
      "cpf": "529.982.247-25",
      "encontrado": true,
      "tipo_certidao": "NEGATIVA",
      "tem_feitos": false,
      "nome_certidao": "JOAO DA SILVA",
      "valida_ate": "12/04/2026"
    }
  }
}
```

O nome é lido diretamente do PDF emitido pela certidão — o TRT3 consulta a Receita Federal para preencher o nome vinculado ao CPF, tornando esse campo confiável para validação.

**Parâmetros:**

| Campo        | Tipo   | Descrição                                                       |
| ------------ | ------ | --------------------------------------------------------------- |
| `cpf_parcial`| string | CPF com 10 ou 11 dígitos (com ou sem formatação)                |
| `nome`       | string | Parte do nome para filtrar (case-insensitive, opcional)         |
| `workers`    | int    | Threads paralelas para consultar o TRT3 (padrão: 8)            |

---

## Fluxo de consulta TRT3

```
1. GET página          → extrai JSF ViewState + URL do CAPTCHA
2. GET imagem CAPTCHA  → resolve com CRNN local (PyTorch, CPU/GPU)
3. POST formulário     → impersonação Chrome-124 via curl_cffi (bypass TLS fingerprint)
4. Retry até 4×        → em caso de CAPTCHA recusado
5. Parse resultado     → PDF: extrai campos via pypdf regex / HTML: parse direto
```

---

## Modelo de CAPTCHA

O CAPTCHA do TRT3 é resolvido por uma **rede neural própria**, treinada do zero nas imagens reais do site.

### Arquitetura CRNN

```
Input (1×60×160)
    → Conv2D ×4 + BatchNorm + ReLU + MaxPool   (extração de features visuais)
    → BiLSTM ×2 (128 hidden, bidirectional)    (modelagem de sequência)
    → Linear → CTC Loss                         (decode sem segmentação)
Output: string de 5 caracteres [0-9a-z]
```

### Processo de treinamento — bootstrapping em 3 rodadas

O modelo foi construído de forma iterativa, usando cada versão treinada para gerar um dataset mais limpo para a próxima rodada:

| Rodada | Amostras | Rotulador              | Acurácia dos labels | Acurácia do modelo |
| ------ | -------- | ---------------------- | ------------------- | ------------------ |
| 1      | 15.000   | ddddocr (OCR genérico) | ~43%                | **98.70%**         |
| 2      | 20.000   | Modelo R1              | ~96%                | **98.80%**         |
| 3      | 20.000   | Modelo R2              | ~99.3%              | **98.55%**         |

**Total: 55.000 amostras coletadas ao longo do processo.**

A cada rodada os labels ficaram mais limpos, reduzindo o ruído de rotulação e permitindo que o modelo aprendesse os padrões visuais reais. O modelo final (v1) foi treinado sobre as 20k amostras da rodada 3, com labels gerados pelo modelo R2 a 99.3% de acurácia, e convergiu na época 106 de 120 com val_loss=0.0072.

O versionamento de modelos é feito automaticamente pelo `registry.py`. Para consultar o histórico:

```bash
python -m app.captcha.registry
```

### Hiperparâmetros de treino

- **Optimizer:** AdamW
- **LR:** 1e-3 com CosineAnnealingLR
- **Epochs:** 120 (early stopping: para após 20 épocas sem melhora no val_loss)
- **Batch size:** 128
- **AMP:** float16 na GPU via `torch.amp.autocast`
- **Data augmentation:** rotação, shear, translate, color jitter, gaussian blur, random erasing

---

## Instalação

```bash
git clone https://github.com/opastorello/cpf-validador-mcp
cd cpf-validador-mcp
pip install -r requirements.txt
```

## Modelo pré-treinado

O arquivo `app/captcha/captcha_model.pt` não está incluso no repositório. Baixe via [GitHub Releases](https://github.com/opastorello/cpf-validador-mcp/releases) e coloque em `app/captcha/captcha_model.pt`.

Ou treine do zero seguindo as instruções em [Treinar o modelo](#treinar-o-modelo).

O modelo treinado (`app/captcha/captcha_model.pt`) precisa estar presente. Veja a seção [Treinar o modelo](#treinar-o-modelo) se quiser treinar do zero.

## Iniciando o servidor

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- REST docs: `http://localhost:8000/docs`
- MCP endpoint: `http://localhost:8000/mcp`

## Docker

```bash
docker build -t cpf-validador-mcp .
docker run -p 8000:8000 cpf-validador-mcp
```

## Configurar no Claude Desktop / Claude Code

Adicione ao seu `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cpf-validador": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8000/mcp", "--allow-http"]
    }
  }
}
```

Com autenticação:

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

## Treinar o modelo

Para treinar o modelo de CAPTCHA do zero:

**1. Coletar amostras**

```bash
python -m app.captcha.collector --cpf 000.000.000-00 --target 15000 --delay 0 --workers 4
```

Use `--workers N` para coleta paralela (recomendado: 4–8).

**2. Treinar**

```bash
python -m app.captcha.train --epochs 120 --batch 128 --lr 1e-3
```

O melhor modelo (menor `val_loss`) é salvo automaticamente em `app/captcha/captcha_model.pt`.

**3. Bootstrap (opcional — melhora a qualidade dos labels)**

Após treinar, delete os dados e colete novamente com o modelo gerado:

```bash
rm -rf app/captcha/data/
python -m app.captcha.collector --cpf 000.000.000-00 --target 20000 --delay 0 --workers 4
python -m app.captcha.train --epochs 120 --batch 128 --lr 1e-3
```

Repita até a acurácia de coleta estabilizar (geralmente 2–3 rodadas são suficientes).

---

## Dependências principais

| Pacote                                              | Uso                                          |
| --------------------------------------------------- | -------------------------------------------- |
| [FastMCP](https://github.com/jlowin/fastmcp)        | Framework MCP server                         |
| [FastAPI](https://fastapi.tiangolo.com/)            | REST API                                     |
| [curl-cffi](https://github.com/yifeikong/curl-cffi) | HTTP com impersonação TLS Chrome-124         |
| [PyTorch](https://pytorch.org/)                     | Rede neural CRNN para CAPTCHA                |
| [torchvision](https://pytorch.org/vision/)          | Transforms e augmentation de imagem          |
| [pypdf](https://github.com/py-pdf/pypdf)            | Extração de dados do PDF de certidão         |
| [Pillow](https://python-pillow.org/)                | Processamento de imagem                      |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | Carregamento de variáveis do `.env` |
