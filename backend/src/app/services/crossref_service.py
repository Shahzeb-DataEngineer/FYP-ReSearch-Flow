"""
Crossref API Service
Free, no API key. Crossref is a registry of scholarly metadata
(DOI, title, authors, venue, publication date) for 100M+ works.

API: https://api.crossref.org/works
Polite pool: a mailto address is sent so Crossref can contact us
about usage; it also gets better rate limits than anonymous use.
"""
import logging
import re
import requests
from typing import List, Dict, Any, Optional

CROSSREF_BASE = "https://api.crossref.org/works"
# Polite-pool contact. Replace with a real project address when deploying.
CONTACT_MAILTO = "research-flow@example.com"


def fetch_crossref_papers(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Fetch papers from Crossref.

    Args:
        query: Search query/topic
        limit: Maximum number of results to return (max: 100)

    Returns:
        List of paper dictionaries in the common ReSearch Flow format
    """
    logging.info(f"Fetching Crossref papers for query: {query}, limit: {limit}")
    try:
        params = {
            "query.bibliographic": query,
            "rows": min(limit, 100),
            "select": "DOI,title,author,published,abstract,URL,container-title,type,link",
            "mailto": CONTACT_MAILTO,
        }
        headers = {
            "User-Agent": f"ReSearch-Flow/1.0 (mailto:{CONTACT_MAILTO})",
            "Accept": "application/json",
        }
        response = requests.get(CROSSREF_BASE, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        items = (data.get("message") or {}).get("items", [])
        if not items:
            logging.info("No papers found from Crossref")
            return []
        papers = []
        for item in items:
            paper = _parse_crossref_item(item)
            if paper:
                papers.append(paper)
        logging.info(f"Successfully fetched {len(papers)} papers from Crossref")
        return papers
    except requests.exceptions.RequestException as e:
        logging.error(f"Crossref API error: {str(e)}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error in fetch_crossref_papers: {str(e)}")
        return []


def _parse_crossref_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        doi = item.get("DOI")
        titles = item.get("title") or []
        title = titles[0] if titles else ""
        if not doi or not title:
            return None

        authors = []
        for author in item.get("author") or []:
            if isinstance(author, dict):
                name = " ".join(
                    part for part in (author.get("given", ""), author.get("family", "")) if part
                ).strip()
                if name:
                    authors.append(name)

        year = None
        published = item.get("published") or {}
        date_parts = published.get("date-parts") or []
        if date_parts and date_parts[0]:
            year = date_parts[0][0]

        abstract = item.get("abstract", "") or ""
        # Crossref abstracts sometimes carry JATS tags; strip them.
        abstract = re.sub(r"<[^>]+>", "", abstract).strip()

        pdf_url = None
        for link in item.get("link") or []:
            if isinstance(link, dict) and link.get("content-type") == "application/pdf":
                pdf_url = link.get("URL")
                break

        venues = item.get("container-title") or []
        venue = venues[0] if venues else ""
        url = item.get("URL") or f"https://doi.org/{doi}"

        return {
            "paperId": doi,
            "crossref_id": doi,
            "title": title,
            "authors": authors,
            "published_date": None,
            "year": year,
            "abstract": abstract,
            "pdf_url": pdf_url,
            "openAccessPdf": pdf_url,
            "url": url,
            "venue": venue,
            "citationCount": 0,
            "isOpenAccess": bool(pdf_url),
            "doi": f"https://doi.org/{doi}",
            "source": "Crossref",
            "original_source": "Crossref",
        }
    except Exception as e:
        logging.warning(f"Error parsing Crossref item: {str(e)}")
        return None
