from fastmcp import FastMCP
import re
from starlette.concurrency import run_in_threadpool
from app.services.cpf import validate_cpf as _validate_cpf, generate_valid_variations as _generate_valid_variations, gerar_cpfs_de_mascara, is_valido, formatar
from app.services.trt3 import consultar_trt3, consultar_trt3_multiplos
from app import metrics as _m

mcp = FastMCP("cpf-validador")


@mcp.tool
def validate_cpf(cpf: str) -> dict:
    """Valida se um CPF é matematicamente válido (dígitos verificadores corretos)."""
    result = _validate_cpf(cpf)
    label = "valid" if result.get("valido") else "invalid"
    _m.trt3_mcp_calls_total.labels(tool="validate_cpf", result=label).inc()
    return result


@mcp.tool
def generate_valid_variations(cpf: str) -> dict:
    """Gera variações matematicamente válidas de um CPF possivelmente errado.
    Estratégias: original, recalcula dígitos verificadores, troca 1 dígito (posições 0-8), transpõe pares adjacentes."""
    result = _generate_valid_variations(cpf)
    if "error" in result:
        _m.trt3_mcp_calls_total.labels(tool="generate_valid_variations", result="invalid").inc()
    else:
        _m.trt3_mcp_calls_total.labels(tool="generate_valid_variations", result="success").inc()
        _m.cpf_variations_generated_total.inc(result.get("total_variacoes", 0))
    return result


@mcp.tool
async def check_feitos_trabalhistas(cpf: str) -> dict:
    """Consulta feitos trabalhistas no TRT 3ª Região (certidao.trt3.jus.br).
    Valida o CPF, resolve captcha automaticamente e retorna o resultado da certidão."""
    cpf_limpo = re.sub(r"\D", "", cpf)
    if len(cpf_limpo) != 11:
        _m.trt3_mcp_calls_total.labels(tool="check_feitos_trabalhistas", result="invalid").inc()
        return {"erro": f"CPF deve ter 11 dígitos, recebido {len(cpf_limpo)}"}
    if not is_valido(cpf_limpo):
        _m.trt3_mcp_calls_total.labels(tool="check_feitos_trabalhistas", result="invalid").inc()
        return {"erro": "CPF matematicamente inválido", "cpf": formatar(cpf_limpo)}
    result = await run_in_threadpool(consultar_trt3, cpf_limpo)
    if result.get("encontrado"):
        _m.trt3_mcp_calls_total.labels(tool="check_feitos_trabalhistas", result="found").inc()
        _m.trt3_matches_total.labels(type="mcp_feitos").inc()
    elif result.get("erro"):
        _m.trt3_mcp_calls_total.labels(tool="check_feitos_trabalhistas", result="error").inc()
    else:
        _m.trt3_mcp_calls_total.labels(tool="check_feitos_trabalhistas", result="not_found").inc()
    return result


@mcp.tool
async def find_cpf_by_mask(mascara: str, nome: str | None = None, workers: int = 8) -> dict:
    """Descobre o CPF completo a partir de uma máscara com curingas nos dígitos desconhecidos.
    Gera todas as combinações matematicamente válidas e consulta o TRT3 em paralelo.
    Se 'nome' for informado, filtra somente os resultados que contenham o nome na certidão.

    Args:
        mascara: CPF com curingas nos dígitos desconhecidos. Curingas equivalentes: * X x ? _ #
            Separadores (. - / espaço) são ignorados e os dígitos verificadores podem ser omitidos,
            então '***.444.777-**', '***444777**', '___.444.777-__' e '***.444.777' são a mesma máscara.
            Ex: '11X.593.91X-00', '***.587.570-**', '111.444.777'
        nome: nome ou parte do nome para filtrar (ex: 'Italvino Rebelatto')
        workers: número de threads paralelas (padrão 8)
    """
    workers = max(1, min(workers, 20))
    try:
        candidates = gerar_cpfs_de_mascara(mascara)
    except ValueError as e:
        _m.trt3_mcp_calls_total.labels(tool="find_cpf_by_mask", result="invalid").inc()
        return {"erro": str(e)}

    if not candidates:
        _m.trt3_mcp_calls_total.labels(tool="find_cpf_by_mask", result="invalid").inc()
        return {"erro": "Nenhum CPF válido gerado pela máscara", "mascara": mascara}

    _m.cpf_mask_searches_total.inc()
    _m.cpf_mask_candidates_total.inc(len(candidates))
    resultado = await run_in_threadpool(consultar_trt3_multiplos, candidates, nome, workers)
    resultado["candidatos_gerados"] = len(candidates)
    matches = len(resultado.get("matches", {}))
    _m.trt3_mcp_calls_total.labels(tool="find_cpf_by_mask", result="success" if matches else "not_found").inc()
    if matches:
        _m.trt3_matches_total.labels(type="mcp_mascara").inc(matches)
    return resultado


@mcp.tool
async def find_cpf_by_variations(cpf_parcial: str, nome: str | None = None, workers: int = 8) -> dict:
    """Dado um CPF parcial ou com erros, encontra o CPF correto filtrando pelo nome.
    Gera todas as variações matematicamente válidas e consulta o TRT3 em paralelo.
    Ideal para recuperar um CPF com um dígito faltando ou digitado errado.

    Args:
        cpf_parcial: CPF com dígitos faltando ou errados (9 a 11 dígitos)
        nome: nome ou parte do nome para filtrar (ex: 'nicolas', 'pastorello')
        workers: número de threads paralelas (padrão 8)
    """
    workers = max(1, min(workers, 20))
    from app.services.cpf import generate_valid_variations

    cpf_limpo = re.sub(r"\D", "", cpf_parcial)

    candidates = set()

    if len(cpf_limpo) == 11:
        result = generate_valid_variations(cpf_limpo)
        candidates = {v["cpf_numeros"] for v in result.get("variations", [])}
    else:
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
        _m.trt3_mcp_calls_total.labels(tool="find_cpf_by_variations", result="invalid").inc()
        return {"erro": "Nenhum candidato válido gerado", "cpf_parcial": cpf_parcial}

    _m.cpf_variation_searches_total.inc()
    _m.cpf_variation_candidates_total.inc(len(candidates))
    resultado = await run_in_threadpool(
        consultar_trt3_multiplos, list(candidates), nome, workers
    )
    resultado["candidatos_gerados"] = len(candidates)
    matches = len(resultado.get("matches", {}))
    _m.trt3_mcp_calls_total.labels(tool="find_cpf_by_variations", result="success" if matches else "not_found").inc()
    if matches:
        _m.trt3_matches_total.labels(type="mcp_variacoes").inc(matches)
    return resultado


@mcp.tool
async def check_multiple_cpfs(cpfs: list[str], workers: int = 8) -> dict:
    """Valida e confirma titularidade de uma lista de CPFs em paralelo consultando o TRT3.
    CPFs inválidos são agrupados no campo 'erros' sem interromper os demais.

    Args:
        cpfs: lista de CPFs (aceita com ou sem formatação)
        workers: número de threads paralelas (padrão 8)
    """
    workers = max(1, min(workers, 20))
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

    if erros:
        _m.cpf_bulk_invalid_total.inc(len(erros))

    if not cpfs_validos:
        _m.trt3_mcp_calls_total.labels(tool="check_multiple_cpfs", result="invalid").inc()
        return {"total": len(cpfs), "erros": erros, "resultados": {}, "matches": {}}

    _m.cpf_bulk_queries_total.inc()
    _m.cpf_bulk_size.observe(len(cpfs_validos))
    resultado = await run_in_threadpool(consultar_trt3_multiplos, cpfs_validos, None, workers)
    resultado["erros"] = erros
    matches = len(resultado.get("matches", {}))
    _m.trt3_mcp_calls_total.labels(tool="check_multiple_cpfs", result="success" if matches else "not_found").inc()
    if matches:
        _m.trt3_matches_total.labels(type="mcp_multiplos").inc(matches)
    return resultado
