"""
Caminhos de falha da consulta ao TRT3.

São os ramos que só disparam quando algo dá errado de verdade — tribunal fora
do ar, layout mudado, PDF corrompido — e por isso nunca eram exercitados. São
justamente os que produzem os logs de WARNING e ERROR que alguém vai ler às
duas da manhã.
"""
import logging
from unittest.mock import MagicMock, patch

import pytest

from app.services.sources import trt3 as m
from app.services.sources.base import MSG_CPF_INEXISTENTE


@pytest.fixture(autouse=True)
def _rapido(monkeypatch):
    """Sem espera entre tentativas e com poucas tentativas, para o teste não
    levar os 20 retries reais."""
    monkeypatch.setattr(m._cfg, "MAX_CAPTCHA_ATTEMPTS", 2)
    monkeypatch.setattr(m._cfg, "RETRY_DELAY", 0)
    monkeypatch.setattr(m, "_requests", MagicMock())


def _resposta(content_type="text/html", text="", content=b""):
    r = MagicMock()
    r.headers = {"Content-Type": content_type}
    r.text = text
    r.content = content
    r.raise_for_status = MagicMock()
    return r


def test_pagina_sem_captcha_loga_erro_de_layout(caplog):
    """Sinal de que o TRT3 mudou a página — precisa ser ERROR, não um retry
    silencioso, porque nenhuma tentativa vai resolver."""
    with caplog.at_level(logging.ERROR, logger="trt3"):
        with patch.object(m, "_fetch_page", return_value=("http://x", "vs", "")):
            r = m._consultar_trt3_com_sessao("15187982095", "151.879.820-95")

    assert r["encontrado"] is None
    assert "CAPTCHA URL não encontrada" in r["erro"]
    texto = "\n".join(x.getMessage() for x in caplog.records)
    assert "layout mudou?" in texto
    assert "151.***.***-95" in texto      # mascarado também no erro


def test_excecao_na_tentativa_vira_warning(caplog):
    """Antes o `except Exception: continue` engolia isto sem deixar rastro."""
    with caplog.at_level(logging.WARNING, logger="trt3"):
        with patch.object(m, "_fetch_page", side_effect=ConnectionError("conexão recusada")):
            r = m._consultar_trt3_com_sessao("15187982095", "151.879.820-95")

    texto = "\n".join(x.getMessage() for x in caplog.records)
    assert "ConnectionError" in texto          # o tipo da exceção aparece
    assert "conexão recusada" in texto         # a mensagem também
    assert "tentativa 1/2" in texto
    assert r["encontrado"] is None


def test_tentativas_esgotadas_loga_desistencia(caplog):
    with caplog.at_level(logging.ERROR, logger="trt3"):
        with patch.object(m, "_fetch_page", side_effect=TimeoutError("estourou")):
            r = m._consultar_trt3_com_sessao("15187982095", "151.879.820-95")

    texto = "\n".join(x.getMessage() for x in caplog.records)
    assert "desisti de cpf=151.***.***-95 após 2 tentativas" in texto
    assert "CAPTCHA não resolvido após 2 tentativas" in r["erro"]


def test_pdf_ilegivel_loga_warning_mas_nao_perde_o_resultado(caplog):
    """PDF corrompido não pode derrubar a consulta: o TRT3 respondeu com um
    PDF, então o CPF tem titular — só não deu para ler os campos."""
    resp = _resposta(content_type="application/pdf", content=b"isto nao e um pdf")
    with caplog.at_level(logging.WARNING, logger="trt3"):
        with patch.object(m, "_fetch_page", return_value=("http://x", "vs", "http://c")), \
             patch.object(m, "_solve_captcha", return_value="abc123"), \
             patch.object(m, "_post_form", return_value=resp):
            r = m._consultar_trt3_com_sessao("15187982095", "151.879.820-95")

    assert r["encontrado"] is True
    assert "PDF recebido mas ilegível" in "\n".join(x.getMessage() for x in caplog.records)


def test_captcha_errado_reabre_sessao_e_tenta_de_novo(caplog):
    """Resposta com o campo do captcha de volta = captcha recusado."""
    devolveu_formulario = _resposta(text='<input name="form:verifyCaptcha_" />')
    with caplog.at_level(logging.DEBUG, logger="trt3"):
        with patch.object(m, "_fetch_page", return_value=("http://x", "vs", "http://c")), \
             patch.object(m, "_solve_captcha", return_value="errad"), \
             patch.object(m, "_post_form", return_value=devolveu_formulario):
            r = m._consultar_trt3_com_sessao("15187982095", "151.879.820-95")

    texto = "\n".join(x.getMessage() for x in caplog.records)
    assert "rejeitado" in texto
    assert "nova sessão" in texto
    assert r["encontrado"] is None      # esgotou as 2 tentativas


# ── CPF válido no módulo-11 mas inexistente na Receita Federal ─────────────

NAO_CADASTRADO = (
    __import__("pathlib").Path(__file__).parent / "fixtures" / "trt3_cpf_nao_cadastrado.html"
).read_text(encoding="utf-8")


def test_cpf_nao_cadastrado_nao_vira_retry_de_captcha(caplog):
    """O TRT3 devolve o formulário — igualzinho a quando recusa o CAPTCHA. Se
    cair no retry, queima as 20 tentativas e reporta erro de CAPTCHA para um
    CPF que simplesmente não existe."""
    resp = _resposta(text=NAO_CADASTRADO)
    with caplog.at_level(logging.INFO, logger="trt3"):
        with patch.object(m, "_fetch_page", return_value=("http://x", "vs", "http://c")), \
             patch.object(m, "_solve_captcha", return_value="abc123") as solve, \
             patch.object(m, "_post_form", return_value=resp):
            r = m._consultar_trt3_com_sessao("15187982095", "151.879.820-95")

    assert r["encontrado"] is False
    assert r["cpf_inexistente"] is True
    assert r["mensagem"] == MSG_CPF_INEXISTENTE   # frase padrão, não texto do TRT3
    assert "erro" not in r
    assert solve.call_count == 1, "resolveu CAPTCHA mais de uma vez"
    assert "não cadastrado na Receita Federal" in "\n".join(x.getMessage() for x in caplog.records)


def test_a_fixture_tem_o_campo_de_captcha():
    """Se a fixture não tiver o campo, o teste acima passa por acidente: é
    justamente a presença dele que fazia a resposta ser lida como captcha
    errado."""
    assert "form:verifyCaptcha_" in NAO_CADASTRADO


def test_falha_na_transacao_nao_vira_retry_de_captcha(caplog):
    """Erro do TRT3 chega com o formulário de volta, igual a captcha recusado.
    Sem distinguir, gasta as 20 tentativas e reporta erro de CAPTCHA."""
    resp = _resposta(text='<span class="erro">Falha na Transação</span>'
                          '<input name="form:verifyCaptcha_" />')
    with caplog.at_level(logging.WARNING, logger="trt3"):
        with patch.object(m, "_fetch_page", return_value=("http://x", "vs", "http://c")), \
             patch.object(m, "_solve_captcha", return_value="abc123") as solve, \
             patch.object(m, "_post_form", return_value=resp):
            r = m._consultar_trt3_com_sessao("15187982095", "151.879.820-95")

    assert r["encontrado"] is None
    assert "Falha na Transação" in r["erro"]
    assert solve.call_count == 1, "gastou mais de um CAPTCHA num erro do tribunal"
    assert "recusou a transação" in "\n".join(x.getMessage() for x in caplog.records)
