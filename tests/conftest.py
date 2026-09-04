"""
Mock carregado antes de qualquer import do app.

`app.services.sources.trt3` importa `app.captcha.predictor` no nível do módulo,
que puxa PyTorch (~3s) e, na primeira predição, carregaria o modelo do disco.
Nenhum teste resolve CAPTCHA de verdade, então o predictor é substituído por um
stub — é economia de tempo, não impedimento técnico.

`prometheus_client` já foi mockado aqui sob a alegação de que travava neste
ambiente; não trava, e o mock impedia testar `/metrics`. Foi removido.
"""
import sys
from unittest.mock import MagicMock

_mock_predictor = MagicMock()
_mock_predictor.predict = MagicMock(return_value="abcd12")
sys.modules["app.captcha.predictor"] = _mock_predictor
