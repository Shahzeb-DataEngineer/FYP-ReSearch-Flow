"""
Draft Service
Generates structured research drafts from papers using the local
Ollama model (zero cost, no API key).

Replaces the old OpenAI GPT-4o / OpenRouter implementation. The
public functions keep their old shape so routes/draft.py does not
change: generate_draft(...) -> dict with the six draft sections (or
None on error), analyze_figure(...) -> dict or None.

Figure / vision analysis is OPTIONAL and OFF by default: it only
runs when OLLAMA_VISION_MODEL is set in the environment (e.g.
"llava:7b"). A vision model needs far more RAM than the 3B chat
model, so with no vision model configured analyze_figure() returns
None and generate_draft() notes in the draft that figures were
extracted but not analyzed, instead of failing.

Chunking: Ollama runs with num_ctx=8192, so the paper text sent to
the model is capped at ~24000 characters (about 6000 tokens) after
stripping the references section, instead of the old 90000-char
single call that assumed a 128K-context OpenAI model.
"""
import json
import logging
import re
from typing import Dict, List, Optional

from ..core.config import settings
from .llm_provider import check_ollama_available, get_chat_model
from .model_registry import get_active_chat_model
from .usage_meter import record_llm_call
from .citation_verification_service import (
    get_paper_badges,
    split_sentences,
    token_overlap_score,
    verify_claim,
)
import time

logger = logging.getLogger(__name__)

# About 6000 tokens at num_ctx=8192, leaving room for the prompt
# and the JSON draft the model has to produce.
MAX_DRAFT_CHARS = 24000

DRAFT_FIELDS = (
    "introduction",
    "literature_context",
    "methodology_overview",
    "key_analysis",
    "figure_discussions",
    "conclusion",
)
REQUIRED_FIELDS = ("introduction", "methodology_overview", "key_analysis", "conclusion")

VISION_DISABLED_NOTE = (
    "Figure analysis is disabled: no local vision model is configured "
    "(set OLLAMA_VISION_MODEL, e.g. 'llava:7b'). Figures were extracted "
    "from the PDF but not analyzed."
)


def _resolve_chat_model(model: Optional[str]) -> Optional[str]:
    """Map a legacy model name to a local Ollama model.

    Old callers pass "gpt-4o" (the previous default). That is not an
    Ollama model, so it means "use the configured local chat model".
    Any other non-empty name is treated as an Ollama model name.
    """
    if not model or model.startswith(("gpt-", "openai")):
        return None  # get_chat_model falls back to settings.OLLAMA_CHAT_MODEL
    return model


def _extract_json(content: str) -> Optional[Dict]:
    """Pull a JSON object out of model output.

    qwen2.5:3b does not have OpenAI-style response_format JSON mode,
    so it may wrap the object in a ```json fence or add a short
    preamble. Try plain parse, then a fenced block, then the first
    {...} span.
    """
    if not content:
        return None
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if fence:
        try:
            parsed = json.loads(fence.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    brace = re.search(r"\{.*\}", content, re.DOTALL)
    if brace:
        try:
            parsed = json.loads(brace.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return None



# --- Move 8: honest drafting -------------------------------------------
# Drafts are built from an extraction table (one row per source paper:
# problem / method / key result, each traceable to the paper it came
# from) instead of from free-form model recall. Every draft sentence
# is then checked against the source texts, and every cited paper is
# checked for retraction / contradiction before export.

_NEGATION_PHRASES = (
    "no effect", "does not", "did not", "not significant",
    "no significant", "fails to", "failed to", "no benefit",
    "does not improve", "no improvement", "ineffective",
)
_POSITIVE_PHRASES = (
    "improves", "improved", "effective", "significantly",
    "benefit", "benefits", "reduces", "reduced", "increases",
    "increased", "enhances", "enhanced",
)
_STOP = {
    "the", "a", "an", "and", "or", "in", "on", "of", "to", "for",
    "with", "by", "from", "as", "is", "was", "are", "were", "we",
    "this", "that", "these", "those", "it", "its", "they", "our",
}


def _first_sentence(text: str) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if s.strip()]
    return sentences[0] if sentences else (text or "").strip()[:300]


def _content_tokens(text: str) -> set:
    return {w for w in re.findall(r"\b[a-z0-9]+\b", (text or "").lower())
            if w not in _STOP and len(w) > 2}


def build_extraction_table(papers: Optional[List[Dict]]) -> List[Dict]:
    """One extraction row per source paper, traceable to its abstract.

    Each row carries problem / method / key_result plus a verbatim
    quote (first abstract sentence when the paper supplies none) and
    a source_text used for sentence-support checking. Fields the
    paper does not supply are filled from its abstract, never from
    model memory.
    """
    table: List[Dict] = []
    for i, paper in enumerate(papers or [], 1):
        paper = paper or {}
        abstract = (paper.get("abstract") or "").strip()
        title = (paper.get("title") or "Untitled").strip()
        problem = (paper.get("problem") or "").strip() or _first_sentence(abstract)
        method = (paper.get("method") or "").strip()
        if not method:
            method = "Method not stated in the abstract."
        key_result = (paper.get("key_result") or paper.get("result") or "").strip() or _first_sentence(abstract)
        quote = (paper.get("quote") or "").strip()
        if not quote or quote not in abstract:
            quote = _first_sentence(abstract)
        source_text = " ".join(
            part for part in (title, abstract, problem, method, key_result, quote) if part
        )
        table.append({
            "index": i,
            "title": title,
            "authors": paper.get("authors") or [],
            "year": paper.get("year"),
            "doi": (paper.get("doi") or "").strip(),
            "url": paper.get("url") or "",
            "problem": problem,
            "method": method,
            "key_result": key_result,
            "quote": quote,
            "source_text": source_text,
        })
    return table


def _sentence_support(sentence: str, table: List[Dict]) -> Dict:
    """Check one draft sentence against the extraction table.

    Fast path: token overlap against the source sentences (threshold
    0.30, the same as citation verification). Only when no source
    sentence passes on overlap does it fall back to the embedding
    check in verify_claim, so a draft with dozens of sentences does
    not pay one embedding call per sentence per paper.
    """
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", sentence or "")})
    result: Dict = {
        "sentence": sentence,
        "supported": False,
        "citations": cited,
        "score": 0.0,
        "supporting_sentence": None,
        "source_title": None,
        "source_doi": None,
        "source_index": None,
        "method": "token_overlap",
    }
    if not table or not (sentence or "").strip():
        return result
    best: Optional[Dict] = None
    for row in table:
        for source_sentence in split_sentences(row["source_text"]):
            score = token_overlap_score(sentence, source_sentence)
            if best is None or score > best["score"]:
                best = {"score": score, "row": row, "sentence": source_sentence}
    if best is not None and best["score"] >= 0.30:
        result.update({
            "supported": True, "score": round(float(best["score"]), 4),
            "supporting_sentence": best["sentence"][:300],
            "source_title": best["row"]["title"],
            "source_doi": best["row"]["doi"],
            "source_index": best["row"]["index"],
            "method": "token_overlap",
        })
        if best["row"]["index"] not in result["citations"]:
            result["citations"] = sorted(result["citations"] + [best["row"]["index"]])
        return result
    # Embedding fallback: one verify_claim against the combined sources.
    combined = "\n".join(row["source_text"] for row in table)
    checked = verify_claim(sentence, combined)
    if checked.get("verified"):
        idx = checked.get("sentence_index")
        # Attribute to the paper whose source text holds that sentence.
        owner = table[0]
        seen = 0
        for row in table:
            count = len(split_sentences(row["source_text"]))
            if idx is not None and seen <= idx < seen + count:
                owner = row
                break
            seen += count
        result.update({
            "supported": True, "score": round(float(checked.get("score") or 0.0), 4),
            "supporting_sentence": (checked.get("supporting_sentence") or "")[:300],
            "source_title": owner["title"], "source_doi": owner["doi"],
            "source_index": owner["index"], "method": "embedding",
        })
        if owner["index"] not in result["citations"]:
            result["citations"] = sorted(result["citations"] + [owner["index"]])
    else:
        result["score"] = round(float(checked.get("score") or 0.0), 4)
        result["method"] = str(checked.get("method") or "token_overlap")
    return result


def check_sentence_support(draft: Dict, table: List[Dict]) -> List[Dict]:
    """Per-sentence support flags for every draft section."""
    flags: List[Dict] = []
    for section in DRAFT_FIELDS:
        text = (draft or {}).get(section) or ""
        for sentence in split_sentences(text):
            entry = _sentence_support(sentence, table)
            entry["section"] = section
            flags.append(entry)
    return flags


def _possible_contradiction(a: Dict, b: Dict) -> Optional[str]:
    """Honest contradiction heuristic between two extracted results.

    Flags only when the two results share real topic words AND one
    states a negation / no-effect finding while the other states a
    positive effect. It is labelled a *possible* contradiction that
    needs a human check, never a proven one.
    """
    text_a = (a.get("key_result") or "") + " " + (a.get("problem") or "")
    text_b = (b.get("key_result") or "") + " " + (b.get("problem") or "")
    shared = _content_tokens(text_a) & _content_tokens(text_b)
    if len(shared) < 3:
        return None
    low_a, low_b = text_a.lower(), text_b.lower()
    a_neg = any(p in low_a for p in _NEGATION_PHRASES)
    b_neg = any(p in low_b for p in _NEGATION_PHRASES)
    a_pos = any(p in low_a for p in _POSITIVE_PHRASES)
    b_pos = any(p in low_b for p in _POSITIVE_PHRASES)
    if (a_neg and b_pos) or (b_neg and a_pos):
        return (
            f"Possible contradiction on shared topic words "
            f"({', '.join(sorted(shared)[:5])}): "
            f"'{a.get('title', '')[:60]}' reports '{(a.get('key_result') or '')[:120]}' "
            f"while '{b.get('title', '')[:60]}' reports '{(b.get('key_result') or '')[:120]}'. "
            f"Check both papers yourself before relying on either claim."
        )
    return None


def check_draft_references(citations: List[Dict]) -> Dict:
    """Pre-export check: retraction + contradiction check for cited papers.

    Every cited paper with a DOI is checked against the badges
    service (OpenAlex is_retracted). Export is blocked when any
    cited paper is retracted. Contradictions are warnings only:
    they never block, because the heuristic can be wrong.
    """
    items = [c or {} for c in (citations or [])]
    table = build_extraction_table(items)
    checked: List[Dict] = []
    retracted: List[Dict] = []
    warnings: List[str] = []
    for row in table:
        entry = {
            "index": row["index"], "title": row["title"], "doi": row["doi"],
            "retracted": False, "badges_checked": False, "status": "no_doi",
        }
        if row["doi"]:
            badges = get_paper_badges(row["doi"])
            if badges is None:
                entry["status"] = "not_found"
                warnings.append(
                    f"No OpenAlex record found for DOI {row['doi']} "
                    f"('{row['title'][:60]}'): retraction status unknown, "
                    f"verify it yourself before citing."
                )
            else:
                entry["badges_checked"] = True
                entry["retracted"] = bool(badges.get("retracted"))
                entry["status"] = "retracted" if entry["retracted"] else "ok"
                if entry["retracted"]:
                    retracted.append(entry)
                    warnings.append(
                        f"RETRACTED: '{row['title'][:80]}' (DOI {row['doi']}) "
                        f"is marked retracted in OpenAlex. Remove it before export."
                    )
        checked.append(entry)
    contradictions: List[str] = []
    for i in range(len(table)):
        for j in range(i + 1, len(table)):
            note = _possible_contradiction(table[i], table[j])
            if note:
                contradictions.append(note)
    warnings.extend(contradictions)
    blocked = bool(retracted)
    return {
        "export_allowed": not blocked,
        "blocked": blocked,
        "block_reason": (
            f"{len(retracted)} cited paper(s) retracted. Remove them before export."
            if blocked else None
        ),
        "checked": checked,
        "retracted": retracted,
        "contradictions": contradictions,
        "warnings": warnings,
        "papers_checked": len(checked),
    }


def analyze_figure(image_base64: str, mime_type: str, caption_hint: str = "", model: str = "gpt-4o") -> Optional[Dict]:
    """
    Analyze a single figure/chart using a local Ollama vision model.

    Off by default: returns None immediately when OLLAMA_VISION_MODEL
    is not set, so the caller can record "extracted but not analyzed"
    instead of failing the whole draft.

    Args:
        image_base64: Base64-encoded image
        mime_type: MIME type (e.g. "image/png")
        caption_hint: Optional caption text found near the figure
        model: Ignored unless it names an Ollama vision model; the
            configured OLLAMA_VISION_MODEL takes precedence.

    Returns:
        Dict with keys: description, data_insights, chart_type, or None
    """
    vision_model = settings.OLLAMA_VISION_MODEL
    if model and not model.startswith(("gpt-", "openai")):
        vision_model = model
    if not vision_model:
        logger.info("Figure analysis skipped: no OLLAMA_VISION_MODEL configured")
        return None

    if not check_ollama_available():
        logger.warning("Figure analysis skipped: Ollama unreachable")
        return None

    caption_context = f'\nCaption found near this figure: "{caption_hint}"' if caption_hint else ""
    try:
        from langchain_core.messages import HumanMessage

        llm = get_chat_model(model=vision_model, temperature=0.2)
        message = HumanMessage(content=[
            {
                "type": "text",
                "text": (
                    "Analyze this figure from a research paper. Respond with ONLY "
                    "a JSON object, no other text:\n"
                    "{\n"
                    '  "chart_type": "type of visualization (e.g., bar chart, line graph, scatter plot, diagram, table, photograph)",\n'
                    '  "description": "Clear description of what the figure shows (2-3 sentences)",\n'
                    '  "data_insights": "Key data points, trends, or takeaways from this figure (2-3 sentences)"\n'
                    "}" + caption_context
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
            },
        ])
        response = llm.invoke([message])
        content = response.content if isinstance(response.content, str) else str(response.content)
        analysis = _extract_json(content)
        if not analysis:
            logger.warning("Vision model did not return JSON for a figure")
            return None
        return {
            "chart_type": analysis.get("chart_type", "Unknown"),
            "description": analysis.get("description", ""),
            "data_insights": analysis.get("data_insights", ""),
        }
    except Exception as e:
        logger.error(f"Figure analysis failed: {e}")
        return None


def generate_draft(
    paper_text: str,
    figure_analyses: List[Dict],
    title: str = "",
    authors: str = "",
    abstract: str = "",
    model: str = "gpt-4o",
    figures_found: int = 0,
    papers: Optional[List[Dict]] = None,
) -> Optional[Dict]:
    """
    Generate a structured research draft from paper text and figure analyses.

    Args:
        paper_text: Full extracted text of the paper
        figure_analyses: List of figure analysis dicts from analyze_figure()
        title: Paper title
        authors: Paper authors
        abstract: Paper abstract
        model: Legacy OpenAI model name (ignored) or an Ollama model name
        figures_found: How many figures were extracted from the PDF
            (used for the vision-disabled note when none were analyzed)

    Returns:
        Dict with draft sections plus, when source papers are known,
        extraction_table and sentence_support (one support flag per
        draft sentence, with citations). Returns None on error.
        Raises ValueError when the local Ollama server is not
        reachable.
    """
    if not paper_text or len(paper_text.strip()) < 100:
        logger.warning("Paper text too short for draft generation")
        return None

    # Strip references section to save context
    ref_match = re.search(
        r'\n\s*(?:References|REFERENCES|Bibliography|BIBLIOGRAPHY)\s*\n', paper_text
    )
    if ref_match:
        paper_text = paper_text[:ref_match.start()]

    # Truncate to what fits in the local model's context window
    if len(paper_text) > MAX_DRAFT_CHARS:
        paper_text = paper_text[:MAX_DRAFT_CHARS] + "\n\n[Content truncated to fit the local model's context window...]"

    # Move 8: build the extraction table the draft must be built from.
    # With explicit papers, one row per paper. Otherwise the single
    # paper being drafted from is the one-row table, so every claim
    # still traces to a real source.
    if papers:
        extraction_table = build_extraction_table(papers)
    else:
        extraction_table = build_extraction_table([{
            "title": title or "Untitled",
            "authors": authors,
            "abstract": abstract or _first_sentence(paper_text),
            "doi": "",
        }])
    extraction_context = "\n\n--- EXTRACTION TABLE (the only sources for factual claims) ---\n"
    for row in extraction_table:
        extraction_context += (
            f"\n[{row['index']}] {row['title']} ({row.get('year') or 'n.d.'})\n"
            f"  Problem: {row['problem']}\n"
            f"  Method: {row['method']}\n"
            f"  Key result: {row['key_result']}\n"
            f"  Quote: {row['quote']}\n"
        )

    # Build figure context for the prompt
    figure_context = ""
    vision_note = ""
    if figure_analyses:
        figure_context = "\n\n--- FIGURE ANALYSES ---\n"
        for i, fig in enumerate(figure_analyses, 1):
            figure_context += f"\nFigure {i} (Page {fig.get('page_number', '?')}, {fig.get('chart_type', 'Unknown')}):\n"
            figure_context += f"  Description: {fig.get('description', 'N/A')}\n"
            figure_context += f"  Key Insights: {fig.get('data_insights', 'N/A')}\n"
    elif figures_found > 0:
        vision_note = f"{VISION_DISABLED_NOTE} {figures_found} figure(s) were extracted."

    # Build metadata context
    meta_context = ""
    if title:
        meta_context += f"Title: {title}\n"
    if authors:
        meta_context += f"Authors: {authors}\n"
    if abstract:
        meta_context += f"Abstract: {abstract}\n"

    prompt = f"""You are an expert academic writer. Based on the following research paper content and figure analyses, generate a structured research draft.

{meta_context}
{extraction_context}

--- PAPER CONTENT ---
{paper_text}
{figure_context}

Respond with ONLY a JSON object, no other text, in this format:
{{
  "introduction": "A well-written introduction covering the background, significance, and objectives of this research (3-5 paragraphs)",
  "literature_context": "How this paper fits within the broader research landscape, key related work referenced, and gaps addressed (2-4 paragraphs)",
  "methodology_overview": "Detailed analysis of the methods, experimental design, datasets, and tools used in this research (2-4 paragraphs)",
  "key_analysis": "Critical analysis and discussion of the main findings, results, and their significance. Reference relevant figures where applicable (3-5 paragraphs)",
  "figure_discussions": "Detailed discussion of the visual data presented in the paper's figures, what they reveal, and their implications (1-3 paragraphs, or 'No figures available' if none)",
  "conclusion": "Synthesis of the paper's contributions, limitations, and potential future research directions (2-3 paragraphs)"
}}

IMPORTANT GUIDELINES:
- Write in formal academic English
- Build every factual claim ONLY from the extraction table above, and end each factual sentence with the citation number of the paper it came from, like [1] or [2]. Do not state facts that are not in the extraction table; if a claim has no source, leave it out
- Reference specific data, metrics, and results from the paper
- When discussing figures, reference the figure analyses provided
- Be thorough but concise — each section should be substantive
- The draft should read as a cohesive academic document"""

    if not check_ollama_available():
        raise ValueError(
            "Local Ollama server is not reachable at "
            f"{settings.OLLAMA_BASE_URL}. Start Ollama and pull the chat "
            f"model ({settings.OLLAMA_CHAT_MODEL}) before generating drafts."
        )

    _started = time.time()
    try:
        llm = get_chat_model(model=_resolve_chat_model(model), temperature=0.3)
        logger.info(f"Generating draft with local Ollama model {get_active_chat_model()}")
        response = llm.invoke(prompt)
        content = response.content if isinstance(response.content, str) else str(response.content)
        draft = _extract_json(content)
        if draft is None:
            logger.error("Draft model did not return parseable JSON")
            return None

        # Validate required sections
        for section in REQUIRED_FIELDS:
            if section not in draft or not draft[section]:
                draft[section] = f"Unable to generate {section.replace('_', ' ')}. Please try again."

        # Optional sections fallback
        draft.setdefault("literature_context", "")
        if not draft.get("figure_discussions"):
            if figure_analyses:
                draft["figure_discussions"] = ""
            elif vision_note:
                draft["figure_discussions"] = vision_note
            else:
                draft["figure_discussions"] = "No figures available"
        elif vision_note and not figure_analyses:
            draft["figure_discussions"] = f"{vision_note}\n\n{draft['figure_discussions']}"

        # Move 8: check every draft sentence against the extraction
        # table and attach the flags (and a copy of the table, minus
        # the internal source_text) to the result.
        sentence_support = check_sentence_support(draft, extraction_table)
        supported = sum(1 for f in sentence_support if f["supported"])
        draft["extraction_table"] = [
            {k: v for k, v in row.items() if k != "source_text"}
            for row in extraction_table
        ]
        draft["sentence_support"] = sentence_support
        draft["support_summary"] = {
            "total_sentences": len(sentence_support),
            "supported_sentences": supported,
            "unsupported_sentences": len(sentence_support) - supported,
            "unsupported": [f["sentence"] for f in sentence_support if not f["supported"]],
        }
        record_llm_call("draft", get_active_chat_model(), paper_text,
                        " ".join(str(v) for v in draft.values() if isinstance(v, str)),
                        time.time() - _started)
        logger.info("Successfully generated research draft with local Ollama model")
        return draft

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Draft generation error: {e}", exc_info=True)
        return None
