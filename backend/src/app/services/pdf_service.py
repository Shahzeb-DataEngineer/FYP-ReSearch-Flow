"""
PDF Service
Handles downloading and text extraction from PDFs using PyMuPDF.
"""
import logging
import requests
import re
from typing import Optional, Tuple
import fitz  # PyMuPDF


# Domains that require human verification (CAPTCHA) and block automated downloads
BLOCKED_PDF_DOMAINS = [
    'researchgate.net',
    'academia.edu',
]


def _is_blocked_domain(url: str) -> bool:
    """Check if URL belongs to a domain that blocks automated PDF downloads."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in BLOCKED_PDF_DOMAINS)


def download_pdf(url: str, timeout: int = 30) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Download PDF from URL.
    
    Args:
        url: PDF URL
        timeout: Request timeout in seconds
    
    Returns:
        Tuple of (PDF content as bytes, error_message)
        If successful: (bytes, None)
        If failed: (None, error_message)
    """
    try:
        # Check for domains that require human verification
        if _is_blocked_domain(url):
            logging.info(f"Skipping blocked domain (requires CAPTCHA): {url}")
            return (None, "BLOCKED_DOMAIN: This paper is hosted on a platform that requires human verification. Summary will be generated from the abstract instead.")

        # EXACT headers from your working snippet
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # arXiv specific: try export.arxiv.org if main domain fails
        if 'arxiv.org' in url and 'export' not in url:
            # We'll try the export domain as it is much more bot-friendly
            url = url.replace('arxiv.org', 'export.arxiv.org')
            logging.info(f"Using arXiv export domain for download: {url}")

        response = requests.get(url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()
        
        # Check if it's actually a PDF
        content_type = response.headers.get('Content-Type', '').lower()
        if 'pdf' in content_type or response.content[:4] == b'%PDF':
            return (response.content, None)
        elif 'html' in content_type:
            # Try to extract the direct PDF link from meta tags
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            meta_tag = soup.find('meta', attrs={'name': 'citation_pdf_url'})
            if meta_tag and meta_tag.get('content'):
                pdf_link = meta_tag.get('content')
                logging.info(f"Found citation_pdf_url in HTML: {pdf_link}")
                pdf_response = requests.get(pdf_link, headers=headers, timeout=timeout)
                pdf_response.raise_for_status()
                pdf_content_type = pdf_response.headers.get('Content-Type', '').lower()
                if 'pdf' in pdf_content_type or pdf_response.content[:4] == b'%PDF':
                    return (pdf_response.content, None)
                
            error_msg = "The URL points to an HTML page, and no direct PDF link could be found."
            logging.warning(f"URL is HTML and no citation_pdf_url found: {url}")
            return (None, error_msg)
        else:
            error_msg = f"The URL does not point to a valid PDF file. Content-Type: {content_type}"
            logging.warning(f"URL does not appear to be a PDF: {url}")
            return (None, error_msg)
            
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        if status == 404:
            error_msg = "PDF not found. This paper may not have a PDF available."
        elif status == 403:
            error_msg = "Access denied. The PDF may be restricted or unavailable."
        elif status >= 500:
            error_msg = f"Server error ({status}). The paper repository is temporarily down."
        else:
            error_msg = f"Failed to access PDF (HTTP {status})."
        logging.error(f"HTTP error downloading PDF from {url}: {str(e)}")
        return (None, error_msg)
    except Exception as e:
        logging.error(f"Error downloading PDF from {url}: {str(e)}")
        return (None, f"Failed to download PDF: {str(e)}")


def extract_text_from_pdf(pdf_content: bytes, max_pages: Optional[int] = None) -> str:
    """
    Extract text from PDF using PyMuPDF (fitz).
    """
    try:
        # Open PDF from bytes
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        
        text_parts = []
        total_pages = len(doc)
        pages_to_process = min(max_pages, total_pages) if max_pages else total_pages
        
        for page_num in range(pages_to_process):
            page = doc[page_num]
            text = page.get_text()
            if text:
                text_parts.append(text)
        
        doc.close()
        
        # Join all text
        full_text = "\n\n".join(text_parts)
        
        # Clean up the text
        cleaned_text = clean_extracted_text(full_text, preserve_all=True)
        
        logging.info(f"Extracted text: {len(cleaned_text)} characters")
        return cleaned_text
        
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {str(e)}")
        return ""


def clean_extracted_text(text: str, preserve_all: bool = True) -> str:
    """
    Clean extracted text.
    """
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {3,}', ' ', text)
    
    if not preserve_all:
        lines = text.split('\n')
        cleaned_lines = []
        skip = False
        for line in lines:
            line_l = line.lower().strip()
            if any(p in line_l for p in ['references', 'bibliography']):
                if len(line.strip()) < 50: skip = True; continue
            if not skip: cleaned_lines.append(line)
        text = '\n'.join(cleaned_lines)
    
    return text.strip()


def get_pdf_text_from_url(pdf_url: str, max_pages: Optional[int] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Download PDF from URL and extract text.

    Europe PMC special case: the PDF links Europe PMC returns
    (https://europepmc.org/articles/PMC...?pdf=render) are served from
    the europepmc.org website, which blocks automated requests with a
    Cloudflare challenge (HTTP 403, "Just a moment..."), so the PDF
    can never be downloaded that way. The same full text is available
    without any bot protection from the Europe PMC REST API as JATS
    XML, so for Europe PMC article URLs we fetch and convert that
    XML first. If the XML fetch fails we fall through to the normal
    PDF download, so other sources are unaffected.
    """
    pmcid = _europe_pmc_id_from_url(pdf_url)
    if pmcid:
        full_text, xml_error = _fetch_europe_pmc_full_text(pmcid)
        if full_text is not None:
            return (full_text, None)
        logging.warning(
            f"Europe PMC full-text XML unavailable for {pmcid} "
            f"({xml_error}); falling back to PDF download"
        )

    pdf_content, download_error = download_pdf(pdf_url)
    if pdf_content is None:
        return (None, download_error)
    
    extracted_text = extract_text_from_pdf(pdf_content, max_pages=max_pages)
    if not extracted_text or len(extracted_text.strip()) < 100:
        return (None, "Failed to extract sufficient text from PDF.")
    
    return (extracted_text, None)


# ---------------------------------------------------------------------------
# Europe PMC full-text XML fallback
# ---------------------------------------------------------------------------

EUROPE_PMC_ARTICLE_RE = re.compile(
    r"europepmc\.org/articles/(PMC\d+)", re.IGNORECASE
)
EUROPE_PMC_FULLTEXT_XML_URL = (
    "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
)


def _europe_pmc_id_from_url(url: str) -> Optional[str]:
    """Return the PMCID if the URL is a Europe PMC article page/PDF link."""
    match = EUROPE_PMC_ARTICLE_RE.search(url or "")
    return match.group(1).upper() if match else None


def _text_from_jats_xml(xml_bytes: bytes) -> str:
    """Convert JATS full-text XML to plain text.

    Uses the <body> element when present (the article text without the
    front-matter metadata); otherwise the whole document. Element text
    and tails are joined, then whitespace is collapsed.
    """
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_bytes)
    body = root.find(".//body")
    scope = body if body is not None else root

    parts = []

    def collect(element):
        if element.text:
            parts.append(element.text)
        for child in element:
            collect(child)
            if child.tail:
                parts.append(child.tail)

    collect(scope)
    text = re.sub(r"\s+", " ", "".join(parts)).strip()
    return text


def _fetch_europe_pmc_full_text(pmcid: str) -> Tuple[Optional[str], Optional[str]]:
    """Fetch an open-access article's full text from Europe PMC as XML.

    Returns (text, None) on success, or (None, error_message).
    """
    try:
        url = EUROPE_PMC_FULLTEXT_XML_URL.format(pmcid=pmcid)
        response = requests.get(
            url,
            headers={"User-Agent": "ReSearch-Flow/1.0"},
            timeout=30,
        )
        response.raise_for_status()
        text = _text_from_jats_xml(response.content)
        if not text or len(text) < 100:
            return (None, "Full-text XML contained too little text.")
        logging.info(
            f"Extracted Europe PMC full text via XML for {pmcid}: "
            f"{len(text)} characters"
        )
        return (text, None)
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        if status == 404:
            return (None, "No full-text XML available for this article.")
        return (None, f"Full-text XML request failed (HTTP {status}).")
    except Exception as e:
        logging.error(f"Error fetching Europe PMC full text for {pmcid}: {str(e)}")
        return (None, f"Failed to fetch full-text XML: {str(e)}")


