FROM python:3.12-slim

WORKDIR /app

# Install backend dependencies first so the layer is cached
# when only application code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

EXPOSE 8000

# Config (Ollama URL, keys, ...) comes from the environment, not
# from a copied .env file; see docker-compose.yml at the repo root.
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
