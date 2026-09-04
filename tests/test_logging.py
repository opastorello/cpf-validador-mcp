"""
Logs da consulta — o que aparece e, principalmente, o que não pode aparecer.
"""
import logging
from unittest.mock import patch

from app.services.sources import consultar_multiplos
from app.services.sources.base import Fonte, mascarar_cpf

FAKE = {
    "cpf": "151.879.820-95",
    "encontrado": True,
    "nome_certidao": "FULANO DE TAL",
    "tipo_certidao": "NEGATIVA",
}


class FonteFake(Fonte):
    nome = "fake"
    rotulo = "Fonte de teste"

    def consultar(self, cpf_limpo: str) -> dict:
        return FAKE


def test_mascarar_cpf_esconde_o_meio():
    assert mascarar_cpf("151.879.820-95") == "151.***.***-95"
    assert mascarar_cpf("15187982095") == "151.***.***-95"


def _rodar_lote(caplog, level):
    with caplog.at_level(level, logger="consulta"):
        with patch("app.services.sources.get_fonte", return_value=FonteFake()):
            consultar_multiplos(["15187982095"])
    return "\n".join(r.getMessage() for r in caplog.records)


def test_log_padrao_nao_vaza_cpf_completo_nem_nome(caplog):
    texto = _rodar_lote(caplog, logging.INFO)
    assert "151.***.***-95" in texto      # CPF mascarado aparece
    assert "879.820" not in texto         # CPF completo, não
    assert "FULANO" not in texto          # nome da certidão é PII
    assert "MATCH" in texto               # o match em si é logado


def test_nome_aparece_apenas_em_debug(caplog):
    texto = _rodar_lote(caplog, logging.DEBUG)
    assert "FULANO" in texto


def test_lote_loga_inicio_progresso_e_fim(caplog):
    texto = _rodar_lote(caplog, logging.INFO)
    assert "lote iniciado" in texto
    assert "fonte=fake" in texto          # a fonte usada aparece no log
    assert "lote 1/1 (100%)" in texto
    assert "lote concluído" in texto
