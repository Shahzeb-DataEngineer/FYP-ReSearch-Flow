"""
Unified Chat Routes
Handles paper Q&A conversations with Redis-backed session persistence.
All chat goes through chat_service.py using local Ollama RAG (FAISS + BM25).
"""
import asyncio
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Body
from ....core.jwt_auth import get_current_user, scoped_session_id
from ....services.chat_service import (
    ask_about_paper_with_session,
    load_session,
    delete_session,
)
from ....services.pdf_service import get_pdf_text_from_url

router = APIRouter()


@router.post("/ask")
async def chat_ask(
    request_data: dict = Body(...),
    user: dict = Depends(get_current_user),
):
    """
    Ask a question about a research paper using RAG.

    Requires a logged-in user (Supabase JWT). The chat session is
    scoped to that user: the client-supplied session id is stored
    under "<user_id>:<session_id>", so one user cannot read or wipe
    another user's history by guessing a UUID.

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
        # Scope the session to the logged-in user; the client keeps
        # using its own uuid, which is re-scoped on every call.
        scoped_id = scoped_session_id(user["id"], session_id)
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
            scoped_id,
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
        # Do not leak internals to the client: log the traceback,
        # answer with a generic message.
        logging.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Chat failed. Please try again.",
        )


@router.get("/history/{session_id}")
async def get_chat_history(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Retrieve conversation history for a session from Redis.

    Requires a logged-in user; the session id is scoped to that
    user, so history from another user's session is unreachable.
    """
    try:
        history = load_session(scoped_session_id(user["id"], session_id))
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
            detail="Failed to retrieve chat history",
        )


@router.delete("/history/{session_id}")
async def clear_chat_history(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Clear/delete a chat session from Redis.

    Requires a logged-in user; only the session owner's history can
    be deleted. (Previously this was guarded by the shared
    BACKEND_API_KEY only, which any client could not know and which
    did not scope by user at all.)
    """
    try:
        delete_session(scoped_session_id(user["id"], session_id))
        return {
            "status": "success",
            "message": f"Session {session_id} cleared",
        }
    except Exception as e:
        logging.error(f"Error clearing chat history: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to clear chat history",
        )
