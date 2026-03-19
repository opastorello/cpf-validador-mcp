from fastapi import FastAPI
from app.routers import cpf, trt3
from app.mcp_server import mcp
from app.auth import TokenMiddleware

# FastMCP 3.0 requires its lifespan to be wired into the parent app
_mcp_app = mcp.http_app(path="/")

app = FastAPI(
    title="CPF Validador",
    description="Validação de CPF e consulta de feitos trabalhistas no TRT3",
    version="2.0.0",
    lifespan=_mcp_app.lifespan,
)

app.add_middleware(TokenMiddleware)

# REST routers
app.include_router(cpf.router)
app.include_router(trt3.router)

# Mount FastMCP as ASGI sub-application at /mcp
app.mount("/mcp", _mcp_app)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
