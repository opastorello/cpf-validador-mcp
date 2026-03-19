"""
Registro de versões de modelos treinados.

Estrutura em disco:
  app/captcha/models/
    v1/
      model.pt
      meta.json
    v2/
      model.pt
      meta.json
    ...
  app/captcha/captcha_model.pt  ← sempre aponta para o melhor de todos os tempos
  app/captcha/models/registry.json  ← índice de todas as versões
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

_MODELS_DIR = Path(__file__).parent / "models"
_REGISTRY_FILE = _MODELS_DIR / "registry.json"
_ACTIVE_MODEL = Path(__file__).parent / "captcha_model.pt"


def _load_registry() -> list[dict]:
    if not _REGISTRY_FILE.exists():
        return []
    return json.loads(_REGISTRY_FILE.read_text(encoding="utf-8"))


def _save_registry(entries: list[dict]) -> None:
    _MODELS_DIR.mkdir(exist_ok=True)
    _REGISTRY_FILE.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def next_version() -> int:
    entries = _load_registry()
    return max((e["version"] for e in entries), default=0) + 1


def save_version(
    model_src: Path,
    version: int,
    val_accuracy: float,
    val_loss: float,
    epochs_trained: int,
    samples: int,
    batch_size: int,
    lr: float,
) -> Path:
    """Copia o model.pt para models/vN/ e registra os metadados."""
    version_dir = _MODELS_DIR / f"v{version}"
    version_dir.mkdir(parents=True, exist_ok=True)

    dest = version_dir / "model.pt"
    shutil.copy2(model_src, dest)

    meta = {
        "version": version,
        "date": datetime.now(timezone.utc).isoformat(),
        "val_accuracy": round(val_accuracy, 6),
        "val_loss": round(val_loss, 6),
        "epochs_trained": epochs_trained,
        "samples": samples,
        "batch_size": batch_size,
        "lr": lr,
        "model_path": f"models/v{version}/model.pt",
    }
    (version_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    entries = _load_registry()
    entries.append(meta)
    _save_registry(entries)

    return dest


def promote_if_best(version: int, val_accuracy: float) -> bool:
    """Copia vN/model.pt para captcha_model.pt se for o melhor val_accuracy já registrado."""
    entries = _load_registry()
    all_accs = [e["val_accuracy"] for e in entries if e["version"] != version]
    if not all_accs or val_accuracy >= max(all_accs):
        src = _MODELS_DIR / f"v{version}" / "model.pt"
        shutil.copy2(src, _ACTIVE_MODEL)
        return True
    return False


def list_versions() -> list[dict]:
    return _load_registry()


def print_registry() -> None:
    entries = _load_registry()
    if not entries:
        print("Nenhuma versão registrada.")
        return
    print(f"\n{'Ver':>4}  {'Data':>20}  {'Amostras':>8}  {'Epochs':>6}  {'Batch':>5}  {'LR':>6}  {'val_acc':>8}  {'val_loss':>9}")
    print("-" * 80)
    best_acc = max(e["val_accuracy"] for e in entries)
    for e in entries:
        marker = " *" if e["val_accuracy"] == best_acc else "  "
        print(
            f"{e['version']:>4}  "
            f"{e['date'][:19]:>20}  "
            f"{e['samples']:>8}  "
            f"{e['epochs_trained']:>6}  "
            f"{e['batch_size']:>5}  "
            f"{e['lr']:>6}  "
            f"{e['val_accuracy']:>8.4f}  "
            f"{e['val_loss']:>9.4f}"
            f"{marker}"
        )
    print("\n* melhor modelo (ativo em captcha_model.pt)")


if __name__ == "__main__":
    print_registry()
