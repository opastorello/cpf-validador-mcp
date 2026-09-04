from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.cpf import validate_cpf, generate_valid_variations
from app import metrics as _m


class CpfRequest(BaseModel):
    model_config = {"json_schema_extra": {"example": {"cpf": "111.444.777-35"}}}
    cpf: str = Field(..., description="CPF com ou sem formatação", examples=["111.444.777-35", "11144477735"])


router = APIRouter(prefix="/cpf", tags=["cpf"])


@router.post(
    "/validate",
    summary="Valida um CPF matematicamente",
    description="Verifica se o CPF é válido pelo algoritmo módulo-11 (dígitos verificadores). Não consulta nenhum serviço externo.",
    responses={200: {"content": {"application/json": {"example": {
        "valido": True,
        "cpf_formatado": "111.444.777-35",
        "cpf_numeros": "11144477735",
        "mensagem": "CPF válido.",
    }}}}},
)
def validate(body: CpfRequest):
    result = validate_cpf(body.cpf)
    if not result.get("cpf_numeros") or len(result["cpf_numeros"]) != 11:
        _m.cpf_validations_total.labels(result="invalid").inc()
        raise HTTPException(status_code=422, detail=result.get("mensagem", "CPF inválido"))
    if not result.get("valido"):
        _m.cpf_validations_total.labels(result="invalid").inc()
        raise HTTPException(status_code=422, detail=result.get("mensagem", "CPF inválido"))
    _m.cpf_validations_total.labels(result="valid").inc()
    return result


@router.post(
    "/variations",
    summary="Gera variações válidas de um CPF",
    description=(
        "Gera todas as variações matematicamente válidas a partir de um CPF possivelmente errado. "
        "Estratégias: recalcula os dígitos verificadores, troca 1 dígito (posições 0–8) e "
        "transpõe pares adjacentes. Útil para recuperar um CPF com um dígito digitado errado."
    ),
    responses={200: {"content": {"application/json": {"example": {
        "original": "11144477735",
        "original_valido": True,
        "total_variacoes": 2,
        "variations": [
            {"cpf_numeros": "11144477735", "cpf_formatado": "111.444.777-35"},
            {"cpf_numeros": "11154477770", "cpf_formatado": "111.544.777-70"},
        ],
    }}}}},
)
def variations(body: CpfRequest):
    result = generate_valid_variations(body.cpf)
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    _m.cpf_variations_generated_total.inc(result["total_variacoes"])
    return result
