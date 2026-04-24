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

_EXAMPLE_FEITO = {
    "cpf": "529.982.247-25",
    "encontrado": True,
    "nome_certidao": "JOAO DA SILVA",
    "tipo_certidao": "NEGATIVA",
    "tem_feitos": False,
    "cpf_certidao": "529.982.247-25",
    "valida_ate": "18/04/2026",
    "numero_certidao": "511684/2026",
}

_EXAMPLE_MULTIPLOS = {
    "total": 2,
    "matches": {"52998224725": _EXAMPLE_FEITO},
    "resultados": {
        "52998224725": _EXAMPLE_FEITO,
        "11144477735": {"cpf": "111.444.777-35", "encontrado": False, "mensagem": "Nenhum feito trabalhista encontrado."},
    },
    "erros": {},
}

_EXAMPLE_MASCARA = {
    "total": 3,
    "matches": {"52998224725": _EXAMPLE_FEITO},
    "resultados": {"52998224725": _EXAMPLE_FEITO},
    "candidatos_gerados": 3,
}

_EXAMPLE_VARIACOES = {
    "total": 4,
    "matches": {"52998224725": _EXAMPLE_FEITO},
    "resultados": {"52998224725": _EXAMPLE_FEITO},
    "candidatos_gerados": 4,
}


class CpfRequest(BaseModel):
    model_config = {"json_schema_extra": {"example": {"cpf": "529.982.247-25"}}}
    cpf: str = Field(..., description="CPF com ou sem formatação (pontos e traço opcionais)", examples=["529.982.247-25", "52998224725"])


class BuscarVariacoesRequest(BaseModel):
    model_config = {"json_schema_extra": {"example": {"cpf_parcial": "5299824725", "nome": "joao"}}}
    cpf_parcial: str = Field(..., description="CPF com 9 a 11 dígitos, podendo ter erros ou estar incompleto", examples=["5299824725", "529982247"])
    nome: str | None = Field(None, description="Fragmento do nome para filtrar os resultados (opcional, case-insensitive)", examples=["joao", "Maria Silva"])
    workers: int = Field(default=_cfg.DEFAULT_WORKERS, ge=1, le=_cfg.MAX_WORKERS, description=f"Threads paralelas para consulta ao TRT3 (1–{_cfg.MAX_WORKERS})")


class FeitosMultiplosRequest(BaseModel):
    model_config = {"json_schema_extra": {"example": {"cpfs": ["529.982.247-25", "111.444.777-35"], "workers": 4}}}
    cpfs: list[str] = Field(..., description="Lista de CPFs (com ou sem formatação)", examples=[["529.982.247-25", "111.444.777-35"]])
    workers: int = Field(default=_cfg.DEFAULT_WORKERS, ge=1, le=_cfg.MAX_WORKERS, description=f"Threads paralelas para consulta ao TRT3 (1–{_cfg.MAX_WORKERS})")


class BuscarMascaraRequest(BaseModel):
    model_config = {"json_schema_extra": {"example": {"mascara": "***.982.247-**", "nome": "joao"}}}
    mascara: str = Field(..., description="CPF com wildcards nos dígitos desconhecidos. Aceita `*`, `X`, `x` ou `?`. Máximo de 5 wildcards na parte base (posições 0–8)", examples=["11X.593.91X-00", "***.982.247-**", "529.982.***-**"])
    nome: str | None = Field(None, description="Fragmento do nome para filtrar os resultados (opcional, case-insensitive)", examples=["joao", "Maria Silva"])
    workers: int = Field(default=_cfg.DEFAULT_WORKERS, ge=1, le=_cfg.MAX_WORKERS, description=f"Threads paralelas para consulta ao TRT3 (1–{_cfg.MAX_WORKERS})")


router = APIRouter(prefix="/trt3", tags=["trt3"])


@router.post(
    "/feitos",
    summary="Confirma titularidade de um CPF",
    description=(
        "Consulta o TRT3 para confirmar a quem o CPF pertence. "
        "Resolve o CAPTCHA automaticamente via rede neural local (CRNN ~99% de acurácia). "
        "Retorna nome, tipo da certidão (NEGATIVA/POSITIVA) e validade."
    ),
    responses={200: {"content": {"application/json": {"example": _EXAMPLE_FEITO}}}},
)
@limiter.limit(_cfg.RATE_LIMIT_FEITOS)
async def feitos(request: Request, body: CpfRequest):
    cpf_limpo = re.sub(r"\D", "", body.cpf)
    if len(cpf_limpo) != 11:
        raise HTTPException(status_code=422, detail="CPF deve ter 11 dígitos")
    if not is_valido(cpf_limpo):
        raise HTTPException(status_code=422, detail="CPF matematicamente inválido")
    result = await run_in_threadpool(consultar_trt3, cpf_limpo)
    return result


@router.post(
    "/feitos-multiplos",
    summary="Confirma titularidade de múltiplos CPFs em paralelo",
    description=(
        "Recebe uma lista de CPFs e consulta o TRT3 em paralelo usando múltiplas threads. "
        "CPFs inválidos são separados no campo `erros` sem interromper os demais. "
        "O campo `matches` retorna apenas os CPFs encontrados."
    ),
    responses={200: {"content": {"application/json": {"example": _EXAMPLE_MULTIPLOS}}}},
)
@limiter.limit(_cfg.RATE_LIMIT_MULTIPLOS)
async def feitos_multiplos(request: Request, body: FeitosMultiplosRequest):
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


@router.post(
    "/buscar-por-mascara",
    summary="Descobre CPF completo por máscara com wildcards",
    description=(
        "Recebe uma máscara de CPF com `*` nos dígitos desconhecidos, gera todas as combinações "
        "matematicamente válidas e consulta o TRT3 em paralelo. "
        "Se `nome` for informado, filtra somente os resultados que contenham o nome. "
        f"Máximo de {_cfg.MAX_WILDCARDS_IN_MASK} wildcards na parte base (posições 0–8) para evitar explosão combinatória."
    ),
    responses={200: {"content": {"application/json": {"example": _EXAMPLE_MASCARA}}}},
)
@limiter.limit(_cfg.RATE_LIMIT_MASK)
async def buscar_por_mascara(request: Request, body: BuscarMascaraRequest):
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


@router.post(
    "/buscar-por-variacoes",
    summary="Recupera CPF correto a partir de dígitos errados ou incompletos",
    description=(
        "Recebe um CPF parcial ou com erros (9 a 11 dígitos), gera todos os candidatos válidos "
        "aplicando as estratégias: inserção de dígito, troca de dígito e transposição. "
        "Consulta o TRT3 em paralelo e filtra pelo nome quando informado. "
        "Ideal para recuperar um CPF com um dígito faltando ou digitado errado."
    ),
    responses={200: {"content": {"application/json": {"example": _EXAMPLE_VARIACOES}}}},
)
@limiter.limit(_cfg.RATE_LIMIT_VARIACOES)
async def buscar_por_variacoes(request: Request, body: BuscarVariacoesRequest):
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
