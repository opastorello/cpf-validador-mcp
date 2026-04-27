import hmac
import os

from dotenv import load_dotenv
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

load_dotenv()

_TOKEN = os.getenv("API_TOKEN", "").strip()
_ENV = os.getenv("ENV", "development").strip().lower()

# "/" e "/health" são sempre acessíveis sem token (qualquer ambiente)
# Em desenvolvimento, /docs, /redoc, /openapi.json também ficam abertos
_OPEN_PATHS_ALWAYS = {"/", "/health", "/metrics"}
_OPEN_PATHS_DEV = {"/docs", "/redoc", "/openapi.json"}

_OPEN_PATHS = _OPEN_PATHS_ALWAYS | (_OPEN_PATHS_DEV if _ENV == "development" else set())


class TokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _TOKEN:
            return await call_next(request)

        if request.url.path in _OPEN_PATHS:
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        if not hmac.compare_digest(auth[7:], _TOKEN):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        return await call_next(request)
