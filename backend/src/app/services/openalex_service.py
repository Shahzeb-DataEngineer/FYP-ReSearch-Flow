import logging
from typing import List, Dict, Any

import requests
import pandas as pd

from .openalex_client import get_openalex_headers, is_key_not_activated


OPENALEX_BASE_URL = "https://api.openalex.org"

# Last fetch error, if any (None when the most recent fetch succeeded).
# Read by callers that must tell "the API failed" apart from "no
# papers exist", e.g. the Deep Review pipeline.
last_error: str | None = None


def _flatten_abstract(abstract_inverted_index: Dict[str, List[int]] | None) -> str:
    """
    OpenAlex stores abstracts as an inverted index: {word: [positions...]}.
    Reconstruct a simple plain-text abstract.
    """
    if not abstract_inverted_index:
        return "N/A"

    # Find maximum position to size the list
    max_pos = max(pos for positions in abstract_inverted_index.values() for pos in positions)
    tokens: List[str] = [""] * (max_pos + 1)

    for word, positions in abstract_inverted_index.items():
        for pos in positions:
            if 0 <= pos < len(tokens):
                tokens[pos] = word

    abstract = " ".join(t for t in tokens if t)
    return abstract.strip() or "N/A"


def fetch_openalex_papers(topic: str, limit: int = 100) -> pd.DataFrame:
    """
    Fetch papers (works) from the OpenAlex API and normalize into a DataFrame
    compatible with the existing clean_and_deduplicate + Paper schema.
    Supports pagination to fetch more than 50 results.
    """
    logging.info(f"Fetching OpenAlex works for topic: {topic}, limit: {limit}")

    global last_error
    last_error = None

    per_page = 50  # OpenAlex max per page
    url = f"{OPENALEX_BASE_URL}/works"
    all_results: List[Dict[str, Any]] = []
    
    try:
        # Calculate number of pages needed
        pages_needed = (limit + per_page - 1) // per_page
        
        for page in range(1, pages_needed + 1):
            params = {
                "search": topic,
                "per-page": per_page,
                "page": page,
                # Sort by relevance then citations to get useful results
                "sort": "relevance_score:desc,cited_by_count:desc",
            }
            
            logging.info(f"Fetching page {page} of {pages_needed}...")
            headers = get_openalex_headers()
            resp = requests.get(url, params=params, headers=headers, timeout=30)
            if headers and is_key_not_activated(resp):
                # Key requested but not activated yet: fall back to a
                # keyless request so search keeps working until the
                # activation link is clicked.
                logging.warning(
                    "OpenAlex API key not activated yet (key_not_activated); "
                    "retrying without a key"
                )
                resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results: List[Dict[str, Any]] = data.get("results", [])
            
            if not results:
                logging.info(f"No more results at page {page}")
                break
                
            all_results.extend(results)
            
            # Stop if we have enough
            if len(all_results) >= limit:
                break

        if not all_results:
            logging.warning(f"No results from OpenAlex for topic: {topic}")
            return pd.DataFrame()

        logging.info(f"Total results fetched: {len(all_results)}")
        
        papers: List[Dict[str, Any]] = []
        for w in all_results[:limit]:
            abstract = _flatten_abstract(w.get("abstract_inverted_index"))

            # Authors
            authorships = w.get("authorships", []) or []
            authors = [
                (a.get("author") or {}).get("display_name", "Unknown Author")
                for a in authorships
            ]

            # Extract institutions from authorships
            # Each authorship has an institutions array with institution objects
            institutions_set = set()
            for authorship in authorships:
                institutions = authorship.get("institutions", []) or []
                for inst in institutions:
                    inst_name = inst.get("display_name")
                    if inst_name:
                        institutions_set.add(inst_name)
            institutions_list = sorted(list(institutions_set))  # Sort for consistency

            # Primary location / venue
            primary_location = w.get("primary_location") or {}
            source = primary_location.get("source") or {}

            venue_name = source.get("display_name") or "N/A"

            # Prefer landing_page_url, fallback to OA URL or OpenAlex URL
            landing_page = primary_location.get("landing_page_url") or ""
            oa_info = w.get("open_access") or {}
            oa_url = oa_info.get("oa_url") or ""
            openalex_id = w.get("id") or ""

            url_final = landing_page or oa_url or openalex_id

            # External IDs (DOI, etc.)
            external_ids = w.get("ids") or {}

            # Concepts as fields of study
            concepts = w.get("concepts") or []
            fields_of_study = [c.get("display_name", "") for c in concepts if c.get("display_name")]

            referenced_works = w.get("referenced_works") or []
            # Also get cited_by (papers that cite this paper) for bidirectional graph
            cited_by_works = w.get("cited_by_api_url")  # URL to fetch citing papers

            # Extract publication type from OpenAlex
            # OpenAlex uses 'type' field with values like: article, book, book-chapter, dataset, 
            # dissertation, editorial, erratum, letter, note, peer-review, posted-content, 
            # proceedings-article, reference-entry, report, review, review-article, software, standard, thesis
            work_type = w.get("type", "article")
            # Normalize type names for better display
            type_mapping = {
                "article": "article",
                "book": "book",
                "book-chapter": "book chapter",
                "dataset": "dataset",
                "dissertation": "dissertation",
                "editorial": "editorial",
                "erratum": "erratum",
                "letter": "letter",
                "note": "note",
                "peer-review": "peer review",
                "posted-content": "posted content",
                "proceedings-article": "proceedings article",
                "reference-entry": "reference entry",
                "report": "report",
                "review": "review",
                "review-article": "review article",
                "software": "software",
                "standard": "standard",
                "thesis": "thesis"
            }
            normalized_type = type_mapping.get(work_type, work_type.replace("-", " "))
            publication_types = [normalized_type] if normalized_type else ["article"]

            paper = {
                "paperId": w.get("id"),
                "title": w.get("display_name") or "N/A",
                "abstract": abstract,
                "authors": authors,
                "url": url_final,
                "year": w.get("publication_year"),
                "venue": venue_name,
                "publicationTypes": publication_types,  # Extract from OpenAlex type field
                "citationCount": w.get("cited_by_count", 0),
                "referenceCount": len(referenced_works),
                "referencedWorks": referenced_works,  # List of OpenAlex IDs this paper references
                "isOpenAccess": bool(oa_info.get("is_oa", False)),
                "openAccessPdf": oa_url,
                "externalIds": external_ids,
                "fieldsOfStudy": fields_of_study,
                "institutions": institutions_list,  # List of unique institution names
                "source": "OpenAlex",
                "topic": topic,
                "content": "",
            }

            papers.append(paper)

        df = pd.DataFrame(papers)
        logging.info(f"Fetched {len(df)} papers from OpenAlex")
        return df

    except requests.exceptions.RequestException as e:
        last_error = str(e)
        logging.error(f"OpenAlex API error: {str(e)}")
        return pd.DataFrame()
    except Exception as e:
        last_error = str(e)
        logging.error(f"Unexpected error in fetch_openalex_papers: {str(e)}")
        return pd.DataFrame()


