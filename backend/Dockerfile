FROM python:3.12-slim

WORKDIR /app

# Install backend dependencies first so the layer is cached
# when only application code changes.
# Build context is the repo root (Railway's root railway.json and
# docker-compose.yml both build from there), so paths are
# backend/-prefixed. Do not build with context backend/: the COPY
# lines below would fail.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/src ./src

EXPOSE 8000

# Config (Ollama URL, keys, ...) comes from the environment, not
# from a copied .env file; see docker-compose.yml at the repo root.
# Shell form so $PORT expands at runtime: Railway injects PORT and
# exec-form CMD would pass the literal string "$PORT" to uvicorn.
# Locally PORT is unset and the default 8000 is used.
CMD ["sh", "-c", "uvicorn src.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
