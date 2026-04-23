from fastmcp import FastMCP
import re
from starlette.concurrency import run_in_threadpool
from app.services.cpf import validate_cpf as _validate_cpf, generate_valid_variations as _generate_valid_variations, gerar_cpfs_de_mascara, is_valido, formatar
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
async def find_cpf_by_mask(mascara: str, nome: str | None = None, workers: int = 8) -> dict:
    """Descobre o CPF completo a partir de uma máscara com * nos dígitos desconhecidos.
    Gera todas as combinações válidas e consulta o TRT3 em paralelo.
    Se 'nome' for informado, filtra pelo nome na certidão.

    Args:
        mascara: CPF com * nos dígitos desconhecidos. Ex: '***.587.570-**', '382.***.570-**'
        nome: nome ou parte do nome para filtrar (ex: 'Italvino Rebelatto')
        workers: número de threads paralelas (padrão 8)
    """
    try:
        candidates = gerar_cpfs_de_mascara(mascara)
    except ValueError as e:
        return {"erro": str(e)}

    if not candidates:
        return {"erro": "Nenhum CPF válido gerado pela máscara", "mascara": mascara}

    resultado = await run_in_threadpool(consultar_trt3_multiplos, candidates, nome, workers)
    resultado["candidatos_gerados"] = len(candidates)
    return resultado


@mcp.tool
async def find_cpf_by_variations(cpf_parcial: str, nome: str | None = None, workers: int = 8) -> dict:
    """Dado um CPF parcial ou com erros, gera todas as variações matematicamente válidas
    e consulta o TRT3 em paralelo. Se 'nome' for informado, filtra os resultados pelo
    nome na certidão — útil para identificar o CPF correto de uma pessoa.

    Args:
        cpf_parcial: CPF com dígitos faltando ou errados (aceita 10 ou 11 dígitos)
        nome: nome ou parte do nome para filtrar (ex: 'nicolas', 'pastorello')
        workers: número de threads paralelas (padrão 8)
    """
    from app.services.cpf import generate_valid_variations

    cpf_limpo = re.sub(r"\D", "", cpf_parcial)

    # Gera candidatos: se 11 dígitos usa variações normais, se 10 insere dígito em cada posição
    candidates = set()

    if len(cpf_limpo) == 11:
        result = generate_valid_variations(cpf_limpo)
        candidates = {v["cpf_numeros"] for v in result.get("variations", [])}
    else:
        # 10 dígitos: inserir dígito + trocar dígito
        base = cpf_limpo
        for pos in range(11):
            for digit in "0123456789":
                c = base[:pos] + digit + base[pos:]
                if is_valido(c):
                    candidates.add(c)
        for wrong_pos in range(len(base)):
            for wrong_digit in "0123456789":
                if wrong_digit == base[wrong_pos]:
                    continue
                modified = base[:wrong_pos] + wrong_digit + base[wrong_pos + 1:]
                for pos in range(11):
                    for digit in "0123456789":
                        c = modified[:pos] + digit + modified[pos:]
                        if is_valido(c):
                            candidates.add(c)

    if not candidates:
        return {"erro": "Nenhum candidato válido gerado", "cpf_parcial": cpf_parcial}

    resultado = await run_in_threadpool(
        consultar_trt3_multiplos, list(candidates), nome, workers
    )
    resultado["candidatos_gerados"] = len(candidates)
    return resultado


@mcp.tool
async def check_multiple_cpfs(cpfs: list[str], workers: int = 8) -> dict:
    """Consulta feitos trabalhistas no TRT3 para uma lista de CPFs em paralelo.
    Valida cada CPF antes de consultar e agrupa erros de validação separadamente.

    Args:
        cpfs: lista de CPFs (aceita com ou sem formatação)
        workers: número de threads paralelas (padrão 8)
    """
    cpfs_validos = []
    erros = {}

    for cpf in cpfs:
        cpf_limpo = re.sub(r"\D", "", cpf)
        if len(cpf_limpo) != 11:
            erros[cpf] = {"erro": f"CPF deve ter 11 dígitos, recebido {len(cpf_limpo)}"}
        elif not is_valido(cpf_limpo):
            erros[cpf] = {"erro": "CPF matematicamente inválido", "cpf": formatar(cpf_limpo)}
        else:
            cpfs_validos.append(cpf_limpo)

    if not cpfs_validos:
        return {"total": len(cpfs), "erros": erros, "resultados": {}, "matches": {}}

    resultado = await run_in_threadpool(consultar_trt3_multiplos, cpfs_validos, None, workers)
    resultado["erros"] = erros
    return resultado
