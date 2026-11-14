"""
Semantic Scholar API Service
Handles queries to the Semantic Scholar API for academic papers.
"""
import logging
import os
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from ..core.config import settings

SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_SCHOLAR_PAPER_URL = "https://www.semanticscholar.org/paper"

# Last fetch error, if any (None when the most recent fetch succeeded).
# See openalex_service.last_error.
last_error: str | None = None


def fetch_semantic_scholar_papers(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Fetch papers from Semantic Scholar API.
    
    Args:
        query: Search query/topic
        limit: Maximum number of results to return (max: 100)
    
    Returns:
        List of paper dictionaries with Semantic Scholar-specific fields
    """
    logging.info(f"Fetching Semantic Scholar papers for query: {query}, limit: {limit}")

    global last_error
    last_error = None

    try:
        # Semantic Scholar API endpoint
        url = f"{SEMANTIC_SCHOLAR_BASE}/paper/search"
        
        params = {
            "query": query,
            "limit": min(limit, 100),  # Semantic Scholar API limit
            # Keep fields conservative to avoid API 400 on unsupported fields.
            "fields": "paperId,title,authors,year,abstract,venue,openAccessPdf,citationCount,publicationDate,url,externalIds"
        }
        
        headers = {
            "User-Agent": "ReSearch-Flow/1.0 (mailto:contact@example.com)"  # Semantic Scholar requires user agent
        }
        # Using an API key significantly reduces 429 rate-limit failures.
        s2_key = (
            settings.SEMANTIC_SCHOLAR_API_KEY
            or os.getenv("SEMANTIC_SCHOLAR_API_KEY")
            or os.getenv("S2_API_KEY")
        )
        if s2_key:
            headers["x-api-key"] = s2_key
        
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        papers_data = data.get("data", [])
        
        if not papers_data:
            logging.info("No papers found from Semantic Scholar")
            return []
        
        papers = []
        for paper_data in papers_data:
            paper = _parse_semantic_scholar_paper(paper_data)
            if paper:
                papers.append(paper)
        
        logging.info(f"Successfully fetched {len(papers)} papers from Semantic Scholar")
        return papers
        
    except requests.exceptions.HTTPError as e:
        last_error = str(e)
        if e.response.status_code == 429:
            logging.error("Semantic Scholar API rate limit exceeded")
        else:
            logging.error(f"Semantic Scholar API HTTP error: {str(e)}")
            try:
                logging.error(f"Semantic Scholar API response: {e.response.text}")
            except Exception:
                pass
        return []
    except requests.exceptions.RequestException as e:
        last_error = str(e)
        logging.error(f"Semantic Scholar API error: {str(e)}")
        return []
    except Exception as e:
        last_error = str(e)
        logging.error(f"Unexpected error in fetch_semantic_scholar_papers: {str(e)}")
        return []


def _parse_semantic_scholar_paper(paper_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parse a Semantic Scholar paper data into our paper format.
    
    Args:
        paper_data: Paper data from Semantic Scholar API
    
    Returns:
        Parsed paper dictionary or None if parsing fails
    """
    try:
        # Paper ID
        paper_id = paper_data.get("paperId")
        if not paper_id:
            return None
        
        # Title
        title = paper_data.get("title", "Untitled")
        if not title or title == "Untitled":
            return None
        
        # Authors
        authors = []
        authors_data = paper_data.get("authors", [])
        for author in authors_data:
            if isinstance(author, dict):
                author_name = author.get("name", "")
                if author_name:
                    authors.append(author_name)
        
        # Year
        year = paper_data.get("year")
        
        # Published date
        published_date = None
        pub_date = paper_data.get("publicationDate")
        if pub_date:
            try:
                # Try to parse date string
                published_date = pub_date
            except:
                pass
        
        # Abstract
        abstract = paper_data.get("abstract", "") or ""
        
        # PDF URL - prioritize openAccessPdf
        pdf_url = None
        open_access_pdf = paper_data.get("openAccessPdf")
        if open_access_pdf and isinstance(open_access_pdf, dict):
            pdf_url = open_access_pdf.get("url")
        
        # If no open access PDF, try external IDs for arXiv
        if not pdf_url:
            external_ids = paper_data.get("externalIds", {})
            if external_ids:
                arxiv_id = external_ids.get("arXiv")
                if arxiv_id:
                    # Construct arXiv PDF URL
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        
        # Paper URL
        url = paper_data.get("url") or f"{SEMANTIC_SCHOLAR_PAPER_URL}/{paper_id}"
        
        # Venue/Journal
        venue = paper_data.get("venue", "") or ""
        
        # Citation count
        citation_count = paper_data.get("citationCount", 0) or 0
        
        # Reference count
        reference_count = paper_data.get("referenceCount", 0) or 0
        
        # Publication types
        publication_types = paper_data.get("publicationTypes", []) or []
        
        # Fields of study
        fields_of_study = paper_data.get("fieldsOfStudy", []) or []
        
        # External IDs (arXiv, DOI, etc.)
        external_ids = paper_data.get("externalIds", {}) or {}
        arxiv_id = external_ids.get("arXiv")
        doi = external_ids.get("DOI")
        if doi and not doi.startswith("http"):
            doi = f"https://doi.org/{doi}"
        
        # Determine original source based on external IDs or venue
        source = "Semantic Scholar"
        if arxiv_id:
            source = "arXiv"
        elif "pubmed" in venue.lower() or "pmc" in venue.lower():
            source = "PMC"
        elif "core" in venue.lower():
            source = "CORE"
        
        paper = {
            "paperId": paper_id,
            "semantic_scholar_id": paper_id,
            "title": title,
            "authors": authors,
            "published_date": published_date,
            "year": year,
            "abstract": abstract,
            "pdf_url": pdf_url,
            "openAccessPdf": pdf_url,  # For compatibility
            "url": url,
            "venue": venue,
            "citationCount": citation_count,
            "referenceCount": reference_count,
            "publicationTypes": publication_types,
            "fieldsOfStudy": fields_of_study,
            "isOpenAccess": bool(pdf_url),
            "arxiv_id": arxiv_id,
            "doi": doi,
            "externalIds": external_ids,
            "source": source,
            # Also include original source info for compatibility
            "original_source": source
        }
        
        return paper
        
    except Exception as e:
        logging.warning(f"Error parsing Semantic Scholar paper: {str(e)}")
        return None


