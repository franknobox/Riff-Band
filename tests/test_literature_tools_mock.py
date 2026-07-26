from __future__ import annotations

import asyncio
import io
import unittest
from unittest.mock import MagicMock, patch

from project.tools.literature_tools import (
    ArxivSearchTool,
    _compact_literature_records,
    _contains_cjk,
    _http_get_text,
    _research_query_candidates,
    _short_text,
    _strip_html,
)
from research.artifacts import _bib_key, _escape_latex


class TestLiteratureToolsPureFunctions(unittest.TestCase):
    def test_compact_literature_records(self):
        raw = [
            {
                "title": "  Deep  Learning  ",
                "authors": ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Hank", "Ivy"],
                "year": 2023,
                "venue": "ICML",
                "source_url": "https://example.com/paper",
                "doi": "10.1000/test",
                "external_ids": {"DOI": "10.1000/other", "ArXiv": "2301.00001"},
                "paper_id": "p1",
                "citation_count": 42,
                "reference_count": 100,
                "publication_types": ["JournalArticle"],
                "abstract": "A very long abstract " * 50,
                "backend": "semantic_scholar",
            }
        ]
        result = _compact_literature_records(raw, "semantic_scholar")
        self.assertEqual(len(result), 1)
        # title is not stripped in _compact_literature_records
        self.assertEqual(result[0]["title"], "  Deep  Learning  ")
        self.assertEqual(len(result[0]["authors"]), 8)
        self.assertEqual(result[0]["doi"], "10.1000/test")
        self.assertEqual(result[0]["arxiv_id"], "2301.00001")
        self.assertEqual(len(result[0]["abstract"]), 600)  # truncated to limit

    def test_bib_key(self):
        # _bib_key removes all non-alphanumeric chars and title-cases
        self.assertEqual(_bib_key("Alice Smith", "2024", "Demo Paper")[:20], "Smith2024DemoPaper")
        self.assertTrue(_bib_key("Bob", "2023", "Test").startswith("Bob"))

    def test_escape_latex(self):
        self.assertEqual(_escape_latex("100% & $50"), r"100\% \& \$50")
        self.assertIn(r"\textbackslash{}", _escape_latex("C:\\path"))

    def test_strip_html(self):
        self.assertEqual(_strip_html("<p>Hello <b>world</b></p>"), "Hello world")
        self.assertEqual(_strip_html("<script>alert(1)</script>text"), "text")

    def test_contains_cjk(self):
        self.assertTrue(_contains_cjk("中文"))
        self.assertFalse(_contains_cjk("English"))

    def test_short_text(self):
        self.assertEqual(_short_text("short"), "short")
        self.assertTrue(_short_text("x" * 1000, 50).endswith("..."))

    def test_research_query_candidates(self):
        query = "AI adoption and firm innovation"
        self.assertEqual(_research_query_candidates(query), [query])


class TestLiteratureToolsMock(unittest.TestCase):
    def _mock_arxiv_xml(self, entries: int = 1) -> bytes:
        entries_xml = ""
        for i in range(entries):
            entries_xml += f"""<entry>
                <id>https://arxiv.org/abs/2301.{i:05d}</id>
                <title>Title {i}</title>
                <author><name>Author {i}</name></author>
                <summary>Summary {i}</summary>
                <published>2023-01-01T00:00:00Z</published>
                <link href="https://arxiv.org/pdf/2301.{i:05d}.pdf"/>
            </entry>"""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <title>Search Results</title>
    {entries_xml}
</feed>""".encode("utf-8")

    @patch("project.tools.literature_tools._http_get_text")
    def test_arxiv_search_returns_papers(self, mock_get):
        mock_get.return_value = self._mock_arxiv_xml(2).decode("utf-8")
        tool = ArxivSearchTool()
        result = asyncio.run(tool(query="machine learning", max_results=5))

        self.assertTrue(result["success"])
        self.assertEqual(result["record_count"], 2)
        # papers are serialized into the 'output' field
        import json
        papers = json.loads(result["output"])
        self.assertEqual(len(papers), 2)
        self.assertEqual(papers[0]["title"], "Title 0")
        self.assertEqual(result["query_used"], "machine learning")

    @patch("project.tools.literature_tools._http_get_text")
    def test_arxiv_search_empty_query_fails(self, mock_get):
        mock_get.return_value = ""
        tool = ArxivSearchTool()
        result = asyncio.run(tool(query=""))
        self.assertFalse(result["success"])

    @patch("project.tools.literature_tools._http_get_text")
    def test_arxiv_search_http_error_returns_empty(self, mock_get):
        import urllib.error
        mock_get.side_effect = urllib.error.HTTPError(
            url="https://export.arxiv.org/api/query",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=io.BytesIO(b"error"),
        )
        tool = ArxivSearchTool()
        result = asyncio.run(tool(query="test", max_results=5))
        # When all queries fail and no papers are found, success is False
        self.assertFalse(result["success"])
        # errors are concatenated into the message field
        self.assertIn("HTTP 503", result.get("message", ""))


if __name__ == "__main__":
    unittest.main()
