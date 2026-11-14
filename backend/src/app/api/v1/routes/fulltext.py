"""
Open-access full-text bridge routes.

GET /papers/fulltext resolves the legal open-access PDF for a DOI
(OpenAlex, then Unpaywall) without downloading anything. A
paywalled or unknown DOI returns status not_available with no
PDF URL, never an invented one.

POST /papers/fulltext downloads the resolved PDF, extracts its
text and indexes it into the FAISS + BM25 RAG store, so chat can
answer from the full text.
"""
import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ....services.fulltext_service import fetch_fulltext, resolve_oa_copy

logger = logging.getLogger(__name__)
router = APIRouter()


class FulltextRequest(BaseModel):
    doi: str
    download: bool = True
    index: bool = True


@router.get("/fulltext")
async def fulltext_resolve_endpoint(doi: str = ""):
    clean_doi = (doi or "").strip()
    if not clean_doi:
        raise HTTPException(status_code=400, detail="doi query parameter is required")
    try:
        return resolve_oa_copy(clean_doi)
    except Exception as e:
        logger.error("Full-text resolve failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "fulltext_failed",
                "message": "Full-text lookup failed. Please try again.",
            },
        )


@router.post("/fulltext")
async def fulltext_fetch_endpoint(request: FulltextRequest):
    clean_doi = (request.doi or "").strip()
    if not clean_doi:
        raise HTTPException(status_code=400, detail="doi is required")
    try:
        result = await asyncio.to_thread(
            fetch_fulltext, clean_doi, request.download, request.index
        )
    except Exception as e:
        logger.error("Full-text fetch failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "fulltext_failed",
                "message": "Full-text fetch failed. Please try again.",
            },
        )
    if result.get("status") == "not_available":
        return result
    return result
