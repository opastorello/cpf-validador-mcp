"""
Parsers do TRT3 contra a resposta real do tribunal.

A fixture `trt3_form.html` é a página do formulário capturada de
certidao.trt3.jus.br, com jsessionid e ViewState redigidos (os parsers leem o
formato, não o valor). É ela que detecta mudança de layout: se o TRT3 mexer no
`id` do form, no nome do ViewState ou no caminho do CAPTCHA, estes testes caem.
"""
from pathlib import Path
from unittest.mock import MagicMock

from app.services.sources.trt3 import (
    _fetch_page,
    _parse_html_resultado,
    _parse_texto_certidao,
)

FIXTURES = Path(__file__).parent / "fixtures"
FORM_HTML = (FIXTURES / "trt3_form.html").read_text(encoding="utf-8")


def _sessao_falsa(html: str):
    """Sessão curl_cffi mínima: devolve o HTML dado em qualquer GET."""
    resp = MagicMock()
    resp.text = html
    resp.raise_for_status = MagicMock()
    sessao = MagicMock()
    sessao.get = MagicMock(return_value=resp)
    return sessao


# ── _fetch_page ────────────────────────────────────────────────────────────

def test_fetch_page_extrai_os_tres_campos():
    action_url, viewstate, captcha_url = _fetch_page(_sessao_falsa(FORM_HTML))

    assert action_url.startswith("https://certidao.trt3.jus.br/certidao/feitosTrabalhistas/")
    assert viewstate == "VIEWSTATE_REDIGIDO"
    assert captcha_url.startswith("https://certidao.trt3.jus.br/certidao/seam/resource/captcha")


def test_fetch_page_transforma_action_relativa_em_absoluta():
    _, _, captcha_url = _fetch_page(_sessao_falsa(FORM_HTML))
    assert captcha_url.count("https://") == 1


def test_fetch_page_sem_captcha_devolve_string_vazia():
    """Se o TRT3 mudar o caminho do CAPTCHA, a consulta precisa perceber —
    é isso que dispara o log de ERROR 'layout mudou?'."""
    html = FORM_HTML.replace("/certidao/seam/resource/captcha", "/certidao/seam/resource/OUTRACOISA")
    _, _, captcha_url = _fetch_page(_sessao_falsa(html))
    assert captcha_url == ""


def test_fetch_page_sem_viewstate_nao_quebra():
    html = FORM_HTML.replace('name="javax.faces.ViewState"', 'name="outro.campo"')
    _, viewstate, _ = _fetch_page(_sessao_falsa(html))
    assert viewstate == ""


# ── _parse_html_resultado ──────────────────────────────────────────────────

def _resp(html: str):
    r = MagicMock()
    r.text = html
    return r


def test_resultado_com_link_de_pdf():
    html = '<html><a href="/certidao/arquivos/certidao_123.pdf">baixar</a></html>'
    r = _parse_html_resultado("11144477735", "111.444.777-35", _resp(html))
    assert r["encontrado"] is True
    assert r["pdf_url"] == "https://certidao.trt3.jus.br/certidao/arquivos/certidao_123.pdf"


def test_pdf_com_url_absoluta_nao_e_prefixada():
    html = '<html><a href="https://certidao.trt3.jus.br/x/certidao_9.pdf">baixar</a></html>'
    r = _parse_html_resultado("11144477735", "111.444.777-35", _resp(html))
    assert r["pdf_url"].count("https://") == 1


def test_resultado_sem_feitos():
    for texto in [
        "Não foram encontrados registros",
        "nenhum feito trabalhista",
        "CERTIDÃO NEGATIVA de feitos",
        "não há feitos em nome do requerente",
    ]:
        r = _parse_html_resultado("11144477735", "111.444.777-35", _resp(f"<html>{texto}</html>"))
        assert r["encontrado"] is False, texto


def test_resposta_desconhecida_fica_indeterminada():
    """Nem PDF nem frase conhecida: melhor devolver None do que chutar."""
    r = _parse_html_resultado("11144477735", "111.444.777-35", _resp("<html>algo inesperado</html>"))
    assert r["encontrado"] is None


# ── _parse_texto_certidao ──────────────────────────────────────────────────
#
# As fixtures reproduzem a estrutura real do PDF do TRT3 (quebras de linha,
# ordem dos blocos, "Certidão n." seguida do código de autenticidade numa linha
# e do número noutra) com nome e CPF fictícios. O PDF real não pode ser
# versionado: é dado pessoal de terceiro.

NEGATIVA = (FIXTURES / "certidao_negativa.txt").read_text(encoding="utf-8")
POSITIVA = (FIXTURES / "certidao_positiva.txt").read_text(encoding="utf-8")


def test_certidao_negativa():
    d = _parse_texto_certidao(NEGATIVA)
    assert d["tipo_certidao"] == "NEGATIVA"
    assert d["tem_feitos"] is False
    assert d["nome_certidao"] == "FULANO DE TAL"
    assert d["valida_ate"] == "03/10/2026"
    assert d["numero_certidao"] == "1195030/2026"


def test_certidao_positiva_marca_tem_feitos():
    d = _parse_texto_certidao(POSITIVA)
    assert d["tipo_certidao"] == "POSITIVA"
    assert d["tem_feitos"] is True


def test_numero_da_certidao_pula_o_codigo_de_autenticidade():
    """O layout é 'Certidão n.' / <código> / <número>/<ano>: o parser tem de
    pegar a segunda linha, não o código."""
    assert _parse_texto_certidao(NEGATIVA)["numero_certidao"] == "1195030/2026"
    assert "RJJN" not in _parse_texto_certidao(NEGATIVA)["numero_certidao"]


def test_texto_vazio_nao_quebra():
    assert _parse_texto_certidao("") == {"tem_feitos": False}


def test_cpf_da_certidao_e_extraido():
    """O texto real é '...no CPF sob o nº 111.444.777-35.' — havia palavras
    entre 'CPF' e o número, e o padrão antigo exigia que fossem adjacentes."""
    assert _parse_texto_certidao(NEGATIVA)["cpf_certidao"] == "111.444.777-35"
