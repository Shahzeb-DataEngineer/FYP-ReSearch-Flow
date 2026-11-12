"""
Unified Chat Routes
Handles paper Q&A conversations with Redis-backed session persistence.
All chat goes through chat_service.py using local Ollama RAG (FAISS + BM25).
"""
import asyncio
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Body
from ....core.auth import verify_api_key
from ....services.chat_service import (
    ask_about_paper_with_session,
    load_session,
    delete_session,
)
from ....services.pdf_service import get_pdf_text_from_url

router = APIRouter()


@router.post("/ask")
async def chat_ask(request_data: dict = Body(...)):
    """
    Ask a question about a research paper using RAG.

    Uses local FAISS for vector storage, LangChain for retrieval + generation,
    and Upstash Redis for server-side conversation history.

    Request body:
        {
            "question": "What is the main contribution?",
            "pdf_text": "...(pre-extracted text)...",          # preferred
            "pdf_url": "https://arxiv.org/pdf/...",            # fallback
            "abstract": "...",                                  # last-resort
            "session_id": "optional-uuid",                     # resume a session
            "paper_title": "Optional title",
            "paper_source": "arXiv",                           # arXiv|CORE|PMC|etc
            "model": "qwen2.5:3b"                              # optional, Ollama model
        }

    Returns:
        {
            "status": "success",
            "session_id": "uuid",
            "question": "...",
            "answer": "...",
            "paper_id": "40-char hex hash of paper text"
        }
    """
    try:
        question = request_data.get("question", "").strip()
        if not question:
            raise HTTPException(status_code=400, detail="Question is required")

        session_id = request_data.get("session_id") or str(uuid.uuid4())
        pdf_text = request_data.get("pdf_text")
        pdf_url = request_data.get("pdf_url")
        abstract = request_data.get("abstract", "")
        paper_title = request_data.get("paper_title") or request_data.get("title", "")
        paper_source = request_data.get("paper_source") or request_data.get("source", "")
        model = request_data.get("model") or None

        # ── Resolve paper text ────────────────────────────────────────
        # Priority: pdf_text > pdf_url extraction > abstract
        if pdf_text and len(pdf_text.strip()) > 50:
            logging.info(f"Chat: using pre-extracted text ({len(pdf_text)} chars)")
        elif pdf_url:
            logging.info(f"Chat: extracting PDF from {pdf_url}")
            extracted, err = get_pdf_text_from_url(pdf_url, max_pages=None)
            if extracted:
                pdf_text = extracted
            elif abstract and len(abstract.strip()) > 10:
                pdf_text = abstract
                logging.info("Chat: PDF extraction failed, using abstract")
            else:
                raise HTTPException(
                    status_code=404,
                    detail=err or "PDF not available and no abstract provided",
                )
        elif abstract and len(abstract.strip()) > 10:
            pdf_text = abstract
            logging.info("Chat: using abstract as paper text")
        else:
            raise HTTPException(
                status_code=400,
                detail="Provide 'pdf_text', 'pdf_url', or 'abstract'",
            )

        # ── Get answer via local Ollama RAG (FAISS + BM25 + Redis) ─────────
        # Run sync RAG in a thread so indexing + LLM work does not block the event loop.
        answer = await asyncio.to_thread(
            ask_about_paper_with_session,
            session_id,
            question,
            pdf_text,
            model,
            paper_title or None,
            paper_source or None,
        )

        if not answer:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate answer. Please try again.",
            )

        return {
            "status": "success",
            "session_id": session_id,
            "question": question,
            "answer": answer,
        }

    except HTTPException:
        raise
    except ValueError as e:
        logging.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Chat failed", "message": str(e)},
        )


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    """
    Retrieve conversation history for a session from Redis.
    """
    try:
        history = load_session(session_id)
        return {
            "status": "success",
            "session_id": session_id,
            "messages": history,
            "count": len(history),
        }
    except Exception as e:
        logging.error(f"Error retrieving chat history: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to retrieve chat history", "message": str(e)},
        )


@router.delete("/history/{session_id}", dependencies=[Depends(verify_api_key)])
async def clear_chat_history(session_id: str):
    """
    Clear/delete a chat session from Redis.
    """
    try:
        delete_session(session_id)
        return {
            "status": "success",
            "message": f"Session {session_id} cleared",
        }
    except Exception as e:
        logging.error(f"Error clearing chat history: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to clear chat history", "message": str(e)},
        )
