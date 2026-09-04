"""Contrato que toda fonte de consulta precisa cumprir.

Uma *fonte* responde à pergunta "a quem pertence este CPF?" consultando algum
serviço externo. Hoje a única fonte real é o TRT3; esta camada existe para que
uma segunda (outro tribunal, outra base pública) entre sem tocar em `routers/`,
em `mcp_server.py` nem na lógica de máscara e variações — todas elas só sabem
pedir "consulte estes CPFs" para a fonte ativa.

Para escrever uma fonte nova, copie `exemplo.py`.
"""
from abc import ABC, abstractmethod

from app.services.cpf import formatar


# Mensagens exibidas ao usuário quando não há resultado. Ficam aqui, e não
# dentro de cada fonte, para que todas digam a mesma coisa nos mesmos casos: o
# usuário não deve descobrir qual fonte respondeu pelo texto da mensagem. Uma
# fonte só escreve texto próprio quando tem algo que nenhuma outra teria.
MSG_CPF_INEXISTENTE = "CPF não localizado na base consultada."
MSG_SEM_REGISTRO = "Nenhum registro encontrado."
MSG_INDETERMINADO = "Resposta não reconhecida pela fonte."


def mascarar_cpf(cpf: str) -> str:
    """CPF parcialmente mascarado para uso em log (LGPD): 111.***.***-35.

    Aceita o CPF com ou sem formatação.
    """
    fmt = formatar(cpf) if len(cpf) == 11 and cpf.isdigit() else cpf
    return f"{fmt[:3]}.***.***-{fmt[-2:]}"


class Fonte(ABC):
    """Fonte de consulta de titularidade de CPF.

    Subclasses definem `nome` (identificador usado em `SOURCE=`) e `rotulo`
    (texto legível, exposto ao cliente) e implementam `consultar`.
    """

    #: identificador curto, usado no .env — ex.: "trt3"
    nome: str = ""

    #: descrição legível — ex.: "TRT 3ª Região (certidao.trt3.jus.br)"
    rotulo: str = ""

    #: A fonte resolve CAPTCHA para consultar? A interface usa isto para não
    #: anunciar "CAPTCHA resolvido" numa fonte que não tem CAPTCHA nenhum.
    usa_captcha: bool = False

    @abstractmethod
    def consultar(self, cpf_limpo: str) -> dict:
        """Consulta um CPF (11 dígitos, sem formatação) e devolve o resultado.

        Contrato do dicionário retornado — são estas as chaves que o resto do
        sistema entende:

        ==============  ===============  ==================================================
        chave           tipo             significado
        ==============  ===============  ==================================================
        ``cpf``         str              CPF formatado. Obrigatório.
        ``encontrado``  bool | None      ``True`` achou titular, ``False`` não há registro,
                                         ``None`` indeterminado ou erro.
        ``nome_certidao`` str            Nome do titular. É por ele que o filtro
                                         ``nome=`` das buscas em lote decide o match.
        ``erro``        str              Presente apenas quando a consulta falhou.
        ``cpf_inexistente`` bool         A fonte respondeu que este CPF não existe —
                                         diferente de existir e não ter registro.
                                         Acompanha ``encontrado=False``.
        ``mensagem``    str              Texto exibido ao usuário quando não há
                                         resultado. Use as constantes ``MSG_*``
                                         deste módulo para os casos comuns; a
                                         interface mostra como veio, sem reescrever.
        ==============  ===============  ==================================================

        Qualquer chave extra (``tipo_certidao``, ``valida_ate``, ``pdf_url``…)
        é repassada ao cliente sem interpretação.

        **Não deve levantar exceção**: falha vira
        ``{"cpf": ..., "encontrado": None, "erro": "..."}``. Quem chama roda
        centenas destas em paralelo e trata ausência de resultado, não stack
        trace.
        """
        raise NotImplementedError
