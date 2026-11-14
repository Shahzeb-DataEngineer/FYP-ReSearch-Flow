"""
Model registry: transparent local model picker (Move 7).

Lists the models actually installed on the local Ollama server and
remembers which chat / embedding model is active. Nothing here calls
a paid API: the only source of truth is Ollama's /api/tags.

Persistence: the active choice is stored in a local JSON file under
backend/data/model_selection.json (gitignored, never committed - it
is machine state, not code). The file is only ever read/written by
this module; the selection is also honoured in-process by
llm_provider, which asks this module for the active model before
falling back to settings.OLLAMA_CHAT_MODEL / OLLAMA_EMBED_MODEL.
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

import requests

from ..core.config import settings

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


def _selection_path() -> Path:
    override = os.environ.get("RESEARCH_FLOW_MODEL_SELECTION_PATH")
    if override:
        return Path(override)
    return BASE_DIR / "data" / "model_selection.json"


def _read_selection() -> Dict[str, str]:
    try:
        path = _selection_path()
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {k: str(v) for k, v in data.items() if v}
    except Exception as e:
        logger.warning("Could not read model selection: %s", e)
    return {}


def _write_selection(selection: Dict[str, str]) -> None:
    path = _selection_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(selection, indent=2), encoding="utf-8")
    tmp.replace(path)


def get_active_chat_model() -> str:
    """Active chat model: persisted selection, else settings default."""
    return _read_selection().get("chat_model") or settings.OLLAMA_CHAT_MODEL


def get_active_embed_model() -> str:
    """Active embedding model: persisted selection, else settings default."""
    return _read_selection().get("embed_model") or settings.OLLAMA_EMBED_MODEL


def _base_name(name: str) -> str:
    return (name or "").split(":")[0].strip().lower()


def list_installed_models(timeout: int = 10) -> List[Dict[str, object]]:
    """Models installed on the local Ollama server, with size/context.

    Returns [] when Ollama is unreachable (callers report that
    honestly instead of inventing a list). Each entry carries name,
    size_bytes, size_mb, parameter_size, context_length, family and
    capabilities straight from Ollama's /api/tags response.
    """
    url = settings.OLLAMA_BASE_URL.rstrip("/") + "/api/tags"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Ollama /api/tags unreachable at %s: %s", url, e)
        return []
    models = []
    for entry in (resp.json() or {}).get("models") or []:
        details = entry.get("details") or {}
        capabilities = entry.get("capabilities") or []
        size = int(entry.get("size") or 0)
        models.append(
            {
                "name": entry.get("model") or entry.get("name") or "",
                "size_bytes": size,
                "size_mb": round(size / (1024 * 1024), 1),
                "parameter_size": details.get("parameter_size"),
                "context_length": details.get("context_length"),
                "family": details.get("family"),
                "quantization": details.get("quantization_level"),
                "capabilities": capabilities,
                "is_chat": "completion" in capabilities,
                "is_embedding": "embedding" in capabilities,
            }
        )
    return [m for m in models if m["name"]]


def list_models() -> Dict[str, object]:
    """Full picker payload: installed models plus which are active."""
    models = list_installed_models()
    active_chat = get_active_chat_model()
    active_embed = get_active_embed_model()
    return {
        "ollama_base_url": settings.OLLAMA_BASE_URL,
        "ollama_available": bool(models),
        "active_chat_model": active_chat,
        "active_embed_model": active_embed,
        "models": models,
        "chat_models": [m["name"] for m in models if m["is_chat"]],
        "embedding_models": [m["name"] for m in models if m["is_embedding"]],
        "note": (
            "All models run locally on Ollama. No cloud model is ever "
            "used, so model use costs $0.00."
        ),
    }


def select_model(model: str, kind: str = "chat") -> Dict[str, object]:
    """Switch the active model, validating against the installed list.

    Raises ValueError for an unknown model, a model of the wrong kind
    (e.g. an embedding model as the chat model), or an unknown kind.
    The choice is persisted to the local selection file.
    """
    name = (model or "").strip()
    kind = (kind or "chat").strip().lower()
    if kind not in ("chat", "embed"):
        raise ValueError("kind must be 'chat' or 'embed'")
    if not name:
        raise ValueError("model is required")
    models = list_installed_models()
    if not models:
        raise ValueError(
            "Ollama is not reachable, so the installed model list "
            "cannot be checked. Start Ollama and retry."
        )
    match = None
    for entry in models:
        if entry["name"] == name or _base_name(str(entry["name"])) == _base_name(name):
            match = entry
            break
    if match is None:
        installed = ", ".join(m["name"] for m in models)
        raise ValueError(
            f"Model '{name}' is not installed on this Ollama server. "
            f"Installed models: {installed}."
        )
    if kind == "chat" and not match["is_chat"]:
        raise ValueError(
            f"Model '{match['name']}' is an embedding model, not a chat model."
        )
    if kind == "embed" and not match["is_embedding"]:
        raise ValueError(
            f"Model '{match['name']}' is not an embedding model."
        )
    selection = _read_selection()
    key = "chat_model" if kind == "chat" else "embed_model"
    selection[key] = str(match["name"])
    _write_selection(selection)
    logger.info("Active %s model switched to %s", kind, match["name"])
    return {
        "status": "success",
        "kind": kind,
        "active_model": str(match["name"]),
        "active_chat_model": selection.get("chat_model") or settings.OLLAMA_CHAT_MODEL,
        "active_embed_model": selection.get("embed_model") or settings.OLLAMA_EMBED_MODEL,
    }
