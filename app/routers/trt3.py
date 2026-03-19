from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import re
from starlette.concurrency import run_in_threadpool
from app.services.cpf import is_valido
from app.services.trt3 import consultar_trt3, consultar_trt3_multiplos


class CpfRequest(BaseModel):
    cpf: str


class BuscarVariacoesRequest(BaseModel):
    cpf_parcial: str
    nome: str | None = None
    workers: int = 8


router = APIRouter(prefix="/trt3", tags=["trt3"])


@router.post("/feitos")
async def feitos(body: CpfRequest):
    cpf_limpo = re.sub(r"\D", "", body.cpf)
    if len(cpf_limpo) != 11:
        raise HTTPException(status_code=422, detail="CPF deve ter 11 dígitos")
    if not is_valido(cpf_limpo):
        raise HTTPException(status_code=422, detail="CPF matematicamente inválido")
    result = await run_in_threadpool(consultar_trt3, cpf_limpo)
    return result


@router.post("/buscar-por-variacoes")
async def buscar_por_variacoes(body: BuscarVariacoesRequest):
    """Consulta todas as variações válidas de um CPF parcial em paralelo.
    Se 'nome' for informado, retorna apenas os matches com aquele nome na certidão."""
    cpf_limpo = re.sub(r"\D", "", body.cpf_parcial)
    if len(cpf_limpo) < 9:
        raise HTTPException(status_code=422, detail="CPF parcial deve ter ao menos 9 dígitos")

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
        raise HTTPException(status_code=422, detail="Nenhum candidato válido gerado")

    resultado = await run_in_threadpool(
        consultar_trt3_multiplos, list(candidates), body.nome, body.workers
    )
    resultado["candidatos_gerados"] = len(candidates)
    return resultado
