from fastapi import FastAPI
from app.routers import cpf, trt3, ui, history
from app.mcp_server import mcp
from app.auth import TokenMiddleware

# FastMCP — endpoint will live at /mcp (no sub-mount, avoids 307 redirect)
_mcp_app = mcp.http_app(path="/mcp")

app = FastAPI(
    title="CPF Validador",
    description="Validação de CPF e consulta de feitos trabalhistas no TRT3",
    version="2.0.0",
    lifespan=_mcp_app.lifespan,
)

app.add_middleware(TokenMiddleware)

# REST routers — all defined before mount so they aren't swallowed by the "/" catch-all
@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}

app.include_router(ui.router)
app.include_router(history.router)
app.include_router(cpf.router)
app.include_router(trt3.router)

# Mount FastMCP last — catch-all at "/"
app.mount("/", _mcp_app)
