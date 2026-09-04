"""Fonte de exemplo — o esqueleto para escrever uma fonte nova.

Não acessa rede nenhuma: devolve dados **fictícios e determinísticos**, para
servir de modelo de código e para exercitar a interface, o MCP e a busca em
lote sem bater em serviço externo.

Ative com ``SOURCE=exemplo`` no .env.

Para criar uma fonte de verdade, copie este arquivo e siga os cinco passos
marcados abaixo. Depois registre a classe em ``sources/__init__.py``.
"""
import logging

from app.services.cpf import formatar
from app.services.sources.base import Fonte, mascarar_cpf

log = logging.getLogger("exemplo")

# Nomes propositalmente fictícios — nunca use dados de pessoa real aqui.
_NOMES_FICTICIOS = [
    "FULANO DE TAL",
    "BELTRANO DE SOUZA",
    "SICRANO DA SILVA",
]


class Exemplo(Fonte):
    """Modelo de fonte. Responde sem consultar nada.

    Regra: CPF cuja soma dos dígitos é par "tem titular"; ímpar, "não consta".
    É determinístico de propósito — o mesmo CPF devolve sempre o mesmo
    resultado, o que torna a busca em lote reproduzível em teste.
    """

    nome = "exemplo"
    rotulo = "Fonte de exemplo (dados fictícios, não consulta nada)"
    usa_captcha = False   # herdaria False do contrato; explícito por ser o modelo

    def consultar(self, cpf_limpo: str) -> dict:
        cpf_fmt = formatar(cpf_limpo)

        # ─── passo 1: preparar a requisição ────────────────────────────────
        # Numa fonte real, aqui entram sessão HTTP, headers, token, cookie ou
        # o que o serviço exigir. Veja `trt3.py` para um caso com CAPTCHA e
        # impersonação de TLS.
        log.debug("consulta iniciada cpf=%s", mascarar_cpf(cpf_limpo))

        # ─── passo 2: consultar ────────────────────────────────────────────
        # Aqui iria a chamada de rede. Como esta fonte é um modelo, o
        # "resultado externo" é calculado a partir do próprio CPF.
        soma = sum(int(d) for d in cpf_limpo)
        tem_registro = soma % 2 == 0

        # ─── passo 3: tratar "não encontrado" ──────────────────────────────
        # Ausência de registro NÃO é erro: é `encontrado: False`. Só use
        # `erro` quando a consulta em si falhou (rede, layout, bloqueio).
        if not tem_registro:
            return {
                "cpf": cpf_fmt,
                "encontrado": False,
                "fonte": self.nome,
                "aviso": "dados fictícios — fonte de exemplo",
                "mensagem": "Nenhum registro encontrado.",
            }

        # ─── passo 4: traduzir a resposta externa para o contrato ──────────
        # `nome_certidao` é a chave que o filtro por nome das buscas em lote
        # usa; sem ela, `find_cpf_by_mask(nome=...)` não consegue casar nada.
        nome = _NOMES_FICTICIOS[soma % len(_NOMES_FICTICIOS)]

        # ─── passo 5: devolver ─────────────────────────────────────────────
        # Chaves extras são repassadas ao cliente sem interpretação — use-as
        # para o que a sua fonte tiver de específico.
        return {
            "cpf": cpf_fmt,
            "encontrado": True,
            "nome_certidao": nome,
            "fonte": self.nome,
            "aviso": "dados fictícios — fonte de exemplo",
        }
