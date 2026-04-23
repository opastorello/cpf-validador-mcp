import json
import os
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Path
from pydantic import BaseModel, Field

from app import config as _cfg

router = APIRouter(prefix="/history", tags=["history"])

_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "history.json")
_lock = threading.Lock()
_RETENTION_DAYS = _cfg.HISTORY_RETENTION_DAYS
_TZ = ZoneInfo(_cfg.APP_TIMEZONE)

_EXAMPLE_ENTRY = {
    "cpf": "529.982.247-25",
    "nome": "JOAO DA SILVA",
    "numero_certidao": "511684/2026",
    "consultas": 3,
    "primeira_consulta": "2026-04-20T10:30:00-03:00",
    "ultima_consulta": "2026-04-23T14:22:10-03:00",
    "ultima_duracao_s": 4.2,
}


def _load() -> dict:
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    if not os.path.exists(_FILE):
        return {}
    with open(_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _persist(data: dict):
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _purge_old(data: dict) -> dict:
    if _RETENTION_DAYS <= 0:
        return data
    cutoff = (datetime.now(_TZ) - timedelta(days=_RETENTION_DAYS)).isoformat()
    return {k: v for k, v in data.items() if v.get("ultima_consulta", "") >= cutoff}


class SaveRequest(BaseModel):
    model_config = {"json_schema_extra": {"example": {"cpf": "529.982.247-25", "nome": "JOAO DA SILVA", "numero_certidao": "511684/2026", "duracao_segundos": 4.2}}}
    cpf: str = Field(..., description="CPF consultado (com ou sem formatação)", examples=["529.982.247-25"])
    nome: str | None = Field(None, description="Nome retornado pela certidão do TRT3", examples=["JOAO DA SILVA"])
    numero_certidao: str | None = Field(None, description="Número da certidão emitida pelo TRT3", examples=["511684/2026"])
    duracao_segundos: float | None = Field(None, description="Tempo de resposta da consulta em segundos", examples=[4.2])


@router.post(
    "/save",
    summary="Salva ou atualiza uma entrada no histórico",
    description="Registra a consulta de um CPF no histórico server-side. Se o CPF já existe, incrementa o contador e atualiza nome, número da certidão e duração. Entradas são retidas por `HISTORY_RETENTION_DAYS` dias.",
    responses={200: {"content": {"application/json": {"example": {"ok": True}}}}},
)
def save(entry: SaveRequest):
    key = entry.cpf.replace(".", "").replace("-", "")
    now = datetime.now(_TZ).isoformat()
    with _lock:
        data = _purge_old(_load())
        if key in data:
            data[key]["consultas"] += 1
            data[key]["ultima_consulta"] = now
            if entry.nome:
                data[key]["nome"] = entry.nome
            if entry.numero_certidao:
                data[key]["numero_certidao"] = entry.numero_certidao
            if entry.duracao_segundos is not None:
                data[key]["ultima_duracao_s"] = round(entry.duracao_segundos, 1)
        else:
            data[key] = {
                "cpf": entry.cpf,
                "nome": entry.nome,
                "numero_certidao": entry.numero_certidao,
                "consultas": 1,
                "primeira_consulta": now,
                "ultima_consulta": now,
                "ultima_duracao_s": round(entry.duracao_segundos, 1) if entry.duracao_segundos else None,
            }
        _persist(data)
    return {"ok": True}


@router.get(
    "/",
    summary="Lista o histórico de consultas",
    description="Retorna todas as entradas do histórico server-side, ordenadas pela consulta mais recente. Entradas expiradas pelo período de retenção são removidas automaticamente.",
    responses={200: {"content": {"application/json": {"example": {"entries": [_EXAMPLE_ENTRY], "total": 1}}}}},
)
def get_all():
    with _lock:
        data = _purge_old(_load())
    entries = sorted(data.values(), key=lambda x: x.get("ultima_consulta", ""), reverse=True)
    return {"entries": entries, "total": len(entries)}


@router.delete(
    "/",
    summary="Limpa todo o histórico",
    description="Remove permanentemente todas as entradas do histórico server-side.",
    responses={200: {"content": {"application/json": {"example": {"ok": True}}}}},
)
def clear_all():
    with _lock:
        _persist({})
    return {"ok": True}


@router.delete(
    "/{cpf_raw}",
    summary="Remove uma entrada do histórico",
    description="Remove do histórico a entrada correspondente ao CPF informado (com ou sem pontuação).",
    responses={200: {"content": {"application/json": {"example": {"ok": True}}}}},
)
def delete_entry(
    cpf_raw: str = Path(..., description="CPF a remover (com ou sem formatação)", example="529.982.247-25"),
):
    key = cpf_raw.replace(".", "").replace("-", "")
    with _lock:
        data = _load()
        data.pop(key, None)
        _persist(data)
    return {"ok": True}
