"""Certidão de Contas Julgadas Irregulares do TCU (certidoes.apps.tcu.gov.br).

O CAPTCHA aqui é **Altcha**, um proof-of-work: em vez de ler uma imagem, o
cliente recebe um desafio e procura um contador cujo PBKDF2 comece com um
prefixo dado. Custa CPU, não visão computacional — nada do modelo CRNN do TRT3
se aplica. É o exemplo de que cada fonte resolve o seu CAPTCHA do seu jeito.

Fluxo de uma consulta:

1. ``GET /api/publico/captcha`` devolve o desafio (nonce, salt, cost, keyPrefix)
2. resolve o proof-of-work localmente (via altcha-solver), procurando o contador
3. ``POST .../pessoa-fisica`` com ``{cpf, nome, captcha}``, onde ``captcha`` é o
   desafio + a solução em Base64

O desafio vale ~90s e é de uso único, então não dá para pré-computar em lote:
cada consulta pede o seu.
"""
import logging
import threading
import time

from altcha_solver import AltchaSolver
from curl_cffi import requests as _requests

from app import config as _cfg
from app import metrics as _m
from app.services.cpf import formatar
from app.services.sources.base import MSG_CPF_INEXISTENTE, Fonte, mascarar_cpf

log = logging.getLogger("tcu")

_TCU_BASE = _cfg.TCU_BASE_URL
_URL_CAPTCHA = f"{_TCU_BASE}/api/publico/captcha"
_URL_CONSULTA = f"{_TCU_BASE}/api/publico/certidoes/contas-julgadas-irregulares/pessoa-fisica"
_REFERER = f"{_TCU_BASE}/emitir-certidao-contas-julgadas-irregulares"

# O proof-of-work é resolvido pela altcha-solver, que cobre os 8 algoritmos do
# Altcha — a nossa implementação anterior só fazia PBKDF2/SHA-256, que é o que o
# TCU usa hoje. Se o tribunal trocar o algoritmo, a troca é da biblioteca.
_SOLVER = AltchaSolver(max_iterations=_cfg.TCU_POW_MAX_COUNTER)

# Limita conexões simultâneas ao TCU, como o TRT3 faz com as dele
_TCU_SEMAPHORE = threading.Semaphore(_cfg.MAX_WORKERS)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/json",
    "Referer": _REFERER,
    "Origin": _TCU_BASE,
}

# Mensagem do TCU quando o CPF não existe na base da Receita
_NAO_LOCALIZADO = "não localizado"


def _obter_desafio(session) -> dict:
    resp = session.get(_URL_CAPTCHA, headers=_HEADERS, timeout=_cfg.HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _parse_resposta(cpf_fmt: str, status: int, corpo: dict) -> dict:
    """Traduz a resposta do TCU para o contrato de `base.Fonte`."""
    dados = corpo.get("dadosCertidao")
    if dados:
        negativa = dados.get("seCertidaoNegativa")
        return {
            "cpf": cpf_fmt,
            "encontrado": True,
            "nome_certidao": dados.get("nome"),
            "tipo_certidao": dados.get("modeloCertidao"),
            "tem_registro": negativa is False,
            "cpf_certidao": dados.get("cpfCnpj"),
            "valida_ate": dados.get("dataValidade"),
            "numero_certidao": dados.get("codigoControle"),
        }

    # O TCU devolve 412 com a lista de violações; a primeira já explica o caso
    violacoes = corpo.get("violacoes") or []
    mensagem = (violacoes[0].get("mensagem") if violacoes else "") or ""

    if _NAO_LOCALIZADO in mensagem.lower():
        # CPF válido no cálculo que não existe na base — resposta, não erro.
        # A frase do TCU ("...na base da Receita Federal disponível no TCU") é
        # longa e específica demais: o usuário vê a mensagem padrão.
        return {
            "cpf": cpf_fmt,
            "encontrado": False,
            "cpf_inexistente": True,
            "mensagem": MSG_CPF_INEXISTENTE,
        }

    return {
        "cpf": cpf_fmt,
        "encontrado": None,
        "erro": mensagem or f"Resposta inesperada do TCU (HTTP {status}).",
    }


def _consultar_tcu_interno(cpf_limpo: str) -> dict:
    cpf_fmt = formatar(cpf_limpo)
    _m.tcu_concurrent_queries.inc()
    try:
        with _TCU_SEMAPHORE:
            return _consultar_com_sessao(cpf_limpo, cpf_fmt)
    finally:
        _m.tcu_concurrent_queries.dec()


def _consultar_com_sessao(cpf_limpo: str, cpf_fmt: str) -> dict:
    cpf_log = mascarar_cpf(cpf_fmt)
    session = _requests.Session(impersonate="chrome124")
    log.debug("consulta iniciada cpf=%s", cpf_log)

    for tentativa in range(_cfg.TCU_MAX_ATTEMPTS):
        try:
            desafio = _obter_desafio(session)

            t_pow = time.time()
            solucao = _SOLVER.solve(desafio)
            dt_pow = time.time() - t_pow
            _m.tcu_pow_duration_seconds.observe(dt_pow)
            _m.tcu_pow_counter.observe(solucao["counter"])
            log.debug("tentativa %d/%d cpf=%s: PoW counter=%d em %.1fs",
                      tentativa + 1, _cfg.TCU_MAX_ATTEMPTS, cpf_log,
                      solucao["counter"], dt_pow)

            resp = session.post(
                _URL_CONSULTA,
                headers=_HEADERS,
                json={"cpf": cpf_limpo, "nome": "",
                      "captcha": _SOLVER.build_payload(desafio, solucao)},
                timeout=_cfg.HTTP_TIMEOUT,
            )
            try:
                corpo = resp.json()
            except Exception:
                corpo = {}

            resultado = _parse_resposta(cpf_fmt, resp.status_code, corpo)

            if resultado.get("encontrado") is True:
                log.info("certidão obtida cpf=%s tipo=%s tentativas=%d",
                         cpf_log, resultado.get("tipo_certidao"), tentativa + 1)
            elif resultado.get("cpf_inexistente"):
                log.info("CPF não localizado na base do TCU cpf=%s", cpf_log)
            else:
                # Desafio expirado ou recusado: vale tentar de novo com outro
                log.warning("resposta não reconhecida cpf=%s (HTTP %d): %s",
                            cpf_log, resp.status_code, resultado.get("erro"))
                if tentativa + 1 < _cfg.TCU_MAX_ATTEMPTS:
                    session = _requests.Session(impersonate="chrome124")
                    time.sleep(_cfg.RETRY_DELAY)
                    continue
            return resultado

        except Exception as exc:
            _m.tcu_http_errors_total.labels(type=type(exc).__name__).inc()
            log.warning("tentativa %d/%d falhou cpf=%s: %s: %s",
                        tentativa + 1, _cfg.TCU_MAX_ATTEMPTS, cpf_log,
                        type(exc).__name__, exc)
            session = _requests.Session(impersonate="chrome124")
            time.sleep(_cfg.RETRY_DELAY)

    log.error("desisti de cpf=%s após %d tentativas", cpf_log, _cfg.TCU_MAX_ATTEMPTS)
    return {
        "cpf": cpf_fmt,
        "encontrado": None,
        "erro": f"TCU não respondeu após {_cfg.TCU_MAX_ATTEMPTS} tentativas.",
    }


class TCU(Fonte):
    """Certidão de Contas Julgadas Irregulares do Tribunal de Contas da União.

    Cobre todo o país, ao contrário do TRT3, que é só Minas Gerais.
    """

    nome = "tcu"
    rotulo = "TCU — Contas Julgadas Irregulares (certidoes.apps.tcu.gov.br)"
    usa_captcha = True   # Altcha (proof-of-work), não imagem

    def consultar(self, cpf_limpo: str) -> dict:
        return _consultar_tcu_interno(cpf_limpo)
