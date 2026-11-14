"""Minimal offline tests for ReSearch Flow backend.

Covers the dedup helpers and the paper-normalization (parsing)
functions of the free paper-source services. No network calls, no
Ollama, no live APIs: every test feeds a hand-built fixture (a dict
or an XML string) straight into a parsing function, or mocks
``requests.get`` where a fetch wrapper is under test.

Runner: pytest is not a project dependency, so these are plain
stdlib unittest tests. From the backend/ directory run:

    python -m unittest discover -s src/app/tests -v

(Run from backend/: the ``src`` package is importable from there,
not from src/app/tests/.)
"""

import asyncio
import time
import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pandas as pd
from fastapi import HTTPException, Request

from src.app.core import jwt_auth, rate_limit
from src.app.services import (
    crossref_service,
    doaj_service,
    europe_pmc_service,
    llm_service,
    pdf_service,
    pubmed_service,
    unpaywall_service,
)
from src.app.services.llm_service import (
    _chunk_text,
    _extract_json_object,
    _fill_missing_fields,
    _is_placeholder,
    _summarize_chunk,
    summarize_with_llm,
)
from src.app.services.crossref_service import _parse_crossref_item
from src.app.services.doaj_service import _parse_doaj_item
from src.app.services.europe_pmc_service import (
    _dedup_ids as europe_pmc_dedup_ids,
)
from src.app.services.europe_pmc_service import _parse_europe_pmc_item
from src.app.services.pubmed_service import (
    _dedup_ids as pubmed_dedup_ids,
)
from src.app.services.pubmed_service import _parse_pubmed_article
from src.app.services.unpaywall_service import (
    _clean_doi,
    _parse_unpaywall_item,
)
from src.app.utils.dedupe import clean_and_deduplicate


def _paper(title, **overrides):
    """Minimal paper row for clean_and_deduplicate."""
    row = {
        "paperId": title,
        "title": title,
        "abstract": "abstract",
        "authors": ["A. Author"],
        "url": "https://example.com",
        "year": 2024,
        "venue": "Journal",
        "source": "Test",
    }
    row.update(overrides)
    return row


class TestCleanAndDeduplicate(unittest.TestCase):
    def test_duplicate_titles_removed_keeping_first(self):
        df = pd.DataFrame(
            [
                _paper("Deep Learning for X", paperId="first"),
                _paper("Deep Learning for X", paperId="second"),
                _paper("A Different Paper", paperId="third"),
            ]
        )
        out = clean_and_deduplicate(df, topic="test")
        self.assertEqual(len(out), 2)
        self.assertEqual(out.iloc[0]["paperId"], "first")
        self.assertEqual(set(out["title"]), {"Deep Learning for X", "A Different Paper"})

    def test_empty_dataframe_returned_unchanged(self):
        out = clean_and_deduplicate(pd.DataFrame(), topic="test")
        self.assertTrue(out.empty)

    def test_missing_columns_are_filled_and_year_coerced(self):
        df = pd.DataFrame([{"title": "Only Title", "year": "not-a-year"}])
        out = clean_and_deduplicate(df, topic="test")
        self.assertEqual(len(out), 1)
        self.assertEqual(out.iloc[0]["year"], 0)
        self.assertEqual(out.iloc[0]["topic"], "test")
        self.assertEqual(out.iloc[0]["authors"], [])
        self.assertEqual(out.iloc[0]["citationCount"], 0)

    def test_title_match_is_exact_not_case_insensitive(self):
        # Documents current behaviour: dedup is on the raw title.
        df = pd.DataFrame([_paper("Same Title"), _paper("same title")])
        out = clean_and_deduplicate(df, topic="test")
        self.assertEqual(len(out), 2)


class TestEuropePmcDedupIds(unittest.TestCase):
    def test_doi_prefix_and_case_normalized(self):
        pmcid, doi, title = europe_pmc_dedup_ids(
            {"pmcid": "PMC123", "doi": "https://doi.org/10.1234/ABC", "title": "Hello, World!"}
        )
        self.assertEqual(pmcid, "pmc123")
        self.assertEqual(doi, "10.1234/abc")
        self.assertEqual(title, "hello world")

    def test_missing_identifiers_are_empty_strings(self):
        self.assertEqual(europe_pmc_dedup_ids({}), ("", "", ""))

    def test_title_punctuation_collapsed(self):
        _, _, title = europe_pmc_dedup_ids({"title": "A  Study:  On   X-Ray!"})
        self.assertEqual(title, "a study on x ray")


class TestPubmedParsing(unittest.TestCase):
    PUBMED_XML = """<PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>12345678</PMID>
          <Article>
            <ArticleTitle>Effects of <i>sleep</i> on memory</ArticleTitle>
            <AuthorList>
              <Author><ForeName>Jane</ForeName><LastName>Smith</LastName></Author>
              <Author><CollectiveName>The Sleep Group</CollectiveName></Author>
            </AuthorList>
            <Abstract>
              <AbstractText Label="BACKGROUND">Sleep matters.</AbstractText>
              <AbstractText>It consolidates memory.</AbstractText>
            </Abstract>
            <Journal>
              <Title>Nature Neuroscience</Title>
              <JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue>
            </Journal>
            <ELocationID EIdType="doi">10.1038/s41593-023-00001</ELocationID>
          </Article>
        </MedlineCitation>
      </PubmedArticle>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>12345678</PMID>
          <Article>
            <ArticleTitle>Effects of sleep on memory</ArticleTitle>
            <AuthorList><Author><ForeName>Jane</ForeName><LastName>Smith</LastName></Author></AuthorList>
            <Journal><Title>Nature Neuroscience</Title></Journal>
          </Article>
        </MedlineCitation>
      </PubmedArticle>
      <PubmedArticle>
        <MedlineCitation><PMID>999</PMID><Article></Article></MedlineCitation>
      </PubmedArticle>
    </PubmedArticleSet>"""

    def test_parse_article_fields(self):
        article = ET.fromstring(self.PUBMED_XML).findall("PubmedArticle")[0]
        paper = _parse_pubmed_article(article)
        self.assertEqual(paper["title"], "Effects of sleep on memory")
        self.assertEqual(paper["pmid"], "12345678")
        self.assertEqual(paper["authors"], ["Jane Smith", "The Sleep Group"])
        self.assertEqual(paper["year"], 2023)
        self.assertEqual(paper["venue"], "Nature Neuroscience")
        self.assertEqual(paper["doi"], "https://doi.org/10.1038/s41593-023-00001")
        self.assertEqual(paper["url"], "https://pubmed.ncbi.nlm.nih.gov/12345678/")
        self.assertIn("BACKGROUND: Sleep matters.", paper["abstract"])
        self.assertIn("It consolidates memory.", paper["abstract"])
        self.assertEqual(paper["source"], "PubMed")
        self.assertIsNone(paper["pdf_url"])

    def test_parse_article_without_title_returns_none(self):
        article = ET.fromstring(self.PUBMED_XML).findall("PubmedArticle")[2]
        self.assertIsNone(_parse_pubmed_article(article))

    def test_dedup_ids_normalize_doi_prefix(self):
        pmid, doi, title = pubmed_dedup_ids(
            {"pmid": "123", "doi": "http://dx.doi.org/10.1/ABC", "title": "Some Title"}
        )
        self.assertEqual((pmid, doi, title), ("123", "10.1/abc", "some title"))

    def test_efetch_dedups_same_paper_under_merged_pmids(self):
        class FakeResponse:
            content = self.PUBMED_XML.encode()

            def raise_for_status(self):
                pass

        with patch.object(pubmed_service.requests, "get", return_value=FakeResponse()):
            papers = pubmed_service._efetch_papers(["12345678", "12345678"])
        # First article and its near-duplicate (same PMID/title) collapse to one.
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["pmid"], "12345678")


class TestDoajParsing(unittest.TestCase):
    ITEM = {
        "id": "doaj-1",
        "bibjson": {
            "title": "Open Access in Practice",
            "author": [{"name": "Ana Ray"}, {"name": "Bo Lee"}],
            "identifier": [{"type": "doi", "id": "10.1234/oa.1"}],
            "journal": {"title": "Journal of Open Science"},
            "year": "2022",
            "abstract": "An abstract.",
            "link": [
                {"type": "fulltext", "url": "https://publisher.example.com/article"},
                {"type": "fulltext", "url": "https://publisher.example.com/article.pdf"},
            ],
        },
    }

    def test_parse_item_fields(self):
        paper = _parse_doaj_item(self.ITEM)
        self.assertEqual(paper["title"], "Open Access in Practice")
        self.assertEqual(paper["authors"], ["Ana Ray", "Bo Lee"])
        self.assertEqual(paper["year"], 2022)
        self.assertEqual(paper["venue"], "Journal of Open Science")
        self.assertEqual(paper["doi"], "https://doi.org/10.1234/oa.1")
        self.assertEqual(paper["pdf_url"], "https://publisher.example.com/article.pdf")
        self.assertEqual(paper["url"], "https://publisher.example.com/article")
        self.assertTrue(paper["isOpenAccess"])
        self.assertEqual(paper["source"], "DOAJ")

    def test_parse_item_without_title_returns_none(self):
        item = {"id": "doaj-2", "bibjson": {"title": ""}}
        self.assertIsNone(_parse_doaj_item(item))

    def test_parse_item_without_pdf_link_has_no_pdf_url(self):
        item = {
            "id": "doaj-3",
            "bibjson": {
                "title": "Landing Only",
                "link": [{"type": "fulltext", "url": "https://publisher.example.com/page"}],
            },
        }
        paper = _parse_doaj_item(item)
        self.assertIsNone(paper["pdf_url"])
        self.assertEqual(paper["url"], "https://publisher.example.com/page")


class TestUnpaywallParsing(unittest.TestCase):
    ITEM = {
        "title": "A Quantum Leap",
        "is_oa": True,
        "oa_status": "gold",
        "best_oa_location": {
            "url_for_pdf": "https://publisher.example.com/paper.pdf",
            "url": "https://publisher.example.com/paper",
        },
        "z_authors": [{"raw_author_name": "G. Kucsko"}],
        "year": 2021,
        "journal_name": "Nature Physics",
        "published_date": "2021-03-04",
    }

    def test_clean_doi_strips_prefix(self):
        self.assertEqual(_clean_doi("https://doi.org/10.1234/ABC "), "10.1234/ABC")
        self.assertEqual(_clean_doi("http://dx.doi.org/10.1/x"), "10.1/x")
        self.assertEqual(_clean_doi(""), "")
        self.assertEqual(_clean_doi(None), "")

    def test_parse_item_fields(self):
        paper = _parse_unpaywall_item(self.ITEM, "10.1038/s41567-021-00001")
        self.assertEqual(paper["title"], "A Quantum Leap")
        self.assertEqual(paper["authors"], ["G. Kucsko"])
        self.assertEqual(paper["year"], 2021)
        self.assertEqual(paper["venue"], "Nature Physics")
        self.assertEqual(paper["pdf_url"], "https://publisher.example.com/paper.pdf")
        self.assertEqual(paper["doi"], "https://doi.org/10.1038/s41567-021-00001")
        self.assertEqual(paper["oa_status"], "gold")
        self.assertTrue(paper["isOpenAccess"])
        self.assertEqual(paper["source"], "Unpaywall")

    def test_non_open_access_returns_none(self):
        item = dict(self.ITEM, is_oa=False)
        self.assertIsNone(_parse_unpaywall_item(item, "10.1/x"))

    def test_open_access_without_any_location_returns_none(self):
        item = dict(self.ITEM, best_oa_location={})
        self.assertIsNone(_parse_unpaywall_item(item, "10.1/x"))

    def test_fetch_sends_configured_contact_email(self):
        # The fetch must send the email from Settings (which loads
        # backend/.env), not a hardcoded value: the old code read
        # os.getenv directly and missed backend/.env, so live lookups
        # silently used the rejected example.com placeholder.
        from src.app.core.config import settings

        with patch(
            "src.app.services.unpaywall_service.requests.get"
        ) as mock_get:
            mock_get.return_value = SimpleNamespace(
                status_code=200,
                json=lambda: dict(self.ITEM),
                raise_for_status=lambda: None,
            )
            paper = unpaywall_service.fetch_unpaywall_paper(
                "10.1038/s41567-021-00001"
            )
            self.assertIsNotNone(paper)
            _, kwargs = mock_get.call_args
            self.assertEqual(
                kwargs["params"]["email"], settings.UNPAYWALL_EMAIL
            )


class TestCrossrefParsing(unittest.TestCase):
    ITEM = {
        "DOI": "10.1234/cr.1",
        "title": ["Crossref Title"],
        "author": [{"given": "Ada", "family": "Lovelace"}, {"family": "Turing"}],
        "published": {"date-parts": [[2020, 7, 15]]},
        "abstract": "<jats:p>First sentence.</jats:p> Second.",
        "URL": "https://publisher.example.com/cr",
        "container-title": ["Journal of Crossref"],
        "link": [
            {"URL": "https://publisher.example.com/cr.html", "content-type": "text/html"},
            {"URL": "https://publisher.example.com/cr.pdf", "content-type": "application/pdf"},
        ],
    }

    def test_parse_item_fields(self):
        paper = _parse_crossref_item(self.ITEM)
        self.assertEqual(paper["title"], "Crossref Title")
        self.assertEqual(paper["authors"], ["Ada Lovelace", "Turing"])
        self.assertEqual(paper["year"], 2020)
        self.assertEqual(paper["venue"], "Journal of Crossref")
        self.assertEqual(paper["abstract"], "First sentence. Second.")
        self.assertEqual(paper["pdf_url"], "https://publisher.example.com/cr.pdf")
        self.assertTrue(paper["isOpenAccess"])
        self.assertEqual(paper["doi"], "https://doi.org/10.1234/cr.1")
        self.assertEqual(paper["source"], "Crossref")

    def test_parse_item_without_doi_returns_none(self):
        self.assertIsNone(_parse_crossref_item({"title": ["No DOI"]}))

    def test_parse_item_without_pdf_link_is_not_open_access(self):
        item = dict(self.ITEM, link=[])
        paper = _parse_crossref_item(item)
        self.assertIsNone(paper["pdf_url"])
        self.assertFalse(paper["isOpenAccess"])


class TestEuropePmcParsing(unittest.TestCase):
    ITEM = {
        "id": "12345",
        "title": "Europe PMC Paper",
        "authorString": "Smith J, Doe A,  Roe B",
        "doi": "10.1234/epmc.1",
        "pmcid": "PMC999",
        "pmid": "111",
        "journalInfo": {"journal": {"title": "eLife"}},
        "pubYear": "2021",
        "abstractText": "Abstract here.",
        "isOpenAccess": "Y",
        "citedByCount": 7,
        "fullTextUrlList": {
            "fullTextUrl": [
                {"documentStyle": "html", "url": "https://europepmc.org/article/MED/111"},
                {"documentStyle": "pdf", "url": "https://europepmc.org/articles/PMC999?pdf=1"},
            ]
        },
    }

    def test_parse_item_fields(self):
        paper = _parse_europe_pmc_item(self.ITEM)
        self.assertEqual(paper["title"], "Europe PMC Paper")
        self.assertEqual(paper["authors"], ["Smith J", "Doe A", "Roe B"])
        self.assertEqual(paper["year"], "2021")
        self.assertEqual(paper["venue"], "eLife")
        self.assertEqual(paper["doi"], "https://doi.org/10.1234/epmc.1")
        self.assertEqual(paper["pmcid"], "PMC999")
        self.assertEqual(paper["citationCount"], 7)
        self.assertTrue(paper["isOpenAccess"])
        self.assertEqual(paper["pdf_url"], "https://europepmc.org/articles/PMC999?pdf=1")
        self.assertEqual(paper["url"], "https://europepmc.org/article/MED/111")
        self.assertEqual(paper["source"], "Europe PMC")

    def test_parse_item_without_title_returns_none(self):
        self.assertIsNone(_parse_europe_pmc_item({"id": "1", "title": ""}))

    def test_fetch_dedups_preprint_and_journal_versions_sharing_a_doi(self):
        journal_version = dict(self.ITEM)
        preprint_version = dict(
            self.ITEM,
            id="67890",
            pmcid="PPR999",
            title="Europe PMC Paper (preprint)",
        )
        payload = {"resultList": {"result": [journal_version, preprint_version]}}

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return payload

        with patch.object(europe_pmc_service.requests, "get", return_value=FakeResponse()):
            papers = europe_pmc_service.fetch_europe_pmc_papers("test", limit=10)
        # Same DOI, different PMCID: still one paper.
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["pmcid"], "PMC999")


class TestEuropePmcFullTextXml(unittest.TestCase):
    """Europe PMC PDF links are Cloudflare-blocked (HTTP 403), so
    get_pdf_text_from_url must fetch the same article's full text as
    JATS XML from the Europe PMC REST API instead. No network: every
    requests.get call is mocked."""

    JATS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<article><front><article-meta><title-group>
<article-title>Test Paper Title</article-title>
</title-group></article-meta></front>
<body><sec><title>Introduction</title>
<p>First body sentence about transformers.</p>
<p>Second body sentence with a <italic>number</italic> 42.</p>
<p>Third body sentence describing the study design in more detail, with
enough words to pass the minimum-length check for extracted full text.</p>
</sec></body></article>"""

    def _xml_response(self):
        class FakeResponse:
            content = TestEuropePmcFullTextXml.JATS_XML
            headers = {"Content-Type": "application/xml"}

            def raise_for_status(self):
                pass

        return FakeResponse()

    def _pdf_bytes(self):
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Fallback PDF text " * 10)
        data = doc.tobytes()
        doc.close()
        return data

    def test_render_url_uses_fulltext_xml(self):
        with patch.object(
            pdf_service.requests, "get", return_value=self._xml_response()
        ) as mock_get:
            text, error = pdf_service.get_pdf_text_from_url(
                "https://europepmc.org/articles/PMC13576103?pdf=render"
            )
        self.assertIsNone(error)
        self.assertIn("First body sentence about transformers", text)
        self.assertIn("Second body sentence with a number 42", text)
        self.assertNotIn("<", text)
        # Front matter (the title) must not leak into the body text.
        self.assertNotIn("Test Paper Title", text)
        mock_get.assert_called_once()
        called_url = mock_get.call_args.args[0]
        self.assertEqual(
            called_url,
            "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13576103/fullTextXML",
        )

    def test_paragraphs_kept_separate_with_blank_lines(self):
        # Regression: the old extractor collapsed all whitespace, so
        # the whole body arrived as one glued blob ("BackgroundThyroid
        # nodules...") with no paragraph breaks for chunking or section
        # detection.
        with patch.object(
            pdf_service.requests, "get", return_value=self._xml_response()
        ):
            text, error = pdf_service.get_pdf_text_from_url(
                "https://europepmc.org/articles/PMC999"
            )
        self.assertIsNone(error)
        self.assertIn("\n\n", text)
        self.assertIn("Introduction\n\nFirst body sentence", text)
        self.assertNotIn("IntroductionFirst", text)

    def test_plain_article_url_also_uses_fulltext_xml(self):
        with patch.object(
            pdf_service.requests, "get", return_value=self._xml_response()
        ) as mock_get:
            text, error = pdf_service.get_pdf_text_from_url(
                "https://europepmc.org/articles/PMC999"
            )
        self.assertIsNone(error)
        self.assertIn("First body sentence about transformers", text)
        self.assertIn("PMC999/fullTextXML", mock_get.call_args.args[0])

    def test_xml_failure_falls_back_to_pdf_download(self):
        import requests

        class NotFoundResponse:
            status_code = 404
            content = b""
            headers = {"Content-Type": "text/html"}

            def raise_for_status(self):
                error = requests.exceptions.HTTPError("404 Not Found")
                error.response = self
                raise error

        class PdfResponse:
            content = None  # set per-instance below
            headers = {"Content-Type": "application/pdf"}

            def raise_for_status(self):
                pass

        pdf_response = PdfResponse()
        pdf_response.content = self._pdf_bytes()
        calls = []

        def fake_get(url, **kwargs):
            calls.append(url)
            if "fullTextXML" in url:
                return NotFoundResponse()
            return pdf_response

        with patch.object(pdf_service.requests, "get", side_effect=fake_get):
            text, error = pdf_service.get_pdf_text_from_url(
                "https://europepmc.org/articles/PMC999?pdf=render"
            )
        self.assertIsNone(error)
        self.assertIn("Fallback PDF text", text)
        self.assertTrue(any("fullTextXML" in url for url in calls))

    def test_non_europe_pmc_url_never_calls_fulltext_api(self):
        class PdfResponse:
            content = None
            headers = {"Content-Type": "application/pdf"}

            def raise_for_status(self):
                pass

        pdf_response = PdfResponse()
        pdf_response.content = self._pdf_bytes()
        calls = []

        def fake_get(url, **kwargs):
            calls.append(url)
            return pdf_response

        with patch.object(pdf_service.requests, "get", side_effect=fake_get):
            text, error = pdf_service.get_pdf_text_from_url(
                "https://arxiv.org/pdf/1706.03762"
            )
        self.assertIsNone(error)
        self.assertIn("Fallback PDF text", text)
        self.assertFalse(any("fullTextXML" in url for url in calls))


class TestSummaryJsonRobustness(unittest.TestCase):
    """The 3B model returns malformed JSON or drops fields, so the
    summarizer must extract tolerant JSON, retry once with a repair
    prompt, and fill still-missing fields from the extractive fallback
    of the same text instead of "Unable to extract..." placeholders.
    No network, no live Ollama: the LLM is a fake returning canned
    responses."""

    GOOD_JSON = (
        '{"problem_statement": "The problem is X.", '
        '"methodology": "We used method Y.", '
        '"key_findings": "We found Z.", '
        '"conclusion": "X works."}'
    )

    # Paper text with real newline-separated sections, so the extractive
    # fallback can find each section.
    SECTION_TEXT = (
        "Abstract\n"
        "This study asks whether X causes Y in patients with diabetes.\n\n"
        "Introduction\n"
        "The problem matters because X is common and poorly understood.\n\n"
        "Methods\n"
        "We ran a randomized trial of method Y on 200 patients.\n\n"
        "Results\n"
        "The trial found Z improved outcomes by half in all groups.\n\n"
        "Conclusion\n"
        "X works and should be adopted in clinics everywhere."
    )

    def _fake_llm(self, responses):
        class FakeLLM:
            def __init__(self, replies):
                self.replies = list(replies)
                self.calls = []

            def invoke(self, prompt):
                self.calls.append(prompt)
                return SimpleNamespace(content=self.replies.pop(0))

        return FakeLLM(responses)

    def test_extract_plain_json(self):
        out = _extract_json_object(self.GOOD_JSON)
        self.assertEqual(out["problem_statement"], "The problem is X.")
        self.assertEqual(out["conclusion"], "X works.")

    def test_extract_fenced_json(self):
        out = _extract_json_object("Here is the summary:\n```json\n" + self.GOOD_JSON + "\n```")
        self.assertEqual(out["methodology"], "We used method Y.")

    def test_extract_json_with_prose_around_it(self):
        out = _extract_json_object(
            "Sure, here is the structured summary.\n" + self.GOOD_JSON + "\nHope that helps."
        )
        self.assertEqual(out["key_findings"], "We found Z.")

    def test_extract_repairs_trailing_comma(self):
        broken = self.GOOD_JSON.replace('"X works."}', '"X works.",}')
        out = _extract_json_object(broken)
        self.assertIsNotNone(out)
        self.assertEqual(out["conclusion"], "X works.")

    def test_extract_malformed_json_returns_none(self):
        self.assertIsNone(_extract_json_object("not json at all"))
        self.assertIsNone(_extract_json_object('{"problem_statement": "unclosed'))

    def test_placeholder_json_values_are_treated_as_missing(self):
        self.assertEqual(
            _extract_json_object(
                '{"problem_statement": "...", "methodology": "N/A", '
                '"key_findings": "Real finding here.", "conclusion": "..."}'
            ),
            {
                "problem_statement": "",
                "methodology": "",
                "key_findings": "Real finding here.",
                "conclusion": "",
            },
        )

    def test_is_placeholder(self):
        for value in ("", "...", "..", "N/A", "not available", " - "):
            self.assertTrue(_is_placeholder(value), value)
        for value in ("Real sentence here.", "X works."):
            self.assertFalse(_is_placeholder(value), value)

    def test_chunk_text_hard_splits_a_blob_with_no_newlines(self):
        # Regression: the Europe PMC JATS body arrived as one 54k-char
        # run with no blank lines and became a single chunk, far past
        # the model's 8192-token context window.
        blob = "Word " * 6000  # 30000 chars, no newlines at all
        chunks = _chunk_text(blob, 12000)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 12000 for c in chunks))
        self.assertEqual("".join(c.replace("\n\n", "") for c in chunks), blob)

    def test_repair_prompt_has_no_placeholder_template(self):
        llm = self._fake_llm(["{not valid json", self.GOOD_JSON])
        _summarize_chunk(llm, "Some paper text " * 20)
        self.assertEqual(len(llm.calls), 2)
        self.assertNotIn('"problem_statement": "..."', llm.calls[1])
        self.assertIn("Paper text:", llm.calls[1])

    def test_placeholder_echo_is_filled_from_chunk_text(self):
        # The 3B model copied the old repair prompt's "..." template
        # values, which the extractor accepted as valid JSON.
        echo = (
            '{"problem_statement": "...", "methodology": "...", '
            '"key_findings": "...", "conclusion": "..."}'
        )
        llm = self._fake_llm([echo, echo])
        summary = _summarize_chunk(llm, self.SECTION_TEXT)
        for field in ("problem_statement", "methodology", "key_findings", "conclusion"):
            self.assertNotIn("...", summary[field])
            self.assertGreater(len(summary[field]), 20)
        self.assertIn("clinics", summary["conclusion"])
        out = _extract_json_object('{"problem_statement": "Only this."}')
        self.assertEqual(out["problem_statement"], "Only this.")
        self.assertEqual(out["conclusion"], "")

    def test_first_try_valid_json_needs_no_retry(self):
        llm = self._fake_llm([self.GOOD_JSON])
        summary = _summarize_chunk(llm, "Some paper text " * 20)
        self.assertEqual(summary["problem_statement"], "The problem is X.")
        self.assertEqual(len(llm.calls), 1)

    def test_malformed_first_response_is_repaired_on_retry(self):
        llm = self._fake_llm(["{not valid json", self.GOOD_JSON])
        summary = _summarize_chunk(llm, "Some paper text " * 20)
        self.assertEqual(summary["key_findings"], "We found Z.")
        self.assertEqual(len(llm.calls), 2)
        self.assertIn("not valid JSON", llm.calls[1])

    def test_missing_field_filled_from_chunk_text_not_placeholder(self):
        incomplete = (
            '{"problem_statement": "The problem is X.", '
            '"methodology": "We used method Y.", '
            '"key_findings": "We found Z.", '
            '"conclusion": ""}'
        )
        llm = self._fake_llm([incomplete, incomplete])
        summary = _summarize_chunk(llm, self.SECTION_TEXT)
        self.assertEqual(summary["problem_statement"], "The problem is X.")
        # Conclusion must come from the chunk itself, never a placeholder.
        self.assertNotIn("Unable to extract", summary["conclusion"])
        self.assertIn("clinics", summary["conclusion"])

    def test_fill_missing_fields_uses_real_sentences(self):
        out = _fill_missing_fields(
            {"problem_statement": "Kept.", "methodology": "", "key_findings": "", "conclusion": ""},
            self.SECTION_TEXT,
        )
        self.assertEqual(out["problem_statement"], "Kept.")
        self.assertIn("trial", out["methodology"])
        self.assertIn("found Z", out["key_findings"])
        self.assertIn("adopted", out["conclusion"])

    def test_merge_fills_missing_field_instead_of_discarding_llm_fields(self):
        # Two chunks (>12000 chars each) so the merge path runs.
        para = (
            "Abstract. This study asks whether X causes Y in patients. "
            "Introduction. The problem matters because X is common. "
            "Methods. We ran a randomized trial of method Y on 200 patients. "
            "Results. The trial found Z improved outcomes by half. "
            "Conclusion. X works and should be adopted in clinics. "
        )
        text = (para * 40) + "\n\n" + (para * 40)
        first = (
            '{"problem_statement": "Problem X.", "methodology": "Method Y.", '
            '"key_findings": "Found Z.", "conclusion": ""}'
        )
        second = (
            '{"problem_statement": "Problem X again.", "methodology": "Method Y again.", '
            '"key_findings": "Found Z again.", "conclusion": ""}'
        )
        llm = self._fake_llm([first, second, first, second])
        with (
            patch.object(llm_service, "check_ollama_available", return_value=True),
            patch.object(llm_service, "get_chat_model", return_value=llm),
        ):
            summary = summarize_with_llm(text)
        # LLM fields survive the merge; the missing conclusion is filled
        # from the paper text, not discarded and not a placeholder.
        self.assertIn("Problem X", summary["problem_statement"])
        self.assertNotIn("Unable to extract", summary["conclusion"])
        self.assertIn("clinics", summary["conclusion"])


class TestJwtAuth(unittest.TestCase):
    """Supabase JWT verification: local HS256, Auth API fallback, guards."""

    def setUp(self):
        jwt_auth._verified_cache.clear()

    def _patch_settings(self, **overrides):
        defaults = {
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "SUPABASE_JWT_SECRET": None,
            "SUPABASE_JWT_AUDIENCE": "authenticated",
            "AUTH_CACHE_TTL_SECONDS": 60,
        }
        defaults.update(overrides)
        return [
            patch.object(jwt_auth.settings, key, value)
            for key, value in defaults.items()
        ]

    def _run_patches(self, patches):
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patches])

    def _hs256_token(self, secret="test-secret", **claims):
        payload = {
            "sub": "user-123",
            "email": "researcher@example.com",
            "role": "authenticated",
            "aud": "authenticated",
            "iss": "https://test.supabase.co/auth/v1",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
        payload.update(claims)
        return jwt.encode(payload, secret, algorithm="HS256")

    def test_missing_authorization_header_raises_401(self):
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(jwt_auth.get_current_user(None))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_malformed_authorization_header_raises_401(self):
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(jwt_auth.get_current_user("Token abc"))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_auth_not_configured_raises_503(self):
        patches = self._patch_settings(SUPABASE_URL="", SUPABASE_KEY="")
        self._run_patches(patches)
        with self.assertRaises(HTTPException) as ctx:
            jwt_auth.verify_supabase_jwt("anything")
        self.assertEqual(ctx.exception.status_code, 503)

    def test_hs256_valid_token_returns_user(self):
        patches = self._patch_settings(SUPABASE_JWT_SECRET="test-secret")
        self._run_patches(patches)
        user = jwt_auth.verify_supabase_jwt(self._hs256_token())
        self.assertEqual(user["id"], "user-123")
        self.assertEqual(user["email"], "researcher@example.com")

    def test_hs256_wrong_signature_raises_401(self):
        patches = self._patch_settings(SUPABASE_JWT_SECRET="test-secret")
        self._run_patches(patches)
        bad = self._hs256_token(secret="someone-elses-secret")
        with self.assertRaises(HTTPException) as ctx:
            jwt_auth.verify_supabase_jwt(bad)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_hs256_expired_token_raises_401(self):
        patches = self._patch_settings(SUPABASE_JWT_SECRET="test-secret")
        self._run_patches(patches)
        old = self._hs256_token(exp=int(time.time()) - 10)
        with self.assertRaises(HTTPException) as ctx:
            jwt_auth.verify_supabase_jwt(old)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_auth_api_fallback_returns_user_and_caches(self):
        patches = self._patch_settings()
        self._run_patches(patches)
        fake_resp = SimpleNamespace(
            status_code=200,
            json=lambda: {"id": "user-456", "email": "a@b.c"},
        )
        with patch.object(jwt_auth.httpx, "get", return_value=fake_resp) as get:
            first = jwt_auth.verify_supabase_jwt("opaque-token")
            second = jwt_auth.verify_supabase_jwt("opaque-token")
        self.assertEqual(first["id"], "user-456")
        self.assertEqual(second["id"], "user-456")
        # Second call served from the in-memory cache: one HTTP call.
        self.assertEqual(get.call_count, 1)

    def test_auth_api_rejection_raises_401(self):
        patches = self._patch_settings()
        self._run_patches(patches)
        fake_resp = SimpleNamespace(status_code=401, json=lambda: {})
        with patch.object(jwt_auth.httpx, "get", return_value=fake_resp):
            with self.assertRaises(HTTPException) as ctx:
                jwt_auth.verify_supabase_jwt("bad-token")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_scoped_session_id_namespaces_by_user(self):
        scoped = jwt_auth.scoped_session_id("user-1", "session-abc")
        self.assertEqual(scoped, "user-1:session-abc")
        self.assertNotEqual(
            scoped, jwt_auth.scoped_session_id("user-2", "session-abc")
        )


def _fake_request(path, ip="10.0.0.1"):
    """Minimal Starlette request for the rate limiter."""
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "query_string": b"",
        "headers": [],
        "client": (ip, 1234),
        "server": ("testserver", 80),
    }
    return Request(scope)


class TestRateLimit(unittest.TestCase):
    """Per-IP sliding-window limits for the LLM endpoints."""

    def setUp(self):
        rate_limit.reset_rate_limits()

    def test_summarize_allows_ten_then_denies(self):
        req = _fake_request("/api/v1/arxiv/summarize", ip="10.0.0.1")
        for _ in range(10):
            allowed, _ = rate_limit.check_rate_limit(req)
            self.assertTrue(allowed)
        allowed, retry_after = rate_limit.check_rate_limit(req)
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry_after, 1)

    def test_draft_allows_two_per_hour_then_denies(self):
        req = _fake_request("/api/v1/draft/generate", ip="10.0.0.2")
        for _ in range(2):
            allowed, _ = rate_limit.check_rate_limit(req)
            self.assertTrue(allowed)
        allowed, retry_after = rate_limit.check_rate_limit(req)
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 60)

    def test_chat_has_its_own_larger_bucket(self):
        req = _fake_request("/api/v1/chat/ask", ip="10.0.0.3")
        for _ in range(20):
            allowed, _ = rate_limit.check_rate_limit(req)
            self.assertTrue(allowed)
        allowed, _ = rate_limit.check_rate_limit(req)
        self.assertFalse(allowed)

    def test_buckets_are_independent_per_endpoint(self):
        summarize = _fake_request("/api/v1/arxiv/summarize", ip="10.0.0.4")
        chat = _fake_request("/api/v1/chat/ask", ip="10.0.0.4")
        for _ in range(10):
            rate_limit.check_rate_limit(summarize)
        allowed, _ = rate_limit.check_rate_limit(summarize)
        self.assertFalse(allowed)
        # Exhausting summarize does not touch the chat bucket.
        allowed, _ = rate_limit.check_rate_limit(chat)
        self.assertTrue(allowed)

    def test_limits_are_per_ip(self):
        for ip in ("10.0.0.5", "10.0.0.6"):
            req = _fake_request("/api/v1/arxiv/summarize", ip=ip)
            for _ in range(10):
                allowed, _ = rate_limit.check_rate_limit(req)
                self.assertTrue(allowed)

    def test_non_llm_paths_are_not_limited(self):
        req = _fake_request("/api/v1/arxiv/search", ip="10.0.0.7")
        for _ in range(50):
            allowed, _ = rate_limit.check_rate_limit(req)
            self.assertTrue(allowed)

    def test_ready_route_exists(self):
        from src.app.main import app

        paths = {getattr(route, "path", None) for route in app.routes}
        self.assertIn("/ready", paths)
        self.assertIn("/health", paths)


class TestCitationVerification(unittest.TestCase):
    """Move 2: claim verification never claims support it does not have."""

    _SOURCE = (
        "Sleep deprivation impairs memory consolidation in healthy adults. "
        "Participants who slept for eight hours recalled significantly more word pairs "
        "than participants kept awake overnight. "
        "The effect was strongest for declarative memory tasks."
    )

    def test_token_overlap_matching_claim_scores_high(self):
        from src.app.services.citation_verification_service import token_overlap_score

        score = token_overlap_score(
            "sleep deprivation impairs memory consolidation",
            "Sleep deprivation impairs memory consolidation in healthy adults.",
        )
        self.assertGreaterEqual(score, 0.8)

    def test_token_overlap_unrelated_claim_scores_low(self):
        from src.app.services.citation_verification_service import token_overlap_score

        score = token_overlap_score(
            "caffeine improves sprint performance in cyclists",
            "Sleep deprivation impairs memory consolidation in healthy adults.",
        )
        self.assertLess(score, 0.3)

    def test_verify_true_claim_with_mocked_embeddings(self):
        from src.app.services import citation_verification_service as cvs

        # Claim vector matches sentence 1 exactly, nothing else.
        vectors = [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]]
        with patch.object(cvs, "_embed_texts", return_value=vectors):
            result = cvs.verify_claim("sleep deprivation impairs memory", self._SOURCE)
        self.assertTrue(result["verified"])
        self.assertEqual(result["method"], "embedding")
        self.assertEqual(result["sentence_index"], 0)
        self.assertIn("Sleep deprivation impairs memory consolidation", result["quote"])

    def test_verify_false_claim_with_mocked_embeddings(self):
        from src.app.services import citation_verification_service as cvs

        vectors = [[1.0, 0.0], [0.0, 1.0], [0.0, 1.0], [0.0, 1.0]]
        with patch.object(cvs, "_embed_texts", return_value=vectors):
            result = cvs.verify_claim("caffeine improves sprint performance", self._SOURCE)
        self.assertFalse(result["verified"])
        self.assertIsNone(result["supporting_sentence"])
        self.assertIsNone(result["sentence_index"])
        self.assertIsNone(result["quote"])

    def test_verify_falls_back_to_token_overlap_without_embeddings(self):
        from src.app.services import citation_verification_service as cvs

        with patch.object(cvs, "_embed_texts", return_value=None):
            good = cvs.verify_claim("sleep deprivation impairs memory consolidation", self._SOURCE)
            bad = cvs.verify_claim("caffeine improves sprint performance in cyclists", self._SOURCE)
        self.assertTrue(good["verified"])
        self.assertEqual(good["method"], "token_overlap")
        self.assertFalse(bad["verified"])

    def test_verify_marginal_embedding_score_is_not_verified(self):
        from src.app.services import citation_verification_service as cvs

        # Cosine 0.55 between claim and best sentence: below the 0.70
        # threshold, so an unrelated claim must not verify.
        import math

        vectors = [[1.0, 0.0], [0.55, math.sqrt(1 - 0.55**2)], [0.0, 1.0], [0.0, 1.0]]
        with patch.object(cvs, "_embed_texts", return_value=vectors):
            result = cvs.verify_claim("caffeine improves sprint performance", self._SOURCE)
        self.assertFalse(result["verified"])
        self.assertAlmostEqual(result["score"], 0.55, places=2)

    def test_verify_empty_inputs_are_not_verified(self):
        from src.app.services import citation_verification_service as cvs

        self.assertFalse(cvs.verify_claim("", self._SOURCE)["verified"])
        self.assertFalse(cvs.verify_claim("sleep impairs memory", "")["verified"])


class _FakeOpenAlexResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or str(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests_error(self.status_code)


def requests_error(status_code):
    import requests as _requests

    resp = _requests.Response()
    resp.status_code = status_code
    return _requests.exceptions.HTTPError(response=resp)


class TestPaperBadges(unittest.TestCase):
    """Move 2: badges come only from the live OpenAlex response."""

    _WORK = {
        "id": "https://openalex.org/W123",
        "display_name": "A test paper",
        "type": "article",
        "is_retracted": False,
        "cited_by_count": 12345,
        "open_access": {"is_oa": True},
        "primary_location": {"source": {"display_name": "Nature", "type": "journal"}},
    }

    def test_journal_article_badges(self):
        from src.app.services import citation_verification_service as cvs

        with patch.object(
            cvs.requests, "get", return_value=_FakeOpenAlexResponse(200, self._WORK)
        ):
            badges = cvs.get_paper_badges("10.1038/nature12373")
        self.assertEqual(badges["doi"], "10.1038/nature12373")
        self.assertFalse(badges["retracted"])
        self.assertTrue(badges["open_access"])
        self.assertTrue(badges["peer_reviewed"])
        self.assertFalse(badges["preprint"])
        self.assertEqual(badges["citation_count"], 12345)
        self.assertEqual(badges["openalex_url"], "https://openalex.org/W123")

    def test_preprint_is_not_peer_reviewed(self):
        from src.app.services import citation_verification_service as cvs

        work = dict(self._WORK)
        work["type"] = "posted-content"
        work["primary_location"] = {"source": {"display_name": "arXiv", "type": "repository"}}
        with patch.object(cvs.requests, "get", return_value=_FakeOpenAlexResponse(200, work)):
            badges = cvs.get_paper_badges("10.48550/arXiv.1234.56789")
        self.assertTrue(badges["preprint"])
        self.assertFalse(badges["peer_reviewed"])

    def test_retracted_flag_comes_from_openalex(self):
        from src.app.services import citation_verification_service as cvs

        work = dict(self._WORK)
        work["is_retracted"] = True
        with patch.object(cvs.requests, "get", return_value=_FakeOpenAlexResponse(200, work)):
            badges = cvs.get_paper_badges("10.1234/retracted")
        self.assertTrue(badges["retracted"])

    def test_unknown_doi_returns_none(self):
        from src.app.services import citation_verification_service as cvs

        with patch.object(cvs.requests, "get", return_value=_FakeOpenAlexResponse(404, {})):
            self.assertIsNone(cvs.get_paper_badges("10.9999/bogus-doi"))


class _FakeLLM:
    def __init__(self, content):
        self._content = content

    def invoke(self, prompt):
        return SimpleNamespace(content=self._content)


class TestDeepReview(unittest.TestCase):
    """Move 1: screening, extraction and synthesis on mocked inputs."""

    _PAPERS = [
        {
            "title": "Sleep and memory",
            "abstract": "Sleep deprivation impairs memory consolidation in healthy adults. "
            "We tested 40 participants after a night of sleep or wakefulness.",
            "authors": ["A. Author"],
            "year": 2023,
            "venue": "Nature",
            "doi": "https://doi.org/10.1234/SLEEP1",
            "url": "https://example.com/1",
            "citation_count": 50,
            "source": "OpenAlex",
        },
        {
            "title": "Sleep and memory (duplicate)",
            "abstract": "Sleep deprivation impairs memory consolidation in healthy adults. "
            "We tested 40 participants after a night of sleep or wakefulness.",
            "authors": ["A. Author"],
            "year": 2023,
            "venue": "Nature",
            "doi": "10.1234/sleep1",
            "url": "https://example.com/2",
            "citation_count": 10,
            "source": "Semantic Scholar",
        },
        {
            "title": "No abstract here",
            "abstract": "",
            "authors": [],
            "year": 2022,
            "venue": "",
            "doi": "10.1234/noabstract",
            "url": "",
            "citation_count": 99,
            "source": "OpenAlex",
        },
    ]

    def test_search_falls_back_to_europe_pmc_when_primaries_empty(self):
        from src.app.services import deep_review_service as drs

        fallback_paper = {
            "title": "Sleep and memory",
            "abstract": "Sleep deprivation impairs memory consolidation in healthy adults. "
            "We tested 40 participants after a night of sleep or wakefulness.",
            "authors": ["A. Author"],
            "year": 2023,
            "venue": "Sleep",
            "doi": "https://doi.org/10.1234/sleep1",
            "url": "https://europepmc.org/article/MED/123",
            "citationCount": 12,
            "source": "Europe PMC",
        }
        with (
            patch.object(drs, "fetch_openalex_papers", return_value=pd.DataFrame()),
            patch.object(drs, "fetch_semantic_scholar_papers", return_value=[]),
            patch.object(drs, "fetch_europe_pmc_papers", return_value=[fallback_paper]),
            patch.object(drs, "fetch_crossref_papers", return_value=[]),
        ):
            papers = drs.search_papers(["sleep deprivation memory"])
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["source"], "Europe PMC")
        self.assertEqual(papers[0]["doi"], "10.1234/sleep1")

    def test_screen_dedupes_by_doi_and_drops_no_abstract(self):
        from src.app.services.deep_review_service import screen_papers

        screened = screen_papers(self._PAPERS, max_papers=5)
        self.assertEqual(len(screened), 1)
        self.assertEqual(screened[0]["title"], "Sleep and memory")

    def test_screen_caps_at_max_papers(self):
        from src.app.services.deep_review_service import screen_papers

        papers = [dict(p, doi=f"10.1234/p{i}", title=f"Paper {i}") for i, p in enumerate(self._PAPERS[:1] * 4)]
        self.assertEqual(len(screen_papers(papers, max_papers=2)), 2)

    def test_derive_subqueries_falls_back_when_llm_down(self):
        from src.app.services import deep_review_service as drs

        with patch.object(drs, "get_chat_model", side_effect=RuntimeError("ollama down")):
            queries = drs.derive_subqueries("does sleep deprivation impair memory consolidation")
        self.assertGreaterEqual(len(queries), 1)
        self.assertIn("does sleep deprivation impair memory consolidation", queries)

    def test_extract_finding_replaces_invented_quote(self):
        from src.app.services.deep_review_service import extract_finding

        fake = _FakeLLM(
            '{"problem": "Does sleep loss hurt memory?", '
            '"method": "40 participants tested after sleep or wakefulness.", '
            '"key_result": "Sleep improved recall.", '
            '"quote": "A sentence that appears nowhere in the abstract."}'
        )
        finding = extract_finding(fake, self._PAPERS[0], 1)
        self.assertEqual(finding["problem"], "Does sleep loss hurt memory?")
        # The invented quote must be replaced by a real abstract sentence.
        self.assertIn(finding["quote"], self._PAPERS[0]["abstract"])

    def test_synthesize_falls_back_to_template_when_llm_down(self):
        from src.app.services import deep_review_service as drs

        finding = {
            "index": 1,
            "title": "Sleep and memory",
            "year": 2023,
            "problem": "Does sleep loss hurt memory?",
            "method": "40 participants tested.",
            "key_result": "Sleep improved recall.",
            "quote": "Sleep deprivation impairs memory consolidation in healthy adults.",
        }
        with patch.object(drs, "get_chat_model", side_effect=RuntimeError("ollama down")):
            report = drs.synthesize_report("does sleep impair memory", [finding])
        self.assertIn("[1] Sleep and memory", report)
        self.assertIn("Sleep improved recall.", report)

    def test_run_deep_review_with_mocked_search_and_llm(self):
        from src.app.services import deep_review_service as drs

        fake_json = (
            '{"problem": "Does sleep loss hurt memory?", '
            '"method": "40 participants tested after sleep or wakefulness.", '
            '"key_result": "Sleep improved recall.", '
            '"quote": "Sleep deprivation impairs memory consolidation in healthy adults."}'
        )
        with (
            patch.object(drs, "derive_subqueries", return_value=["sleep deprivation memory"]),
            patch.object(drs, "search_papers_with_status", return_value=(self._PAPERS, False)),
            patch.object(drs, "get_chat_model", return_value=_FakeLLM(fake_json)),
            patch.object(
                drs, "synthesize_report",
                return_value="Sleep improves memory consolidation [1].",
            ),
        ):
            result = drs.run_deep_review("does sleep deprivation impair memory", max_papers=3)
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["findings"]), 1)
        self.assertIn("[1]", result["report"])
        self.assertIn("check the cited papers yourself", result["verification_note"].lower())

    def test_run_deep_review_no_results(self):
        from src.app.services import deep_review_service as drs

        with (
            patch.object(drs, "derive_subqueries", return_value=["nothing matches this"]),
            patch.object(drs, "search_papers_with_status", return_value=([], False)),
        ):
            result = drs.run_deep_review("zzz qqq nonexistent topic", max_papers=3)
        self.assertEqual(result["status"], "no_results")
        self.assertEqual(result["findings"], [])

    def test_run_deep_review_search_unavailable(self):
        from src.app.services import deep_review_service as drs

        with (
            patch.object(drs, "derive_subqueries", return_value=["sleep deprivation memory"]),
            patch.object(drs, "search_papers_with_status", return_value=([], True)),
        ):
            result = drs.run_deep_review("does sleep deprivation impair memory", max_papers=3)
        self.assertEqual(result["status"], "search_unavailable")
        self.assertIn("rate-limiting", result["message"])
        self.assertEqual(result["findings"], [])


class TestNewRoutes(unittest.TestCase):
    """The new routes are registered and call the new services."""

    def test_routes_registered(self):
        from src.app.main import app

        # This FastAPI version mounts the API router as one included
        # router, so app.routes does not list the API paths directly;
        # the generated OpenAPI schema does.
        paths = app.openapi()["paths"]
        self.assertIn("/api/v1/review/deep", paths)
        self.assertIn("/api/v1/citations/verify", paths)
        self.assertIn("/api/v1/citations/papers/badges", paths)
        self.assertIn("post", paths["/api/v1/review/deep"])
        self.assertIn("post", paths["/api/v1/citations/verify"])
        self.assertIn("get", paths["/api/v1/citations/papers/badges"])

    def test_deep_review_route_calls_service(self):
        from src.app.api.v1.routes.review import DeepReviewRequest, deep_review_endpoint

        canned = {"status": "success", "question": "q", "report": "r [1]", "findings": []}
        with patch(
            "src.app.api.v1.routes.review.run_deep_review", return_value=dict(canned)
        ):
            result = asyncio.run(deep_review_endpoint(DeepReviewRequest(question="q")))
        self.assertEqual(result["status"], "success")
        self.assertIn("processing_time_seconds", result)

    def test_deep_review_route_rejects_empty_question(self):
        from src.app.api.v1.routes.review import DeepReviewRequest, deep_review_endpoint

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(deep_review_endpoint(DeepReviewRequest(question="  ")))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_verify_route_returns_service_result(self):
        from src.app.api.v1.routes.citations import VerifyRequest, verify_citation_endpoint

        canned = {"verified": True, "score": 0.9, "supporting_sentence": "s", "sentence_index": 0, "quote": "s"}
        with patch("src.app.api.v1.routes.citations.verify_claim", return_value=canned):
            result = asyncio.run(
                verify_citation_endpoint(VerifyRequest(claim="c", source_text="s text here"))
            )
        self.assertTrue(result["verified"])

    def test_badges_route_not_found(self):
        from src.app.api.v1.routes.citations import paper_badges_endpoint

        with patch("src.app.api.v1.routes.citations.get_paper_badges", return_value=None):
            result = asyncio.run(paper_badges_endpoint(doi="10.9999/bogus"))
        self.assertEqual(result["status"], "not_found")
        self.assertIsNone(result["badges"])

    def test_badges_route_success(self):
        from src.app.api.v1.routes.citations import paper_badges_endpoint

        badges = {"doi": "10.1/x", "retracted": False, "open_access": True}
        with patch("src.app.api.v1.routes.citations.get_paper_badges", return_value=badges):
            result = asyncio.run(paper_badges_endpoint(doi="10.1/x"))
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["badges"]["open_access"])

    def test_deep_review_path_is_rate_limited(self):
        rate_limit.reset_rate_limits()
        req = _fake_request("/api/v1/review/deep", ip="10.0.0.9")
        for _ in range(10):
            allowed, _ = rate_limit.check_rate_limit(req)
            self.assertTrue(allowed)
        allowed, retry_after = rate_limit.check_rate_limit(req)
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry_after, 1)


class TestOpenAlexApiKey(unittest.TestCase):
    """OpenAlex API key: sent when configured, keyless when unset,
    and a 403 key_not_activated retries once without the key."""

    _WORK = {
        "id": "https://openalex.org/W123",
        "display_name": "A test paper",
        "type": "article",
        "is_retracted": False,
        "cited_by_count": 7,
        "abstract_inverted_index": None,
        "authorships": [],
        "primary_location": {"source": {"display_name": "Nature", "type": "journal"}},
        "open_access": {"is_oa": True, "oa_url": ""},
        "ids": {},
        "concepts": [],
        "referenced_works": [],
        "publication_year": 2024,
    }

    def _key_not_activated(self):
        return _FakeOpenAlexResponse(
            403,
            {"error": "key_not_activated"},
            text='{"error": "key_not_activated"}',
        )

    def test_headers_empty_when_key_unset(self):
        from src.app.core.config import settings
        from src.app.services import openalex_client

        with patch.object(settings, "OPENALEX_API_KEY", ""):
            self.assertEqual(openalex_client.get_openalex_headers(), {})

    def test_headers_carry_bearer_token_when_key_set(self):
        from src.app.core.config import settings
        from src.app.services import openalex_client

        with patch.object(settings, "OPENALEX_API_KEY", "test-key-123"):
            self.assertEqual(
                openalex_client.get_openalex_headers(),
                {"Authorization": "Bearer test-key-123"},
            )

    def test_search_sends_key_when_configured(self):
        from src.app.core.config import settings
        from src.app.services import openalex_service

        seen = {}

        def fake_get(url, params=None, headers=None, timeout=None):
            seen["headers"] = headers
            return _FakeOpenAlexResponse(200, {"results": [self._WORK]})

        with (
            patch.object(settings, "OPENALEX_API_KEY", "test-key-123"),
            patch.object(openalex_service.requests, "get", side_effect=fake_get),
        ):
            df = openalex_service.fetch_openalex_papers("sleep", limit=1)
        self.assertEqual(seen["headers"], {"Authorization": "Bearer test-key-123"})
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["title"], "A test paper")

    def test_search_is_keyless_when_key_unset(self):
        from src.app.core.config import settings
        from src.app.services import openalex_service

        seen = {}

        def fake_get(url, params=None, headers=None, timeout=None):
            seen["headers"] = headers
            return _FakeOpenAlexResponse(200, {"results": [self._WORK]})

        with (
            patch.object(settings, "OPENALEX_API_KEY", ""),
            patch.object(openalex_service.requests, "get", side_effect=fake_get),
        ):
            df = openalex_service.fetch_openalex_papers("sleep", limit=1)
        self.assertEqual(seen["headers"], {})
        self.assertEqual(len(df), 1)

    def test_search_retries_keyless_once_on_key_not_activated(self):
        from src.app.core.config import settings
        from src.app.services import openalex_service

        calls = []

        def fake_get(url, params=None, headers=None, timeout=None):
            calls.append(headers)
            if len(calls) == 1:
                return self._key_not_activated()
            return _FakeOpenAlexResponse(200, {"results": [self._WORK]})

        with (
            patch.object(settings, "OPENALEX_API_KEY", "pending-key"),
            patch.object(openalex_service.requests, "get", side_effect=fake_get),
        ):
            df = openalex_service.fetch_openalex_papers("sleep", limit=1)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], {"Authorization": "Bearer pending-key"})
        self.assertEqual(calls[1], None)
        self.assertEqual(len(df), 1)

    def test_badges_retry_keyless_once_on_key_not_activated(self):
        from src.app.core.config import settings
        from src.app.services import citation_verification_service as cvs

        work = dict(TestPaperBadges._WORK)
        calls = []

        def fake_get(url, headers=None, timeout=None):
            calls.append(headers)
            if len(calls) == 1:
                return self._key_not_activated()
            return _FakeOpenAlexResponse(200, work)

        with (
            patch.object(settings, "OPENALEX_API_KEY", "pending-key"),
            patch.object(cvs.requests, "get", side_effect=fake_get),
        ):
            badges = cvs.get_paper_badges("10.1038/nature12373")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], {"Authorization": "Bearer pending-key"})
        self.assertEqual(calls[1], None)
        self.assertIsNotNone(badges)
        self.assertEqual(badges["citation_count"], 12345)


if __name__ == "__main__":
    unittest.main()
