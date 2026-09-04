"""
Testes do parser de máscaras de CPF — lógica pura, sem rede.
"""
import pytest

from app.services.cpf import gerar_cpfs_de_mascara

CPF = "11144477735"

# Todas estas máscaras descrevem o mesmo CPF de formas diferentes
FORMATOS_EQUIVALENTES = [
    "***.444.777-**",     # mascaramento LGPD (documento público)
    "***444777**",        # sem separador
    "*** 444 777 **",     # separado por espaço
    "***/444/777/**",     # separado por barra
    "XXX.444.777-XX",     # anotação manual maiúscula
    "xxx.444.777-xx",     # minúscula
    "???.444.777-??",     # interrogação
    "___.444.777-__",     # campo de formulário
    "###.444.777-##",     # planilha
    "*X?.444.777-_#",     # curingas misturados
    " ***.444.777-** ",  # espaço não-quebrável (colado de PDF/web)
]


@pytest.mark.parametrize("mascara", FORMATOS_EQUIVALENTES)
def test_formatos_equivalentes_geram_o_mesmo_resultado(mascara):
    candidatos = gerar_cpfs_de_mascara(mascara)
    assert CPF in candidatos
    assert candidatos == gerar_cpfs_de_mascara(FORMATOS_EQUIVALENTES[0])


def test_digitos_verificadores_omitidos_viram_curinga():
    """Máscara de 9 posições: os DVs são calculados."""
    assert gerar_cpfs_de_mascara("111.444.777") == [CPF]


def test_um_digito_verificador_omitido():
    """Máscara de 10 posições: o DV informado filtra, o omitido é calculado."""
    assert gerar_cpfs_de_mascara("111.444.777-3") == [CPF]


def test_digito_verificador_informado_filtra():
    candidatos = gerar_cpfs_de_mascara("111.444.77*-35")
    assert CPF in candidatos
    assert all(c.endswith("35") for c in candidatos)


def test_digito_verificador_incompativel_nao_gera_nada():
    """DVs que não batem com nenhuma combinação da base."""
    assert gerar_cpfs_de_mascara("111.444.777-00") == []


def test_todos_os_candidatos_sao_validos():
    for cpf in gerar_cpfs_de_mascara("111.444.7**-**"):
        assert len(cpf) == 11 and cpf.isdigit()
        assert len(set(cpf)) > 1  # repetidos (111.111.111-11) são rejeitados


def test_caractere_invalido_e_apontado():
    with pytest.raises(ValueError, match="Caractere inválido"):
        gerar_cpfs_de_mascara("111.444.77A-35")


def test_tamanho_invalido():
    with pytest.raises(ValueError, match="11 posições"):
        gerar_cpfs_de_mascara("111.444")


def test_excesso_de_curingas_e_recusado():
    with pytest.raises(ValueError, match="curingas na base"):
        gerar_cpfs_de_mascara("******777-**")  # 6 curingas na base, limite é 5
