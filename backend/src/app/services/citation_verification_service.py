"""
Citation verification and paper badges.

Move 2 of the competitor playbook: a verifiable-citation engine.
Trust is the market weak point (fabricated citations, citations that
do not support the adjacent sentence), so this module answers one
narrow question with evidence attached: does this source text actually
say what the claim says?

- verify_claim: finds the best supporting sentence in a source text
  using local embeddings (nomic-embed-text) with a pure token-overlap
  fallback when embeddings are unavailable. It only reports verified
  when a sentence passes the threshold; otherwise it says so.
- get_paper_badges: resolves a DOI through the live OpenAlex API and
  returns retraction, open-access and peer-review/preprint badges.
  Every badge field comes from the OpenAlex response; nothing is
  invented. Returns None when OpenAlex has no record for the DOI.
"""
import logging
import math
import re
import urllib.parse
from typing import Dict, List, Optional

import requests

from .llm_provider import get_embeddings
from .openalex_client import get_openalex_headers, is_key_not_activated

logger = logging.getLogger(__name__)

OPENALEX_WORKS_URL = "https://api.openalex.org/works"

# Cosine similarity at or above this value counts as support when
# embeddings are available. Calibrated live against nomic-embed-text
# on 2026-11-13: true paraphrases of a source sentence scored
# 0.84-0.90, unrelated claims scored 0.50-0.56, so 0.70 separates
# them with margin on both sides. Token overlap uses its own threshold.
EMBEDDING_THRESHOLD = 0.70
TOKEN_OVERLAP_THRESHOLD = 0.30

# OpenAlex work types that are normally peer reviewed when they appear
# in a journal or proceedings source.
PEER_REVIEWED_TYPES = {
    "article",
    "review",
    "review-article",
    "proceedings-article",
    "editorial",
    "letter",
}

_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "must", "can", "this",
    "that", "these", "those", "it", "its", "they", "we", "you", "he",
    "she", "not", "no", "than", "then", "so", "such", "if", "when",
}


def split_sentences(text: str) -> List[str]:
    """Split text into sentences, keeping fragments over 10 chars."""
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]


def _tokens(text: str) -> set:
    words = re.findall(r"\b[a-z0-9]+\b", text.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 2}


def token_overlap_score(claim: str, sentence: str) -> float:
    """Overlap coefficient of content tokens: |intersection| / |claim|.

    Ranges 0-1. A sentence that contains most of the claim's content
    words scores near 1; a sentence sharing only one word scores low.
    """
    claim_tokens = _tokens(claim)
    if not claim_tokens:
        return 0.0
    sentence_tokens = _tokens(sentence)
    if not sentence_tokens:
        return 0.0
    return len(claim_tokens & sentence_tokens) / len(claim_tokens)


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _embed_texts(texts: List[str]) -> Optional[List[List[float]]]:
    """Embed texts with the local model, or None if it is unavailable."""
    try:
        embeddings = get_embeddings()
        return embeddings.embed_documents(texts)
    except Exception as e:
        logger.warning("Local embeddings unavailable, using token overlap: %s", e)
        return None


def verify_claim(
    claim: str,
    source_text: str,
    threshold: float = EMBEDDING_THRESHOLD,
) -> Dict[str, object]:
    """Check whether any sentence in source_text supports the claim.

    Returns a dict with verified (bool), score (float), the best
    supporting_sentence, its sentence_index, and a short quote (the
    supporting sentence itself, truncated). When no sentence passes
    the threshold, verified is False and supporting_sentence is None:
    the function never claims verification it does not have.
    """
    result: Dict[str, object] = {
        "verified": False,
        "score": 0.0,
        "supporting_sentence": None,
        "sentence_index": None,
        "quote": None,
        "method": "token_overlap",
    }
    if not claim or not claim.strip() or not source_text or not source_text.strip():
        return result

    sentences = split_sentences(source_text)
    if not sentences:
        return result

    vectors = _embed_texts([claim] + sentences)
    if vectors is not None and len(vectors) == len(sentences) + 1:
        claim_vec = vectors[0]
        scores = [_cosine(claim_vec, vec) for vec in vectors[1:]]
        result["method"] = "embedding"
        use_threshold = threshold
    else:
        scores = [token_overlap_score(claim, s) for s in sentences]
        result["method"] = "token_overlap"
        use_threshold = TOKEN_OVERLAP_THRESHOLD

    best_idx = max(range(len(sentences)), key=lambda i: scores[i])
    best_score = round(float(scores[best_idx]), 4)
    result["score"] = best_score
    if best_score >= use_threshold:
        result["verified"] = True
        result["supporting_sentence"] = sentences[best_idx]
        result["sentence_index"] = best_idx
        result["quote"] = sentences[best_idx][:300]
    return result


def _normalize_doi(doi: str) -> str:
    doi = (doi or "").strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi


def get_paper_badges(doi: str) -> Optional[Dict[str, object]]:
    """Fetch trust badges for a DOI from the live OpenAlex API.

    Returns None when OpenAlex has no record for the DOI (HTTP 404
    or an empty response). Every returned field is read from the
    OpenAlex work record:
    - retracted: work.is_retracted
    - open_access: open_access.is_oa
    - peer_reviewed: type is a peer-reviewed type and the primary
      location source type is journal or proceedings
    - preprint: type is posted-content or the source type is repository
    - citation_count: cited_by_count
    - openalex_url: the work id (its OpenAlex URL)
    """
    clean_doi = _normalize_doi(doi)
    if not clean_doi:
        return None
    url = f"{OPENALEX_WORKS_URL}/{urllib.parse.quote('https://doi.org/' + clean_doi, safe='')}"
    try:
        headers = get_openalex_headers()
        resp = requests.get(url, headers=headers, timeout=30)
        if headers and is_key_not_activated(resp):
            # Key requested but not activated yet: fall back to a
            # keyless request so badges keep working until the
            # activation link is clicked.
            logger.warning(
                "OpenAlex API key not activated yet (key_not_activated); "
                "retrying without a key"
            )
            resp = requests.get(url, timeout=30)
    except requests.exceptions.RequestException as e:
        logger.error("OpenAlex badges lookup failed for DOI %s: %s", clean_doi, e)
        return None
    if resp.status_code == 404:
        return None
    try:
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error("OpenAlex badges lookup failed for DOI %s: %s", clean_doi, e)
        return None
    work = resp.json() or {}
    if not work.get("id"):
        return None

    oa_info = work.get("open_access") or {}
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    work_type = (work.get("type") or "").lower()
    source_type = (source.get("type") or "").lower()

    peer_reviewed = work_type in PEER_REVIEWED_TYPES and source_type in {
        "journal",
        "proceedings",
        "conference",
        "book",
    }
    preprint = work_type == "posted-content" or source_type == "repository"

    return {
        "doi": clean_doi,
        "retracted": bool(work.get("is_retracted", False)),
        "open_access": bool(oa_info.get("is_oa", False)),
        "peer_reviewed": peer_reviewed,
        "preprint": preprint,
        "publication_type": work_type or None,
        "source_type": source_type or None,
        "venue": source.get("display_name"),
        "citation_count": int(work.get("cited_by_count") or 0),
        "openalex_url": work.get("id"),
        "title": work.get("display_name"),
    }
