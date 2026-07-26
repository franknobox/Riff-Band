from __future__ import annotations

import asyncio
import json
import shutil
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from project.tools import (
    ArxivSearchTool,
    BibtexExportTool,
    CitationAuditTool,
    CrossrefLookupTool,
    DblpLookupTool,
    LocalPdfExtractTool,
    NoveltyCheckTool,
    OpenAlexSearchTool,
    SemanticScholarSearchTool,
    WebFetchTool,
)


class _FakeResponse:
    def __init__(self, text: str):
        self._text = text

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._text.encode("utf-8")


class TestLiteratureTools(unittest.TestCase):
    def setUp(self):
        self.root = Path("workspace") / "test_lit_tools"
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_arxiv_search_parses_atom_response(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <updated>2024-01-02T00:00:00Z</updated>
    <published>2024-01-01T00:00:00Z</published>
    <title> Test Paper </title>
    <summary> A useful abstract. </summary>
    <author><name>Ada Lovelace</name></author>
    <link href="http://arxiv.org/pdf/2401.00001v1" />
  </entry>
</feed>"""
        with patch("project.tools.literature_tools.urllib.request.urlopen", return_value=_FakeResponse(xml)):
            result = asyncio.run(ArxivSearchTool()(query="test", max_results=1))

        self.assertTrue(result["success"])
        papers = json.loads(result["output"])
        self.assertEqual(papers[0]["title"], "Test Paper")
        self.assertEqual(papers[0]["arxiv_id"], "2401.00001v1")

    def test_arxiv_search_preserves_domain_query(self):
        hit_xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00002v1</id>
    <updated>2024-01-02T00:00:00Z</updated>
    <published>2024-01-01T00:00:00Z</published>
    <title> AI Adoption and Firm Innovation </title>
    <summary> A useful abstract. </summary>
    <author><name>Ada Lovelace</name></author>
  </entry>
</feed>"""
        with patch(
            "project.tools.literature_tools.urllib.request.urlopen",
            return_value=_FakeResponse(hit_xml),
        ):
            query = "生成式人工智能采用与企业创新"
            result = asyncio.run(ArxivSearchTool()(query=query, max_results=1))

        self.assertTrue(result["success"])
        self.assertEqual(result["tried_queries"], [query])
        self.assertEqual(result["query_used"], query)
        papers = json.loads(result["output"])
        self.assertEqual(papers[0]["title"], "AI Adoption and Firm Innovation")

    def test_semantic_scholar_search_parses_json_response(self):
        payload = {
            "data": [
                {
                    "paperId": "abc",
                    "title": "Semantic Paper",
                    "authors": [{"name": "Grace Hopper"}],
                    "year": 2023,
                    "url": "https://semanticscholar.org/paper/abc",
                    "citationCount": 7,
                    "referenceCount": 2,
                    "externalIds": {"DOI": "10.123/test"},
                }
            ]
        }
        with patch(
            "project.tools.literature_tools.urllib.request.urlopen",
            return_value=_FakeResponse(json.dumps(payload)),
        ):
            result = asyncio.run(SemanticScholarSearchTool()(query="semantic", limit=1))

        self.assertTrue(result["success"])
        papers = json.loads(result["output"])
        self.assertEqual(papers[0]["title"], "Semantic Paper")
        self.assertEqual(papers[0]["authors"], ["Grace Hopper"])

    def test_semantic_scholar_search_retries_rate_limit(self):
        payload = {"data": [{"paperId": "abc", "title": "Recovered Paper"}]}
        rate_limit = urllib.error.HTTPError(
            url="https://api.semanticscholar.org/graph/v1/paper/search",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None,
        )
        with patch(
            "project.tools.literature_tools.urllib.request.urlopen",
            side_effect=[rate_limit, _FakeResponse(json.dumps(payload))],
        ), patch("project.tools.literature_tools.asyncio.sleep", return_value=None) as sleep_mock:
            result = asyncio.run(SemanticScholarSearchTool(max_retries=1)(query="semantic", limit=1))

        self.assertTrue(result["success"])
        self.assertTrue(sleep_mock.called)
        papers = json.loads(result["output"])
        self.assertEqual(papers[0]["title"], "Recovered Paper")

    def test_semantic_scholar_search_reports_rate_limit_after_retries(self):
        rate_limit = urllib.error.HTTPError(
            url="https://api.semanticscholar.org/graph/v1/paper/search",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None,
        )
        with patch(
            "project.tools.literature_tools.urllib.request.urlopen",
            side_effect=rate_limit,
        ), patch("project.tools.literature_tools.asyncio.sleep", return_value=None):
            result = asyncio.run(SemanticScholarSearchTool(max_retries=1)(query="semantic", limit=1))

        self.assertFalse(result["success"])
        self.assertTrue(result["rate_limited"])
        self.assertTrue(result["retryable"])
        self.assertEqual(result["attempts"], 2)
        self.assertIn("rate limited", result["message"])

    def test_openalex_search_parses_json_response(self):
        payload = {
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "display_name": "OpenAlex Paper",
                    "publication_year": 2024,
                    "cited_by_count": 12,
                    "referenced_works_count": 3,
                    "doi": "https://doi.org/10.123/openalex",
                    "primary_location": {
                        "landing_page_url": "https://example.org/openalex",
                        "source": {"display_name": "Journal"},
                    },
                    "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
                    "abstract_inverted_index": {"Useful": [0], "abstract": [1]},
                    "type": "article",
                }
            ]
        }
        with patch("project.tools.literature_tools.urllib.request.urlopen", return_value=_FakeResponse(json.dumps(payload))):
            result = asyncio.run(OpenAlexSearchTool()(query="openalex", limit=1))

        self.assertTrue(result["success"])
        rows = json.loads(result["output"])
        self.assertEqual(rows[0]["title"], "OpenAlex Paper")
        self.assertEqual(rows[0]["abstract"], "Useful abstract")
        self.assertEqual(rows[0]["backend"], "openalex")

    def test_citation_audit_checks_report_and_findings(self):
        report = self.root / "report.md"
        findings = self.root / "findings.jsonl"
        report.write_text(
            "# Report\n\n## Evidence\n\nClaim https://example.org/source\n",
            encoding="utf-8",
        )
        findings.write_text(
            json.dumps(
                {
                    "finding": "Claim",
                    "source_url": "https://example.org/source",
                    "evidence": "source-backed",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        tool = CitationAuditTool(default_report_path=report, default_findings_path=findings)

        result = asyncio.run(tool(required_sections=["Evidence"], min_citations=1))

        self.assertTrue(result["success"])
        audit = json.loads(result["output"])
        self.assertTrue(audit["passed"])
        self.assertEqual(audit["stats"]["findings_count"], 1)

    def test_web_fetch_strips_html(self):
        html = "<html><head><style>x</style></head><body><h1>Title</h1><p>Useful text</p></body></html>"
        with patch("project.tools.literature_tools.urllib.request.urlopen", return_value=_FakeResponse(html)):
            result = asyncio.run(WebFetchTool()(url="https://example.org/page"))

        self.assertTrue(result["success"])
        payload = json.loads(result["output"])
        self.assertIn("Useful text", payload["text"])
        self.assertNotIn("<p>", payload["text"])

    def test_crossref_lookup_parses_json_response(self):
        payload = {
            "message": {
                "items": [
                    {
                        "title": ["Crossref Paper"],
                        "author": [{"given": "Ada", "family": "Lovelace"}],
                        "issued": {"date-parts": [[2022]]},
                        "container-title": ["Journal"],
                        "DOI": "10.123/test",
                        "URL": "https://doi.org/10.123/test",
                    }
                ]
            }
        }
        with patch("project.tools.literature_tools.urllib.request.urlopen", return_value=_FakeResponse(json.dumps(payload))):
            result = asyncio.run(CrossrefLookupTool()(query="crossref", rows=1))

        self.assertTrue(result["success"])
        rows = json.loads(result["output"])
        self.assertEqual(rows[0]["title"], "Crossref Paper")
        self.assertEqual(rows[0]["authors"], ["Ada Lovelace"])

    def test_dblp_lookup_parses_json_response(self):
        payload = {
            "result": {
                "hits": {
                    "hit": [
                        {
                            "info": {
                                "title": "DBLP Paper",
                                "authors": {"author": [{"text": "Grace Hopper"}]},
                                "year": "2021",
                                "venue": "CONF",
                                "url": "https://dblp.org/rec/test",
                                "doi": "10.555/test",
                            }
                        }
                    ]
                }
            }
        }
        with patch("project.tools.literature_tools.urllib.request.urlopen", return_value=_FakeResponse(json.dumps(payload))):
            result = asyncio.run(DblpLookupTool()(query="dblp", limit=1))

        self.assertTrue(result["success"])
        rows = json.loads(result["output"])
        self.assertEqual(rows[0]["title"], "DBLP Paper")
        self.assertEqual(rows[0]["authors"], ["Grace Hopper"])

    def test_bibtex_export_from_papers_jsonl(self):
        papers = self.root / "papers.jsonl"
        out = self.root / "references.bib"
        papers.write_text(
            json.dumps(
                {
                    "title": "A Test Paper",
                    "authors": ["Ada Lovelace", "Grace Hopper"],
                    "year": "2024",
                    "venue": "Journal",
                    "doi": "10.123/test",
                    "source_url": "https://example.org/paper",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        result = asyncio.run(BibtexExportTool(papers_path=papers, default_output_path=out)())

        self.assertTrue(result["success"])
        text = out.read_text(encoding="utf-8")
        self.assertIn("@article", text)
        self.assertIn("Ada Lovelace and Grace Hopper", text)

    def test_local_pdf_extract_fallback_reads_text_like_file(self):
        pdf = self.root / "sample.pdf"
        pdf.write_bytes(b"%PDF-1.4\nVisible fallback text")
        result = asyncio.run(LocalPdfExtractTool(root_dir=self.root)(path="sample.pdf", max_chars=1000))

        self.assertTrue(result["success"])
        payload = json.loads(result["output"])
        self.assertIn("Visible fallback text", payload["text"])

    def test_novelty_check_matches_existing_records(self):
        papers = self.root / "papers.jsonl"
        findings = self.root / "findings.jsonl"
        papers.write_text(json.dumps({"title": "Graph Neural Networks for Molecules"}) + "\n", encoding="utf-8")
        findings.write_text(json.dumps({"finding": "Molecular graph neural networks are widely studied"}) + "\n", encoding="utf-8")

        result = asyncio.run(
            NoveltyCheckTool(default_papers_path=papers, default_findings_path=findings)(
                claim="Graph neural networks for molecules are useful"
            )
        )

        self.assertTrue(result["success"])
        payload = json.loads(result["output"])
        self.assertEqual(payload["status"], "covered")


if __name__ == "__main__":
    unittest.main()
