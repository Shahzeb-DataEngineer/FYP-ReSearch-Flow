"""
Private knowledge graph routes (Move 6).

A local, per-user knowledge layer over saved papers and notes. All
state lives in JSON files under backend/data/library/ on this
machine; nothing is uploaded anywhere. ``user_id`` selects whose
library is used (the frontend passes the signed-in user's id, or
"local" for anonymous use); it is a plain key, not a credential.
"""
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from ....services import knowledge_graph_service as kg

logger = logging.getLogger(__name__)
router = APIRouter()


class IndexRequest(BaseModel):
    user_id: str = "local"
    papers: list = Field(default_factory=list)
    topics: list = Field(default_factory=list)


class AskRequest(BaseModel):
    user_id: str = "local"
    question: str
    top_k: int = Field(default=3, ge=1, le=5)


class AlertsRequest(BaseModel):
    user_id: str = "local"
    topics: list = Field(default_factory=list)


class ZoteroImportRequest(BaseModel):
    user_id: str = "local"
    limit: int = Field(default=50, ge=1, le=100)


@router.post("/index")
async def index_library(request: IndexRequest):
    if not request.papers:
        raise HTTPException(status_code=400, detail="papers is required")
    try:
        result = kg.index_papers(request.user_id, request.papers)
    except Exception as e:
        logger.error("Library index failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Library indexing failed.")
    if request.topics:
        library = kg.load_library(request.user_id)
        library["topics"] = sorted(
            {t.strip() for t in library.get("topics", []) + request.topics if t.strip()}
        )
        kg.save_library(request.user_id, library)
        result["topics"] = library["topics"]
    return result


class SyncSavedRequest(BaseModel):
    user_id: str = "local"


@router.post("/sync-saved")
async def sync_saved(request: SyncSavedRequest):
    """Index the user's Supabase saved articles (resolved via OpenAlex)."""
    try:
        return kg.sync_saved_from_supabase(request.user_id)
    except Exception as e:
        logger.error("Saved sync failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Saved sync failed.")


@router.get("/papers")
async def list_library_papers(user_id: str = "local"):
    library = kg.load_library(user_id)
    return {
        "user_id": user_id,
        "papers": library.get("papers", []),
        "topics": library.get("topics", []),
        "paper_count": len(library.get("papers", [])),
    }


@router.get("/graph")
async def library_graph(user_id: str = "local"):
    return kg.build_knowledge_graph(user_id)


@router.post("/ask")
async def ask_library_endpoint(request: AskRequest):
    if not (request.question or "").strip():
        raise HTTPException(status_code=400, detail="question is required")
    try:
        return kg.ask_library(request.user_id, request.question, top_k=request.top_k)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Library ask failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Library ask failed.")


@router.post("/zotero/import")
async def zotero_import(request: ZoteroImportRequest):
    try:
        return kg.import_zotero_library(request.user_id, limit=request.limit)
    except Exception as e:
        logger.error("Zotero import failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Zotero import failed.")


@router.get("/zotero/export")
async def zotero_export(user_id: str = "local", format: str = "bibtex"):
    library = kg.load_library(user_id)
    papers = library.get("papers", [])
    fmt = (format or "bibtex").lower()
    if fmt == "ris":
        text = kg.export_ris(papers)
        return PlainTextResponse(text, media_type="application/x-research-info-systems")
    if fmt != "bibtex":
        raise HTTPException(status_code=400, detail="format must be bibtex or ris")
    text = kg.export_bibtex(papers)
    return PlainTextResponse(text, media_type="application/x-bibtex")


@router.post("/alerts/check")
async def alerts_check(request: AlertsRequest):
    try:
        return kg.check_alerts(request.user_id, topics=request.topics or None)
    except Exception as e:
        logger.error("Alerts check failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Alerts check failed.")


@router.get("/alerts")
async def list_alerts(user_id: str = "local"):
    library = kg.load_library(user_id)
    return {
        "user_id": user_id,
        "topics": library.get("topics", []),
        "last_alert_check": library.get("last_alert_check"),
        "alerts": library.get("alerts", []),
        "new_count": len(library.get("alerts", [])),
    }
