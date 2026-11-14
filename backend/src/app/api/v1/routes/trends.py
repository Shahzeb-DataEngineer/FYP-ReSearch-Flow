from fastapi import APIRouter, HTTPException
import requests
import logging
from typing import List, Dict, Any
import datetime
from cachetools import TTLCache, cached

from ....services.openalex_client import get_openalex_headers, is_key_not_activated

router = APIRouter()

# Cache for 12 hours (43200 seconds), max 5 items
trends_cache = TTLCache(maxsize=5, ttl=43200)

@cached(cache=trends_cache)
def fetch_openalex_trends() -> List[Dict[str, Any]]:
    """
    Fetch trending concepts from OpenAlex in Computer Science & Technology.
    Gets concepts with high works_count and recent activity.
    """
    try:
        logging.info("Fetching fresh trends from OpenAlex API...")
        # Get concepts in Computer Science (level 0 or 1) sorted by works_count
        # Concept ID for Computer Science is c41008148
        # We can also search for works in the last year sorted by cited_by_count
        
        # A better approach for "Trends": find recent highly-cited works in CS,
        # then extract common concepts from them, OR just fetch top concepts
        # For simplicity and speed, let's query the concepts endpoint directly
        # or do a quick search for recent AI/CS works and extract their topics.
        
        url = "https://api.openalex.org/concepts"
        params = {
            "filter": "level:1,ancestors.id:c41008148", # Level 1 concepts under CS
            "sort": "works_count:desc",
            "per-page": 15
        }
        
        headers = get_openalex_headers()
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if headers and is_key_not_activated(response):
            # Key requested but not activated yet: fall back to a
            # keyless request so trends keep working until the
            # activation link is clicked.
            logging.warning(
                "OpenAlex API key not activated yet (key_not_activated); "
                "retrying without a key"
            )
            response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        trends = []
        for i, concept in enumerate(data.get("results", [])[:10]):
            trends.append({
                "id": concept.get("id"),
                "text": concept.get("display_name"),
                "works_count": concept.get("works_count"),
                "description": concept.get("description", ""),
                "hint": "Trending Topic"
            })
            
        # Add some highly specific static ones if the API fails or returns generic stuff
        if not trends:
            trends = [
                {"text": "Large Language Models", "hint": "Trending in AI"},
                {"text": "Quantum Computing", "hint": "Trending in Tech"},
                {"text": "Graph Neural Networks", "hint": "Trending in ML"},
            ]
            
        return trends
        
    except Exception as e:
        logging.error(f"Error fetching OpenAlex trends: {e}")
        # Return fallback trends
        return [
            {"text": "Large Language Models", "hint": "Trending in AI"},
            {"text": "Retrieval-Augmented Generation", "hint": "Trending in AI"},
            {"text": "Graph Neural Networks", "hint": "Trending in ML"},
            {"text": "Quantum Computing", "hint": "Trending in Tech"},
            {"text": "Federated Learning", "hint": "Trending in Security/ML"}
        ]

@router.get("/topics", response_model=Dict[str, Any])
async def get_trending_topics():
    """Get list of trending research topics/queries"""
    try:
        trends = fetch_openalex_trends()
        return {
            "status": "success",
            "topics": trends
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
