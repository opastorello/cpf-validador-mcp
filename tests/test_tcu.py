"""
Fonte TCU: proof-of-work do Altcha e tradução da resposta.

As duas partes com lógica são puras de propósito — `_resolver_pow` e
`_parse_resposta` — então dá para exercitá-las sem rede. Os formatos de
resposta abaixo são os reais, capturados de certidoes.apps.tcu.gov.br, com
nome e CPF trocados por fictícios.
"""
import hashlib
from unittest.mock import MagicMock, patch

import pytest

from app.services.sources import tcu as m
from app.services.sources.base import MSG_CPF_INEXISTENTE
from app.services.sources.tcu import (
    TCU,
    _montar_captcha,
    _parse_resposta,
    _resolver_pow,
)

CPF = "15187982095"
CPF_FMT = "151.879.820-95"


def _desafio(counter_alvo: int, cost: int = 50) -> dict:
    """Monta um desafio cuja resposta é `counter_alvo`.

    O prefixo sai do próprio PBKDF2 daquele contador, então o desafio é
    legítimo e resolvível — só barato, para o teste não gastar segundos.
    """
    nonce, salt = "00" * 16, "11" * 16
    chave = hashlib.pbkdf2_hmac(
        "sha256",
        bytes.fromhex(nonce) + counter_alvo.to_bytes(4, "big"),
        bytes.fromhex(salt), cost, 32,
    )
    return {
        "parameters": {
            "algorithm": "PBKDF2/SHA-256",
            "nonce": nonce, "salt": salt, "cost": cost,
            "keyLength": 32, "keyPrefix": chave.hex()[:32],
        },
        "signature": "assinatura-ficticia",
    }


# ── proof-of-work ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("alvo", [0, 1, 37, 250])
def test_resolve_o_proof_of_work(alvo):
    solucao = _resolver_pow(_desafio(alvo))
    assert solucao["counter"] == alvo
    assert len(solucao["derivedKey"]) == 64


def test_a_chave_derivada_comeca_com_o_prefixo():
    desafio = _desafio(42)
    solucao = _resolver_pow(desafio)
    assert solucao["derivedKey"].startswith(desafio["parameters"]["keyPrefix"])


def test_desiste_quando_nao_ha_solucao(monkeypatch):
    """Prefixo impossível: precisa falhar em vez de girar para sempre."""
    monkeypatch.setattr(m._cfg, "TCU_POW_MAX_COUNTER", 20)
    desafio = _desafio(0)
    desafio["parameters"]["keyPrefix"] = "f" * 32
    with pytest.raises(ValueError, match="Proof-of-work não resolvido"):
        _resolver_pow(desafio)


def test_captcha_vai_em_base64_com_desafio_e_solucao():
    import base64
    import json

    desafio = _desafio(3)
    solucao = _resolver_pow(desafio)
    decodificado = json.loads(base64.b64decode(_montar_captcha(desafio, solucao)))
    assert decodificado["challenge"] == desafio      # o desafio vai intacto
    assert decodificado["solution"]["counter"] == 3


# ── tradução da resposta ───────────────────────────────────────────────────

SUCESSO = {
    "dadosCertidao": {
        "codigo": 49441673,
        "tipoDocumento": "CPF",
        "numeroDocumento": CPF,
        "nome": "FULANO DE TAL",
        "codigoControle": "VBKE20260903235404",
        "modeloCertidao": "NEGATIVA",
        "seCertidaoNegativa": True,
        "cpfCnpj": CPF_FMT,
        "dataEmissao": "03/09/2026",
        "dataValidade": "03/10/2026",
        "validadeEmDias": 30,
    }
}

NAO_LOCALIZADO = {
    "violacoes": [{
        "tipo": "ERRO", "codigo": "422",
        "mensagem": "CPF não localizado na base da Receita Federal disponível no TCU",
    }]
}


def test_certidao_negativa():
    r = _parse_resposta(CPF_FMT, 200, SUCESSO)
    assert r["encontrado"] is True
    assert r["nome_certidao"] == "FULANO DE TAL"
    assert r["tipo_certidao"] == "NEGATIVA"
    assert r["tem_registro"] is False
    assert r["valida_ate"] == "03/10/2026"
    assert r["numero_certidao"] == "VBKE20260903235404"


def test_certidao_positiva_marca_tem_registro():
    corpo = {"dadosCertidao": {**SUCESSO["dadosCertidao"],
                               "modeloCertidao": "POSITIVA",
                               "seCertidaoNegativa": False}}
    r = _parse_resposta(CPF_FMT, 200, corpo)
    assert r["tem_registro"] is True


def test_cpf_nao_localizado_nao_e_erro():
    """412 com 'não localizado' é resposta definitiva, não falha — e a mensagem
    é a do TCU, não a do TRT3."""
    r = _parse_resposta(CPF_FMT, 412, NAO_LOCALIZADO)
    assert r["encontrado"] is False
    assert r["cpf_inexistente"] is True
    assert r["mensagem"] == MSG_CPF_INEXISTENTE   # frase padrão, igual em toda fonte
    assert "erro" not in r


def test_outra_violacao_vira_erro():
    corpo = {"violacoes": [{"tipo": "ERRO", "mensagem": "Captcha inválido"}]}
    r = _parse_resposta(CPF_FMT, 412, corpo)
    assert r["encontrado"] is None
    assert r["erro"] == "Captcha inválido"


def test_corpo_vazio_vira_erro_com_o_status():
    r = _parse_resposta(CPF_FMT, 500, {})
    assert r["encontrado"] is None
    assert "HTTP 500" in r["erro"]


# ── a fonte ────────────────────────────────────────────────────────────────

def test_fonte_declara_captcha_e_cumpre_o_contrato():
    fonte = TCU()
    assert fonte.nome == "tcu"
    assert fonte.usa_captcha is True   # Altcha é CAPTCHA, ainda que sem imagem


def test_consulta_completa_sem_rede():
    """Amarra desafio, PoW e parse no fluxo real, só trocando o HTTP."""
    desafio = _desafio(5)
    resp = MagicMock(status_code=200)
    resp.json = MagicMock(return_value=SUCESSO)
    sessao = MagicMock()
    sessao.post = MagicMock(return_value=resp)

    with patch.object(m, "_obter_desafio", return_value=desafio), \
         patch.object(m._requests, "Session", return_value=sessao):
        r = TCU().consultar(CPF)

    assert r["encontrado"] is True
    enviado = sessao.post.call_args.kwargs["json"]
    assert enviado["cpf"] == CPF
    assert enviado["captcha"]          # captcha resolvido acompanha a consulta


def test_falha_de_rede_vira_erro_e_nao_excecao(monkeypatch):
    """Quem chama roda centenas em paralelo: falha é resultado, não stack trace."""
    monkeypatch.setattr(m._cfg, "TCU_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(m._cfg, "RETRY_DELAY", 0)
    with patch.object(m, "_obter_desafio", side_effect=ConnectionError("recusada")), \
         patch.object(m._requests, "Session", MagicMock()):
        r = TCU().consultar(CPF)

    assert r["encontrado"] is None
    assert "2 tentativas" in r["erro"]
