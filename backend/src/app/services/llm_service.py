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
        if all(merged.values()):
            return merged
        return _extractive_fallback(text)
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
    """Split text into chunks of at most max_chars, on paragraph breaks."""
    if len(text) <= max_chars:
        return [text]
    chunks: List[str] = []
    current = ""
    for para in text.split("\n\n"):
        if len(current) + len(para) + 2 > max_chars and current:
            chunks.append(current)
            current = para
        else:
            current = (current + "\n\n" + para) if current else para
    if current:
        chunks.append(current)
    return chunks


def _summarize_chunk(llm, chunk: str) -> Optional[Dict[str, str]]:
    prompt = (
        "You are an expert academic researcher. Analyze the following research paper "
        "text and provide a detailed, structured summary.\n\n"
        "IMPORTANT: Provide your response EXACTLY in this JSON format:\n"
        "{\n"
        '  "problem_statement": "A clear description of the research problem or question addressed (2-4 sentences)",\n'
        '  "methodology": "Detailed description of the methods, approaches, techniques, or frameworks used (3-5 sentences)",\n'
        '  "key_findings": "The main results, discoveries, or findings from the research (3-6 sentences)",\n'
        '  "conclusion": "The key conclusions, implications, or contributions of the research (2-4 sentences)"\n'
        "}\n\n"
        f"Research Paper Content:\n{chunk}\n\n"
        "Now provide the JSON-formatted summary:"
    )
    response = llm.invoke(prompt)
    content = response.content if isinstance(response.content, str) else str(response.content)
    try:
        summary_json = json.loads(content)
        if isinstance(summary_json, dict):
            summary = {
                field: str(summary_json.get(field, "")).strip() for field in SUMMARY_FIELDS
            }
            if all(summary.values()):
                return summary
    except json.JSONDecodeError:
        logging.warning("Ollama summary not in JSON format, attempting text parsing")
    return _parse_llm_summary(content)


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
        "conclusion": rf"(?:conclusion|conclusions?|summary|closing)[\.\s:]+\n?(.*?)(?=\n\s*(?:references|acknowledgments?|bibliography|$))",
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
    (Kept from the original llm_service.py; unchanged logic.)
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
        if not summary[key] or len(summary[key]) < 10:
            summary[key] = f"Unable to extract {key.replace('_', ' ')} from the summary. Please try again."

    return summary
