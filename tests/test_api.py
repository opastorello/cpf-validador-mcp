"""
Testes da API REST — todos os chamados ao TRT3 são mockados.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from app.main import app
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
    with patch("app.routers.trt3.consultar_trt3", return_value=MOCK_FEITOS):
        r = client.post("/trt3/feitos", json={"cpf": "111.444.777-35"})
    assert r.status_code == 200
    assert r.json()["cpf"] == "11144477735"


def test_trt3_feitos_payload_invalido(client):
    r = client.post("/trt3/feitos", json={})
    assert r.status_code == 422
