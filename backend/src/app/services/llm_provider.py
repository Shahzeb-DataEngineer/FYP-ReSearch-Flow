"""
LLM Provider - Ollama (local, zero cost).

Single place where the chat model and the embedding model are created.
Everything else in the backend asks this module for a model; nothing
imports an OpenAI / Pinecone client directly any more.

Models are chosen by environment, so the same code runs on different
machines:
- This dev machine (no GPU, ~6 GB RAM): OLLAMA_CHAT_MODEL=qwen2.5:3b
- A laptop with 16 GB RAM (documented default): qwen2.5:7b
  (llama3.1:8b is an equivalent alternative)

Embedding model is nomic-embed-text (768 dimensions). That is NOT the
1536 dimensions OpenAI text-embedding-3-small produced, so any vector
index built with the old embeddings must be rebuilt from scratch.
There is no migration path between the two embedding spaces.
"""
import logging
import os
from typing import Tuple

from ..core.config import settings

logger = logging.getLogger(__name__)

# nomic-embed-text produces 768-dim vectors.
EMBEDDING_DIMENSION = 768


def _sanitize_no_proxy() -> None:
    """
    Workaround for an httpx bug on this machine: the ollama python
    client (used by langchain-ollama) parses NO_PROXY with httpx,
    which raises InvalidURL on bracketed IPv6 entries such as [::1]
    that this environment puts in NO_PROXY. Strip bracketed entries;
    localhost and 127.0.0.1 already cover the local Ollama server.
    Only the process environment is changed, not the system.
    """
    for key in ("NO_PROXY", "no_proxy"):
        value = os.environ.get(key)
        if not value:
            continue
        cleaned = ",".join(
            part.strip() for part in value.split(",") if "[" not in part
        )
        if "localhost" not in cleaned:
            cleaned = (cleaned + ",localhost,127.0.0.1") if cleaned else "localhost,127.0.0.1"
        os.environ[key] = cleaned


_sanitize_no_proxy()


def get_ollama_base_url() -> str:
    return settings.OLLAMA_BASE_URL


def get_chat_model(model: str | None = None, temperature: float = 0.0):
    """Return a LangChain ChatOllama for the configured local model."""
    from langchain_ollama import ChatOllama

    name = (model or settings.OLLAMA_CHAT_MODEL or "qwen2.5:3b").strip()
    return ChatOllama(
        model=name,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=temperature,
        num_ctx=settings.OLLAMA_NUM_CTX,
    )


def get_embeddings():
    """Return a LangChain OllamaEmbeddings for nomic-embed-text."""
    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(
        model=settings.OLLAMA_EMBED_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )


def get_models(chat_model: str | None = None, temperature: float = 0.0) -> Tuple[object, object]:
    """Return (embeddings, llm) for the RAG pipeline."""
    return get_embeddings(), get_chat_model(chat_model, temperature=temperature)


def check_ollama_available(timeout: int = 5) -> bool:
    """True if the local Ollama server answers on OLLAMA_BASE_URL."""
    import requests

    try:
        resp = requests.get(
            settings.OLLAMA_BASE_URL.rstrip("/") + "/api/tags", timeout=timeout
        )
        return resp.status_code == 200
    except Exception as e:
        logger.warning("Ollama not reachable at %s: %s", settings.OLLAMA_BASE_URL, e)
        return False


def ollama_base_url_from_env() -> str:
    return os.getenv("OLLAMA_BASE_URL", settings.OLLAMA_BASE_URL)
