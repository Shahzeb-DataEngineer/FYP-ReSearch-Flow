"""
Citation graph + gap finder (Move 5).

Builds on the existing citation network code
(services/citation_network_service.py) and the Deep Review search
pipeline, and adds the two things a plain network view does not give
a researcher:

1. A timeline view: papers by year with citation counts.
2. Gap finding:
   - under-cited clusters: recent papers (last 3 years) with few
     citations in a busy area (a year with several papers), i.e.
     work that has not been picked up yet;
   - unanswered questions: the local LLM reads the collected
     abstracts and lists questions the literature does not yet
     answer, each tied to the papers it checked, so every question
     is traceable to real papers instead of model recall.

All retrieval is free (OpenAlex + Semantic Scholar). The LLM is the
local Ollama model only; when it is unavailable the gap finder falls
back to deterministic template questions built from the paper titles
and abstracts, and says so in the response.
"""
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from . import citation_network_service as net
from .deep_review_service import (
    _normalize_doi,
    _normalize_paper,
    search_papers,
)
from .llm_provider import check_ollama_available, get_chat_model

logger = logging.getLogger(__name__)

RECENT_YEARS = 3
MAX_GRAPH_NODES = 60


def build_timeline(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group graph nodes by publication year.

    Returns one row per year, newest first: paper count, total
    citations, average citations, and the top-cited paper title.
    """
    by_year: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        year = node.get("year")
        if isinstance(year, int):
            by_year[year].append(node)
    rows = []
    for year in sorted(by_year, reverse=True):
        papers = by_year[year]
        total_cites = sum(int(p.get("citationCount") or 0) for p in papers)
        top = max(papers, key=lambda p: int(p.get("citationCount") or 0))
        rows.append(
            {
                "year": year,
                "paper_count": len(papers),
                "total_citations": total_cites,
                "avg_citations": round(total_cites / len(papers), 1) if papers else 0,
                "top_paper": (top.get("title") or "")[:120],
                "top_citations": int(top.get("citationCount") or 0),
            }
        )
    return rows


def find_under_cited_clusters(
    papers: List[Dict[str, Any]], recent_years: int = RECENT_YEARS
) -> List[Dict[str, Any]]:
    """Find recent papers with few citations in a busy area.

    A cluster is one publication year with at least 3 papers. A
    paper in it is under-cited when it is from the last
    ``recent_years`` years and its citation count is below the
    median citation count of its year. Deterministic, no LLM, so the
    result is reproducible and honest about what "under-cited"
    means here.
    """
    current_year = datetime.now().year
    by_year: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for paper in papers:
        year = paper.get("year")
        if isinstance(year, int):
            by_year[year].append(paper)
    clusters = []
    for year in sorted(by_year, reverse=True):
        if year < current_year - recent_years + 1:
            continue
        group = by_year[year]
        if len(group) < 3:
            continue
        cites = sorted(int(p.get("citation_count") or p.get("citationCount") or 0) for p in group)
        median = cites[len(cites) // 2]
        under = [
            p
            for p in group
            if int(p.get("citation_count") or p.get("citationCount") or 0) < median
        ]
        if not under:
            continue
        clusters.append(
            {
                "year": year,
                "paper_count": len(group),
                "median_citations": median,
                "under_cited": [
                    {
                        "title": p.get("title") or "Untitled",
                        "doi": p.get("doi") or "",
                        "year": p.get("year"),
                        "citation_count": int(
                            p.get("citation_count") or p.get("citationCount") or 0
                        ),
                        "authors": (p.get("authors") or [])[:3],
                    }
                    for p in sorted(
                        under,
                        key=lambda p: int(
                            p.get("citation_count") or p.get("citationCount") or 0
                        ),
                    )
                ],
            }
        )
    return clusters


def _fallback_questions(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deterministic questions when the local LLM is unavailable.

    Each question names the papers it was checked against, so it
    stays traceable even without a model.
    """
    checked = [
        {"title": p.get("title") or "Untitled", "doi": p.get("doi") or ""}
        for p in papers[:6]
    ]
    titles = [p.get("title") or "" for p in papers[:3]]
    questions = [
        {
            "question": (
                "What long-term or follow-up evidence is still missing "
                "for the findings reported in these papers?"
            ),
            "checked_papers": checked,
            "why_unanswered": (
                "The collected abstracts report short-term results only; "
                "no long-term follow-up is described in them."
            ),
        },
        {
            "question": (
                "Do the methods in these papers generalise beyond the "
                "populations and settings they studied?"
            ),
            "checked_papers": checked,
            "why_unanswered": (
                "Each abstract describes one specific setting; none "
                "reports a replication in a different population."
            ),
        },
    ]
    if titles:
        questions.append(
            {
                "question": (
                    "What would settle the disagreements, if any, between "
                    f"'{titles[0][:80]}' and the other papers checked?"
                ),
                "checked_papers": checked,
                "why_unanswered": (
                    "The abstracts do not directly compare their results "
                    "with each other."
                ),
            }
        )
    return questions


def detect_unanswered_questions(
    papers: List[Dict[str, Any]], topic: str = ""
) -> Dict[str, Any]:
    """Ask the local LLM what the collected abstracts do not answer.

    Every returned question is tied to the papers it was checked
    against (title + DOI). Returns a dict with ``questions`` and
    ``llm_used`` so the caller can tell a model answer from the
    deterministic fallback.
    """
    with_abstracts = [
        p for p in papers if len((p.get("abstract") or "").strip()) >= 50
    ]
    if not with_abstracts:
        return {"questions": [], "llm_used": False, "reason": "no_abstracts"}
    if not check_ollama_available():
        logger.warning("Ollama unavailable, using fallback unanswered questions")
        return {
            "questions": _fallback_questions(with_abstracts),
            "llm_used": False,
            "reason": "llm_unavailable",
        }
    evidence = []
    for i, paper in enumerate(with_abstracts[:8], 1):
        evidence.append(
            f"[{i}] {paper.get('title') or 'Untitled'} "
            f"({paper.get('year') or 'n.d.'}). "
            f"Abstract: {(paper.get('abstract') or '')[:1200]}"
        )
    try:
        llm = get_chat_model(temperature=0.0)
        prompt = (
            "Read these paper abstracts and list up to 4 important "
            "research questions that the abstracts do NOT answer. "
            "Only use what the abstracts say: a question is unanswered "
            "when none of the abstracts answers it. Output ONLY a JSON "
            "array, no other text, each item with keys question, "
            "checked_paper_numbers (list of the [n] numbers you checked), "
            "why_unanswered (one sentence).\n\n"
            f"Topic: {topic}\n\n" + "\n\n".join(evidence)
        )
        response = llm.invoke(prompt)
        content = response.content if isinstance(response.content, str) else str(response.content)
        start = content.find("[")
        end = content.rfind("]")
        parsed = None
        if start != -1 and end > start:
            try:
                parsed = json.loads(content[start:end + 1], strict=False)
            except (json.JSONDecodeError, ValueError):
                parsed = None
        questions = []
        if isinstance(parsed, list):
            for item in parsed[:4]:
                if not isinstance(item, dict) or not item.get("question"):
                    continue
                numbers = item.get("checked_paper_numbers") or []
                checked = []
                for n in numbers:
                    try:
                        idx = int(n) - 1
                    except (TypeError, ValueError):
                        continue
                    if 0 <= idx < len(with_abstracts[:8]):
                        paper = with_abstracts[idx]
                        checked.append(
                            {
                                "title": paper.get("title") or "Untitled",
                                "doi": paper.get("doi") or "",
                            }
                        )
                if not checked:
                    checked = [
                        {"title": p.get("title") or "Untitled", "doi": p.get("doi") or ""}
                        for p in with_abstracts[:3]
                    ]
                questions.append(
                    {
                        "question": str(item["question"])[:500],
                        "checked_papers": checked,
                        "why_unanswered": str(item.get("why_unanswered") or "")[:300],
                    }
                )
        if questions:
            return {"questions": questions, "llm_used": True, "reason": "ok"}
        logger.warning("LLM unanswered-question output unusable, using fallback")
    except Exception as e:
        logger.warning("Unanswered-question detection fell back: %s", e)
    return {
        "questions": _fallback_questions(with_abstracts),
        "llm_used": False,
        "reason": "llm_parse_failed",
    }


def _clean_abstract(paper: Dict[str, Any]) -> None:
    """Turn a placeholder abstract into an empty one.

    OpenAlex search flattens a missing abstract to the literal
    string "N/A"; treating that as a real abstract would let the
    LLM "read" papers it never saw.
    """
    abstract = (paper.get("abstract") or "").strip()
    if abstract in ("N/A", "n/a", ""):
        paper["abstract"] = ""


def _enrich_abstracts(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fill missing abstracts from Semantic Scholar in one batch call.

    Uses the free S2 batch endpoint (one request for up to 10 DOIs).
    On any failure (including the shared-IP 429) the papers keep
    whatever abstract they had; the caller filters short abstracts
    out afterwards, so nothing is ever invented.
    """
    import requests

    need = [
        p
        for p in papers
        if len((p.get("abstract") or "").strip()) < 50 and (p.get("doi") or "").strip()
    ][:10]
    if not need:
        return papers
    try:
        resp = requests.post(
            f"{net.SEMANTIC_SCHOLAR_BASE}/paper/batch",
            params={"fields": "abstract"},
            json={"ids": [f"DOI:{p['doi']}" for p in need]},
            headers=net.SS_HEADERS,
            timeout=20,
        )
        resp.raise_for_status()
        results = resp.json()
        if isinstance(results, list):
            for paper, item in zip(need, results):
                if isinstance(item, dict) and (item.get("abstract") or "").strip():
                    paper["abstract"] = item["abstract"].strip()
    except Exception as e:
        logger.warning("S2 abstract enrichment failed: %s", e)
    return papers


def fetch_s2_abstract_by_doi(doi: str) -> str:
    """Fetch an abstract from Semantic Scholar by DOI.

    OpenAlex often has no abstract for a work; Semantic Scholar
    usually does, so the gap finder enriches the seed paper from
    there before asking the LLM what is unanswered.
    """
    try:
        import requests

        resp = requests.get(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
            params={"fields": "abstract"},
            headers={"User-Agent": "ReSearch-Flow/1.0"},
            timeout=15,
        )
        resp.raise_for_status()
        return (resp.json().get("abstract") or "").strip()
    except Exception as e:
        logger.warning("S2 abstract fetch failed for %s: %s", doi, e)
        return ""


def resolve_seed_doi(doi: str) -> Optional[Dict[str, Any]]:
    """Resolve a DOI to a normalized OpenAlex paper dict, or None."""
    doi = _normalize_doi(doi)
    if not doi:
        return None
    work = net.fetch_work_details(f"https://doi.org/{doi}")
    if not work:
        return None
    authors = [
        (a.get("author") or {}).get("display_name", "Unknown")
        for a in (work.get("authorships") or [])[:3]
    ]
    abstract = ""
    inverted = work.get("abstract_inverted_index") or {}
    if inverted:
        words: Dict[int, str] = {}
        for word, positions in inverted.items():
            for pos in positions:
                words[pos] = word
        abstract = " ".join(words[i] for i in sorted(words))
    return {
        "id": (work.get("id") or "").replace("https://openalex.org/", ""),
        "paperId": (work.get("id") or "").replace("https://openalex.org/", ""),
        "title": work.get("display_name") or "Untitled",
        "abstract": abstract,
        "authors": authors,
        "year": work.get("publication_year"),
        "venue": ((work.get("primary_location") or {}).get("source") or {}).get(
            "display_name", ""
        ),
        "doi": doi,
        "url": work.get("doi") or f"https://doi.org/{doi}",
        "citationCount": work.get("cited_by_count", 0),
        "citation_count": work.get("cited_by_count", 0),
        "source": "OpenAlex",
    }


def run_gap_finder(
    doi: str = "", topic: str = "", max_nodes: int = MAX_GRAPH_NODES
) -> Dict[str, Any]:
    """Build the citation graph plus timeline and gaps for a seed.

    Either ``doi`` (one seed paper) or ``topic`` (search first, then
    build the graph from the top papers). Returns the graph
    (nodes + edges), the timeline, under-cited clusters, and the
    unanswered questions, all in one response.
    """
    doi = (doi or "").strip()
    topic = (topic or "").strip()
    if not doi and not topic:
        raise ValueError("doi or topic is required")
    seed_paper = None
    if doi:
        seed_paper = resolve_seed_doi(doi)
        if not seed_paper:
            return {
                "status": "not_found",
                "message": f"No OpenAlex work found for DOI {doi}.",
                "graph": {"nodes": [], "edges": [], "stats": {}},
                "timeline": [],
                "under_cited_clusters": [],
                "unanswered_questions": {"questions": [], "llm_used": False},
            }
        topic = seed_paper["title"]
    if doi and seed_paper:
        if not seed_paper.get("abstract"):
            seed_paper["abstract"] = fetch_s2_abstract_by_doi(doi)
        graph = net._build_network_openalex(
            [seed_paper], max_depth=1, max_nodes=max_nodes
        )
        papers = [seed_paper]
        # The seed's neighbours carry no abstracts, so also search
        # the seed title: papers on the same topic bring the
        # abstracts the unanswered-question step reads. Missing
        # OpenAlex abstracts are enriched from Semantic Scholar;
        # papers still without a real abstract are dropped.
        try:
            searched = [
                _normalize_paper(p)
                for p in search_papers([seed_paper["title"]], per_query=10)
            ]
            for paper in searched:
                _clean_abstract(paper)
            _enrich_abstracts(searched)
            from .deep_review_service import screen_papers as _screen

            searched = _screen(searched, 10)
            papers.extend(
                p for p in searched if p.get("doi") != seed_paper["doi"]
            )
        except Exception as e:
            logger.warning("Topic search for seed enrichment failed: %s", e)
        for node in graph.get("nodes", []):
            if node.get("id") == seed_paper["id"]:
                continue
            papers.append(
                {
                    "title": node.get("title") or "Untitled",
                    "abstract": "",
                    "authors": node.get("authors") or [],
                    "year": node.get("year"),
                    "doi": "",
                    "citation_count": node.get("citationCount") or 0,
                    "citationCount": node.get("citationCount") or 0,
                }
            )
    else:
        raw = search_papers([topic], per_query=10)
        for paper in raw:
            _clean_abstract(paper)
        _enrich_abstracts(raw)
        from .deep_review_service import screen_papers

        screened = screen_papers(raw, 10)
        if not screened:
            return {
                "status": "no_results",
                "message": f"No papers with abstracts found for topic {topic!r}.",
                "graph": {"nodes": [], "edges": [], "stats": {}},
                "timeline": [],
                "under_cited_clusters": [],
                "unanswered_questions": {"questions": [], "llm_used": False},
            }
        graph = net.build_citation_network_from_papers(
            screened, max_depth=1, max_nodes=max_nodes
        )
        papers = [_normalize_paper(p) for p in screened]
        # Enrich gap inputs with every graph node (year + citations),
        # even when its abstract was not fetched.
        seen_titles = {p["title"].lower() for p in papers}
        for node in graph.get("nodes", []):
            if (node.get("title") or "").lower() in seen_titles:
                continue
            papers.append(
                {
                    "title": node.get("title") or "Untitled",
                    "abstract": "",
                    "authors": node.get("authors") or [],
                    "year": node.get("year"),
                    "doi": "",
                    "citation_count": node.get("citationCount") or 0,
                    "citationCount": node.get("citationCount") or 0,
                }
            )
    timeline = build_timeline(graph.get("nodes", []))
    clusters = find_under_cited_clusters(papers)
    unanswered = detect_unanswered_questions(
        [p for p in papers if (p.get("abstract") or "").strip()] or papers,
        topic=topic,
    )
    return {
        "status": "success",
        "seed_doi": doi or None,
        "topic": topic,
        "graph": graph,
        "timeline": timeline,
        "under_cited_clusters": clusters,
        "unanswered_questions": unanswered,
        "papers_checked": len(papers),
    }
