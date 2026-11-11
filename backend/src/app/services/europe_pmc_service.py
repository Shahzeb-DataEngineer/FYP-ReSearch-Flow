"""
Europe PMC API Service
Free, no API key. Europe PMC indexes life-science literature
(PubMed, PMC, preprints) with abstracts and open-access full text.

API: https://www.ebi.ac.uk/europepmc/webservices/rest/search
"""
import logging
import requests
from typing import List, Dict, Any, Optional

EUROPE_PMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def fetch_europe_pmc_papers(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Fetch papers from Europe PMC.

    Args:
        query: Search query/topic
        limit: Maximum number of results to return (max: 100)

    Returns:
        List of paper dictionaries in the common ReSearch Flow format
    """
    logging.info(f"Fetching Europe PMC papers for query: {query}, limit: {limit}")
    try:
        params = {
            "query": query,
            "format": "json",
            "pageSize": min(limit, 100),
            "resultType": "core",
        }
        headers = {
            "User-Agent": "ReSearch-Flow/1.0",
            "Accept": "application/json",
        }
        response = requests.get(EUROPE_PMC_BASE, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        results = (data.get("resultList") or {}).get("result", [])
        if not results:
            logging.info("No papers found from Europe PMC")
            return []
        papers = []
        seen_pmcids: set = set()
        seen_dois: set = set()
        seen_titles: set = set()
        skipped = 0
        for item in results:
            paper = _parse_europe_pmc_item(item)
            if not paper:
                continue
            # Europe PMC can return the same paper twice in one query
            # (e.g. a preprint and its journal version, or the same
            # record under two result rows). A row is a duplicate if
            # ANY of its identifiers was already seen: the two
            # versions often share a DOI but have different PMCIDs,
            # and some rows are missing a PMCID entirely, so a single
            # "first available id" key would miss those matches.
            pmcid, doi, title = _dedup_ids(paper)
            if (
                (pmcid and pmcid in seen_pmcids)
                or (doi and doi in seen_dois)
                or (title and title in seen_titles)
            ):
                skipped += 1
                continue
            if pmcid:
                seen_pmcids.add(pmcid)
            if doi:
                seen_dois.add(doi)
            if title:
                seen_titles.add(title)
            papers.append(paper)
        if skipped:
            logging.info(f"Skipped {skipped} duplicate Europe PMC result(s)")
        logging.info(f"Successfully fetched {len(papers)} papers from Europe PMC")
        return papers
    except requests.exceptions.RequestException as e:
        logging.error(f"Europe PMC API error: {str(e)}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error in fetch_europe_pmc_papers: {str(e)}")
        return []


def _dedup_ids(paper: Dict[str, Any]) -> tuple:
    """Normalized (pmcid, doi, title) identifiers for dedup.

    Empty strings mean "not present". The caller treats a row as a
    duplicate when any non-empty identifier was already seen, so a
    preprint/journal pair sharing a DOI is caught even when the
    PMCIDs differ, and a row missing a PMCID is still caught by DOI
    or title.
    """
    import re

    pmcid = (paper.get("pmcid") or "").strip().lower()
    doi = (paper.get("doi") or "").strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    title = re.sub(r"[^a-z0-9]+", " ", (paper.get("title") or "").lower()).strip()
    return pmcid, doi, title


def _parse_europe_pmc_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        paper_id = item.get("id")
        title = (item.get("title") or "").strip()
        if not paper_id or not title:
            return None

        authors = []
        author_string = item.get("authorString") or ""
        if author_string:
            authors = [a.strip() for a in author_string.split(",") if a.strip()]

        doi = item.get("doi")
        pmcid = item.get("pmcid")
        pmid = item.get("pmid")
        journal = (item.get("journalInfo") or {}).get("journal", {}) or {}
        venue = journal.get("title", "") or ""

        pdf_url = None
        for link in ((item.get("fullTextUrlList") or {}).get("fullTextUrl") or []):
            if not isinstance(link, dict):
                continue
            url = link.get("url") or ""
            if link.get("documentStyle") == "pdf" or url.lower().endswith(".pdf"):
                pdf_url = url
                break
        if not pdf_url and pmcid:
            pdf_url = f"https://europepmc.org/articles/{pmcid}"

        url = f"https://europepmc.org/article/MED/{pmid}" if pmid else (
            f"https://europepmc.org/articles/{pmcid}" if pmcid else ""
        )

        return {
            "paperId": pmcid or pmid or paper_id,
            "europe_pmc_id": paper_id,
            "title": title,
            "authors": authors,
            "published_date": None,
            "year": item.get("pubYear"),
            "abstract": item.get("abstractText", "") or "",
            "pdf_url": pdf_url,
            "openAccessPdf": pdf_url if item.get("isOpenAccess") == "Y" else None,
            "url": url,
            "venue": venue,
            "citationCount": item.get("citedByCount", 0) or 0,
            "isOpenAccess": item.get("isOpenAccess") == "Y",
            "doi": f"https://doi.org/{doi}" if doi else None,
            "pmcid": pmcid,
            "pmid": pmid,
            "source": "Europe PMC",
            "original_source": "Europe PMC",
        }
    except Exception as e:
        logging.warning(f"Error parsing Europe PMC item: {str(e)}")
        return None
