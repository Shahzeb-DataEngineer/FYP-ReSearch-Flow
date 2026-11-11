"""
Unpaywall Search and Summarization Routes
Free source, no API key (only a contact email parameter).
Unpaywall is DOI-based and has no keyword search: GET /search takes
a DOI and returns the open-access record for that work, or a
no_results response when it has no open-access location.
"""
from fastapi import APIRouter, HTTPException, Body
import logging
from ....services.unpaywall_service import fetch_unpaywall_paper
from ....services.pdf_service import get_pdf_text_from_url
from ....services.summarization_service import summarize_paper
from ....services.chat_service import ask_about_paper

router = APIRouter()


@router.get("/search")
async def search_unpaywall_papers(doi: str = ""):
    try:
        if not doi or not doi.strip():
            raise HTTPException(status_code=400, detail="DOI parameter is required")
        logging.info(f"Looking up Unpaywall record for DOI: {doi}")
        paper = fetch_unpaywall_paper(doi.strip())
        if not paper:
            return {"status": "no_results", "message": f"No open-access copy found for DOI '{doi}'", "count": 0, "papers": []}
        return {"status": "success", "message": f"Found open-access copy for '{doi}'", "count": 1, "doi": doi, "papers": [paper]}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error searching Unpaywall: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "Failed to search Unpaywall", "message": str(e)})


@router.post("/extract")
async def extract_pdf_content(request_data: dict = Body(...)):
    try:
        pdf_url = request_data.get("pdf_url")
        if not pdf_url:
            raise HTTPException(status_code=400, detail="'pdf_url' must be provided")
        logging.info(f"Extracting PDF content from: {pdf_url}")
        pdf_text, extraction_error = get_pdf_text_from_url(pdf_url, max_pages=None)
        if pdf_text is None:
            return {"status": "error", "message": extraction_error or "PDF is not available or could not be processed.", "pdf_url": pdf_url}
        return {"status": "success", "pdf_url": pdf_url, "full_text": pdf_text, "text_length": len(pdf_text), "character_count": len(pdf_text), "word_count": len(pdf_text.split())}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error extracting PDF content: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "Failed to extract PDF content", "message": str(e)})


@router.post("/summarize")
async def summarize_paper_endpoint(request_data: dict = Body(...)):
    try:
        pdf_url = request_data.get("pdf_url")
        title = request_data.get("title", "")
        abstract = request_data.get("abstract", "")
        doi = request_data.get("doi", "")
        if not pdf_url and not abstract:
            raise HTTPException(status_code=400, detail="'pdf_url' or 'abstract' must be provided")
        pdf_text = None
        fallback_used = False
        if pdf_url:
            logging.info(f"Summarizing paper from: {pdf_url}")
            pdf_text, extraction_error = get_pdf_text_from_url(pdf_url, max_pages=None)
            if pdf_text is None:
                logging.warning(f"PDF extraction failed: {extraction_error}")
        if pdf_text is None and abstract and len(abstract.strip()) > 50:
            logging.info(f"Using abstract-based fallback summarization for: {title[:80]}")
            fallback_text = (f"Title: {title}\n\n" if title else "") + f"Abstract: {abstract}"
            pdf_text = fallback_text
            fallback_used = True
        if pdf_text is None:
            raise HTTPException(status_code=404, detail={"error": "PDF not available", "message": "PDF is not available and no abstract was provided for fallback summarization."})
        summary = summarize_paper(pdf_text, max_sentences=5, use_llm=True)
        response = {"status": "success", "source": "Unpaywall", "identifier": doi or pdf_url, "summary": summary, "full_text": pdf_text if not fallback_used else None, "text_length": len(pdf_text)}
        if fallback_used:
            response["fallback"] = True
            response["fallback_note"] = "Summary was generated from the paper's abstract because the PDF could not be accessed directly."
        return response
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error summarizing paper: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "Failed to summarize paper", "message": str(e)})


@router.post("/ask")
async def ask_question_endpoint(request_data: dict = Body(...)):
    try:
        pdf_url = request_data.get("pdf_url")
        question = request_data.get("question")
        pdf_text_direct = request_data.get("pdf_text")
        conversation_history = request_data.get("conversation_history", [])
        abstract = request_data.get("abstract", "")
        if not question or not question.strip():
            raise HTTPException(status_code=400, detail="Question is required")
        if pdf_text_direct and len(pdf_text_direct.strip()) > 50:
            pdf_text = pdf_text_direct
        else:
            if not pdf_url:
                if abstract and len(abstract.strip()) > 10:
                    pdf_text = abstract
                else:
                    raise HTTPException(status_code=400, detail="Either 'pdf_url', 'pdf_text', or 'abstract' must be provided")
            else:
                pdf_text, extraction_error = get_pdf_text_from_url(pdf_url, max_pages=None)
                if pdf_text is None:
                    if abstract and len(abstract.strip()) > 10:
                        pdf_text = abstract
                    else:
                        raise HTTPException(status_code=404, detail={"error": "PDF not available", "message": extraction_error or "PDF is not available or could not be processed."})
        title = request_data.get("title", "")
        answer = ask_about_paper(question.strip(), pdf_text, conversation_history=conversation_history if conversation_history else None, paper_title=title or None, paper_source="Unpaywall")
        if not answer:
            raise HTTPException(status_code=500, detail="Failed to generate answer. Please try again.")
        return {"status": "success", "pdf_url": pdf_url or "(text provided directly)", "question": question, "answer": answer}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error answering question: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "Failed to answer question", "message": str(e)})
