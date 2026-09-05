FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model's ONNX weights into the image at build
# time, into the same directory main.py's EMBEDDING_CACHE_DIR points at.
# Without this, the first semantic-search request on a fresh container would
# fetch ~80MB from Hugging Face over the network inside the request itself.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='sentence-transformers/all-MiniLM-L6-v2', cache_dir='/app/model_cache')"

COPY main.py schema_glossary.py ./

CMD exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 120 main:app
