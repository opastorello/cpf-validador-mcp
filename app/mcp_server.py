from fastmcp import FastMCP
import re
from starlette.concurrency import run_in_threadpool
from app.services.cpf import validate_cpf as _validate_cpf, generate_valid_variations as _generate_valid_variations, is_valido, formatar
from app.services.trt3 import consultar_trt3, consultar_trt3_multiplos

mcp = FastMCP("cpf-validador")


@mcp.tool
def validate_cpf(cpf: str) -> dict:
    """Valida se um CPF é matematicamente válido (dígitos verificadores corretos)."""
    return _validate_cpf(cpf)


@mcp.tool
def generate_valid_variations(cpf: str) -> dict:
    """Gera variações matematicamente válidas de um CPF possivelmente errado.
    Estratégias: original, recalcula dígitos verificadores, troca 1 dígito (posições 0-8), transpõe pares adjacentes."""
    return _generate_valid_variations(cpf)


@mcp.tool
async def check_feitos_trabalhistas(cpf: str) -> dict:
    """Consulta feitos trabalhistas no TRT 3ª Região (certidao.trt3.jus.br).
    Valida o CPF, resolve captcha automaticamente e retorna o resultado da certidão."""
    cpf_limpo = re.sub(r"\D", "", cpf)
    if len(cpf_limpo) != 11:
        return {"erro": f"CPF deve ter 11 dígitos, recebido {len(cpf_limpo)}"}
    if not is_valido(cpf_limpo):
        return {"erro": "CPF matematicamente inválido", "cpf": formatar(cpf_limpo)}
    return await run_in_threadpool(consultar_trt3, cpf_limpo)


@mcp.tool
async def find_cpf_by_variations(cpf_parcial: str, nome: str | None = None) -> dict:
    """Dado um CPF parcial ou com erros, gera todas as variações matematicamente válidas
    e consulta o TRT3 em paralelo. Se 'nome' for informado, filtra os resultados pelo
    nome na certidão — útil para identificar o CPF correto de uma pessoa.

    Args:
        cpf_parcial: CPF com dígitos faltando ou errados (aceita 10 ou 11 dígitos)
        nome: nome ou parte do nome para filtrar (ex: 'nicolas', 'pastorello')
    """
    from app.services.cpf import generate_valid_variations

    cpf_limpo = re.sub(r"\D", "", cpf_parcial)

    # Gera candidatos: se 11 dígitos usa variações normais, se 10 insere dígito em cada posição
    candidates = set()

    def _valid(d):
        if len(d) != 11:
            return False
        s = sum(int(d[i]) * (10 - i) for i in range(9))
        r = s % 11
        d1 = 0 if r < 2 else 11 - r
        if int(d[9]) != d1:
            return False
        s = sum(int(d[i]) * (11 - i) for i in range(10))
        r = s % 11
        d2 = 0 if r < 2 else 11 - r
        return int(d[10]) == d2

    if len(cpf_limpo) == 11:
        result = generate_valid_variations(cpf_limpo)
        candidates = {v["cpf_numeros"] for v in result.get("variations", [])}
    else:
        # 10 dígitos: inserir dígito + trocar dígito
        base = cpf_limpo
        for pos in range(11):
            for digit in "0123456789":
                c = base[:pos] + digit + base[pos:]
                if _valid(c):
                    candidates.add(c)
        for wrong_pos in range(len(base)):
            for wrong_digit in "0123456789":
                if wrong_digit == base[wrong_pos]:
                    continue
                modified = base[:wrong_pos] + wrong_digit + base[wrong_pos + 1:]
                for pos in range(11):
                    for digit in "0123456789":
                        c = modified[:pos] + digit + modified[pos:]
                        if _valid(c):
                            candidates.add(c)

    if not candidates:
        return {"erro": "Nenhum candidato válido gerado", "cpf_parcial": cpf_parcial}

    resultado = await run_in_threadpool(
        consultar_trt3_multiplos, list(candidates), nome, 8
    )
    resultado["candidatos_gerados"] = len(candidates)
    return resultado
