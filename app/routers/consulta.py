from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import asyncio
import json
import re
import threading
from starlette.concurrency import run_in_threadpool
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.services.cpf import is_valido, formatar, gerar_cpfs_de_mascara
from app.services.sources import consultar, consultar_multiplos
from app import config as _cfg
from app import metrics as _m

limiter = Limiter(key_func=get_remote_address)

_EXAMPLE_CPF = {
    "cpf": "151.879.820-95",
    "encontrado": True,
    "nome_certidao": "JOAO DA SILVA",
    "tipo_certidao": "NEGATIVA",
    "tem_registro": False,
    "cpf_certidao": "151.879.820-95",
    "valida_ate": "18/04/2026",
    "numero_certidao": "511684/2026",
}

_EXAMPLE_MULTIPLOS = {
    "total": 2,
    "total_consultados": 2,
    "matches": {"15187982095": _EXAMPLE_CPF},
    "resultados": {
        "15187982095": _EXAMPLE_CPF,
        "15187982176": {"cpf": "151.879.821-76", "encontrado": False, "mensagem": "Nenhum feito trabalhista encontrado."},
    },
    "erros": {},
}

_EXAMPLE_MASCARA = {
    "total": 3,
    "matches": {"15187982095": _EXAMPLE_CPF},
    "resultados": {"15187982095": _EXAMPLE_CPF},
    "candidatos_gerados": 3,
}

_EXAMPLE_VARIACOES = {
    "total": 4,
    "matches": {"15187982095": _EXAMPLE_CPF},
    "resultados": {"15187982095": _EXAMPLE_CPF},
    "candidatos_gerados": 4,
}


class CpfRequest(BaseModel):
    model_config = {"json_schema_extra": {"example": {"cpf": "151.879.820-95"}}}
    cpf: str = Field(..., description="CPF com ou sem formatação (pontos e traço opcionais)", examples=["151.879.820-95", "15187982095"])


class BuscarVariacoesRequest(BaseModel):
    model_config = {"json_schema_extra": {"example": {"cpf_parcial": "1518798209", "nome": "joao"}}}
    cpf_parcial: str = Field(..., description="CPF com 9 a 11 dígitos, podendo ter erros ou estar incompleto", examples=["1518798209", "151879820"])
    nome: str | None = Field(None, description="Fragmento do nome para filtrar os resultados (opcional, case-insensitive)", examples=["joao", "Maria Silva"])
    workers: int = Field(default=_cfg.DEFAULT_WORKERS, ge=1, le=_cfg.MAX_WORKERS, description=f"Threads paralelas de consulta à fonte (1–{_cfg.MAX_WORKERS})")
    parar_ao_confirmar: bool = Field(default=True, description="Interrompe a busca assim que um resultado confirmar o `nome` informado, em vez de varrer todos os candidatos. Sem `nome`, não tem efeito")


class FeitosMultiplosRequest(BaseModel):
    model_config = {"json_schema_extra": {"example": {"cpfs": ["151.879.820-95", "151.879.821-76"], "workers": 4}}}
    cpfs: list[str] = Field(..., description="Lista de CPFs (com ou sem formatação)", examples=[["151.879.820-95", "151.879.821-76"]])
    workers: int = Field(default=_cfg.DEFAULT_WORKERS, ge=1, le=_cfg.MAX_WORKERS, description=f"Threads paralelas de consulta à fonte (1–{_cfg.MAX_WORKERS})")


class BuscarMascaraRequest(BaseModel):
    model_config = {"json_schema_extra": {"example": {"mascara": "***.879.820-**", "nome": "joao"}}}
    mascara: str = Field(..., description=f"CPF com curingas nos dígitos desconhecidos. Aceita `*`, `X`, `x`, `?`, `_` e `#` (equivalentes) e qualquer separador — `.`, `-`, `/` ou espaço — inclusive nenhum. Os dígitos verificadores podem ser omitidos. Máximo de {_cfg.MAX_WILDCARDS_IN_MASK} curingas na parte base (posições 0–8)", examples=["15X.879.82X-95", "***.879.820-**", "151.879.___-95", "151.879.820"])
    nome: str | None = Field(None, description="Fragmento do nome para filtrar os resultados (opcional, case-insensitive)", examples=["joao", "Maria Silva"])
    workers: int = Field(default=_cfg.DEFAULT_WORKERS, ge=1, le=_cfg.MAX_WORKERS, description=f"Threads paralelas de consulta à fonte (1–{_cfg.MAX_WORKERS})")
    parar_ao_confirmar: bool = Field(default=True, description="Interrompe a busca assim que um resultado confirmar o `nome` informado, em vez de varrer todos os candidatos. Sem `nome`, não tem efeito")


# Sem prefixo aqui: main.py monta em /consulta. Os caminhos não citam a fonte,
# que é escolhida por SOURCE no .env.
router = APIRouter()


@router.post(
    "/cpf",
    summary="Confirma titularidade de um CPF",
    description=(
        "Consulta o TRT3 para confirmar a quem o CPF pertence. "
        "Resolve o CAPTCHA automaticamente via rede neural local (CRNN ~99% de acurácia). "
        "Retorna nome, tipo da certidão (NEGATIVA/POSITIVA) e validade."
    ),
    responses={200: {"content": {"application/json": {"example": _EXAMPLE_CPF}}}},
)
@limiter.limit(_cfg.RATE_LIMIT_CPF)
async def consultar_cpf(request: Request, body: CpfRequest):
    cpf_limpo = re.sub(r"\D", "", body.cpf)
    if len(cpf_limpo) != 11:
        raise HTTPException(status_code=422, detail="CPF deve ter 11 dígitos")
    if not is_valido(cpf_limpo):
        raise HTTPException(status_code=422, detail="CPF matematicamente inválido")
    result = await run_in_threadpool(consultar, cpf_limpo)
    if result.get("encontrado"):
        _m.consulta_cpf_total.labels(fonte=_cfg.SOURCE, result="found").inc()
        _m.consulta_matches_total.labels(fonte=_cfg.SOURCE, type="cpf").inc()
    elif result.get("erro"):
        _m.consulta_cpf_total.labels(fonte=_cfg.SOURCE, result="error").inc()
    else:
        _m.consulta_cpf_total.labels(fonte=_cfg.SOURCE, result="not_found").inc()
    return result


@router.post(
    "/cpfs",
    summary="Confirma titularidade de múltiplos CPFs em paralelo",
    description=(
        "Recebe uma lista de CPFs e consulta o TRT3 em paralelo usando múltiplas threads. "
        "CPFs inválidos são separados no campo `erros` sem interromper os demais. "
        "`total` conta os CPFs recebidos e `total_consultados`, os que foram de fato consultados. "
        "O campo `matches` retorna apenas os CPFs encontrados."
    ),
    responses={200: {"content": {"application/json": {"example": _EXAMPLE_MULTIPLOS}}}},
)
@limiter.limit(_cfg.RATE_LIMIT_CPFS)
async def consultar_cpfs(request: Request, body: FeitosMultiplosRequest):
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

    if erros:
        _m.cpf_bulk_invalid_total.inc(len(erros))

    if not cpfs_validos:
        return {"total": len(body.cpfs), "total_consultados": 0, "erros": erros,
                "resultados": {}, "matches": {}}

    _m.cpf_bulk_queries_total.inc()
    _m.cpf_bulk_size.observe(len(cpfs_validos))
    resultado = await run_in_threadpool(consultar_multiplos, cpfs_validos, None, body.workers)
    # "total" é sempre quantos CPFs vieram na requisição; os inválidos entram em
    # "erros" e não são consultados, então o que foi de fato consultado é
    # "total_consultados". Antes "total" significava uma coisa quando havia
    # algum CPF válido e outra quando não havia nenhum.
    resultado["total_consultados"] = resultado["total"]
    resultado["total"] = len(body.cpfs)
    resultado["erros"] = erros
    matches = len(resultado.get("matches", {}))
    if matches:
        _m.consulta_matches_total.labels(fonte=_cfg.SOURCE, type="multiplos").inc(matches)
    return resultado


@router.post(
    "/buscar-por-mascara",
    summary="Descobre CPF completo por máscara com wildcards",
    description=(
        "Recebe uma máscara de CPF com curingas nos dígitos desconhecidos, gera todas as combinações "
        "matematicamente válidas e consulta o TRT3 em paralelo. "
        "Curingas equivalentes: `*`, `X`, `x`, `?`, `_`, `#`. Separadores (`.`, `-`, `/`, espaço) são "
        "ignorados e os dígitos verificadores podem ser omitidos — `***.879.820-**`, `***879820**` e "
        "`___.879.820` são a mesma máscara. "
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

    _m.cpf_mask_searches_total.inc()
    _m.cpf_mask_candidates_total.inc(len(candidates))
    resultado = await run_in_threadpool(
        consultar_multiplos, candidates, body.nome, body.workers,
        parar_ao_confirmar=body.parar_ao_confirmar
    )
    resultado["candidatos_gerados"] = len(candidates)
    matches = len(resultado.get("matches", {}))
    if matches:
        _m.consulta_matches_total.labels(fonte=_cfg.SOURCE, type="mascara").inc(matches)
    return resultado


@router.post(
    "/buscar-por-mascara/stream",
    summary="Busca CPF por máscara com progresso em tempo real (SSE)",
    include_in_schema=False,
)
@limiter.limit(_cfg.RATE_LIMIT_MASK)
async def buscar_por_mascara_stream(request: Request, body: BuscarMascaraRequest):
    try:
        candidates = gerar_cpfs_de_mascara(body.mascara)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not candidates:
        raise HTTPException(status_code=422, detail="Nenhum CPF válido gerado pela máscara")

    _m.cpf_mask_searches_total.inc()
    _m.cpf_mask_candidates_total.inc(len(candidates))

    total = len(candidates)
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def on_progress(done: int, tot: int):
        loop.call_soon_threadsafe(q.put_nowait, {"progress": done, "total": tot})

    def on_match(result: dict):
        loop.call_soon_threadsafe(q.put_nowait, {"match": result})

    def run():
        try:
            result = consultar_multiplos(candidates, body.nome, body.workers,
                                        progress_cb=on_progress, match_cb=on_match,
                                        parar_ao_confirmar=body.parar_ao_confirmar)
            result["candidatos_gerados"] = total
            loop.call_soon_threadsafe(q.put_nowait, {"done": True, "result": result})
        except Exception as e:
            loop.call_soon_threadsafe(q.put_nowait, {"error": str(e)})

    threading.Thread(target=run, daemon=True).start()

    async def event_stream():
        yield f"data: {json.dumps({'total': total})}\n\n"
        while True:
            item = await q.get()
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            if item.get("done") or item.get("error"):
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _gerar_candidatos_variacoes(cpf_parcial: str) -> list[str]:
    cpf_limpo = re.sub(r"\D", "", cpf_parcial)
    candidates: set[str] = set()
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
    return list(candidates)


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
    if len(re.sub(r"\D", "", body.cpf_parcial)) < 9:
        raise HTTPException(status_code=422, detail="CPF parcial deve ter ao menos 9 dígitos")
    candidates = _gerar_candidatos_variacoes(body.cpf_parcial)
    if not candidates:
        raise HTTPException(status_code=422, detail="Nenhum candidato válido gerado")
    _m.cpf_variation_searches_total.inc()
    _m.cpf_variation_candidates_total.inc(len(candidates))
    resultado = await run_in_threadpool(consultar_multiplos, candidates, body.nome, body.workers,
        parar_ao_confirmar=body.parar_ao_confirmar)
    resultado["candidatos_gerados"] = len(candidates)
    matches = len(resultado.get("matches", {}))
    if matches:
        _m.consulta_matches_total.labels(fonte=_cfg.SOURCE, type="variacoes").inc(matches)
    return resultado


@router.post("/buscar-por-variacoes/stream", include_in_schema=False)
@limiter.limit(_cfg.RATE_LIMIT_VARIACOES)
async def buscar_por_variacoes_stream(request: Request, body: BuscarVariacoesRequest):
    if len(re.sub(r"\D", "", body.cpf_parcial)) < 9:
        raise HTTPException(status_code=422, detail="CPF parcial deve ter ao menos 9 dígitos")
    candidates = _gerar_candidatos_variacoes(body.cpf_parcial)
    if not candidates:
        raise HTTPException(status_code=422, detail="Nenhum candidato válido gerado")
    _m.cpf_variation_searches_total.inc()
    _m.cpf_variation_candidates_total.inc(len(candidates))

    total = len(candidates)
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def on_progress(done: int, tot: int):
        loop.call_soon_threadsafe(q.put_nowait, {"progress": done, "total": tot})

    def on_match(result: dict):
        loop.call_soon_threadsafe(q.put_nowait, {"match": result})

    def run():
        try:
            result = consultar_multiplos(candidates, body.nome, body.workers,
                                        progress_cb=on_progress, match_cb=on_match,
                                        parar_ao_confirmar=body.parar_ao_confirmar)
            result["candidatos_gerados"] = total
            loop.call_soon_threadsafe(q.put_nowait, {"done": True, "result": result})
        except Exception as e:
            loop.call_soon_threadsafe(q.put_nowait, {"error": str(e)})

    threading.Thread(target=run, daemon=True).start()

    async def event_stream():
        yield f"data: {json.dumps({'total': total})}\n\n"
        while True:
            item = await q.get()
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            if item.get("done") or item.get("error"):
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
