import re
import io
import time
from pypdf import PdfReader
from curl_cffi import requests as _requests
from app.captcha.predictor import predict as _solve_captcha
from app import config as _cfg

_TRT3_BASE = _cfg.TRT3_BASE_URL
_TRT3_URL = f"{_TRT3_BASE}{_cfg.TRT3_FORM_PATH}"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def _formatar(cpf: str) -> str:
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


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


def _extrair_dados_pdf(pdf_bytes: bytes) -> dict:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    result = {}

    tipo_match = re.search(r"CERTID[ÃA]O\s+(NEGATIVA|POSITIVA)", text, re.IGNORECASE)
    if tipo_match:
        result["tipo_certidao"] = tipo_match.group(1).upper()

    result["tem_feitos"] = result.get("tipo_certidao", "NEGATIVA") == "POSITIVA"

    nome_match = re.search(r"contra\s+([A-Z][^,]+),\s*inscrito", text)
    if nome_match:
        result["nome_certidao"] = nome_match.group(1).strip()

    cpf_match = re.search(r"CPF[:\s]+([\d]{3}\.[\d]{3}\.[\d]{3}-[\d]{2})", text)
    if cpf_match:
        result["cpf_certidao"] = cpf_match.group(1)

    validade_match = re.search(r"v[aá]lid[ao][^:]*?[:\s]+([\d]{2}/[\d]{2}/[\d]{4})", text, re.IGNORECASE)
    if validade_match:
        result["valida_ate"] = validade_match.group(1)

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
    cpf_fmt = _formatar(cpf_limpo)
    session = _requests.Session(impersonate="chrome124")

    def _init_session():
        nonlocal session
        session = _requests.Session(impersonate="chrome124")
        return _fetch_page(session)

    try:
        action_url, viewstate, captcha_url = _fetch_page(session)
    except Exception as e:
        return {"cpf": cpf_fmt, "encontrado": None, "erro": f"Erro ao carregar página: {e}"}

    if not captcha_url:
        return {"cpf": cpf_fmt, "encontrado": None, "erro": "CAPTCHA URL não encontrada."}

    for attempt in range(_cfg.MAX_CAPTCHA_ATTEMPTS):
        try:
            captcha_resp = session.get(captcha_url, headers=_HEADERS, timeout=_cfg.CAPTCHA_TIMEOUT)
            captcha_resp.raise_for_status()
            captcha_text = _solve_captcha(captcha_resp.content).strip()

            resp = _post_form(session, action_url, viewstate, cpf_fmt, captcha_text)
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "application/pdf" in content_type or "octet-stream" in content_type:
                dados = _extrair_dados_pdf(resp.content)
                return {"cpf": cpf_fmt, "encontrado": True, **dados}

            sessao_expirada = re.search(
                r"sess[aã]o expirada|viewstate.*inv[aá]lid|expirou|sua sess[aã]o",
                resp.text, re.IGNORECASE,
            )
            if sessao_expirada:
                action_url, viewstate, captcha_url = _fetch_page(session)
                if not captcha_url:
                    return {"cpf": cpf_fmt, "encontrado": None, "erro": "CAPTCHA URL não encontrada após refetch."}
                time.sleep(_cfg.RETRY_DELAY)
                continue

            captcha_invalido = re.search(
                r"captcha inv[aá]lido|c[oó]digo incorreto|tente novamente|caracteres da imagem",
                resp.text, re.IGNORECASE,
            )
            if captcha_invalido:
                time.sleep(_cfg.RETRY_DELAY)
                continue

            result = _parse_html_resultado(cpf_limpo, cpf_fmt, resp)

            if result.get("pdf_url"):
                try:
                    pdf_resp = session.get(result["pdf_url"], headers=_HEADERS, timeout=_cfg.HTTP_TIMEOUT)
                    pdf_resp.raise_for_status()
                    pdf_data = _extrair_dados_pdf(pdf_resp.content)
                    result.update(pdf_data)
                except Exception:
                    pass

            return result

        except Exception:
            try:
                action_url, viewstate, captcha_url = _init_session()
                if not captcha_url:
                    return {"cpf": cpf_fmt, "encontrado": None, "erro": "CAPTCHA URL não encontrada após reconexão."}
            except Exception:
                pass
            time.sleep(_cfg.RETRY_DELAY)
            continue

    return {"cpf": cpf_fmt, "encontrado": None, "erro": f"CAPTCHA não resolvido após {_cfg.MAX_CAPTCHA_ATTEMPTS} tentativas."}


def consultar_trt3(cpf_limpo: str) -> dict:
    return _consultar_trt3_interno(cpf_limpo)


def consultar_trt3_multiplos(cpfs: list[str], nome_filtro: str | None = None, workers: int | None = None) -> dict:
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeout

    n_workers = max(1, min(workers if workers is not None else _cfg.DEFAULT_WORKERS, _cfg.MAX_WORKERS))

    resultados = {}
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(_consultar_trt3_interno, cpf): cpf for cpf in cpfs}
        for future in as_completed(futures):
            cpf = futures[future]
            try:
                resultados[cpf] = future.result(timeout=_cfg.TASK_TIMEOUT)
            except FutureTimeout:
                resultados[cpf] = {"cpf": _formatar(cpf), "encontrado": None, "erro": f"Timeout após {_cfg.TASK_TIMEOUT}s"}
            except Exception as e:
                resultados[cpf] = {"cpf": _formatar(cpf), "encontrado": None, "erro": str(e)}

    if nome_filtro:
        filtro = nome_filtro.lower()
        matches = {
            cpf: r for cpf, r in resultados.items()
            if filtro in (r.get("nome_certidao") or "").lower()
        }
    else:
        matches = {cpf: r for cpf, r in resultados.items() if r.get("encontrado") is True}

    return {"total": len(cpfs), "matches": matches, "resultados": resultados}
