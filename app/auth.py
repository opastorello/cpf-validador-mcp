import os

from dotenv import load_dotenv
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

load_dotenv()

_OPEN_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/ui", "/history", "/history/"}

_TOKEN = os.getenv("API_TOKEN", "").strip()


class TokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _TOKEN:
            return await call_next(request)

        if request.url.path in _OPEN_PATHS:
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != _TOKEN:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        return await call_next(request)
