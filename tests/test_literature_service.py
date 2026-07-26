from __future__ import annotations

import asyncio
import json

from ai4ms.literature.broker import LiteratureBroker, LiteratureSearchResult
from ai4ms.literature.normalize import deduplicate_papers
from ai4ms.literature.service import LiteratureSearchService
from ai4ms.services.models import LiteratureSearchRequest


class _Tool:
    def __init__(self, records=None, error: str = ""):
        self.records = records or []
        self.error = error

    async def __call__(self, **_kwargs):
        if self.error:
            return {"success": False, "message": self.error}
        return {"success": True, "output": json.dumps(self.records)}


def test_deduplicate_papers_prefers_doi_and_preserves_provenance():
    papers = deduplicate_papers(
        [
            {
                "title": "A Study of AI Adoption",
                "authors": ["Li Ming"],
                "year": 2024,
                "doi": "https://doi.org/10.1000/ABC",
                "backend": "openalex",
                "query": "AI adoption",
                "abstract": "short",
            },
            {
                "title": "A study of AI adoption",
                "authors": ["Li Ming", "Chen Yi"],
                "year": 2024,
                "doi": "doi:10.1000/abc",
                "backend": "crossref",
                "query": "firm innovation",
                "abstract": "a longer abstract",
            },
        ]
    )

    assert len(papers) == 1
    assert papers[0]["doi"] == "10.1000/abc"
    assert papers[0]["paper_id"].startswith("paper_")
    assert papers[0]["backends"] == ["openalex", "crossref"]
    assert papers[0]["matched_queries"] == ["AI adoption", "firm innovation"]
    assert papers[0]["abstract"] == "a longer abstract"


def test_broker_isolates_backend_failure_and_returns_partial_result():
    broker = LiteratureBroker(
        {
            "openalex": lambda: _Tool(
                [{"title": "Paper A", "authors": ["A"], "year": 2023}]
            ),
            "crossref": lambda: _Tool(error="rate limited"),
        }
    )

    result = asyncio.run(
        broker.search(["AI management"], ["openalex", "crossref"], limit_per_backend=3)
    )

    assert result.status == "partial"
    assert result.identified_count == 1
    assert result.deduplicated_count == 1
    assert [run["success"] for run in result.source_runs] == [True, False]
    assert "rate limited" in result.source_runs[1]["error"]


class _Broker:
    async def search(self, queries, backends, **_kwargs):
        return LiteratureSearchResult(
            search_id="search_test",
            searched_at="2026-07-21T00:00:00+00:00",
            status="complete",
            queries=queries,
            backends=backends,
            identified_count=1,
            deduplicated_count=1,
            papers=[{"paper_id": "paper_a", "title": "Paper A"}],
            source_runs=[{"backend": "openalex", "success": True, "record_count": 1}],
        )


def test_search_service_uses_plan_queries_and_writes_snapshot(tmp_path):
    service = LiteratureSearchService(tmp_path, broker=_Broker())
    payload = asyncio.run(
        service.search(
            "prj_test",
            {"query_blocks": [{"query_en": "AI adoption", "query_zh": "人工智能采用"}]},
            LiteratureSearchRequest(backends=["openalex"], max_queries=2),
        )
    )

    assert payload["queries"] == ["AI adoption", "人工智能采用"]
    assert payload["snapshot_path"] == "artifacts/literature/search_test.json"
    snapshot = tmp_path / "prj_test" / payload["snapshot_path"]
    assert json.loads(snapshot.read_text(encoding="utf-8"))["papers"][0]["paper_id"] == "paper_a"
