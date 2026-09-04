import re
import time
import sys
import argparse
import threading
from pathlib import Path
from curl_cffi import requests as _requests

_MODEL_PT = Path(__file__).parent / "captcha_model.pt"

try:
    import ddddocr as _ddddocr
    _ocr = _ddddocr.DdddOcr(show_ad=False)
except ImportError:
    _ocr = None

_TRT3_BASE = "https://certidao.trt3.jus.br"
_TRT3_URL = f"{_TRT3_BASE}/certidao/feitosTrabalhistas/aba1.emissao.htm"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

_DATA_DIR = Path(__file__).parent / "data"
_DATA_DIR.mkdir(exist_ok=True)

_PROBE_CPF: str = ""  # definido via --cpf na linha de comando


def _fetch_page(session) -> tuple[str, str, str]:
    resp = session.get(_TRT3_URL, headers=_HEADERS, timeout=30)
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


def _post_form(session, action_url, viewstate, captcha_text):
    data = {
        "form": "form",
        "form:tipoPessoa": "F",
        "form:inputCPF": _PROBE_CPF,
        "form:nomeReceitaCPF": "",
        "form:nomeConsulta": "",
        "form:verifyCaptcha_": captcha_text,
        "form:botaoConsultar": "Consultar",
        "javax.faces.ViewState": viewstate,
    }
    headers = {**_HEADERS, "Content-Type": "application/x-www-form-urlencoded", "Referer": _TRT3_URL}
    return session.post(action_url, data=data, headers=headers, timeout=30)


_CAPTCHA_REJECT = re.compile(
    r"captcha inv[aá]lido|c[oó]digo incorreto|tente novamente|caracteres da imagem",
    re.IGNORECASE,
)

def _captcha_accepted(resp) -> bool:
    content_type = resp.headers.get("Content-Type", "")
    if "application/pdf" in content_type or "octet-stream" in content_type:
        return True
    if _CAPTCHA_REJECT.search(resp.text):
        return False
    return True


def collect_one(session) -> tuple[bytes, str] | None:
    action_url, viewstate, captcha_url = _fetch_page(session)

    if not captcha_url:
        return None

    captcha_resp = session.get(captcha_url, headers=_HEADERS, timeout=15)
    captcha_resp.raise_for_status()
    image_bytes = captcha_resp.content

    if _MODEL_PT.exists():
        from app.captcha.predictor import predict
        captcha_text = predict(image_bytes).strip()
    elif _ocr is not None:
        captcha_text = _ocr.classification(image_bytes).strip().lower()
    else:
        return None
    if not captcha_text:
        return None

    resp = _post_form(session, action_url, viewstate, captcha_text)
    resp.raise_for_status()

    if _captcha_accepted(resp):
        return (image_bytes, captcha_text)

    return None


def save_sample(image_bytes: bytes, label: str) -> None:
    timestamp = int(time.time() * 1000)
    filename = _DATA_DIR / f"{label}_{timestamp}.png"
    filename.write_bytes(image_bytes)


def count_samples() -> int:
    return len(list(_DATA_DIR.glob("*.png")))


def _worker(worker_id: int, target: int, delay: float, state: dict, lock: threading.Lock) -> None:
    session = _requests.Session(impersonate="chrome124")

    while True:
        with lock:
            if state["total_saved"] >= target:
                return

        try:
            result = collect_one(session)

            with lock:
                state["total_attempts"] += 1
                if state["total_saved"] >= target:
                    return

                if result is not None:
                    image_bytes, label = result
                    save_sample(image_bytes, label)
                    state["total_saved"] += 1
                    state["session_saved"] += 1
                    success_rate = (state["session_saved"] / state["total_attempts"] * 100)
                    print(f"[{state['total_saved']}/{target}] '{label}' salvo  (acerto sessao: {success_rate:.1f}%)  [w{worker_id}]", flush=True)
                else:
                    print(f"  tentativa {state['total_attempts']}: captcha errado  [w{worker_id}]", flush=True)

        except Exception as exc:
            print(f"Erro w{worker_id}: {exc} — nova sessao", file=sys.stderr)
            session = _requests.Session(impersonate="chrome124")

        if delay > 0:
            time.sleep(delay)


def run_collector(target: int = 1000, delay: float = 1.0, workers: int = 1, cpf: str = "") -> None:
    global _PROBE_CPF
    _PROBE_CPF = cpf
    state = {
        "total_attempts": 0,
        "session_saved": 0,
        "total_saved": count_samples(),
    }
    lock = threading.Lock()

    if workers == 1:
        _worker(0, target, delay, state, lock)
    else:
        threads = [
            threading.Thread(target=_worker, args=(i, target, delay, state, lock), daemon=True)
            for i in range(workers)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    success_rate = (state["session_saved"] / state["total_attempts"] * 100) if state["total_attempts"] > 0 else 0.0
    print(f"Coleta concluida: {state['total_saved']} amostras salvas ({success_rate:.1f}% de acerto)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpf", type=str, required=True, help="CPF válido usado como probe (ex: 151.879.820-95)")
    parser.add_argument("--target", type=int, default=1000)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    print(f"Coletando {args.target} amostras em {_DATA_DIR} ({args.workers} worker(s))")
    print(f"Ja existem: {count_samples()} amostras")
    run_collector(args.target, args.delay, args.workers, args.cpf)
