"""
Summarization Service
Provides text summarization using a local Ollama LLM or fallback to extractive method.
"""
import logging
import re
from typing import Dict, List, Optional
from collections import Counter
from .llm_service import summarize_with_llm


def summarize_paper(text: str, max_sentences: int = 5, use_llm: bool = True) -> Dict[str, str]:
    """
    Generate a structured summary of a research paper.
    Uses the local Ollama LLM if available, otherwise falls back to extractive method.
    
    Args:
        text: Full text of the paper
        max_sentences: Maximum sentences per section (for extractive fallback)
        use_llm: Whether to use LLM for summarization (default: True)
    
    Returns:
        Dictionary with keys: problem_statement, methodology, key_findings, conclusion
    """
    if not text or len(text.strip()) < 100:
        return {
            "problem_statement": "Unable to extract problem statement from the text.",
            "methodology": "Unable to extract methodology from the text.",
            "key_findings": "Unable to extract key findings from the text.",
            "conclusion": "Unable to extract conclusion from the text."
        }
    
    # Try LLM summarization first if enabled
    if use_llm:
        llm_summary = summarize_with_llm(text)
        if llm_summary:
            logging.info("Using LLM-generated summary")
            return llm_summary
        else:
            logging.warning("LLM summarization failed, falling back to extractive method")
    
    # Fallback to extractive summarization
    logging.info("Using extractive summarization method")
    
    # Split text into sections based on common paper structure
    sections = _extract_sections(text)
    
    # Generate summaries for each section
    summary = {
        "problem_statement": _summarize_section(
            sections.get("introduction", "") + " " + sections.get("abstract", ""),
            max_sentences
        ),
        "methodology": _summarize_section(
            sections.get("methodology", "") + " " + sections.get("method", ""),
            max_sentences
        ),
        "key_findings": _summarize_section(
            sections.get("results", "") + " " + sections.get("findings", ""),
            max_sentences
        ),
        "conclusion": _summarize_section(
            sections.get("conclusion", "") + " " + sections.get("discussion", ""),
            max_sentences
        )
    }
    
    # If sections are empty, use generic summarization on full text
    if all(len(v.strip()) < 50 for v in summary.values()):
        full_summary = _extractive_summarize(text, max_sentences * 4)
        # Distribute summary across sections
        sentences = _split_sentences(full_summary)
        chunk_size = len(sentences) // 4
        summary = {
            "problem_statement": " ".join(sentences[:chunk_size]) if sentences else "Summary not available.",
            "methodology": " ".join(sentences[chunk_size:chunk_size*2]) if len(sentences) > chunk_size else "Summary not available.",
            "key_findings": " ".join(sentences[chunk_size*2:chunk_size*3]) if len(sentences) > chunk_size*2 else "Summary not available.",
            "conclusion": " ".join(sentences[chunk_size*3:]) if len(sentences) > chunk_size*3 else "Summary not available."
        }
    
    return summary


def _extract_sections(text: str) -> Dict[str, str]:
    """
    Extract common sections from research paper text using flexible regex.
    """
    sections = {}
    
    # Common section headers with flexible patterns (handling newlines, dots, or spaces)
    # We use a non-greedy catch until the next major section header
    major_sections = r"introduction|background|methodology|methods|related work|results|experiments|evaluation|discussion|conclusion|references|bibliography"
    
    section_patterns = {
        "abstract": rf"(?:abstract|summary)[\.\s:]+\n?(.*?)(?=\n\s*(?:{major_sections}|keywords|1\.|2\.))",
        "introduction": rf"(?:introduction|background|motivation)[\.\s:]+\n?(.*?)(?=\n\s*(?:2\.|methodology|method|related work|background))",
        "methodology": rf"(?:methodology|methods?|approach)[\.\s:]+\n?(.*?)(?=\n\s*(?:3\.|4\.|results?|experiments?|evaluation))",
        "results": rf"(?:results?|experiments?|evaluation|findings?)[\.\s:]+\n?(.*?)(?=\n\s*(?:discussion|conclusion|5\.|6\.))",
        "conclusion": rf"(?:conclusion|conclusions?|summary|closing)[\.\s:]+\n?(.*?)(?=\n\s*(?:references|acknowledgments?|bibliography|$))"
    }
    
    for section_name, pattern in section_patterns.items():
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            # Clean section text: normalize whitespace
            content = match.group(1).strip()
            content = re.sub(r'\s+', ' ', content)
            if len(content) > 50:
                sections[section_name] = content
    
    # Fallback: if we didn't find the Abstract but there's text before the Introduction
    if "abstract" not in sections:
        intro_match = re.search(r'introduction', text, re.IGNORECASE)
        if intro_match:
            potential_abs = text[:intro_match.start()].strip()
            # If it has "Abstract" but our regex missed it, or just find any text before intro
            if "abstract" in potential_abs.lower():
                sections["abstract"] = potential_abs
    
    return sections


def _summarize_section(text: str, max_sentences: int) -> str:
    """
    Summarize a section using extractive summarization.
    """
    if not text or len(text.strip()) < 50:
        return "Content not available for this section."
    
    return _extractive_summarize(text, max_sentences)


def _extractive_summarize(text: str, max_sentences: int) -> str:
    """
    Simple extractive summarization using sentence scoring.
    Scores sentences based on word frequency and position.
    """
    sentences = _split_sentences(text)
    
    if len(sentences) <= max_sentences:
        return " ".join(sentences)
    
    # Calculate word frequencies (excluding stop words)
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "must", "can", "this",
        "that", "these", "those", "it", "they", "we", "you", "he", "she"
    }
    
    words = re.findall(r'\b[a-z]+\b', text.lower())
    word_freq = Counter(word for word in words if word not in stop_words and len(word) > 3)
    
    # Score sentences
    sentence_scores = []
    for i, sentence in enumerate(sentences):
        score = 0
        sentence_words = re.findall(r'\b[a-z]+\b', sentence.lower())
        
        # Score based on word frequency
        for word in sentence_words:
            if word in word_freq:
                score += word_freq[word]
        
        # Boost score for sentences near the beginning (introductions)
        # and near the end (conclusions)
        if i < len(sentences) * 0.1:  # First 10% of sentences
            score *= 1.5
        elif i > len(sentences) * 0.9:  # Last 10% of sentences
            score *= 1.3
        
        # Boost for longer sentences (but not too long)
        sentence_length = len(sentence.split())
        if 15 <= sentence_length <= 30:
            score *= 1.2
        
        sentence_scores.append((score, sentence, i))
    
    # Select top sentences
    sentence_scores.sort(reverse=True, key=lambda x: x[0])
    top_sentences = sentence_scores[:max_sentences]
    
    # Sort back to original order
    top_sentences.sort(key=lambda x: x[2])
    
    summary = " ".join(sentence for _, sentence, _ in top_sentences)
    
    return summary


def _split_sentences(text: str) -> List[str]:
    """
    Split text into sentences using simple regex.
    """
    # Simple sentence splitting (can be improved with nltk if needed)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
    return sentences

