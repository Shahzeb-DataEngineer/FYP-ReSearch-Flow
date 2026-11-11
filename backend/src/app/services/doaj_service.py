"""
DOAJ API Service
Free, no API key. The Directory of Open Access Journals indexes
open-access journal articles with title, authors, journal, year,
abstract, DOI and an open-access full-text link.

API: https://doaj.org/api/search/articles/{query}?pageSize={n}
"""
import logging
import re
from typing import List, Dict, Any, Optional
from urllib.parse import quote

import requests

DOAJ_BASE = "https://doaj.org/api/search/articles"


def fetch_doaj_papers(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Fetch papers from DOAJ.

    Args:
        query: Search query/topic
        limit: Maximum number of results to return (max: 100)

    Returns:
        List of paper dictionaries in the common ReSearch Flow format
    """
    logging.info(f"Fetching DOAJ papers for query: {query}, limit: {limit}")
    try:
        url = f"{DOAJ_BASE}/{quote(query)}"
        params = {
            "pageSize": min(limit, 100),
        }
        headers = {
            "User-Agent": "ReSearch-Flow/1.0",
            "Accept": "application/json",
        }
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", []) or []
        if not results:
            logging.info("No papers found from DOAJ")
            return []
        papers = []
        seen_dois: set = set()
        seen_titles: set = set()
        skipped = 0
        for item in results:
            paper = _parse_doaj_item(item)
            if not paper:
                continue
            # DOAJ can return the same article twice in one query
            # (e.g. indexed under two records). A row is a duplicate
            # if ANY of its identifiers was already seen, same
            # approach as the Europe PMC service.
            doi, title = _dedup_ids(paper)
            if (doi and doi in seen_dois) or (title and title in seen_titles):
                skipped += 1
                continue
            if doi:
                seen_dois.add(doi)
            if title:
                seen_titles.add(title)
            papers.append(paper)
        if skipped:
            logging.info(f"Skipped {skipped} duplicate DOAJ result(s)")
        logging.info(f"Successfully fetched {len(papers)} papers from DOAJ")
        return papers
    except requests.exceptions.RequestException as e:
        logging.error(f"DOAJ API error: {str(e)}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error in fetch_doaj_papers: {str(e)}")
        return []


def _dedup_ids(paper: Dict[str, Any]) -> tuple:
    """Normalized (doi, title) identifiers for dedup.

    Empty strings mean "not present". The caller treats a row as a
    duplicate when any non-empty identifier was already seen.
    """
    doi = (paper.get("doi") or "").strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    title = re.sub(r"[^a-z0-9]+", " ", (paper.get("title") or "").lower()).strip()
    return doi, title


def _parse_doaj_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        record_id = item.get("id")
        bibjson = item.get("bibjson") or {}
        title = (bibjson.get("title") or "").strip()
        if not record_id or not title:
            return None

        authors = []
        for author in bibjson.get("author") or []:
            if isinstance(author, dict) and author.get("name"):
                authors.append(author["name"].strip())

        doi = None
        for identifier in bibjson.get("identifier") or []:
            if isinstance(identifier, dict) and identifier.get("type") == "doi" and identifier.get("id"):
                doi = identifier["id"].strip()
                break

        journal = bibjson.get("journal") or {}
        venue = (journal.get("title") or "").strip()

        year = None
        raw_year = bibjson.get("year")
        if raw_year:
            try:
                year = int(str(raw_year).strip()[:4])
            except ValueError:
                year = None

        abstract = (bibjson.get("abstract") or "").strip()

        fulltext_url = None
        pdf_url = None
        for link in bibjson.get("link") or []:
            if not isinstance(link, dict):
                continue
            link_url = (link.get("url") or "").strip()
            if not link_url:
                continue
            if link.get("type") == "fulltext" and not fulltext_url:
                fulltext_url = link_url
            if link_url.lower().endswith(".pdf") and not pdf_url:
                pdf_url = link_url
        # DOAJ links are open-access, but a full-text link is usually
        # a publisher landing page, not a PDF file. Only expose a
        # real PDF URL as pdf_url so extraction is never pointed at
        # an HTML page; summarization falls back to the abstract.
        url = fulltext_url or (f"https://doi.org/{doi}" if doi else "")

        return {
            "paperId": doi or record_id,
            "doaj_id": record_id,
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
            "isOpenAccess": True,
            "doi": f"https://doi.org/{doi}" if doi else None,
            "source": "DOAJ",
            "original_source": "DOAJ",
        }
    except Exception as e:
        logging.warning(f"Error parsing DOAJ item: {str(e)}")
        return None
