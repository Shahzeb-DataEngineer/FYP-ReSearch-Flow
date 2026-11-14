"""
Deep Review route: unlimited local deep synthesis.

POST /review/deep takes a research question and runs the full
pipeline (multi-query search, screening, per-paper extraction,
cited synthesis) on the local model. No credits, no caps: the only
limit is the per-IP rate limit shared with the summarize endpoints
(see core/rate_limit.py). Public like search and summarization.
"""
import logging
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ....services.deep_review_service import run_deep_review

logger = logging.getLogger(__name__)
router = APIRouter()


class DeepReviewRequest(BaseModel):
    question: str
    max_papers: int = Field(default=5, ge=1, le=10)


@router.post("/deep")
async def deep_review_endpoint(request: DeepReviewRequest):
    start_time = time.time()
    question = (request.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    try:
        result = run_deep_review(question, max_papers=request.max_papers)
    except Exception as e:
        logger.error("Deep review failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "deep_review_failed",
                "message": "Deep review failed. Please try again.",
            },
        )
    result["processing_time_seconds"] = round(time.time() - start_time, 1)
    return result
