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
        Dict with draft sections, or None on error. Raises ValueError
        when the local Ollama server is not reachable.
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

    try:
        llm = get_chat_model(model=_resolve_chat_model(model), temperature=0.3)
        logger.info(f"Generating draft with local Ollama model {settings.OLLAMA_CHAT_MODEL}")
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

        logger.info("Successfully generated research draft with local Ollama model")
        return draft

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Draft generation error: {e}", exc_info=True)
        return None
