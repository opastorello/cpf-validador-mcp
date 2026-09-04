import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app import config as _cfg

_TOKEN = _cfg.API_TOKEN
_ENV = _cfg.ENV.lower()

# "/" e "/health" ficam sempre abertos: "/" carrega o gate da UI e "/health" é
# consumido pelo healthcheck do Docker, que não tem como enviar o token.
# Em desenvolvimento /docs, /redoc, /openapi.json e /metrics também ficam abertos.
# /metrics expõe contadores de negócio (volume de consultas, acerto do CAPTCHA):
# em produção só abre com METRICS_PUBLIC=true.
_OPEN_PATHS_ALWAYS = {"/", "/health"}
_OPEN_PATHS_DEV = {"/docs", "/redoc", "/openapi.json", "/metrics"}

_OPEN_PATHS = _OPEN_PATHS_ALWAYS | (_OPEN_PATHS_DEV if _ENV == "development" else set())
if _cfg.METRICS_PUBLIC:
    _OPEN_PATHS = _OPEN_PATHS | {"/metrics"}


class TokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _TOKEN:
            return await call_next(request)

        if request.url.path in _OPEN_PATHS:
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        # Compara em bytes: com str, compare_digest exige ASCII puro dos dois
        # lados e levanta TypeError se o cliente mandar qualquer caractere fora
        # disso — virando 500 no lugar de 401, e um jeito trivial de provocar
        # erro no servidor. Em bytes vale para qualquer entrada e continua
        # sendo comparação de tempo constante.
        if not hmac.compare_digest(auth[7:].encode("utf-8"), _TOKEN.encode("utf-8")):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        return await call_next(request)
