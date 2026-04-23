import json
import os
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/history", tags=["history"])

_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "history.json")
_lock = threading.Lock()


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


class SaveRequest(BaseModel):
    cpf: str
    nome: str | None = None
    numero_certidao: str | None = None
    duracao_segundos: float | None = None


@router.post("/save")
def save(entry: SaveRequest):
    key = entry.cpf.replace(".", "").replace("-", "")
    now = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()
    with _lock:
        data = _load()
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


@router.get("/")
def get_all():
    with _lock:
        data = _load()
    entries = sorted(data.values(), key=lambda x: x.get("ultima_consulta", ""), reverse=True)
    return {"entries": entries, "total": len(entries)}


@router.delete("/")
def clear_all():
    with _lock:
        _persist({})
    return {"ok": True}


@router.delete("/{cpf_raw}")
def delete_entry(cpf_raw: str):
    key = cpf_raw.replace(".", "").replace("-", "")
    with _lock:
        data = _load()
        data.pop(key, None)
        _persist(data)
    return {"ok": True}
