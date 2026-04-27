"""
Mocks carregados antes de qualquer import do app.
prometheus_client e prometheus_fastapi_instrumentator bloqueiam neste ambiente.
app.captcha.predictor importa PyTorch no nível do módulo via services/trt3.py.
"""
import sys
from unittest.mock import MagicMock

_prom_client = MagicMock()
_prom_client.Counter = MagicMock(return_value=MagicMock())
_prom_client.Histogram = MagicMock(return_value=MagicMock())
_prom_client.Gauge = MagicMock(return_value=MagicMock())
sys.modules["prometheus_client"] = _prom_client

_mock_inst = MagicMock()
_mock_inst.instrument.return_value = _mock_inst
_mock_inst.expose.return_value = _mock_inst
_mock_pfi = MagicMock()
_mock_pfi.Instrumentator.return_value = _mock_inst
sys.modules["prometheus_fastapi_instrumentator"] = _mock_pfi

# app.services.trt3 importa app.captcha.predictor no nível do módulo,
# o que carregaria PyTorch e bloquearia o processo de teste.
_mock_predictor = MagicMock()
_mock_predictor.predict = MagicMock(return_value="abcd12")
sys.modules["app.captcha.predictor"] = _mock_predictor
