"""
Draft Generation Route
Endpoint for generating structured research drafts from open-access papers.
Draft text comes from the local Ollama model (zero cost). Figure
extraction still runs; figure/vision analysis is optional and off by
default (see draft_service.analyze_figure).
"""
import time
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ....core.jwt_auth import get_current_user
from ....services.pdf_service import download_pdf, extract_text_from_pdf
from ....services.figure_extraction_service import extract_figures_from_pdf
from ....services.draft_service import analyze_figure, generate_draft

logger = logging.getLogger(__name__)
router = APIRouter()


class DraftRequest(BaseModel):
    pdf_url: str
    title: Optional[str] = ""
    authors: Optional[str] = ""
    abstract: Optional[str] = ""


@router.post("/generate")
async def generate_draft_endpoint(
    request: DraftRequest,
    user: dict = Depends(get_current_user),
):
    """
    Generate a structured research draft from an open-access paper.

    Requires a logged-in user (Supabase JWT): a draft costs minutes
    of CPU on the local model, so anonymous generation is not
    offered. Search and summarization stay public; chat and drafts
    are the authenticated features.

    1. Downloads and extracts text from the PDF
    2. Extracts figures/images from the PDF
    3. Analyzes each figure with the local vision model, if one is
       configured (off by default; figures are otherwise skipped
       with a note in the draft, not an error)
    4. Generates a comprehensive draft using the local Ollama model

    Returns the draft sections and figure analyses.
    """
    start_time = time.time()

    if not request.pdf_url:
        raise HTTPException(status_code=400, detail="pdf_url is required")

    try:
        # Step 1: Download PDF
        logger.info(f"Draft generation started for: {request.pdf_url}")
        pdf_content, download_error = download_pdf(request.pdf_url)

        if pdf_content is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "PDF not available",
                    "message": download_error or "Failed to download PDF",
                },
            )

        # Step 2: Extract text
        extracted_text = extract_text_from_pdf(pdf_content)
        if not extracted_text or len(extracted_text.strip()) < 100:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "extraction_failed",
                    "message": "Failed to extract sufficient text from PDF",
                },
            )

        logger.info(f"Extracted {len(extracted_text)} chars of text")

        # Step 3: Extract figures
        figures = extract_figures_from_pdf(pdf_content, max_figures=6)
        logger.info(f"Extracted {len(figures)} figures from PDF")

        # Step 4: Analyze figures with the local vision model, if
        # configured (analyze_figure returns None when it is not)
        figure_analyses = []
        for i, fig in enumerate(figures):
            logger.info(f"Analyzing figure {i + 1}/{len(figures)} (page {fig['page_number']})")
            analysis = analyze_figure(
                image_base64=fig["image_base64"],
                mime_type=fig["mime_type"],
                caption_hint=fig.get("caption_hint", ""),
            )
            if analysis:
                analysis["page_number"] = fig["page_number"]
                analysis["figure_number"] = i + 1
                figure_analyses.append(analysis)

        logger.info(f"Successfully analyzed {len(figure_analyses)}/{len(figures)} figures")

        # Step 5: Generate draft
        draft = generate_draft(
            paper_text=extracted_text,
            figure_analyses=figure_analyses,
            title=request.title or "",
            authors=request.authors or "",
            abstract=request.abstract or "",
            figures_found=len(figures),
        )

        if draft is None:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "draft_generation_failed",
                    "message": "Failed to generate draft. Please try again.",
                },
            )

        elapsed = round(time.time() - start_time, 1)
        logger.info(f"Draft generation completed in {elapsed}s")

        return {
            "status": "success",
            "draft": draft,
            "figure_analyses": figure_analyses,
            "metadata": {
                "figures_found": len(figures),
                "figures_analyzed": len(figure_analyses),
                "text_length": len(extracted_text),
                "processing_time_seconds": elapsed,
            },
        }

    except ValueError as e:
        logger.error(f"Configuration error during draft generation: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "configuration_error",
                "message": str(e),
                "hint": "The local Ollama server is not reachable. Start Ollama and check OLLAMA_BASE_URL in the .env file."
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        # Do not leak internals to the client: log the traceback,
        # answer with a generic message.
        logger.error(f"Unexpected error during draft generation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "An unexpected error occurred. Please try again.",
            },
        )
