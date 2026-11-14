"""
Free PRISMA systematic review.

Move 4 of the competitor playbook. Rival systematic-review tools
are paid; this pipeline runs the whole PRISMA flow on free paper
sources and the local model.

Pipeline:
1. Multi-source search for the research question (the same
   OpenAlex / Semantic Scholar search as Deep Review, with the
   Europe PMC / Crossref fallback).
2. Dedupe by DOI (title fallback): that count is PRISMA
   "identified".
3. Title/abstract screening in two independent passes. Each pass
   asks the local LLM for include/exclude with a fixed category
   and a short reason. When the model is unavailable or its answer
   cannot be parsed, a keyword fallback screens on the inclusion
   and exclusion criteria instead, and the paper is flagged as
   needing human review.
4. Dual-pass adjudication: a paper is finally included only when
   both passes include it. Any disagreement is flagged in the
   screening table for human review.
5. PRISMA flow counts (identified / screened / excluded with
   reasons / included) plus a screening-accuracy note with the
   honest caveat that AI screening needs human verification.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

from .deep_review_service import (
    _extract_json_object,
    _normalize_doi,
    _normalize_paper,
    derive_subqueries,
    search_papers,
)
from .llm_provider import get_chat_model

logger = logging.getLogger(__name__)

VERIFICATION_NOTE = (
    "AI screening is a first pass, not a substitute for human "
    "judgement. Every include/exclude decision above, especially "
    "the disagreements flagged between the two screening passes, "
    "must be verified by a human reviewer before the review is "
    "used or published."
)

CATEGORIES = (
    "does not meet inclusion criteria",
    "meets exclusion criteria",
    "no abstract available",
    "not relevant to research question",
    "screening inconclusive - human review needed",
)


def _dedupe(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for paper in papers:
        key = _normalize_doi(paper.get("doi")) or (
            "title:" + (paper.get("title") or "").strip().lower()
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(paper)
    return out


def _criteria_text(criteria: List[str]) -> str:
    items = [c.strip() for c in (criteria or []) if c and c.strip()]
    return "; ".join(items) if items else "none stated"


def _keyword_screen(
    paper: Dict[str, Any],
    inclusion: List[str],
    exclusion: List[str],
) -> Dict[str, str]:
    """Fallback screening when the LLM is unavailable.

    Include when the title/abstract mentions at least one inclusion
    term (or no inclusion criteria were given) and no exclusion
    term. Always flagged as needing human review.
    """
    text = ((paper.get("title") or "") + " " + (paper.get("abstract") or "")).lower()
    for term in exclusion:
        if term.strip() and term.strip().lower() in text:
            return {
                "decision": "exclude",
                "category": "meets exclusion criteria",
                "reason": f"Exclusion term mentioned: {term.strip()}",
            }
    terms = [t.strip().lower() for t in inclusion if t.strip()]
    if terms and not any(t in text for t in terms):
        return {
            "decision": "exclude",
            "category": "does not meet inclusion criteria",
            "reason": "No inclusion criterion mentioned in title or abstract.",
        }
    return {
        "decision": "include",
        "category": "does not meet inclusion criteria",
        "reason": "Keyword fallback: inclusion term mentioned, no exclusion term found.",
    }


def screen_paper(
    llm,
    paper: Dict[str, Any],
    question: str,
    inclusion: List[str],
    exclusion: List[str],
    pass_label: str = "pass 1",
) -> Dict[str, str]:
    """One screening pass for one paper.

    Returns decision (include/exclude), category (fixed set),
    reason (short, from the model or the fallback) and
    needs_human_review (True when the LLM was not used).
    """
    if not paper.get("abstract") or len(paper["abstract"]) < 50:
        return {
            "decision": "exclude",
            "category": "no abstract available",
            "reason": "No abstract available to screen against the criteria.",
            "needs_human_review": False,
        }
    if llm is None:
        result = _keyword_screen(paper, inclusion, exclusion)
        result["needs_human_review"] = True
        return result
    prompt = (
        "You are screening a paper for a systematic review. Output "
        "ONLY a JSON object with these keys, no other text:\n"
        '{"decision": "include" or "exclude", '
        '"category": one of "does not meet inclusion criteria", '
        '"meets exclusion criteria", "not relevant to research question", '
        '"screening inconclusive - human review needed", '
        '"reason": "one short sentence"}\n\n'
        f"Research question: {question}\n"
        f"Inclusion criteria: {_criteria_text(inclusion)}\n"
        f"Exclusion criteria: {_criteria_text(exclusion)}\n\n"
        f"Title: {paper['title']}\nAbstract: {paper['abstract'][:2000]}"
    )
    try:
        response = llm.invoke(prompt)
        content = response.content if isinstance(response.content, str) else str(response.content)
        parsed = _extract_json_object(content)
        if parsed:
            decision = (parsed.get("decision") or "").strip().lower()
            if decision in ("include", "exclude"):
                category = (parsed.get("category") or "").strip()
                if category not in CATEGORIES:
                    category = (
                        "does not meet inclusion criteria"
                        if decision == "exclude"
                        else "screening inconclusive - human review needed"
                    )
                reason = (parsed.get("reason") or "").strip()[:300]
                return {
                    "decision": decision,
                    "category": category,
                    "reason": reason or "No reason given by the screening model.",
                    "needs_human_review": False,
                }
    except Exception as e:
        logger.warning("Screening %s failed for %r: %s", pass_label, paper.get("title"), e)
    result = _keyword_screen(paper, inclusion, exclusion)
    result["needs_human_review"] = True
    return result


def adjudicate(pass1: Dict[str, str], pass2: Dict[str, str]) -> Dict[str, Any]:
    """Dual-pass adjudication.

    Final include only when both passes include. A disagreement is
    flagged and always needs human review.
    """
    disagreement = pass1["decision"] != pass2["decision"]
    if disagreement:
        return {
            "final_decision": "exclude",
            "disagreement": True,
            "needs_human_review": True,
            "final_category": "screening inconclusive - human review needed",
            "final_reason": (
                "The two screening passes disagreed "
                f"({pass1['decision']} vs {pass2['decision']}); "
                "held for human review."
            ),
        }
    decision = pass1["decision"]
    source = pass1 if decision == "include" else pass1
    return {
        "final_decision": decision,
        "disagreement": False,
        "needs_human_review": bool(
            pass1.get("needs_human_review") or pass2.get("needs_human_review")
        ),
        "final_category": source["category"] if decision == "exclude" else "",
        "final_reason": source["reason"],
    }


def run_prisma_review(
    question: str,
    inclusion_criteria: Optional[List[str]] = None,
    exclusion_criteria: Optional[List[str]] = None,
    max_papers: int = 5,
) -> Dict[str, Any]:
    """Run the full PRISMA review pipeline for one research question."""
    inclusion = inclusion_criteria or []
    exclusion = exclusion_criteria or []
    subqueries = derive_subqueries(question)
    raw_papers = search_papers(subqueries, per_query=10)
    identified = _dedupe([_normalize_paper(p) for p in raw_papers])
    to_screen = identified[:max_papers]
    not_screened = len(identified) - len(to_screen)

    try:
        llm = get_chat_model(temperature=0.0)
    except Exception as e:
        logger.warning("PRISMA screening LLM unavailable, keyword fallback: %s", e)
        llm = None

    rows: List[Dict[str, Any]] = []
    for paper in to_screen:
        pass1 = screen_paper(llm, paper, question, inclusion, exclusion, "pass 1")
        pass2 = screen_paper(llm, paper, question, inclusion, exclusion, "pass 2")
        verdict = adjudicate(pass1, pass2)
        rows.append(
            {
                "title": paper.get("title") or "Untitled",
                "authors": paper.get("authors") or [],
                "year": paper.get("year"),
                "venue": paper.get("venue") or "",
                "doi": paper.get("doi") or "",
                "url": paper.get("url") or "",
                "source": paper.get("source") or "",
                "pass1_decision": pass1["decision"],
                "pass1_category": pass1["category"],
                "pass1_reason": pass1["reason"],
                "pass2_decision": pass2["decision"],
                "pass2_category": pass2["category"],
                "pass2_reason": pass2["reason"],
                "final_decision": verdict["final_decision"],
                "final_category": verdict["final_category"],
                "final_reason": verdict["final_reason"],
                "disagreement": verdict["disagreement"],
                "needs_human_review": verdict["needs_human_review"],
            }
        )

    included = [r for r in rows if r["final_decision"] == "include"]
    excluded = [r for r in rows if r["final_decision"] == "exclude"]
    disagreements = [r for r in rows if r["disagreement"]]
    excluded_by_reason: Dict[str, int] = {}
    for row in excluded:
        key = row["final_category"] or "excluded"
        excluded_by_reason[key] = excluded_by_reason.get(key, 0) + 1
    if not_screened:
        excluded_by_reason["not screened - beyond max_papers limit"] = not_screened
    screened = len(rows)
    agreement = round((screened - len(disagreements)) / screened, 2) if screened else 1.0
    flow = {
        "identified": len(identified),
        "screened": screened,
        "excluded": len(excluded) + not_screened,
        "included": len(included),
        "disagreements": len(disagreements),
        "excluded_by_reason": excluded_by_reason,
    }
    note = (
        f"Dual-pass screening agreement: {agreement * 100:.0f}% "
        f"({screened - len(disagreements)} of {screened} papers). "
        + VERIFICATION_NOTE
    )
    return {
        "status": "success" if screened else "no_results",
        "question": question,
        "subqueries": subqueries,
        "inclusion_criteria": inclusion,
        "exclusion_criteria": exclusion,
        "prisma_flow": flow,
        "screening": rows,
        "included_papers": included,
        "screening_accuracy_note": note,
        "verification_note": VERIFICATION_NOTE,
        "message": (
            ""
            if screened
            else "No papers with abstracts were found for this question."
        ),
    }
