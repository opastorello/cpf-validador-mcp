"""
Testes da API REST — todos os chamados ao TRT3 são mockados.
"""
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from contextlib import asynccontextmanager
    import app.auth as _auth
    _auth._TOKEN = ""  # garante que o client de teste roda sem autenticação
    from app.main import app

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    app.router.lifespan_context = _noop_lifespan
    return TestClient(app, raise_server_exceptions=True)


MOCK_FEITOS = {
    "cpf": "11144477735",
    "encontrado": False,
    "processos": [],
}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /cpf/validate
# ---------------------------------------------------------------------------

def test_cpf_validate_valido(client):
    r = client.post("/cpf/validate", json={"cpf": "111.444.777-35"})
    assert r.status_code == 200
    data = r.json()
    assert data["cpf_numeros"] == "11144477735"
    assert data["valido"] is True


def test_cpf_validate_invalido(client):
    r = client.post("/cpf/validate", json={"cpf": "111.111.111-11"})
    assert r.status_code == 422


def test_cpf_validate_payload_invalido(client):
    r = client.post("/cpf/validate", json={})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /cpf/variations
# ---------------------------------------------------------------------------

def test_cpf_variations(client):
    r = client.post("/cpf/variations", json={"cpf": "111.444.777-35"})
    assert r.status_code == 200
    data = r.json()
    assert "variations" in data
    assert isinstance(data["variations"], list)


# ---------------------------------------------------------------------------
# POST /trt3/feitos
# ---------------------------------------------------------------------------

def test_trt3_feitos_cpf_invalido(client):
    r = client.post("/trt3/feitos", json={"cpf": "111.111.111-11"})
    assert r.status_code == 422


def test_trt3_feitos_cpf_curto(client):
    r = client.post("/trt3/feitos", json={"cpf": "123"})
    assert r.status_code == 422


def test_trt3_feitos_sucesso(client):
    with patch("app.routers.trt3.consultar", return_value=MOCK_FEITOS):
        r = client.post("/trt3/feitos", json={"cpf": "111.444.777-35"})
    assert r.status_code == 200
    assert r.json()["cpf"] == "11144477735"


def test_trt3_feitos_payload_invalido(client):
    r = client.post("/trt3/feitos", json={})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------

def test_auth_sem_api_token_configurado(client):
    """Sem API_TOKEN no ambiente — todas as rotas são livres."""
    r = client.get("/health")
    assert r.status_code == 200

    r = client.post("/cpf/validate", json={"cpf": "111.444.777-35"})
    assert r.status_code == 200


def test_auth_com_api_token(monkeypatch):
    """Com API_TOKEN definido — exige Bearer token correto."""
    import app.auth as _auth
    monkeypatch.setattr(_auth, "_TOKEN", "test-secret")
    # simula ENV=production: só "/" e "/health" abertos
    monkeypatch.setattr(_auth, "_OPEN_PATHS", {"/", "/health"})

    from app.auth import TokenMiddleware
    from app.routers import cpf

    test_app = FastAPI()
    test_app.add_middleware(TokenMiddleware)
    test_app.include_router(cpf.router)

    @test_app.get("/health")
    async def health():
        return {"status": "ok"}

    @test_app.get("/auth/check")
    async def auth_check():
        return {"ok": True}

    with TestClient(test_app) as c:
        # health sempre público
        assert c.get("/health").status_code == 200

        # /auth/check é protegido — é ele que o gate da UI usa para validar o
        # token. Se cair numa rota aberta (ex.: /health), qualquer token passa.
        assert c.get("/auth/check").status_code == 401
        assert c.get("/auth/check", headers={"Authorization": "Bearer errado"}).status_code == 401
        assert c.get("/auth/check", headers={"Authorization": "Bearer test-secret"}).status_code == 200

        # /metrics exige token fora de development (METRICS_PUBLIC=false)
        assert c.get("/metrics").status_code == 401

        # sem token → 401
        r = c.post("/cpf/validate", json={"cpf": "111.444.777-35"})
        assert r.status_code == 401

        # token errado → 401
        r = c.post("/cpf/validate",
                   json={"cpf": "111.444.777-35"},
                   headers={"Authorization": "Bearer errado"})
        assert r.status_code == 401

        # token correto → passa para o handler
        r = c.post("/cpf/validate",
                   json={"cpf": "111.444.777-35"},
                   headers={"Authorization": "Bearer test-secret"})
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# POST /trt3/buscar-por-mascara — formatos de máscara
# ---------------------------------------------------------------------------

def test_buscar_por_mascara_aceita_formato_alternativo(client):
    """Curinga '_' e separador padrão chegam até o serviço já normalizados."""
    capturado = {}

    def _fake(candidatos, nome=None, workers=None, **kw):
        capturado["candidatos"] = candidatos
        return {"total": len(candidatos), "matches": {}, "resultados": {}}

    with patch("app.routers.trt3.consultar_multiplos", side_effect=_fake):
        r = client.post("/trt3/buscar-por-mascara", json={"mascara": "___.444.777-__"})

    assert r.status_code == 200
    assert "11144477735" in capturado["candidatos"]


def test_buscar_por_mascara_caractere_invalido(client):
    r = client.post("/trt3/buscar-por-mascara", json={"mascara": "111.444.77A-35"})
    assert r.status_code == 422
    assert "Caractere inválido" in r.json()["detail"]
