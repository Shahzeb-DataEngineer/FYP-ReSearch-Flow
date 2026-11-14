"""
Citation verification and paper badges routes.

POST /citations/verify checks whether a source text supports a claim
and returns the exact supporting sentence when one passes the
threshold, or verified false when none does.

GET /citations/papers/badges resolves a DOI through the live OpenAlex
API and returns retraction, open-access and peer-review/preprint
badges. The frontend can call it per search result. Every badge field
comes from the OpenAlex response; a DOI OpenAlex does not know
returns a clear not_found.
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ....services.citation_verification_service import (
    get_paper_badges,
    verify_claim,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class VerifyRequest(BaseModel):
    claim: str
    source_text: str


@router.post("/verify")
async def verify_citation_endpoint(request: VerifyRequest):
    claim = (request.claim or "").strip()
    source_text = (request.source_text or "").strip()
    if not claim:
        raise HTTPException(status_code=400, detail="claim is required")
    if not source_text:
        raise HTTPException(status_code=400, detail="source_text is required")
    try:
        return verify_claim(claim, source_text)
    except Exception as e:
        logger.error("Citation verification failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "verification_failed",
                "message": "Citation verification failed. Please try again.",
            },
        )


@router.get("/papers/badges")
async def paper_badges_endpoint(doi: str = ""):
    clean_doi = (doi or "").strip()
    if not clean_doi:
        raise HTTPException(status_code=400, detail="doi query parameter is required")
    try:
        badges = get_paper_badges(clean_doi)
    except Exception as e:
        logger.error("Paper badges lookup failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "badges_failed",
                "message": "Paper badges lookup failed. Please try again.",
            },
        )
    if badges is None:
        return {
            "status": "not_found",
            "doi": clean_doi,
            "message": f"No OpenAlex record found for DOI '{clean_doi}'.",
            "badges": None,
        }
    return {"status": "success", "doi": clean_doi, "badges": badges}
