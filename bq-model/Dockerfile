FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
# torch is pulled from the CPU-only wheel index — the default PyPI wheel
# bundles CUDA dependencies that roughly triple image size and are useless
# on Cloud Run, which has no GPU.
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

COPY main.py schema_glossary.py ./

CMD exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 120 main:app
