import io
from pathlib import Path

import torch
import torchvision.transforms as T
from PIL import Image

from app import config as _cfg
from app.captcha.model import IMG_H, IMG_W, CaptchaModel, decode_greedy

_custom = _cfg.CAPTCHA_MODEL_PATH
MODEL_PATH = Path(_custom) if _custom else Path(__file__).parent / "captcha_model.pt"

_model: CaptchaModel | None = None

_transform = T.Compose([
    T.Grayscale(),
    T.Resize((IMG_H, IMG_W)),
    T.ToTensor(),
    T.Normalize(mean=[0.5], std=[0.5]),
])


def _load_model() -> CaptchaModel:
    global _model
    if _model is not None:
        return _model
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Modelo não encontrado: {MODEL_PATH}. Rode: python -m app.captcha.train")
    m = CaptchaModel()
    m.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
    m.eval()
    _model = m
    return _model


def predict(image_bytes: bytes) -> str:
    model = _load_model()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = _transform(img).unsqueeze(0)  # (1, 1, H, W)
    with torch.no_grad():
        output = model(tensor)  # (T, 1, C)
        output = torch.log_softmax(output, dim=2)
    return decode_greedy(output)[0]
