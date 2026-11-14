"""
Open-access full-text bridge.

Move 3 of the competitor playbook. For a DOI, resolve the legal
open-access copy through OpenAlex (best_location / open_access) and
Unpaywall, in that order. Only a real PDF URL from one of those
sources is ever returned: a paywalled paper honestly reports
not_available and no PDF URL is invented.

The resolved PDF can then be downloaded, its text extracted with
the existing PDF service, and indexed into the existing FAISS +
BM25 RAG store (chat_service.index_paper_text), so RAG ask can
answer from the full text instead of only the abstract.
"""
import logging
import re
import urllib.parse
from typing import Any, Dict, Optional

import requests

from .openalex_client import get_openalex_headers, is_key_not_activated
from .pdf_service import get_pdf_text_from_url
from .unpaywall_service import fetch_unpaywall_paper

logger = logging.getLogger(__name__)

OPENALEX_WORKS_URL = "https://api.openalex.org/works"


def normalize_doi(doi: str) -> str:
    doi = (doi or "").strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi.strip()


def _pdf_from_location(location: Dict[str, Any]) -> Optional[str]:
    if not isinstance(location, dict):
        return None
    # url_for_pdf is, by definition, a PDF URL: trust the field
    # name. arXiv PDF URLs (arxiv.org/pdf/1706.03762) carry no
    # .pdf suffix, so a suffix check would wrongly reject them.
    pdf_url = location.get("url_for_pdf") or ""
    if pdf_url:
        return pdf_url
    landing = location.get("url") or location.get("landing_page_url") or ""
    if landing and (landing.lower().endswith(".pdf") or "/pdf/" in landing.lower()):
        return landing
    return None


def _openalex_lookup(clean_doi: str) -> Dict[str, Any]:
    """Raw OpenAlex work record for a DOI, or {} when unknown."""
    url = f"{OPENALEX_WORKS_URL}/{urllib.parse.quote('https://doi.org/' + clean_doi, safe='')}"
    try:
        headers = get_openalex_headers()
        resp = requests.get(url, headers=headers, timeout=30)
        if headers and is_key_not_activated(resp):
            logger.warning("OpenAlex API key not activated; retrying keyless")
            resp = requests.get(url, timeout=30)
    except requests.exceptions.RequestException as e:
        logger.error("OpenAlex full-text lookup failed for DOI %s: %s", clean_doi, e)
        return {}
    if resp.status_code == 404:
        return {}
    try:
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error("OpenAlex full-text lookup failed for DOI %s: %s", clean_doi, e)
        return {}
    work = resp.json() or {}
    return work if isinstance(work, dict) and work.get("id") else {}


def resolve_oa_copy(doi: str) -> Dict[str, Any]:
    """Resolve the legal open-access PDF for a DOI.

    Returns a dict with available (bool), pdf_url (str or None),
    landing_url, oa_status, source (OpenAlex / Unpaywall / None),
    title and a status string (available / not_available).
    A paywalled or unknown DOI returns available False with
    pdf_url None, never a guessed URL.
    """
    clean_doi = normalize_doi(doi)
    if not clean_doi:
        return {
            "doi": "",
            "status": "not_available",
            "available": False,
            "pdf_url": None,
            "landing_url": None,
            "oa_status": None,
            "source": None,
            "title": None,
            "message": "A DOI is required.",
        }
    work = _openalex_lookup(clean_doi)
    oa_info = work.get("open_access") or {}
    best = work.get("best_location") or {}
    pdf_url = _pdf_from_location(best)
    if not pdf_url:
        for location in work.get("locations") or []:
            pdf_url = _pdf_from_location(location)
            if pdf_url:
                break
    landing_url = (
        best.get("landing_page_url")
        or best.get("url")
        or (work.get("primary_location") or {}).get("landing_page_url")
        or None
    )
    if not pdf_url:
        # Some works (e.g. arXiv papers) have no best_location PDF
        # but do list a direct OA PDF in open_access.oa_url.
        oa_url = oa_info.get("oa_url") or ""
        if oa_url.lower().endswith(".pdf") or "/pdf/" in oa_url.lower():
            pdf_url = oa_url
    if pdf_url:
        return {
            "doi": clean_doi,
            "status": "available",
            "available": True,
            "pdf_url": pdf_url,
            "landing_url": landing_url,
            "oa_status": oa_info.get("oa_status"),
            "source": "OpenAlex",
            "title": work.get("display_name"),
            "message": "Open-access PDF found via OpenAlex.",
        }
    # OpenAlex has no PDF: try Unpaywall, which sometimes knows a
    # repository copy OpenAlex does not list.
    try:
        paper = fetch_unpaywall_paper(clean_doi)
    except Exception as e:
        logger.warning("Unpaywall lookup failed for DOI %s: %s", clean_doi, e)
        paper = None
    if paper and paper.get("pdf_url"):
        return {
            "doi": clean_doi,
            "status": "available",
            "available": True,
            "pdf_url": paper["pdf_url"],
            "landing_url": paper.get("url"),
            "oa_status": paper.get("oa_status"),
            "source": "Unpaywall",
            "title": paper.get("title") or work.get("display_name"),
            "message": "Open-access PDF found via Unpaywall.",
        }
    return {
        "doi": clean_doi,
        "status": "not_available",
        "available": False,
        "pdf_url": None,
        "landing_url": landing_url,
        "oa_status": oa_info.get("oa_status"),
        "source": None,
        "title": work.get("display_name"),
        "message": (
            "No legal open-access PDF was found for this DOI. "
            "The paper may be paywalled."
        ),
    }


def _europe_pmc_text_for_doi(clean_doi: str) -> Optional[str]:
    """Full text from Europe PMC as JATS XML, for a DOI that has a
    PMC copy. Used when the publisher PDF cannot be downloaded
    (cookie / bot barriers): the PMC copy is the same legal
    open-access article, served without those barriers.
    """
    try:
        from .pdf_service import _fetch_europe_pmc_full_text

        resp = requests.get(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            params={"query": f"DOI:{clean_doi}", "format": "json", "pageSize": 1},
            headers={"User-Agent": "ReSearch-Flow/1.0"},
            timeout=30,
        )
        resp.raise_for_status()
        results = (resp.json() or {}).get("resultList", {}).get("result", [])
        if not results:
            return None
        pmcid = results[0].get("pmcid")
        if not pmcid:
            return None
        text, _error = _fetch_europe_pmc_full_text(pmcid)
        return text
    except Exception as e:
        logger.warning("Europe PMC fallback failed for DOI %s: %s", clean_doi, e)
        return None


def fetch_fulltext(doi: str, download: bool = True, index: bool = True) -> Dict[str, Any]:
    """Resolve, download, extract and optionally index a paper's full text.

    With download False this is just the resolver. With download
    True the PDF is fetched and its text extracted; with index True
    the text is also indexed into the FAISS + BM25 RAG store so chat
    can answer from the full text. Returns the resolver fields plus
    text_chars, paper_id and chat_ready when indexing succeeded.
    """
    resolved = resolve_oa_copy(doi)
    if not resolved["available"]:
        return dict(resolved, text_chars=0, paper_id=None, chat_ready=False)
    if not download:
        return dict(resolved, text_chars=0, paper_id=None, chat_ready=False)
    pdf_url = resolved["pdf_url"]
    text, error = get_pdf_text_from_url(pdf_url)
    via_pmc = False
    if not text:
        # Publisher PDF blocked (cookie / bot barrier): try the
        # Europe PMC open-access copy of the same article, if any.
        text = _europe_pmc_text_for_doi(resolved["doi"])
        if text:
            error = None
            via_pmc = True
    if not text:
        return dict(
            resolved,
            status="download_failed",
            available=True,
            text_chars=0,
            paper_id=None,
            chat_ready=False,
            message=f"Open-access PDF found but its text could not be extracted: {error or 'unknown error'}",
        )
    paper_id = None
    chat_ready = False
    if index:
        try:
            from .chat_service import index_paper_text

            paper_id = index_paper_text(
                text,
                paper_title=resolved.get("title"),
                paper_source=f"Full text ({resolved['source']})",
            )
            chat_ready = True
        except Exception as e:
            logger.warning("Full-text indexing failed for DOI %s: %s", resolved["doi"], e)
    return dict(
        resolved,
        status="available",
        text_chars=len(text),
        text_preview=text[:500],
        paper_id=paper_id,
        chat_ready=chat_ready,
        fulltext_source="Europe PMC" if via_pmc else resolved["source"],
        message=(
            ("Full text extracted via Europe PMC and indexed for chat."
             if via_pmc else "Full text extracted and indexed for chat.")
            if chat_ready
            else "Full text extracted; chat indexing failed, retry later."
        ),
    )
