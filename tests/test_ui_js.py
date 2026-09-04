"""
Normalização do campo de CPF — o JavaScript de verdade, rodado no node.

A interface são ~1.150 linhas de JS dentro de uma string Python, fora do
alcance do pytest: foi exatamente ali que passou o bug do curinga `*`, que o
CI não pegou. Este teste extrai o handler real da página servida e o executa,
então uma alteração no handler é seguida pelo teste em vez de ficar órfã.
"""
import json
import shutil
import subprocess

import pytest

from app.routers.ui import _HTML

node = pytest.mark.skipif(shutil.which("node") is None, reason="node não disponível")

MARCADOR = "$cpf.addEventListener('input', function() {"


def _corpo_do_handler() -> str:
    """Recorta o corpo do handler casando as chaves a partir do marcador."""
    ini = _HTML.index(MARCADOR) + len(MARCADOR)
    nivel = 1
    for i in range(ini, len(_HTML)):
        if _HTML[i] == "{":
            nivel += 1
        elif _HTML[i] == "}":
            nivel -= 1
            if nivel == 0:
                return _HTML[ini:i]
    raise AssertionError("chaves do handler não fecham")


def _rodar_no_node(entradas: list[str]) -> list[str]:
    script = """
const handler = function() { %s };
const casos = %s;
const saidas = casos.map(txt => {
  // campo falso: digita caractere a caractere, como o usuário faria
  const el = {value: '', selectionStart: 0, setSelectionRange(){}};
  for (const c of txt) { el.value += c; handler.call(el); }
  return el.value;
});
console.log(JSON.stringify(saidas));
""" % (_corpo_do_handler(), json.dumps(entradas))
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_marcador_do_handler_existe():
    """Se alguém renomear o handler, o teste avisa em vez de silenciar."""
    assert MARCADOR in _HTML
    assert "replace" in _corpo_do_handler()


@node
def test_todos_os_curingas_viram_asterisco():
    entradas = [
        "***879820**", "XXX879820XX", "xxx879820xx",
        "???879820??", "___879820__", "###879820##", "*X?879820_#",
    ]
    saidas = _rodar_no_node(entradas)
    assert saidas == ["***.879.820-**"] * len(entradas), saidas


@node
def test_formata_enquanto_digita():
    assert _rodar_no_node(["151", "151879", "151879820", "15187982095"]) == [
        "151", "151.879", "151.879.820", "151.879.820-95",
    ]


@node
def test_descarta_letras_e_limita_a_11_posicoes():
    assert _rodar_no_node(["AAA879820BB"]) == ["879.820"]
    assert _rodar_no_node(["1518798209599999"]) == ["151.879.820-95"]


@node
def test_separadores_digitados_nao_duplicam():
    assert _rodar_no_node(["151.879.820-95", "151 879 820 95"]) == [
        "151.879.820-95", "151.879.820-95",
    ]
