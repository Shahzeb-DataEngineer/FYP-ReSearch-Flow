"""
Cross-project private knowledge graph (Move 6).

A local, per-user knowledge layer over the user's saved papers and
notes. Everything lives on this machine:

- Library storage: one JSON file per user under backend/data/library/
  (papers + notes the frontend sends from the user's saved articles).
  Nothing is uploaded anywhere; there is no cloud index.
- Entity graph: key entities/topics per paper, extracted by the
  local LLM with a deterministic keyword fallback, linked across
  papers by shared entities (co-occurrence edges).
- Cross-paper RAG ask: a local FAISS index (nomic-embed-text, the
  same 768-dim embeddings as the paper chat) built from the user's
  own library, with a keyword fallback when Ollama is down.
- Zotero sync (free API, read-only import): import a Zotero library
  with a user API key from the environment (ZOTERO_API_KEY /
  ZOTERO_USER_ID), and export the saved library to
  Zotero-compatible BibTeX / RIS.
- New-paper alerts: locally computed. For each saved topic the
  backend checks the free OpenAlex API for papers published since
  the last check and lists them. No external alert service.
"""
import hashlib
import json
import logging
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..core.config import settings
from .llm_provider import check_ollama_available, get_chat_model, get_embeddings
from .openalex_client import get_openalex_headers, is_key_not_activated

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "library"
OPENALEX_BASE_URL = "https://api.openalex.org"
ZOTERO_BASE_URL = "https://api.zotero.org"

_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "which", "study",
    "paper", "research", "based", "using", "used", "results", "show", "shows",
    "also", "more", "than", "into", "over", "under", "between", "among",
    "their", "they", "them", "then", "when", "while", "about", "after",
    "before", "have", "has", "were", "been", "being", "such", "other",
    "these", "those", "each", "many", "much", "most", "some", "any",
    "approach", "method", "methods", "model", "models", "analysis",
    "system", "systems", "data", "new", "novel", "review",
}


def _safe_user_id(user_id: str) -> str:
    """File-safe key for one user's library (no path traversal)."""
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", (user_id or "local").strip() or "local")
    return cleaned[:64]


def _library_path(user_id: str) -> Path:
    return DATA_DIR / f"{_safe_user_id(user_id)}.json"


def _empty_library(user_id: str) -> Dict[str, Any]:
    return {
        "user_id": user_id,
        "papers": [],
        "topics": [],
        "last_alert_check": None,
        "alerts": [],
        "updated_at": None,
    }


def load_library(user_id: str) -> Dict[str, Any]:
    """Load one user's local library (empty library if none yet)."""
    path = _library_path(user_id)
    if not path.exists():
        return _empty_library(user_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("papers"), list):
            return data
    except Exception as e:
        logger.warning("Library file unreadable, starting fresh: %s", e)
    return _empty_library(user_id)


def save_library(user_id: str, library: Dict[str, Any]) -> None:
    """Persist one user's library locally. Private to this machine."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    library["updated_at"] = datetime.now(timezone.utc).isoformat()
    _library_path(user_id).write_text(
        json.dumps(library, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _paper_key(paper: Dict[str, Any]) -> str:
    doi = (paper.get("doi") or "").strip().lower()
    if doi:
        return "doi:" + doi
    title = (paper.get("title") or "").strip().lower()
    return "title:" + hashlib.sha256(title.encode()).hexdigest()[:16]


def normalize_library_paper(paper: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize one saved paper / note into the library shape."""
    authors = paper.get("authors") or []
    if authors and isinstance(authors[0], dict):
        authors = [a.get("name", "") for a in authors if a.get("name")]
    return {
        "key": _paper_key(paper),
        "title": (paper.get("title") or "Untitled").strip(),
        "abstract": (paper.get("abstract") or "").strip(),
        "notes": (paper.get("notes") or "").strip(),
        "authors": list(authors)[:5],
        "year": paper.get("year"),
        "venue": paper.get("venue") or "",
        "doi": (paper.get("doi") or "").strip(),
        "url": paper.get("url") or "",
        "source": paper.get("source") or "",
        "entities": list(paper.get("entities") or []),
    }


# ── Entity extraction ──────────────────────────────────────────────

_GENERIC_ENTITIES = {
    "method", "methods", "dataset", "datasets", "disease", "diseases",
    "organism", "organisms", "tool", "tools", "concept", "concepts",
    "paper", "study", "result", "results", "research", "analysis",
}


def _drop_generic_entities(entities: List[str]) -> List[str]:
    """Drop generic words (often echoed from the prompt) from an
    entity list, keeping real topics."""
    return [e for e in entities if e.strip().lower() not in _GENERIC_ENTITIES]


def extract_entities_fallback(paper: Dict[str, Any]) -> List[str]:
    """Deterministic keyword entities from title + abstract + notes.

    Capitalised multi-word phrases and frequent content words, minus
    stopwords. Used when the local LLM is unavailable, and as the
    seed list the LLM refines.
    """
    text = " ".join(
        [
            paper.get("title") or "",
            paper.get("abstract") or "",
            paper.get("notes") or "",
        ]
    )
    phrases = re.findall(r"\b(?:[A-Z][a-z]{2,}\s+){1,2}[A-Z][a-z]{2,}\b", text)
    words = re.findall(r"\b[a-z]{4,}\b", text.lower())
    counts = Counter(w for w in words if w not in _STOPWORDS)
    entities = []
    for phrase in phrases:
        cleaned = " ".join(phrase.split())
        if cleaned.lower() not in [e.lower() for e in entities]:
            entities.append(cleaned)
    for word, _ in counts.most_common(8):
        if word not in [e.lower() for e in entities]:
            entities.append(word)
    return entities[:10]


def extract_entities(paper: Dict[str, Any]) -> List[str]:
    """Extract key entities/topics for one paper with the local LLM.

    Falls back to the deterministic keyword extractor when Ollama is
    down or the model output is unusable, so indexing never fails.
    """
    fallback = extract_entities_fallback(paper)
    fallback = _drop_generic_entities(fallback)
    if not check_ollama_available():
        return fallback
    text = ((paper.get("title") or "") + "\n" + (paper.get("abstract") or "")[:2000]).strip()
    if len(text) < 20:
        return fallback
    try:
        llm = get_chat_model(temperature=0.0)
        prompt = (
            "List the key topics named in this research paper as a "
            "JSON array of short strings, at most 8 items. Use only "
            "words that actually appear in the text. Output ONLY the "
            "JSON array, no other text.\n\n"
            f"{text}"
        )
        response = llm.invoke(prompt)
        content = response.content if isinstance(response.content, str) else str(response.content)
        start = content.find("[")
        end = content.rfind("]")
        if start != -1 and end > start:
            parsed = json.loads(content[start:end + 1], strict=False)
            if isinstance(parsed, list):
                entities = [str(e).strip() for e in parsed if str(e).strip()][:8]
                entities = _drop_generic_entities(entities)
                if entities:
                    return entities
    except Exception as e:
        logger.warning("Entity extraction fell back to keywords: %s", e)
    return fallback


def index_papers(user_id: str, papers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Index saved papers/notes into the user's local library.

    Dedupes by DOI (title fallback), merges notes onto existing
    papers, and extracts entities per paper. Returns the index
    summary.
    """
    library = load_library(user_id)
    existing = {p["key"]: p for p in library.get("papers", [])}
    added = 0
    updated = 0
    for raw in papers:
        paper = normalize_library_paper(raw)
        if not paper["title"] or paper["title"] == "Untitled":
            continue
        if paper["key"] in existing:
            old = existing[paper["key"]]
            if paper["notes"]:
                old["notes"] = paper["notes"]
            if paper["abstract"] and not old.get("abstract"):
                old["abstract"] = paper["abstract"]
            updated += 1
            continue
        paper["entities"] = extract_entities(paper)
        existing[paper["key"]] = paper
        added += 1
    library["papers"] = list(existing.values())
    save_library(user_id, library)
    return {
        "user_id": user_id,
        "papers_indexed": len(library["papers"]),
        "added": added,
        "updated": updated,
        "entities_total": sum(len(p.get("entities") or []) for p in library["papers"]),
    }


# ── Knowledge graph ────────────────────────────────────────────────

def build_knowledge_graph(user_id: str) -> Dict[str, Any]:
    """Build the entity graph over one user's library.

    Nodes: papers and entities. Edges: paper-mentions-entity, and
    entity-co-occurs-with-entity (two entities in the same paper).
    Shared entities are what link papers across projects.
    """
    library = load_library(user_id)
    papers = library.get("papers", [])
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    entity_papers: Dict[str, List[str]] = defaultdict(list)
    for paper in papers:
        nodes.append(
            {
                "id": f"paper:{paper['key']}",
                "type": "paper",
                "label": paper["title"][:100],
                "title": paper["title"],
                "year": paper.get("year"),
                "doi": paper.get("doi") or "",
                "entity_count": len(paper.get("entities") or []),
            }
        )
        for entity in paper.get("entities") or []:
            entity_papers[entity.lower()].append(paper["key"])
    entity_ids: Dict[str, str] = {}
    for entity_lower, paper_keys in sorted(entity_papers.items()):
        eid = f"entity:{hashlib.sha256(entity_lower.encode()).hexdigest()[:12]}"
        entity_ids[entity_lower] = eid
        display = entity_lower
        for paper in papers:
            for entity in paper.get("entities") or []:
                if entity.lower() == entity_lower:
                    display = entity
                    break
            if display != entity_lower:
                break
        nodes.append(
            {
                "id": eid,
                "type": "entity",
                "label": display,
                "title": display,
                "paper_count": len(set(paper_keys)),
                "shared": len(set(paper_keys)) > 1,
            }
        )
    for paper in papers:
        for entity in paper.get("entities") or []:
            edges.append(
                {
                    "source": f"paper:{paper['key']}",
                    "target": entity_ids[entity.lower()],
                    "type": "mentions",
                }
            )
    co_occurrence: Counter = Counter()
    for paper in papers:
        entities = sorted({e.lower() for e in paper.get("entities") or []})
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                co_occurrence[(entities[i], entities[j])] += 1
    for (a, b), count in co_occurrence.items():
        edges.append(
            {
                "source": entity_ids[a],
                "target": entity_ids[b],
                "type": "co_occurs",
                "weight": count,
            }
        )
    shared_entities = [n for n in nodes if n["type"] == "entity" and n.get("shared")]
    return {
        "user_id": user_id,
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "papers": len(papers),
            "entities": len(entity_ids),
            "shared_entities": len(shared_entities),
            "edges": len(edges),
        },
        "shared_entities": [n["label"] for n in shared_entities],
    }


# ── Cross-paper RAG ask ────────────────────────────────────────────

def _keyword_retrieve(papers: List[Dict[str, Any]], question: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Rank library papers by word overlap with the question."""
    words = {w for w in re.findall(r"\b[a-z]{4,}\b", question.lower()) if w not in _STOPWORDS}
    scored = []
    for paper in papers:
        text = ((paper.get("title") or "") + " " + (paper.get("abstract") or "") + " " + (paper.get("notes") or "")).lower()
        overlap = sum(1 for w in words if w in text)
        if overlap:
            scored.append((overlap, paper))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [paper for _, paper in scored[:top_k]]


def ask_library(user_id: str, question: str, top_k: int = 3) -> Dict[str, Any]:
    """Answer a question over the user's own library (cross-paper RAG).

    Retrieves the most relevant saved papers with a local FAISS
    index over their abstracts + notes; when Ollama is down, falls
    back to keyword retrieval and an extractive answer built from
    the retrieved abstracts. Every answer lists its sources.
    """
    question = (question or "").strip()
    if not question:
        raise ValueError("question is required")
    library = load_library(user_id)
    papers = library.get("papers", [])
    if not papers:
        return {
            "status": "empty_library",
            "answer": "Your library is empty. Save some papers first, then ask.",
            "sources": [],
            "retrieval": "none",
        }
    retrieved: List[Dict[str, Any]] = []
    retrieval = "keyword"
    if check_ollama_available():
        try:
            from langchain_core.documents import Document
            from langchain_community.vectorstores import FAISS

            docs = [
                Document(
                    page_content=(
                        f"{p.get('title') or ''}\n"
                        f"{p.get('abstract') or ''}\n"
                        f"Notes: {p.get('notes') or ''}"
                    ),
                    metadata={"key": p["key"], "title": p.get("title") or ""},
                )
                for p in papers
            ]
            store = FAISS.from_documents(docs, get_embeddings())
            hits = store.similarity_search(question, k=top_k)
            hit_keys = {h.metadata.get("key") for h in hits}
            retrieved = [p for p in papers if p["key"] in hit_keys]
            retrieval = "faiss"
        except Exception as e:
            logger.warning("Library FAISS retrieval failed, using keywords: %s", e)
    if not retrieved:
        retrieved = _keyword_retrieve(papers, question, top_k=top_k)
    if not retrieved:
        return {
            "status": "no_match",
            "answer": "None of your saved papers seem to cover this question.",
            "sources": [],
            "retrieval": retrieval,
        }
    sources = [
        {
            "title": p.get("title") or "Untitled",
            "doi": p.get("doi") or "",
            "year": p.get("year"),
            "authors": p.get("authors") or [],
        }
        for p in retrieved
    ]
    if not check_ollama_available():
        parts = [
            "Based on your saved papers (local model unavailable, so this "
            "is an extractive answer from the retrieved abstracts):"
        ]
        for paper in retrieved:
            abstract = (paper.get("abstract") or "")[:500]
            parts.append(f"- {paper.get('title')}: {abstract}")
            if paper.get("notes"):
                parts.append(f"  Your notes: {paper['notes'][:300]}")
        return {
            "status": "success",
            "answer": "\n".join(parts),
            "sources": sources,
            "retrieval": retrieval,
            "llm_used": False,
        }
    try:
        llm = get_chat_model(temperature=0.0)
        evidence = "\n\n".join(
            f"[{i + 1}] {p.get('title') or 'Untitled'} "
            f"({p.get('year') or 'n.d.'}). Abstract: {(p.get('abstract') or '')[:1500]}"
            + (f" Notes: {p.get('notes') or ''}" if p.get("notes") else "")
            for i, p in enumerate(retrieved)
        )
        prompt = (
            "Answer the question below using ONLY the saved papers "
            "listed. Cite each claim with the paper number in square "
            "brackets, like [1]. If the papers do not answer it, say "
            "so plainly.\n\n"
            f"Question: {question}\n\nPapers:\n{evidence}"
        )
        response = llm.invoke(prompt)
        answer = response.content if isinstance(response.content, str) else str(response.content)
        answer = (answer or "").strip()
        if len(answer) < 20:
            raise ValueError("empty LLM answer")
        return {
            "status": "success",
            "answer": answer,
            "sources": sources,
            "retrieval": retrieval,
            "llm_used": True,
        }
    except Exception as e:
        logger.warning("Library ask LLM failed, using extractive answer: %s", e)
        parts = ["Based on your saved papers:"]
        for paper in retrieved:
            parts.append(f"- {paper.get('title')}: {(paper.get('abstract') or '')[:500]}")
        return {
            "status": "success",
            "answer": "\n".join(parts),
            "sources": sources,
            "retrieval": retrieval,
            "llm_used": False,
        }


def _openalex_abstract(work: Dict[str, Any]) -> str:
    """Rebuild an abstract from an OpenAlex inverted index."""
    inverted = work.get("abstract_inverted_index") or {}
    if not inverted:
        return ""
    words: Dict[int, str] = {}
    for word, positions in inverted.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[i] for i in sorted(words))


def sync_saved_from_supabase(user_id: str) -> Dict[str, Any]:
    """Index the user's Supabase saved articles into the local library.

    The saved_articles table only stores paper_id + title + notes,
    so each paper is resolved through OpenAlex to get its abstract
    before indexing. Returns not_configured when Supabase is not
    set up in backend/.env.
    """
    from ..db.client_supabase import get_supabase
    from .citation_network_service import fetch_work_details

    client = get_supabase()
    if client is None:
        return {
            "status": "not_configured",
            "message": "Supabase is not configured on the backend, so saved articles cannot be read.",
            "indexed": 0,
        }
    try:
        rows = (
            client.table("saved_articles")
            .select("paper_id,title,notes")
            .eq("user_id", user_id)
            .execute()
            .data
            or []
        )
    except Exception as e:
        logger.warning("Supabase saved_articles read failed: %s", e)
        return {"status": "error", "message": f"Could not read saved articles: {e}", "indexed": 0}
    papers: List[Dict[str, Any]] = []
    for row in rows:
        paper_id = (row.get("paper_id") or "").strip()
        if not paper_id:
            continue
        work = fetch_work_details(paper_id)
        if work:
            papers.append(
                {
                    "title": work.get("display_name") or row.get("title") or "Untitled",
                    "abstract": _openalex_abstract(work),
                    "notes": row.get("notes") or "",
                    "authors": [
                        (a.get("author") or {}).get("display_name", "Unknown")
                        for a in (work.get("authorships") or [])[:5]
                    ],
                    "year": work.get("publication_year"),
                    "venue": ((work.get("primary_location") or {}).get("source") or {}).get(
                        "display_name", ""
                    ),
                    "doi": (work.get("doi") or "").replace("https://doi.org/", ""),
                    "url": work.get("doi") or "",
                    "source": "Saved articles",
                }
            )
        else:
            papers.append(
                {
                    "title": row.get("title") or "Untitled",
                    "abstract": "",
                    "notes": row.get("notes") or "",
                    "authors": [],
                    "year": None,
                    "venue": "",
                    "doi": "",
                    "url": "",
                    "source": "Saved articles",
                }
            )
    if not papers:
        return {"status": "empty", "message": "No saved articles found for this user.", "indexed": 0}
    result = index_papers(user_id, papers)
    return {
        "status": "success",
        "indexed": result["papers_indexed"],
        "added": result["added"],
        "updated": result["updated"],
        "saved_count": len(papers),
    }


# ── Zotero ─────────────────────────────────────────────────────────

def parse_zotero_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize one Zotero API item into a library paper, or None
    for item types with no title (notes, attachments)."""
    data = item.get("data") or {}
    if data.get("itemType") in ("note", "attachment", "annotation"):
        return None
    title = (data.get("title") or "").strip()
    if not title:
        return None
    creators = data.get("creators") or []
    authors = []
    for creator in creators:
        if not isinstance(creator, dict):
            continue
        name = creator.get("lastName") or ""
        if creator.get("firstName"):
            name = f"{creator['firstName']} {name}".strip()
        if name:
            authors.append(name)
    return {
        "title": title,
        "abstract": (data.get("abstractNote") or "").strip(),
        "notes": "",
        "authors": authors[:5],
        "year": None,
        "venue": (data.get("publicationTitle") or "").strip(),
        "doi": (data.get("DOI") or "").strip(),
        "url": (data.get("url") or "").strip(),
        "source": "Zotero",
    }


def import_zotero_library(
    user_id: str, limit: int = 50
) -> Dict[str, Any]:
    """Import a Zotero library (read-only) into the local library.

    Uses the free Zotero API with ZOTERO_API_KEY and ZOTERO_USER_ID
    from the environment. Nothing is written back to Zotero.
    """
    api_key = (settings.ZOTERO_API_KEY or "").strip()
    zotero_user = (settings.ZOTERO_USER_ID or "").strip()
    if not api_key or not zotero_user:
        return {
            "status": "not_configured",
            "message": (
                "Zotero import needs ZOTERO_API_KEY and ZOTERO_USER_ID "
                "in backend/.env (create a free key at zotero.org/settings/keys)."
            ),
            "imported": 0,
        }
    try:
        resp = requests.get(
            f"{ZOTERO_BASE_URL}/users/{zotero_user}/items",
            params={"format": "json", "limit": max(1, min(limit, 100)), "key": api_key},
            headers={"User-Agent": "ReSearch-Flow/1.0"},
            timeout=20,
        )
        resp.raise_for_status()
        items = resp.json() if isinstance(resp.json(), list) else []
    except Exception as e:
        logger.warning("Zotero import failed: %s", e)
        return {"status": "error", "message": f"Zotero request failed: {e}", "imported": 0}
    papers = []
    for item in items:
        parsed = parse_zotero_item(item)
        if parsed:
            papers.append(parsed)
    result = index_papers(user_id, papers)
    return {
        "status": "success",
        "imported": result["added"],
        "updated": result["updated"],
        "papers_indexed": result["papers_indexed"],
        "fetched": len(items),
    }


def _bibtex_key(paper: Dict[str, Any]) -> str:
    author = (paper.get("authors") or ["unknown"])[0].split()[-1].lower()
    author = re.sub(r"[^a-z0-9]", "", author) or "unknown"
    year = paper.get("year") or "nodate"
    title_word = re.sub(r"[^a-z0-9]", "", (paper.get("title") or "paper").split()[0].lower())
    return f"{author}{year}{title_word}"


def export_bibtex(papers: List[Dict[str, Any]]) -> str:
    """Export library papers to BibTeX (Zotero-compatible)."""
    entries = []
    for paper in papers:
        key = _bibtex_key(paper)
        fields = [
            f"  title = {{{paper.get('title') or 'Untitled'}}}",
        ]
        if paper.get("authors"):
            fields.append(f"  author = {{{' and '.join(paper['authors'])}}}")
        if paper.get("year"):
            fields.append(f"  year = {{{paper['year']}}}")
        if paper.get("venue"):
            fields.append(f"  journal = {{{paper['venue']}}}")
        if paper.get("doi"):
            fields.append(f"  doi = {{{paper['doi']}}}")
        if paper.get("url"):
            fields.append(f"  url = {{{paper['url']}}}")
        if paper.get("abstract"):
            fields.append(f"  abstract = {{{paper['abstract'][:2000]}}}")
        entries.append("@article{" + key + ",\n" + ",\n".join(fields) + "\n}")
    return "\n\n".join(entries) + ("\n" if entries else "")


def export_ris(papers: List[Dict[str, Any]]) -> str:
    """Export library papers to RIS (Zotero-compatible)."""
    records = []
    for paper in papers:
        lines = ["TY  - JOUR"]
        if paper.get("authors"):
            for author in paper["authors"]:
                lines.append(f"AU  - {author}")
        lines.append(f"TI  - {paper.get('title') or 'Untitled'}")
        if paper.get("year"):
            lines.append(f"Y1  - {paper['year']}")
        if paper.get("venue"):
            lines.append(f"JO  - {paper['venue']}")
        if paper.get("doi"):
            lines.append(f"DO  - {paper['doi']}")
        if paper.get("url"):
            lines.append(f"UR  - {paper['url']}")
        if paper.get("abstract"):
            lines.append(f"AB  - {paper['abstract'][:2000]}")
        lines.append("ER  - ")
        records.append("\n".join(lines))
    return "\n\n".join(records) + ("\n" if records else "")


# ── New-paper alerts ───────────────────────────────────────────────

def _fetch_openalex_since(topic: str, since: str, limit: int = 10) -> List[Dict[str, Any]]:
    """OpenAlex works on a topic published on or after ``since``."""
    try:
        headers = get_openalex_headers()
        params = {
            "search": topic,
            "filter": f"from_publication_date:{since}",
            "per-page": limit,
            # No sort=publication_date:desc here: with a date sort
            # OpenAlex returns the newest works in the date window
            # regardless of the search term. The default relevance
            # sort keeps the topic, and the caller sorts by date.
        }
        resp = requests.get(
            f"{OPENALEX_BASE_URL}/works", params=params, headers=headers, timeout=20
        )
        if headers and is_key_not_activated(resp):
            resp = requests.get(f"{OPENALEX_BASE_URL}/works", params=params, timeout=20)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        papers = []
        for work in results:
            doi = (work.get("doi") or "").replace("https://doi.org/", "")
            papers.append(
                {
                    "title": work.get("display_name") or "Untitled",
                    "doi": doi,
                    "year": work.get("publication_year"),
                    "publication_date": work.get("publication_date") or "",
                    "authors": [
                        (a.get("author") or {}).get("display_name", "Unknown")
                        for a in (work.get("authorships") or [])[:3]
                    ],
                    "url": work.get("doi") or "",
                    "citation_count": work.get("cited_by_count", 0),
                }
            )
        papers.sort(key=lambda p: p.get("publication_date") or "", reverse=True)
        return papers
    except Exception as e:
        logger.warning("OpenAlex alerts fetch failed for %r: %s", topic, e)
        return []


def check_alerts(user_id: str, topics: Optional[List[str]] = None) -> Dict[str, Any]:
    """Check the free sources for new papers on the user's topics.

    Compares against the last check time stored locally, so each
    run only reports papers published since then. No external alert
    service is involved.
    """
    library = load_library(user_id)
    if topics:
        library["topics"] = sorted({t.strip() for t in topics if t.strip()})
    saved_topics = library.get("topics") or []
    if not saved_topics:
        return {
            "status": "no_topics",
            "message": "Save some topics first (topics list is empty).",
            "new_papers": [],
            "checked_at": None,
        }
    last_check = library.get("last_alert_check")
    if last_check:
        since = last_check[:10]
    else:
        since = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
    now = datetime.now(timezone.utc)
    new_papers: List[Dict[str, Any]] = []
    seen: set = set()
    for topic in saved_topics:
        for paper in _fetch_openalex_since(topic, since, limit=10):
            key = (paper.get("doi") or paper.get("title") or "").lower()
            if key in seen:
                continue
            seen.add(key)
            new_papers.append({**paper, "topic": topic})
    new_papers.sort(key=lambda p: p.get("publication_date") or "", reverse=True)
    library["last_alert_check"] = now.isoformat()
    library["alerts"] = new_papers
    save_library(user_id, library)
    return {
        "status": "success",
        "topics": saved_topics,
        "since": since,
        "checked_at": now.isoformat(),
        "new_papers": new_papers,
        "new_count": len(new_papers),
    }
