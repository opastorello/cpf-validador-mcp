import os
from dotenv import load_dotenv

load_dotenv()

def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default

def _float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default

def _str(key: str, default: str) -> str:
    return os.getenv(key, default).strip()

def _bool(key: str, default: bool) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes", "on")

# ── Ambiente ────────────────────────────────────────────────
ENV                     = _str("ENV", "development")
IS_PRODUCTION           = ENV == "production"

# ── Auth ────────────────────────────────────────────────────
API_TOKEN               = _str("API_TOKEN", "")

# ── Fonte de consulta ────────────────────────────────────────
# Fonte usada para descobrir a titularidade do CPF. Ver app/services/sources/
SOURCE                  = _str("SOURCE", "trt3").lower()

# ── TRT3 scraping ───────────────────────────────────────────
TRT3_BASE_URL           = _str("TRT3_BASE_URL", "https://certidao.trt3.jus.br")
TRT3_FORM_PATH          = _str("TRT3_FORM_PATH", "/certidao/feitosTrabalhistas/aba1.emissao.htm")
HTTP_TIMEOUT            = _float("HTTP_TIMEOUT", 30.0)
CAPTCHA_TIMEOUT         = _float("CAPTCHA_TIMEOUT", 15.0)
MAX_CAPTCHA_ATTEMPTS    = _int("MAX_CAPTCHA_ATTEMPTS", 20)
RETRY_DELAY             = _float("RETRY_DELAY", 1.0)

# ── TCU (certidoes.apps.tcu.gov.br) ─────────────────────────
TCU_BASE_URL            = _str("TCU_BASE_URL", "https://certidoes.apps.tcu.gov.br")
# Teto da busca do proof-of-work; na prática o contador fica abaixo de 5.000
TCU_POW_MAX_COUNTER     = _int("TCU_POW_MAX_COUNTER", 200_000)
TCU_MAX_ATTEMPTS        = _int("TCU_MAX_ATTEMPTS", 3)

# ── Workers / concorrência ───────────────────────────────────
DEFAULT_WORKERS         = _int("DEFAULT_WORKERS", 8)
MAX_WORKERS             = _int("MAX_WORKERS", 20)
TASK_TIMEOUT            = _float("TASK_TIMEOUT", 60.0)

# ── CPF / máscara ────────────────────────────────────────────
MAX_WILDCARDS_IN_MASK   = _int("MAX_WILDCARDS_IN_MASK", 5)

# ── Rate limits (formato slowapi: "N/minute" ou "N/second") ──
RATE_LIMIT_FEITOS       = _str("RATE_LIMIT_FEITOS", "10/minute")
RATE_LIMIT_MULTIPLOS    = _str("RATE_LIMIT_MULTIPLOS", "5/minute")
RATE_LIMIT_MASK         = _str("RATE_LIMIT_MASK", "3/minute")
RATE_LIMIT_VARIACOES    = _str("RATE_LIMIT_VARIACOES", "3/minute")

# ── Observabilidade ──────────────────────────────────────────
# DEBUG mostra cada tentativa de CAPTCHA; INFO mostra só o resultado da consulta
LOG_LEVEL               = _str("LOG_LEVEL", "INFO").upper()
# /metrics é público em development; em production exige token salvo se true
METRICS_PUBLIC          = _bool("METRICS_PUBLIC", False)

# ── Captcha model ────────────────────────────────────────────
CAPTCHA_MODEL_PATH      = _str("CAPTCHA_MODEL_PATH", "")   # vazio = path padrão relativo

