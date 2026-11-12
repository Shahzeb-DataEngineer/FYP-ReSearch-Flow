"""
LLM Service
Summarization using a local Ollama model (zero cost, no API key).

Replaces the old OpenAI / OpenRouter implementation. The public
function keeps its old shape so existing routes do not change:
summarize_with_llm(text) -> dict with problem_statement, methodology,
key_findings, conclusion, or an extractive fallback dict if Ollama
is unreachable (never None on a long-enough text, unless the text
itself is too short).

Chunking: Ollama runs with num_ctx=8192, so long papers are split
into ~12000-character chunks (about 3000 tokens) instead of the old
100000-character single call. Each chunk is summarized, then the
chunk summaries are merged.

JSON robustness: the 3B model often returns malformed JSON or drops a
field, so each chunk is parsed with a tolerant extractor, retried once
with a repair prompt on failure, and any still-missing field is filled
from the extractive fallback of the same text instead of an
"Unable to extract..." placeholder.
"""
import logging
import json
import re
from typing import Dict, List, Optional

from .llm_provider import get_chat_model, check_ollama_available

MAX_CHUNK_CHARS = 12000

SUMMARY_FIELDS = ("problem_statement", "methodology", "key_findings", "conclusion")


def summarize_with_llm(text: str, model: Optional[str] = None) -> Optional[Dict[str, str]]:
    """
    Summarize a research paper using the local Ollama model.

    Args:
        text: Full text of the paper to summarize
        model: Ollama model name (default: settings.OLLAMA_CHAT_MODEL)

    Returns:
        Dictionary with structured summary sections, or None if the
        text is too short. If Ollama is unreachable, returns a pure
        extractive summary instead of failing.
    """
    if not text or len(text.strip()) < 100:
        logging.warning("Text too short for summarization")
        return None

    text = _strip_references(text)

    if not check_ollama_available():
        logging.warning("Ollama unreachable, using extractive fallback summary")
        return _extractive_fallback(text)

    try:
        chunks = _chunk_text(text, MAX_CHUNK_CHARS)
        logging.info("Summarizing %d chunk(s) with local Ollama model", len(chunks))
        llm = get_chat_model(model=model, temperature=0.2)
        chunk_summaries = []
        for chunk in chunks[:3]:
            summary = _summarize_chunk(llm, chunk)
            if summary:
                chunk_summaries.append(summary)
        if not chunk_summaries:
            return _extractive_fallback(text)
        if len(chunk_summaries) == 1:
            return chunk_summaries[0]
        merged = {field: " ".join(s.get(field, "") for s in chunk_summaries) for field in SUMMARY_FIELDS}
        for field in SUMMARY_FIELDS:
            merged[field] = merged[field].strip()[:2000]
        # Keep the good LLM fields and fill only the missing ones from the
        # extractive fallback, instead of discarding the whole merge.
        return _fill_missing_fields(merged, text)
    except Exception as e:
        logging.error("Ollama summarization failed, using extractive fallback: %s", e, exc_info=True)
        return _extractive_fallback(text)


def _strip_references(text: str) -> str:
    ref_pattern = r'\n\s*(?:References|REFERENCES|Bibliography|BIBLIOGRAPHY|Works Cited|WORKS CITED)\s*\n'
    ref_match = re.search(ref_pattern, text)
    if ref_match:
        original_len = len(text)
        text = text[:ref_match.start()]
        logging.info("Stripped references section: %d -> %d chars", original_len, len(text))
    return text


def _chunk_text(text: str, max_chars: int) -> List[str]:
    """Split text into chunks of at most max_chars.

    Splits on paragraph breaks first, then single newlines, then
    sentences, then hard character splits, so a chunk can never exceed
    max_chars. This matters because some extracted full text (e.g. the
    Europe PMC JATS body) arrives as one long run with no blank lines:
    without the hard split the whole 54k-char paper became a single
    chunk, far past the model's 8192-token context window.
    """
    if len(text) <= max_chars:
        return [text]

    def _split_unit(unit: str) -> List[str]:
        if len(unit) <= max_chars:
            return [unit]
        # Split on sentence boundaries, keeping every fragment (unlike
        # _split_sentences, which drops fragments under 10 chars).
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", unit) if s.strip()]
        if not sentences:
            return [unit[i:i + max_chars] for i in range(0, len(unit), max_chars)]
        pieces = []
        for sentence in sentences:
            if len(sentence) <= max_chars:
                pieces.append(sentence)
            else:
                for start in range(0, len(sentence), max_chars):
                    pieces.append(sentence[start:start + max_chars])
        return pieces

    chunks: List[str] = []
    current = ""

    def _flush():
        nonlocal current
        if current:
            chunks.append(current)
            current = ""

    for para in text.split("\n\n"):
        for line in para.split("\n"):
            for unit in _split_unit(line):
                if len(current) + len(unit) + 2 > max_chars and current:
                    _flush()
                current = (current + "\n\n" + unit) if current else unit
    _flush()
    return chunks


def _summarize_chunk(llm, chunk: str) -> Optional[Dict[str, str]]:
    prompt = (
        "You are an expert academic researcher. Analyze the following research paper "
        "text and provide a detailed, structured summary.\n\n"
        "Output ONLY a valid JSON object, exactly in this format. Do not write any "
        "explanation, preamble, or commentary before or after the JSON. Do not wrap "
        "the JSON in markdown code fences. All four fields must be present and "
        "non-empty, with plain double-quoted strings (no trailing commas):\n"
        "{\n"
        '  "problem_statement": "A clear description of the research problem or question addressed (2-4 sentences)",\n'
        '  "methodology": "Detailed description of the methods, approaches, techniques, or frameworks used (3-5 sentences)",\n'
        '  "key_findings": "The main results, discoveries, or findings from the research (3-6 sentences)",\n'
        '  "conclusion": "The key conclusions, implications, or contributions of the research (2-4 sentences)"\n'
        "}\n\n"
        f"Research Paper Content:\n{chunk}\n\n"
        "Now provide ONLY the JSON object:"
    )
    response = llm.invoke(prompt)
    content = response.content if isinstance(response.content, str) else str(response.content)
    summary = _extract_json_object(content)
    if summary is not None and all(summary.get(field) for field in SUMMARY_FIELDS):
        return summary
    # The 3B model often returns malformed JSON or drops a field: retry
    # once with a repair prompt. The prompt shows the paper text (not a
    # template with "..." values, which the model copies literally) and
    # demands real sentences from it.
    logging.warning("First summary attempt was not usable JSON, retrying once with a repair prompt")
    repair_prompt = (
        "Your previous response was not valid JSON. Write a new summary of "
        "the paper text below as a JSON object with exactly these four keys: "
        "problem_statement, methodology, key_findings, conclusion. Each value "
        "must be 2-6 real sentences taken from the paper text. Do not write "
        "any explanation, preamble, or commentary. Do not wrap the JSON in "
        "markdown code fences. Do not use placeholder values such as ... or "
        "N/A. Do not copy example text.\n\n"
        f"Paper text:\n{chunk[:6000]}\n\n"
        "Now provide ONLY the JSON object:"
    )
    try:
        repair_response = llm.invoke(repair_prompt)
        repair_content = (
            repair_response.content
            if isinstance(repair_response.content, str)
            else str(repair_response.content)
        )
        retry_summary = _extract_json_object(repair_content)
        if retry_summary is not None:
            summary = retry_summary
            content = repair_content
    except Exception as e:
        logging.warning("Summary repair retry failed: %s", e)
    if summary is not None and all(summary.get(field) for field in SUMMARY_FIELDS):
        return summary
    # Last resort: regex/text parsing of whatever the model returned,
    # then fill any still-missing fields from the extractive fallback
    # of this chunk instead of "Unable to extract..." placeholders.
    parsed = _parse_llm_summary(content)
    if summary is not None:
        for field in SUMMARY_FIELDS:
            if not parsed.get(field) and summary.get(field):
                parsed[field] = summary[field]
    return _fill_missing_fields(parsed, chunk)


def _extract_json_object(content: str) -> Optional[Dict[str, str]]:
    """Extract a JSON object with the four summary fields from raw model output.

    The 3B model often adds prose around the JSON, wraps it in fences, or
    leaves a trailing comma, so plain ``json.loads`` on the raw output
    fails. Tries, in order: the raw string, a fenced block (greedy, so
    braces inside string values do not cut it short), the span from the
    first ``{`` to the last ``}``, and the same candidates with trailing
    commas removed. Returns a dict with the four summary fields (values
    coerced to stripped strings) or None if nothing parses.
    """
    if not content:
        return None
    candidates = [content]
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
    if fence:
        candidates.append(fence.group(1))
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end > start:
        candidates.append(content[start:end + 1])
    for candidate in candidates:
        for text in (candidate, re.sub(r",\s*([}\]])", r"\1", candidate)):
            try:
                parsed = json.loads(text, strict=False)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(parsed, dict):
                summary = {}
                for field in SUMMARY_FIELDS:
                    value = str(parsed.get(field, "") or "").strip()
                    # Placeholder-only values ("...", "N/A") are not real
                    # content: treat them as missing so the caller retries
                    # or fills from the extractive fallback instead.
                    if _is_placeholder(value):
                        value = ""
                    summary[field] = value
                return summary
    return None


def _is_placeholder(value: str) -> bool:
    """True when a summary field holds no real content: empty, only
    punctuation, or a stock placeholder such as "..." or "N/A"."""
    cleaned = re.sub(r"[^a-z0-9]+", "", (value or "").lower())
    return not cleaned or cleaned in {"na", "none", "notavailable", "tbd"}


def _fill_missing_fields(summary: Dict[str, str], text: str) -> Dict[str, str]:
    """Fill any empty summary field from the extractive fallback of the text.

    Replaces the old behaviour of returning "Unable to extract ..." for a
    missing field: the paper text is in context, so real sentences from
    the matching section are strictly better than a placeholder. Only
    fills from fallback text that is real content (not the fallback's own
    "not available" markers).
    """
    fallback = _extractive_fallback(text)
    filled = {field: (summary.get(field) or "").strip() for field in SUMMARY_FIELDS}
    for field in SUMMARY_FIELDS:
        if filled[field]:
            continue
        candidate = fallback.get(field, "")
        if candidate and "not available" not in candidate.lower():
            filled[field] = candidate
        elif not filled[field]:
            filled[field] = "Summary not available for this section."
    return filled


def _extractive_fallback(text: str) -> Dict[str, str]:
    """Pure local fallback: first sentences of each detected section.

    No model needed, so summarization never hard-fails when Ollama
    is down. Quality is lower than an LLM summary; the caller logs it.
    """
    sections = _extract_sections(text)
    if not sections:
        sentences = _split_sentences(text)
        chunk = max(1, len(sentences) // 4)
        return {
            "problem_statement": " ".join(sentences[:chunk]) or "Summary not available.",
            "methodology": " ".join(sentences[chunk:chunk * 2]) or "Summary not available.",
            "key_findings": " ".join(sentences[chunk * 2:chunk * 3]) or "Summary not available.",
            "conclusion": " ".join(sentences[chunk * 3:]) or "Summary not available.",
        }
    return {
        "problem_statement": _first_sentences(
            sections.get("introduction", "") + " " + sections.get("abstract", ""), 4
        ),
        "methodology": _first_sentences(
            sections.get("methodology", "") + " " + sections.get("method", ""), 4
        ),
        "key_findings": _first_sentences(
            sections.get("results", "") + " " + sections.get("findings", ""), 4
        ),
        "conclusion": _first_sentences(
            sections.get("conclusion", "") + " " + sections.get("discussion", ""), 4
        ),
    }


def _extract_sections(text: str) -> Dict[str, str]:
    sections: Dict[str, str] = {}
    major = r"introduction|background|methodology|methods|related work|results|experiments|evaluation|discussion|conclusion|references|bibliography"
    patterns = {
        "abstract": rf"(?:abstract|summary)[\.\s:]+\n?(.*?)(?=\n\s*(?:{major}|keywords|1\.|2\.))",
        "introduction": rf"(?:introduction|background|motivation)[\.\s:]+\n?(.*?)(?=\n\s*(?:2\.|methodology|method|related work|background))",
        "methodology": rf"(?:methodology|methods?|approach)[\.\s:]+\n?(.*?)(?=\n\s*(?:3\.|4\.|results?|experiments?|evaluation))",
        "results": rf"(?:results?|experiments?|evaluation|findings?)[\.\s:]+\n?(.*?)(?=\n\s*(?:discussion|conclusion|5\.|6\.))",
        "conclusion": rf"(?:conclusion|conclusions?|summary|closing)[\.\s:]+\n?(.*?)(?=\n\s*(?:references|acknowledgments?|bibliography)|$)",
    }
    for name, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            content = re.sub(r"\s+", " ", match.group(1).strip())
            if len(content) > 50:
                sections[name] = content
    return sections


def _split_sentences(text: str) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]


def _first_sentences(text: str, n: int) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return "Content not available for this section."
    return " ".join(sentences[:n])


def _parse_llm_summary(summary_text: str) -> Dict[str, str]:
    """
    Parse the LLM response into structured sections.
    Last resort after the JSON extractor and the repair retry: regex
    over headings / JSON fragments, then paragraph fallback. Missing
    fields are left empty for the caller to fill from the extractive
    fallback.
    """
    summary = {
        "problem_statement": "",
        "methodology": "",
        "key_findings": "",
        "conclusion": ""
    }

    try:
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', summary_text, re.DOTALL)
        if json_match:
            summary_json = json.loads(json_match.group(1))
            if isinstance(summary_json, dict):
                summary = {
                    "problem_statement": str(summary_json.get("problem_statement", "")).strip(),
                    "methodology": str(summary_json.get("methodology", "")).strip(),
                    "key_findings": str(summary_json.get("key_findings", "")).strip(),
                    "conclusion": str(summary_json.get("conclusion", "")).strip()
                }
                if all(v for v in summary.values()):
                    return summary
    except Exception:
        pass

    patterns = {
        "problem_statement": [
            r'(?:problem\s+statement|problem|research\s+question)[:\-]?\s*(.+?)(?=\n\s*(?:methodology|method|approach|key\s+findings|2\.|conclusion|$))',
            r'"problem_statement"[:\s]*"([^"]+)"',
            r'problem_statement["\']?\s*[:=]\s*["\']?([^"\']+)',
            r'1[\.\)]\s*problem[:\-]?\s*(.+?)(?=\n\s*2[\.\)])',
        ],
        "methodology": [
            r'(?:methodology|method|approach|methods)[:\-]?\s*(.+?)(?=\n\s*(?:key\s+findings|results|findings|3\.|conclusion|$))',
            r'"methodology"[:\s]*"([^"]+)"',
            r'methodology["\']?\s*[:=]\s*["\']?([^"\']+)',
            r'2[\.\)]\s*method[:\-]?\s*(.+?)(?=\n\s*3[\.\)])',
        ],
        "key_findings": [
            r'(?:key\s+findings|findings|results|main\s+results)[:\-]?\s*(.+?)(?=\n\s*(?:conclusion|implications|4\.|$))',
            r'"key_findings"[:\s]*"([^"]+)"',
            r'key_findings["\']?\s*[:=]\s*["\']?([^"\']+)',
            r'3[\.\)]\s*findings[:\-]?\s*(.+?)(?=\n\s*4[\.\)])',
        ],
        "conclusion": [
            r'(?:conclusion|conclusions|summary)[:\-]?\s*(.+?)(?=\n\s*$)',
            r'"conclusion"[:\s]*"([^"]+)"',
            r'conclusion["\']?\s*[:=]\s*["\']?([^"\']+)',
            r'4[\.\)]\s*conclusion[:\-]?\s*(.+?)$',
        ]
    }

    for section, section_patterns in patterns.items():
        for pattern in section_patterns:
            match = re.search(pattern, summary_text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            if match:
                extracted = match.group(1).strip()
                extracted = re.sub(r'^["\']|["\']$', '', extracted)
                extracted = re.sub(r'\s+', ' ', extracted)
                if len(extracted) > 20:
                    summary[section] = extracted
                    break

    if not all(v for v in summary.values()):
        paragraphs = [p.strip() for p in summary_text.split("\n\n") if p.strip() and len(p.strip()) > 30]
        if len(paragraphs) >= 4:
            summary["problem_statement"] = paragraphs[0] if not summary["problem_statement"] else summary["problem_statement"]
            summary["methodology"] = paragraphs[1] if not summary["methodology"] else summary["methodology"]
            summary["key_findings"] = paragraphs[2] if not summary["key_findings"] else summary["key_findings"]
            summary["conclusion"] = paragraphs[3] if not summary["conclusion"] else summary["conclusion"]

    for key in summary:
        summary[key] = summary[key].strip()
    # Do NOT fill missing fields with "Unable to extract..." here: the
    # caller (_summarize_chunk) fills them from the extractive fallback
    # of the source text instead.
    return summary
