from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.cpf import validate_cpf, generate_valid_variations


class CpfRequest(BaseModel):
    cpf: str


router = APIRouter(prefix="/cpf", tags=["cpf"])


@router.post("/validate")
def validate(body: CpfRequest):
    result = validate_cpf(body.cpf)
    if not result.get("cpf_numeros") or len(result["cpf_numeros"]) != 11:
        raise HTTPException(status_code=422, detail=result.get("mensagem", "CPF inválido"))
    if not result.get("valido"):
        raise HTTPException(status_code=422, detail=result.get("mensagem", "CPF inválido"))
    return result


@router.post("/variations")
def variations(body: CpfRequest):
    result = generate_valid_variations(body.cpf)
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    return result
