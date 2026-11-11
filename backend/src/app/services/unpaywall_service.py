"""
Unpaywall API Service
Free, no API key, only a contact email parameter. Unpaywall reports
the open-access status of a work and the best open-access location
for it.

API: https://api.unpaywall.org/v2/{doi}?email={email}

Unpaywall is DOI-based and has no keyword search, so this service
takes a DOI and returns a single paper record (or None when the
work has no open-access location). It never scrapes publisher pages.
"""
import logging
import os
import re
from typing import Dict, Any, Optional

import requests

UNPAYWALL_BASE = "https://api.unpaywall.org/v2"
# Contact email sent with Unpaywall requests, as the API requires.
# NOTE: Unpaywall rejects example.com addresses with HTTP 422
# ("Please use your own email address in API calls"), so the
# placeholder default below does NOT work live. Set UNPAYWALL_EMAIL
# to a real project address when deploying; until then Unpaywall
# lookups return no results.
CONTACT_EMAIL = os.getenv("UNPAYWALL_EMAIL", "research-flow@example.com")


def fetch_unpaywall_paper(doi: str) -> Optional[Dict[str, Any]]:
    """
    Fetch the open-access record for one DOI from Unpaywall.

    Args:
        doi: DOI of the work, with or without a doi.org prefix

    Returns:
        Paper dictionary in the common ReSearch Flow format, or None
        when the DOI is unknown or has no open-access location
    """
    clean_doi = _clean_doi(doi)
    if not clean_doi:
        return None
    logging.info(f"Fetching Unpaywall record for DOI: {clean_doi}")
    try:
        url = f"{UNPAYWALL_BASE}/{clean_doi}"
        params = {"email": CONTACT_EMAIL}
        headers = {
            "User-Agent": "ReSearch-Flow/1.0",
            "Accept": "application/json",
        }
        response = requests.get(url, params=params, headers=headers, timeout=30)
        if response.status_code == 404:
            logging.info(f"No Unpaywall record for DOI: {clean_doi}")
            return None
        response.raise_for_status()
        data = response.json()
        paper = _parse_unpaywall_item(data, clean_doi)
        if paper:
            logging.info(f"Successfully fetched Unpaywall record for DOI: {clean_doi}")
        return paper
    except requests.exceptions.RequestException as e:
        logging.error(f"Unpaywall API error: {str(e)}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error in fetch_unpaywall_paper: {str(e)}")
        return None


def _clean_doi(doi: str) -> str:
    """Strip a doi.org prefix and surrounding whitespace from a DOI."""
    if not doi:
        return ""
    clean = doi.strip()
    clean = re.sub(r"^https?://(dx\.)?doi\.org/", "", clean, flags=re.IGNORECASE)
    return clean.strip()


def _parse_unpaywall_item(item: Dict[str, Any], clean_doi: str) -> Optional[Dict[str, Any]]:
    try:
        title = (item.get("title") or "").strip()
        if not title:
            return None

        best_location = item.get("best_oa_location") or {}
        pdf_url = best_location.get("url_for_pdf") or None
        landing_url = best_location.get("url") or best_location.get("landing_page_url") or None
        # Only expose a real PDF URL as pdf_url. A landing page URL
        # is kept as the record URL, never passed to PDF extraction.
        if pdf_url and not pdf_url.lower().endswith(".pdf"):
            pdf_url = None
        if pdf_url is None and landing_url and landing_url.lower().endswith(".pdf"):
            pdf_url = landing_url
        is_oa = bool(item.get("is_oa"))
        if not is_oa or (not pdf_url and not landing_url):
            # No open-access copy to offer: not an error, just no result.
            return None

        authors = []
        for author in item.get("z_authors") or []:
            if not isinstance(author, dict):
                continue
            # z_authors carries a ready-made display name in
            # raw_author_name ("G. Kucsko"); given/family are not set.
            name = (author.get("raw_author_name") or "").strip()
            if not name:
                name = " ".join(
                    part for part in (author.get("given", ""), author.get("family", "")) if part
                ).strip()
            if name:
                authors.append(name)

        year = item.get("year")
        if year is not None:
            try:
                year = int(year)
            except (ValueError, TypeError):
                year = None

        venue = (item.get("journal_name") or "").strip()
        url = landing_url or f"https://doi.org/{clean_doi}"

        return {
            "paperId": clean_doi,
            "unpaywall_id": clean_doi,
            "title": title,
            "authors": authors,
            "published_date": item.get("published_date"),
            "year": year,
            "abstract": "",
            "pdf_url": pdf_url,
            "openAccessPdf": pdf_url,
            "url": url,
            "venue": venue,
            "citationCount": 0,
            "isOpenAccess": is_oa,
            "doi": f"https://doi.org/{clean_doi}",
            "oa_status": item.get("oa_status"),
            "source": "Unpaywall",
            "original_source": "Unpaywall",
        }
    except Exception as e:
        logging.warning(f"Error parsing Unpaywall item: {str(e)}")
        return None
