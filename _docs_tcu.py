import io


def sub(path, pairs):
    s = io.open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, path + ': NAO ACHEI -> ' + old[:70]
        s = s.replace(old, new, 1)
    io.open(path, 'w', encoding='utf-8').write(s)
    print('ok:', path)


sub('README.md', [
    # tabela de fontes
    ('''| `SOURCE` | Fonte | Consulta rede? | CAPTCHA? |
| -------- | ----- | :------------: | :------: |
| `trt3` *(padrão)* | TRT 3ª Região | sim | sim, CRNN local |
| `exemplo` | Dados fictícios | não | não |''',
     '''| `SOURCE` | Fonte | Abrangência | CAPTCHA |
| -------- | ----- | ----------- | ------- |
| `trt3` *(padrão)* | TRT 3ª Região — feitos trabalhistas | Minas Gerais | imagem, resolvida por CRNN local |
| `tcu` | TCU — contas julgadas irregulares | Nacional | Altcha (proof-of-work) |
| `exemplo` | Dados fictícios, não consulta nada | — | nenhum |

As duas fontes reais não se parecem em nada por dentro, e é essa a prova de que a camada
funciona: o TRT3 é um formulário JSF com `ViewState`, CAPTCHA de imagem e resposta em PDF;
o TCU é uma API JSON cujo CAPTCHA é um **proof-of-work** — o cliente procura um contador
cujo `PBKDF2-HMAC-SHA256` comece com um prefixo dado, gastando CPU em vez de visão
computacional. Nenhum router, tool MCP ou a lógica de máscara precisou mudar para a
segunda entrar.'''),

    # variáveis de ambiente
    ('| `SOURCE` | `trt3` | Fonte consultada: `trt3` (real) ou `exemplo` (fictícia, não consulta nada) |',
     '''| `SOURCE` | `trt3` | Fonte consultada: `trt3`, `tcu` ou `exemplo` |
| `TCU_BASE_URL` | `https://certidoes.apps.tcu.gov.br` | Base da API do TCU |
| `TCU_POW_MAX_COUNTER` | `200000` | Teto da busca do proof-of-work (na prática o contador fica abaixo de 5.000) |
| `TCU_MAX_ATTEMPTS` | `3` | Tentativas por consulta ao TCU (o desafio vale ~90s e é de uso único) |'''),

    # árvore
    ('''│       ├── trt3.py       # TRT3: curl_cffi + CAPTCHA solver + pypdf
│       └── exemplo.py    # Modelo para novas fontes (fictícia, sem rede)''',
     '''│       ├── trt3.py       # TRT3: curl_cffi + CAPTCHA de imagem (CRNN) + pypdf
│       ├── tcu.py        # TCU: API JSON + CAPTCHA Altcha (proof-of-work)
│       └── exemplo.py    # Modelo para novas fontes (fictícia, sem rede)'''),
])

sub('CLAUDE.md', [
    ('''| `SOURCE` | Fonte |
|----------|-------|
| `trt3` (padrão) | TRT 3ª Região — scraping real com CAPTCHA |
| `exemplo` | Dados fictícios, sem rede e sem CAPTCHA — modelo para novas fontes |''',
     '''| `SOURCE` | Fonte | Como consulta |
|----------|-------|---------------|
| `trt3` (padrão) | TRT 3ª Região (MG) | formulário JSF + CAPTCHA de imagem (CRNN) + PDF |
| `tcu` | TCU, nacional | API JSON + CAPTCHA Altcha (proof-of-work PBKDF2) |
| `exemplo` | Fictícia | nada — modelo para novas fontes |'''),

    ('''│       ├── trt3.py     # TRT3: curl_cffi + CAPTCHA CRNN + pypdf
│       └── exemplo.py  # Modelo para novas fontes — fictícia, sem rede e sem CAPTCHA''',
     '''│       ├── trt3.py     # TRT3: curl_cffi + CAPTCHA CRNN + pypdf
│       ├── tcu.py      # TCU: API JSON + Altcha (PoW PBKDF2), sem pypdf
│       └── exemplo.py  # Modelo para novas fontes — fictícia, sem rede e sem CAPTCHA'''),

    ('''- `trt3_*` — CAPTCHA, PDF, resets de sessão e erros HTTP; não existem para uma
  fonte sem CAPTCHA''',
     '''- `trt3_*` — CAPTCHA de imagem, PDF, resets de sessão e erros HTTP
- `tcu_*` — duração e contador do proof-of-work, concorrência e erros HTTP'''),
])
