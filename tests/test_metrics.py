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
        # da consulta — valem para qualquer fonte e levam o label `fonte`
        "consulta_queries_total",
        "consulta_duration_seconds",
        "consulta_feitos_total",
        "consulta_matches_total",
        # do scraping do TRT3 — não existem para uma fonte sem CAPTCHA
        "trt3_captcha_attempts_total",
        "trt3_pdf_parsed_total",
        # da aplicação
        "cpf_validations_total",
        "cpf_mask_searches_total",
        "mcp_calls_total",
        "http_rate_limit_total",
    ]:
        assert nome in texto, f"métrica ausente: {nome}"


def test_metricas_de_consulta_tem_label_de_fonte(client):
    """Sem o label, não dá para separar o desempenho de uma fonte da outra."""
    from app.services.sources import consultar
    consultar("15187982095", fonte="exemplo")
    texto = _metrics(client)
    assert 'consulta_queries_total{fonte="exemplo"' in texto
    assert 'consulta_duration_seconds_count{fonte="exemplo"}' in texto


def test_contador_sobe_de_fato(client):
    """Valida a fiação inteira: endpoint → labels → registry do prometheus."""
    def valor():
        for linha in _metrics(client).splitlines():
            if linha.startswith('cpf_validations_total{result="valid"}'):
                return float(linha.split()[-1])
        return 0.0

    antes = valor()
    client.post("/cpf/validate", json={"cpf": "151.879.820-95"})
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
