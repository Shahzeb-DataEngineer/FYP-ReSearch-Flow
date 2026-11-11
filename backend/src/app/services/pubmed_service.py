"""
PubMed API Service
Free, no API key. PubMed indexes biomedical literature via the
NCBI E-utilities API.

API: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
     https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi
Rate limit for anonymous use: 3 requests per second. This service
makes at most two calls per search (one esearch plus one batched
efetch) and sleeps briefly between them.
"""
import logging
import re
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional

import requests

ESEARCH_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
# Contact details sent with E-utilities requests, as NCBI recommends.
TOOL_NAME = "ReSearch-Flow"
CONTACT_EMAIL = "research-flow@example.com"
# Anonymous E-utilities limit is 3 requests per second.
MIN_REQUEST_INTERVAL = 0.34


def fetch_pubmed_papers(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Fetch papers from PubMed.

    Args:
        query: Search query/topic
        limit: Maximum number of results to return (max: 100)

    Returns:
        List of paper dictionaries in the common ReSearch Flow format
    """
    logging.info(f"Fetching PubMed papers for query: {query}, limit: {limit}")
    try:
        pmids = _esearch_pmids(query, limit)
        if not pmids:
            logging.info("No papers found from PubMed")
            return []
        # One batched efetch for all PMIDs, instead of one call per paper.
        time.sleep(MIN_REQUEST_INTERVAL)
        papers = _efetch_papers(pmids)
        logging.info(f"Successfully fetched {len(papers)} papers from PubMed")
        return papers
    except requests.exceptions.RequestException as e:
        logging.error(f"PubMed API error: {str(e)}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error in fetch_pubmed_papers: {str(e)}")
        return []


def _esearch_pmids(query: str, limit: int) -> List[str]:
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": min(limit, 100),
        "retmode": "json",
        "tool": TOOL_NAME,
        "email": CONTACT_EMAIL,
    }
    headers = {
        "User-Agent": "ReSearch-Flow/1.0",
        "Accept": "application/json",
    }
    response = requests.get(ESEARCH_BASE, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    return (data.get("esearchresult") or {}).get("idlist", []) or []


def _efetch_papers(pmids: List[str]) -> List[Dict[str, Any]]:
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "abstract",
        "retmode": "xml",
        "tool": TOOL_NAME,
        "email": CONTACT_EMAIL,
    }
    headers = {
        "User-Agent": "ReSearch-Flow/1.0",
        "Accept": "application/xml",
    }
    response = requests.get(EFETCH_BASE, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    papers = []
    seen_pmids: set = set()
    seen_dois: set = set()
    seen_titles: set = set()
    skipped = 0
    for article in root.findall("PubmedArticle"):
        paper = _parse_pubmed_article(article)
        if not paper:
            continue
        # PubMed can return the same paper twice in one query
        # (e.g. a record listed under two PMIDs after a merge).
        # A row is a duplicate if ANY of its identifiers was
        # already seen, same approach as the Europe PMC service.
        pmid, doi, title = _dedup_ids(paper)
        if (
            (pmid and pmid in seen_pmids)
            or (doi and doi in seen_dois)
            or (title and title in seen_titles)
        ):
            skipped += 1
            continue
        if pmid:
            seen_pmids.add(pmid)
        if doi:
            seen_dois.add(doi)
        if title:
            seen_titles.add(title)
        papers.append(paper)
    if skipped:
        logging.info(f"Skipped {skipped} duplicate PubMed result(s)")
    return papers


def _dedup_ids(paper: Dict[str, Any]) -> tuple:
    """Normalized (pmid, doi, title) identifiers for dedup.

    Empty strings mean "not present". The caller treats a row as a
    duplicate when any non-empty identifier was already seen.
    """
    pmid = (paper.get("pmid") or "").strip().lower()
    doi = (paper.get("doi") or "").strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    title = re.sub(r"[^a-z0-9]+", " ", (paper.get("title") or "").lower()).strip()
    return pmid, doi, title


def _parse_pubmed_article(article: ET.Element) -> Optional[Dict[str, Any]]:
    try:
        citation = article.find("MedlineCitation")
        if citation is None:
            return None
        pmid_elem = citation.find("PMID")
        pmid = pmid_elem.text.strip() if pmid_elem is not None and pmid_elem.text else ""
        article_elem = citation.find("Article")
        if article_elem is None:
            return None
        title_elem = article_elem.find("ArticleTitle")
        title = "".join(title_elem.itertext()).strip() if title_elem is not None else ""
        if not pmid or not title:
            return None

        authors = []
        for author in article_elem.findall("AuthorList/Author"):
            collective = author.find("CollectiveName")
            if collective is not None and collective.text:
                authors.append(collective.text.strip())
                continue
            last = author.find("LastName")
            fore = author.find("ForeName")
            initials = author.find("Initials")
            name = " ".join(
                part.text.strip()
                for part in (fore, last)
                if part is not None and part.text
            ).strip()
            if not name and last is not None and last.text:
                suffix = initials.text.strip() if initials is not None and initials.text else ""
                name = f"{last.text.strip()} {suffix}".strip()
            if name:
                authors.append(name)

        abstract_parts = []
        for text_elem in article_elem.findall("Abstract/AbstractText"):
            label = text_elem.get("Label")
            text = "".join(text_elem.itertext()).strip()
            if not text:
                continue
            abstract_parts.append(f"{label}: {text}" if label else text)
        abstract = " ".join(abstract_parts)

        journal_elem = article_elem.find("Journal")
        venue = ""
        year = None
        if journal_elem is not None:
            title_journal = journal_elem.find("Title")
            if title_journal is not None and title_journal.text:
                venue = title_journal.text.strip()
            pub_date = journal_elem.find("JournalIssue/PubDate")
            if pub_date is not None:
                year_elem = pub_date.find("Year")
                if year_elem is not None and year_elem.text:
                    try:
                        year = int(year_elem.text.strip())
                    except ValueError:
                        year = None

        doi = None
        for id_elem in article_elem.findall("ELocationID"):
            if id_elem.get("EIdType") == "doi" and id_elem.text:
                doi = id_elem.text.strip()
                break
        if not doi:
            for id_elem in article_elem.findall("ArticleId"):
                if id_elem.get("IdType") == "doi" and id_elem.text:
                    doi = id_elem.text.strip()
                    break

        # PubMed does not serve PDFs itself, and this service never
        # scrapes publisher pages. The DOI link is the route to the
        # publisher record; pdf_url stays None so summarization and
        # chat fall back to the abstract.
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

        return {
            "paperId": pmid,
            "pubmed_id": pmid,
            "title": title,
            "authors": authors,
            "published_date": None,
            "year": year,
            "abstract": abstract,
            "pdf_url": None,
            "openAccessPdf": None,
            "url": url,
            "venue": venue,
            "citationCount": 0,
            "isOpenAccess": False,
            "doi": f"https://doi.org/{doi}" if doi else None,
            "pmid": pmid,
            "source": "PubMed",
            "original_source": "PubMed",
        }
    except Exception as e:
        logging.warning(f"Error parsing PubMed article: {str(e)}")
        return None
