"""
Camada de fontes: registro, seleção via SOURCE e carregamento preguiçoso.
"""
import subprocess
import sys

import pytest

from app.services.sources import fontes_disponiveis, get_fonte


def test_fontes_disponiveis_lista_registro():
    assert "trt3" in fontes_disponiveis()


def test_fonte_desconhecida_lista_as_validas():
    with pytest.raises(ValueError, match="Fonte desconhecida"):
        get_fonte("tribunal-inexistente")
    try:
        get_fonte("tribunal-inexistente")
    except ValueError as e:
        assert "trt3" in str(e)


def test_registro_e_preguicoso():
    """Importar a camada de fontes não pode arrastar o PyTorch do TRT3 junto:
    uma fonte sem CAPTCHA não deve pagar o import de quem tem."""
    codigo = (
        "import sys; import app.services.sources as s; "
        "assert 'app.services.sources.trt3' not in sys.modules, 'trt3 importado cedo demais'; "
        "assert 'torch' not in sys.modules, 'torch importado cedo demais'; "
        "print('ok')"
    )
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout
