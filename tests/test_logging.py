"""
Logs da consulta ao TRT3 — o que aparece e, principalmente, o que não pode aparecer.
"""
import logging
from unittest.mock import patch

from app.services.trt3 import _log_cpf, consultar_trt3_multiplos

FAKE = {
    "cpf": "111.444.777-35",
    "encontrado": True,
    "nome_certidao": "FULANO DE TAL",
    "tipo_certidao": "NEGATIVA",
}


def test_log_cpf_mascara_o_meio():
    assert _log_cpf("111.444.777-35") == "111.***.***-35"


def _rodar_lote(caplog, level):
    with caplog.at_level(level, logger="trt3"):
        with patch("app.services.trt3._consultar_trt3_interno", return_value=FAKE):
            consultar_trt3_multiplos(["11144477735"])
    return "\n".join(r.getMessage() for r in caplog.records)


def test_log_padrao_nao_vaza_cpf_completo_nem_nome(caplog):
    texto = _rodar_lote(caplog, logging.INFO)
    assert "111.***.***-35" in texto      # CPF mascarado aparece
    assert "444.777" not in texto         # CPF completo, não
    assert "FULANO" not in texto          # nome da certidão é PII
    assert "MATCH" in texto               # o match em si é logado


def test_nome_aparece_apenas_em_debug(caplog):
    texto = _rodar_lote(caplog, logging.DEBUG)
    assert "FULANO" in texto


def test_lote_loga_inicio_progresso_e_fim(caplog):
    texto = _rodar_lote(caplog, logging.INFO)
    assert "lote iniciado" in texto
    assert "lote 1/1 (100%)" in texto
    assert "lote concluído" in texto
