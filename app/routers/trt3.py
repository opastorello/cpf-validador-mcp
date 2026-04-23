from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
import re
from starlette.concurrency import run_in_threadpool
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.services.cpf import is_valido, formatar, gerar_cpfs_de_mascara
from app.services.trt3 import consultar_trt3, consultar_trt3_multiplos
from app import config as _cfg

limiter = Limiter(key_func=get_remote_address)


class CpfRequest(BaseModel):
    cpf: str


class BuscarVariacoesRequest(BaseModel):
    cpf_parcial: str
    nome: str | None = None
    workers: int = Field(default=_cfg.DEFAULT_WORKERS, ge=1, le=_cfg.MAX_WORKERS)


class FeitosMultiplosRequest(BaseModel):
    cpfs: list[str]
    workers: int = Field(default=_cfg.DEFAULT_WORKERS, ge=1, le=_cfg.MAX_WORKERS)


class BuscarMascaraRequest(BaseModel):
    mascara: str
    nome: str | None = None
    workers: int = Field(default=_cfg.DEFAULT_WORKERS, ge=1, le=_cfg.MAX_WORKERS)


router = APIRouter(prefix="/trt3", tags=["trt3"])


@router.post("/feitos")
@limiter.limit(_cfg.RATE_LIMIT_FEITOS)
async def feitos(request: Request, body: CpfRequest):
    cpf_limpo = re.sub(r"\D", "", body.cpf)
    if len(cpf_limpo) != 11:
        raise HTTPException(status_code=422, detail="CPF deve ter 11 dígitos")
    if not is_valido(cpf_limpo):
        raise HTTPException(status_code=422, detail="CPF matematicamente inválido")
    result = await run_in_threadpool(consultar_trt3, cpf_limpo)
    return result


@router.post("/buscar-por-variacoes")
@limiter.limit(_cfg.RATE_LIMIT_VARIACOES)
async def buscar_por_variacoes(request: Request, body: BuscarVariacoesRequest):
    """Consulta todas as variações válidas de um CPF parcial em paralelo."""
    cpf_limpo = re.sub(r"\D", "", body.cpf_parcial)
    if len(cpf_limpo) < 9:
        raise HTTPException(status_code=422, detail="CPF parcial deve ter ao menos 9 dígitos")

    candidates = set()
    if len(cpf_limpo) == 11:
        from app.services.cpf import generate_valid_variations
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
        raise HTTPException(status_code=422, detail="Nenhum candidato válido gerado")

    resultado = await run_in_threadpool(
        consultar_trt3_multiplos, list(candidates), body.nome, body.workers
    )
    resultado["candidatos_gerados"] = len(candidates)
    return resultado


@router.post("/feitos-multiplos")
@limiter.limit(_cfg.RATE_LIMIT_MULTIPLOS)
async def feitos_multiplos(request: Request, body: FeitosMultiplosRequest):
    """Consulta feitos trabalhistas no TRT3 para uma lista de CPFs em paralelo."""
    cpfs_validos = []
    erros = {}

    for cpf in body.cpfs:
        cpf_limpo = re.sub(r"\D", "", cpf)
        if len(cpf_limpo) != 11:
            erros[cpf] = {"erro": f"CPF deve ter 11 dígitos, recebido {len(cpf_limpo)}"}
        elif not is_valido(cpf_limpo):
            erros[cpf] = {"erro": "CPF matematicamente inválido", "cpf": formatar(cpf_limpo)}
        else:
            cpfs_validos.append(cpf_limpo)

    if not cpfs_validos:
        return {"total": len(body.cpfs), "erros": erros, "resultados": {}, "matches": {}}

    resultado = await run_in_threadpool(consultar_trt3_multiplos, cpfs_validos, None, body.workers)
    resultado["erros"] = erros
    return resultado


@router.post("/buscar-por-mascara")
@limiter.limit(_cfg.RATE_LIMIT_MASK)
async def buscar_por_mascara(request: Request, body: BuscarMascaraRequest):
    """Consulta TRT3 para todos os CPFs que encaixam na máscara com * nos dígitos desconhecidos."""
    try:
        candidates = gerar_cpfs_de_mascara(body.mascara)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not candidates:
        raise HTTPException(status_code=422, detail="Nenhum CPF válido gerado pela máscara")

    resultado = await run_in_threadpool(
        consultar_trt3_multiplos, candidates, body.nome, body.workers
    )
    resultado["candidatos_gerados"] = len(candidates)
    return resultado
