import re
import io
import time
import logging
import threading
from pypdf import PdfReader
from curl_cffi import requests as _requests
from app.captcha.predictor import predict as _solve_captcha
from app.services.cpf import formatar
from app.services.sources.base import Fonte, mascarar_cpf
from app import config as _cfg
from app import metrics as _m

log = logging.getLogger("trt3")

_TRT3_BASE = _cfg.TRT3_BASE_URL
_TRT3_URL = f"{_TRT3_BASE}{_cfg.TRT3_FORM_PATH}"

# Limita conexões simultâneas ao TRT3 independente de quantos usuários estão consultando
_TRT3_SEMAPHORE = threading.Semaphore(_cfg.MAX_WORKERS)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def _fetch_page(session) -> tuple[str, str, str]:
    resp = session.get(_TRT3_URL, headers=_HEADERS, timeout=_cfg.HTTP_TIMEOUT)
    resp.raise_for_status()
    html = resp.text

    action_match = re.search(r'<form[^>]+id="form"[^>]+action="([^"]+)"', html)
    if not action_match:
        action_match = re.search(r'<form[^>]+action="([^"]+)"[^>]+id="form"', html)
    action_url = action_match.group(1) if action_match else _TRT3_URL
    if action_url.startswith("/"):
        action_url = _TRT3_BASE + action_url

    viewstate_match = re.search(r'name="javax\.faces\.ViewState"[^>]+value="([^"]+)"', html)
    viewstate = viewstate_match.group(1) if viewstate_match else ""

    captcha_match = re.search(r'(/certidao/seam/resource/captcha[^"\']*)', html)
    captcha_url = (_TRT3_BASE + captcha_match.group(1)) if captcha_match else ""

    return action_url, viewstate, captcha_url


def _post_form(session, action_url, viewstate, cpf_fmt, captcha_text):
    data = {
        "form": "form",
        "form:tipoPessoa": "F",
        "form:inputCPF": cpf_fmt,
        "form:nomeReceitaCPF": "",
        "form:nomeConsulta": "",
        "form:verifyCaptcha_": captcha_text,
        "form:botaoConsultar": "Consultar",
        "javax.faces.ViewState": viewstate,
    }
    headers = {**_HEADERS, "Content-Type": "application/x-www-form-urlencoded", "Referer": _TRT3_URL}
    return session.post(action_url, data=data, headers=headers, timeout=_cfg.HTTP_TIMEOUT)


def _texto_do_pdf(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extrair_dados_pdf(pdf_bytes: bytes) -> dict:
    return _parse_texto_certidao(_texto_do_pdf(pdf_bytes))


def _parse_texto_certidao(text: str) -> dict:
    """Extrai os campos da certidão a partir do texto já tirado do PDF.

    Separado de `_texto_do_pdf` para poder ser testado contra fixtures de
    texto, sem versionar PDF de certidão real — que é dado pessoal.
    """
    result = {}

    tipo_match = re.search(r"CERTID[ÃA]O\s+(NEGATIVA|POSITIVA)", text, re.IGNORECASE)
    if tipo_match:
        result["tipo_certidao"] = tipo_match.group(1).upper()

    result["tem_feitos"] = result.get("tipo_certidao", "NEGATIVA") == "POSITIVA"

    nome_match = re.search(r"contra\s+([A-Z][^,]+),\s*inscrito", text)
    if nome_match:
        result["nome_certidao"] = nome_match.group(1).strip()

    # O texto real é "...no CPF sob o nº 111.444.777-35." — o padrão antigo
    # exigia o CPF logo após "CPF" e por isso nunca casava.
    cpf_match = re.search(r"CPF[^\d]{0,30}([\d]{3}\.[\d]{3}\.[\d]{3}-[\d]{2})", text)
    if cpf_match:
        result["cpf_certidao"] = cpf_match.group(1)

    validade_match = re.search(r"v[aá]lid[ao][^:]*?[:\s]+([\d]{2}/[\d]{2}/[\d]{4})", text, re.IGNORECASE)
    if validade_match:
        result["valida_ate"] = validade_match.group(1)

    # TRT3 format: "Certidão n.\n<auth_code>\n<number>/<year>"
    numero_match = re.search(
        r"Certid[ãa]o\s+n[.º°]\s*[\r\n]+\S+[\r\n]+([\d]+\/[\d]{4})",
        text, re.IGNORECASE,
    )
    if not numero_match:
        numero_match = re.search(r"N[úu]mero[:\s]+([\w\-\/\.]+)", text, re.IGNORECASE)
    if numero_match:
        result["numero_certidao"] = numero_match.group(1).strip()

    return result


def _parse_html_resultado(cpf_limpo, cpf_fmt, resp) -> dict:
    html = resp.text

    pdf_match = re.search(r'href="([^"]*\.pdf[^"]*)"', html, re.IGNORECASE)
    if not pdf_match:
        pdf_match = re.search(r'((?:/certidao)?[^"\']*certidao[^"\']*\.pdf[^"\']*)', html, re.IGNORECASE)

    if pdf_match:
        pdf_path = pdf_match.group(1)
        pdf_url = pdf_path if pdf_path.startswith("http") else _TRT3_BASE + pdf_path
        return {"cpf": cpf_fmt, "encontrado": True, "pdf_url": pdf_url}

    nao_encontrado_patterns = [
        r"n[ãa]o foram encontrados",
        r"nenhum feito",
        r"certid[ãa]o negativa",
        r"n[ãa]o h[aá] feitos",
    ]
    for pattern in nao_encontrado_patterns:
        if re.search(pattern, html, re.IGNORECASE):
            return {"cpf": cpf_fmt, "encontrado": False, "mensagem": "Nenhum feito trabalhista encontrado."}

    return {"cpf": cpf_fmt, "encontrado": None, "mensagem": "Resultado indeterminado."}


def _consultar_trt3_interno(cpf_limpo: str) -> dict:
    cpf_fmt = formatar(cpf_limpo)
    _m.trt3_concurrent_queries.inc()
    try:
        with _TRT3_SEMAPHORE:
            return _consultar_trt3_com_sessao(cpf_limpo, cpf_fmt)
    finally:
        _m.trt3_concurrent_queries.dec()


def _consultar_trt3_com_sessao(cpf_limpo: str, cpf_fmt: str) -> dict:
    session = _requests.Session(impersonate="chrome124")
    attempts = 0
    cpf_log = mascarar_cpf(cpf_fmt)

    t_query_start = time.time()
    log.debug("consulta iniciada cpf=%s", cpf_log)

    for attempt in range(_cfg.MAX_CAPTCHA_ATTEMPTS):
        try:
            action_url, viewstate, captcha_url = _fetch_page(session)

            if not captcha_url:
                _m.trt3_queries_total.labels(result="error").inc()
                _m.trt3_captcha_retries_per_query.observe(attempts)
                _m.trt3_query_duration_seconds.observe(time.time() - t_query_start)
                log.error("página do TRT3 sem URL de CAPTCHA (layout mudou?) cpf=%s", cpf_log)
                return {"cpf": cpf_fmt, "encontrado": None, "erro": "CAPTCHA URL não encontrada."}

            _m.trt3_captcha_attempts_total.inc()
            attempts += 1

            t_captcha = time.time()
            try:
                captcha_resp = session.get(captcha_url, headers=_HEADERS, timeout=_cfg.CAPTCHA_TIMEOUT)
                captcha_resp.raise_for_status()
            except Exception as exc:
                err_type = "timeout" if "timeout" in str(exc).lower() else "connection"
                _m.trt3_http_errors_total.labels(type=err_type).inc()
                raise
            captcha_text = _solve_captcha(captcha_resp.content).strip()
            dt_captcha = time.time() - t_captcha
            _m.trt3_captcha_duration_seconds.observe(dt_captcha)
            log.debug("tentativa %d/%d cpf=%s: CRNN leu %r em %.2fs",
                      attempt + 1, _cfg.MAX_CAPTCHA_ATTEMPTS, cpf_log, captcha_text, dt_captcha)

            try:
                resp = _post_form(session, action_url, viewstate, cpf_fmt, captcha_text)
                resp.raise_for_status()
            except Exception as exc:
                err_type = "timeout" if "timeout" in str(exc).lower() else "http_status"
                _m.trt3_http_errors_total.labels(type=err_type).inc()
                raise

            content_type = resp.headers.get("Content-Type", "")
            if "application/pdf" in content_type or "octet-stream" in content_type:
                _m.trt3_captcha_result_total.labels(result="success").inc()
                try:
                    dados = _extrair_dados_pdf(resp.content)
                    _m.trt3_pdf_parsed_total.labels(result="success").inc()
                except Exception as exc:
                    _m.trt3_pdf_parsed_total.labels(result="error").inc()
                    log.warning("PDF recebido mas ilegível cpf=%s: %s: %s",
                                cpf_log, type(exc).__name__, exc)
                    dados = {}
                _m.trt3_captcha_retries_per_query.observe(attempts)
                _m.trt3_queries_total.labels(result="found").inc()
                dt = time.time() - t_query_start
                _m.trt3_query_duration_seconds.observe(dt)
                log.info("certidão obtida cpf=%s tipo=%s tentativas=%d em %.1fs",
                         cpf_log, dados.get("tipo_certidao", "?"), attempts, dt)
                return {"cpf": cpf_fmt, "encontrado": True, **dados}

            # "CPF/CNPJ não encontrado na Receita Federal": o TRT3 devolve o
            # formulário de volta, exatamente como faz quando o CAPTCHA é
            # recusado. Precisa vir ANTES da checagem de captcha, senão a
            # resposta cai no retry e queima todas as tentativas — numa busca
            # por máscara, onde a maioria dos candidatos não é cadastrada, isso
            # multiplicava por 20 as requisições ao tribunal.
            if re.search(r"n[ãa]o encontrado na Receita Federal", resp.text, re.IGNORECASE):
                _m.trt3_captcha_result_total.labels(result="success").inc()
                _m.trt3_captcha_retries_per_query.observe(attempts)
                _m.trt3_queries_total.labels(result="not_registered").inc()
                dt = time.time() - t_query_start
                _m.trt3_query_duration_seconds.observe(dt)
                log.info("CPF não cadastrado na Receita Federal cpf=%s tentativas=%d em %.1fs",
                         cpf_log, attempts, dt)
                return {
                    "cpf": cpf_fmt,
                    "encontrado": False,
                    "cpf_inexistente": True,
                    "mensagem": "CPF não encontrado na Receita Federal.",
                }

            # CAPTCHA errado: TRT3 devolve o formulário — próxima iteração busca página fresca
            captcha_invalido = re.search(
                r"captcha inv[aá]lido|c[oó]digo incorreto|tente novamente|caracteres da imagem|caracteres da figura",
                resp.text, re.IGNORECASE,
            ) or "form:verifyCaptcha_" in resp.text
            if captcha_invalido:
                _m.trt3_captcha_result_total.labels(result="wrong").inc()
                _m.trt3_session_resets_total.labels(reason="wrong_captcha").inc()
                log.debug("captcha %r rejeitado (tentativa %d/%d) cpf=%s — nova sessão",
                          captcha_text, attempt + 1, _cfg.MAX_CAPTCHA_ATTEMPTS, cpf_log)
                session = _requests.Session(impersonate="chrome124")
                time.sleep(_cfg.RETRY_DELAY)
                continue

            _m.trt3_captcha_result_total.labels(result="success").inc()
            result = _parse_html_resultado(cpf_limpo, cpf_fmt, resp)

            if result.get("pdf_url"):
                try:
                    pdf_resp = session.get(result["pdf_url"], headers=_HEADERS, timeout=_cfg.HTTP_TIMEOUT)
                    pdf_resp.raise_for_status()
                    pdf_data = _extrair_dados_pdf(pdf_resp.content)
                    result.update(pdf_data)
                    _m.trt3_pdf_parsed_total.labels(result="success").inc()
                except Exception as exc:
                    _m.trt3_pdf_parsed_total.labels(result="error").inc()
                    log.warning("falha ao baixar/ler o PDF da certidão cpf=%s: %s: %s",
                                cpf_log, type(exc).__name__, exc)

            _m.trt3_captcha_retries_per_query.observe(attempts)
            found = result.get("encontrado")
            label = "found" if found is True else "not_found" if found is False else "indeterminate"
            _m.trt3_queries_total.labels(result=label).inc()
            dt = time.time() - t_query_start
            _m.trt3_query_duration_seconds.observe(dt)
            if found is True:
                log.info("certidão obtida cpf=%s tentativas=%d em %.1fs", cpf_log, attempts, dt)
            elif found is False:
                log.debug("sem feitos cpf=%s tentativas=%d em %.1fs", cpf_log, attempts, dt)
            else:
                log.warning("resposta do TRT3 não reconhecida cpf=%s em %.1fs", cpf_log, dt)
            return result

        except Exception as exc:
            _m.trt3_captcha_result_total.labels(result="error").inc()
            _m.trt3_session_resets_total.labels(reason="exception").inc()
            log.warning("tentativa %d/%d falhou cpf=%s: %s: %s",
                        attempt + 1, _cfg.MAX_CAPTCHA_ATTEMPTS, cpf_log, type(exc).__name__, exc)
            session = _requests.Session(impersonate="chrome124")
            time.sleep(_cfg.RETRY_DELAY)
            continue

    _m.trt3_captcha_retries_per_query.observe(attempts)
    _m.trt3_queries_total.labels(result="error").inc()
    dt = time.time() - t_query_start
    _m.trt3_query_duration_seconds.observe(dt)
    log.error("desisti de cpf=%s após %d tentativas de CAPTCHA (%.1fs)",
              cpf_log, _cfg.MAX_CAPTCHA_ATTEMPTS, dt)
    return {"cpf": cpf_fmt, "encontrado": None, "erro": f"CAPTCHA não resolvido após {_cfg.MAX_CAPTCHA_ATTEMPTS} tentativas."}


class TRT3(Fonte):
    """Certidão de feitos trabalhistas do TRT da 3ª Região (Minas Gerais).

    Resolve o CAPTCHA com a CRNN local e extrai nome, tipo de certidão e
    validade do PDF devolvido.
    """

    nome = "trt3"
    rotulo = "TRT 3ª Região (certidao.trt3.jus.br)"

    def consultar(self, cpf_limpo: str) -> dict:
        return _consultar_trt3_interno(cpf_limpo)
