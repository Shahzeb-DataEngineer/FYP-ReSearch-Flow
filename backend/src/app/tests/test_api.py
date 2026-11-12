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

import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

import pandas as pd

from src.app.services import (
    crossref_service,
    doaj_service,
    europe_pmc_service,
    pdf_service,
    pubmed_service,
    unpaywall_service,
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


if __name__ == "__main__":
    unittest.main()
