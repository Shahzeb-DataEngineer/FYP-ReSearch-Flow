"""
Citation graph + gap finder routes (Move 5).

POST /graph takes a seed DOI or a topic and returns the citation
graph (nodes + edges from free OpenAlex / Semantic Scholar data),
the timeline view, under-cited clusters, and unanswered questions
detected by the local LLM from the collected abstracts. Public
like search and Deep Review.
"""
import logging
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ....services.gap_finder_service import run_gap_finder

logger = logging.getLogger(__name__)
router = APIRouter()


class GapFinderRequest(BaseModel):
    doi: str = ""
    topic: str = ""
    max_nodes: int = Field(default=60, ge=10, le=200)


@router.post("/graph")
async def gap_finder_endpoint(request: GapFinderRequest):
    start_time = time.time()
    if not (request.doi or "").strip() and not (request.topic or "").strip():
        raise HTTPException(status_code=400, detail="doi or topic is required")
    try:
        result = run_gap_finder(
            doi=request.doi, topic=request.topic, max_nodes=request.max_nodes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Gap finder failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "gap_finder_failed",
                "message": "Gap finder failed. Please try again.",
            },
        )
    result["processing_time_seconds"] = round(time.time() - start_time, 1)
    return result
