"""
/metrics de verdade — sem mockar prometheus_client.

Este arquivo só é possível porque o mock obsoleto saiu do conftest. Antes, as
métricas eram MagicMock e nada garantia que os contadores existissem, que os
labels batessem com os usados no código ou que o endpoint respondesse.
"""
import pytest


@pytest.fixture(scope="module")
def client():
    from contextlib import asynccontextmanager
    import app.auth as _auth
    _auth._TOKEN = ""
    from fastapi.testclient import TestClient
    from app.main import app

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    app.router.lifespan_context = _noop_lifespan
    return TestClient(app)


def _metrics(client) -> str:
    r = client.get("/metrics")
    assert r.status_code == 200
    return r.text


def test_endpoint_responde_no_formato_prometheus(client):
    texto = _metrics(client)
    assert "# HELP" in texto and "# TYPE" in texto


def test_metricas_do_projeto_estao_registradas(client):
    texto = _metrics(client)
    for nome in [
        "trt3_queries_total",
        "trt3_captcha_attempts_total",
        "trt3_query_duration_seconds",
        "cpf_validations_total",
        "cpf_mask_searches_total",
        "trt3_mcp_calls_total",
    ]:
        assert nome in texto, f"métrica ausente: {nome}"


def test_contador_sobe_de_fato(client):
    """Valida a fiação inteira: endpoint → labels → registry do prometheus."""
    def valor():
        for linha in _metrics(client).splitlines():
            if linha.startswith('cpf_validations_total{result="valid"}'):
                return float(linha.split()[-1])
        return 0.0

    antes = valor()
    client.post("/cpf/validate", json={"cpf": "111.444.777-35"})
    assert valor() == antes + 1


def test_label_invalido_tambem_e_contado(client):
    def valor():
        for linha in _metrics(client).splitlines():
            if linha.startswith('cpf_validations_total{result="invalid"}'):
                return float(linha.split()[-1])
        return 0.0

    antes = valor()
    client.post("/cpf/validate", json={"cpf": "111.111.111-11"})
    assert valor() == antes + 1
