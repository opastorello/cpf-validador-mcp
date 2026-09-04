"""
Camada de fontes: registro, seleção via SOURCE e o contrato que toda fonte cumpre.
"""
import subprocess
import sys

import pytest

from app.services.sources import (
    _REGISTRO,
    consultar,
    consultar_multiplos,
    fontes_disponiveis,
    get_fonte,
)
from app.services.sources.base import Fonte

CPF_COM_REGISTRO = "11144477735"   # soma 44, par  → a fonte de exemplo "acha"
CPF_SEM_REGISTRO = "11144477905"   # soma 43, ímpar → a fonte de exemplo "não acha"


def test_fontes_disponiveis_lista_registro():
    disponiveis = fontes_disponiveis()
    assert "trt3" in disponiveis
    assert "exemplo" in disponiveis


def test_fonte_desconhecida_lista_as_validas():
    with pytest.raises(ValueError, match="Fonte desconhecida"):
        get_fonte("tribunal-inexistente")
    try:
        get_fonte("tribunal-inexistente")
    except ValueError as e:
        assert "trt3" in str(e) and "exemplo" in str(e)


def test_rotulo_do_registro_bate_com_o_da_classe():
    """O rótulo é duplicado no registro para não precisar importar a fonte só
    para listá-la; este teste impede que as duas cópias divirjam."""
    fonte = get_fonte("exemplo")
    assert fonte.rotulo == _REGISTRO["exemplo"][2]


def test_exemplo_cumpre_o_contrato():
    fonte = get_fonte("exemplo")
    assert isinstance(fonte, Fonte)

    achado = fonte.consultar(CPF_COM_REGISTRO)
    assert achado["cpf"] == "111.444.777-35"
    assert achado["encontrado"] is True
    assert achado["nome_certidao"]
    assert achado["fonte"] == "exemplo"
    assert "fictícios" in achado["aviso"]


def test_exemplo_e_deterministico():
    fonte = get_fonte("exemplo")
    assert fonte.consultar(CPF_COM_REGISTRO) == fonte.consultar(CPF_COM_REGISTRO)


def test_ausencia_de_registro_nao_e_erro():
    """encontrado=False é resposta, não falha — 'erro' fica ausente."""
    r = get_fonte("exemplo").consultar(CPF_SEM_REGISTRO)
    assert r["encontrado"] is False
    assert "erro" not in r
    assert "nome_certidao" not in r


def test_consultar_aceita_fonte_explicita():
    assert consultar(CPF_COM_REGISTRO, fonte="exemplo")["fonte"] == "exemplo"


def test_lote_usa_a_fonte_escolhida_e_filtra_por_nome():
    # o nome vem da própria fonte: o teste não pode chutar qual dos fictícios saiu
    nome = get_fonte("exemplo").consultar(CPF_COM_REGISTRO)["nome_certidao"]

    r = consultar_multiplos([CPF_COM_REGISTRO], nome_filtro=nome.split()[0], fonte="exemplo")
    assert r["total"] == 1
    assert CPF_COM_REGISTRO in r["matches"]

    r = consultar_multiplos([CPF_COM_REGISTRO], nome_filtro="ninguem com esse nome", fonte="exemplo")
    assert r["matches"] == {}


def test_lote_sem_filtro_ignora_quem_nao_tem_registro():
    r = consultar_multiplos([CPF_COM_REGISTRO, CPF_SEM_REGISTRO], fonte="exemplo")
    assert r["total"] == 2
    assert set(r["matches"]) == {CPF_COM_REGISTRO}


def test_registro_e_preguicoso():
    """Importar a camada de fontes não pode arrastar o PyTorch do TRT3 junto:
    uma fonte sem CAPTCHA não deve pagar o import de quem tem."""
    codigo = (
        "import sys; import app.services.sources as s; "
        "assert 'app.services.sources.trt3' not in sys.modules, 'trt3 importado cedo demais'; "
        "assert 'torch' not in sys.modules, 'torch importado cedo demais'; "
        "s.get_fonte('exemplo'); "
        "assert 'app.services.sources.trt3' not in sys.modules, 'usar exemplo importou trt3'; "
        "print('ok')"
    )
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout
