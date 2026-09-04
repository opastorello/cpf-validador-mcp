"""Limitador de taxa compartilhado.

Fica num módulo próprio porque `main.py` e `routers/consulta.py` precisam do
*mesmo* objeto: os decoradores `@limiter.limit(...)` contam no limiter que os
declarou, e o handler de 429 usa o que está em `app.state.limiter`. Com duas
instâncias — que era o caso — cada uma tinha o seu storage em memória e as duas
pontas falavam de contadores diferentes.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# get_remote_address lê request.client.host, que só reflete o IP real do usuário
# porque o uvicorn sobe com --proxy-headers (ver Dockerfile).
limiter = Limiter(key_func=get_remote_address)
