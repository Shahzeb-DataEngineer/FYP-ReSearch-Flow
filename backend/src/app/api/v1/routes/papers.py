"""Stored-papers routes.

Mounted at prefix /papers (see api_router.py), so these routes are
/api/v1/papers and /api/v1/papers/topics/all. The old stub declared
its list route as "/papers" here, which doubled the path to
/api/v1/papers/papers and left the paths the frontend and docs call
returning 404.

Reads come from the research_papers table that search/fetch stores
papers into (see crud/papers_crud.py). When Supabase is not
configured, the list endpoints return an empty list with 200
instead of failing, so local dev without keys still works.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from ....db.client_supabase import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def get_papers(
    topic: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Return stored papers, newest first, optionally filtered by topic."""
    client = get_supabase()
    if client is None:
        return {
            "status": "success",
            "count": 0,
            "papers": [],
            "message": "Supabase not configured: no stored papers available",
        }
    try:
        query = (
            client.table("research_papers")
            .select("*")
            .order("inserted_at", desc=True)
        )
        if topic:
            query = query.eq("topic", topic)
        response = query.range(offset, offset + limit - 1).execute()
        papers = response.data or []
        return {"status": "success", "count": len(papers), "papers": papers}
    except Exception as e:
        logger.error(f"Error fetching stored papers: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to retrieve papers", "message": str(e)},
        )


@router.get("/topics/all")
async def get_topics():
    """Return the distinct topics of stored papers."""
    client = get_supabase()
    if client is None:
        return {"status": "success", "topics": []}
    try:
        response = client.table("research_papers").select("topic").execute()
        topics = sorted(
            {row.get("topic") for row in (response.data or []) if row.get("topic")}
        )
        return {"status": "success", "topics": topics}
    except Exception as e:
        logger.error(f"Error fetching paper topics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to retrieve topics", "message": str(e)},
        )
