FROM python:3.11-slim

WORKDIR /app

# Layer separado para torch — só invalida se mudar a versão aqui, nunca por causa do requirements.txt
RUN pip install --no-cache-dir \
    "torch>=2.0.0" "torchvision>=0.15.0" \
    --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
# torch/torchvision já instalados acima — pip verifica versão e pula, sem re-download
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN useradd -m mcpuser && mkdir -p /app/app/data && chown mcpuser /app/app/data
USER mcpuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
