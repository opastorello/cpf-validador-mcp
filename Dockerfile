FROM python:3.11-slim

WORKDIR /app

# A fonte TRT3 precisa de PyTorch (~780 MB) para a CRNN que lê o CAPTCHA dela.
# Nenhuma outra fonte precisa — o CAPTCHA do TCU é proof-of-work, resolvido só
# com a biblioteca padrão. Para uma imagem sem PyTorch:
#   docker build --build-arg COM_TRT3=false .
ARG COM_TRT3=true

# Layer separado para torch — só invalida se mudar a versão aqui, nunca por causa do requirements.txt
RUN if [ "$COM_TRT3" = "true" ]; then \
      pip install --no-cache-dir "torch>=2.0.0" "torchvision>=0.15.0" \
        --index-url https://download.pytorch.org/whl/cpu; \
    fi

COPY requirements.txt requirements-trt3.txt ./
# torch/torchvision já instalados acima — pip verifica versão e pula, sem re-download
RUN if [ "$COM_TRT3" = "true" ]; then \
      pip install --no-cache-dir -r requirements-trt3.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

COPY app/ ./app/

RUN useradd -m mcpuser
USER mcpuser

EXPOSE 8000

# --proxy-headers faz o uvicorn usar o X-Forwarded-For como IP do cliente. Sem
# isso, atrás de um proxy (Traefik do Coolify, nginx) todo mundo chega com o IP
# do proxy e divide o mesmo balde de rate limit. Quais proxies confiar vem de
# FORWARDED_ALLOW_IPS, lido pelo próprio uvicorn.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
