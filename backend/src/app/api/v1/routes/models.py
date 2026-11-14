"""
Model picker and cost meter routes (Move 7).

GET /models lists the local Ollama models actually installed, with
size and context, plus which chat / embedding model is active.
POST /models/select switches the active model (validated against the
installed list, persisted locally). GET /usage shows per-task tokens
and wall time, the cloud price the same tokens would have cost at
the published GPT-4o-mini rate, and total spent, always $0.00.
All three routes are public: they expose only local machine state.
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ....services.model_registry import list_models, select_model
from ....services.usage_meter import get_usage_summary

logger = logging.getLogger(__name__)

models_router = APIRouter()
usage_router = APIRouter()


class SelectModelRequest(BaseModel):
    model: str
    kind: str = "chat"


@models_router.get("")
async def list_models_endpoint():
    try:
        result = list_models()
    except Exception as e:
        logger.error("Model list failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "models_failed", "message": "Could not list local models."},
        )
    if not result["ollama_available"]:
        result["message"] = (
            "The local Ollama server is not reachable. Start Ollama "
            "and pull a chat model before picking one."
        )
    return result


@models_router.post("/select")
async def select_model_endpoint(request: SelectModelRequest):
    try:
        return select_model(request.model, request.kind)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Model select failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "select_failed", "message": "Could not switch model."},
        )


@usage_router.get("")
async def usage_endpoint():
    try:
        return get_usage_summary()
    except Exception as e:
        logger.error("Usage summary failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "usage_failed", "message": "Could not read usage log."},
        )
