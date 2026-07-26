from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from uuid import uuid4

from ai4ms.literature.normalize import deduplicate_papers
from project.tools.literature_tools import (
    ArxivSearchTool,
    CrossrefLookupTool,
    OpenAlexSearchTool,
    SemanticScholarSearchTool,
)


SUPPORTED_BACKENDS = ("openalex", "crossref", "semantic_scholar", "arxiv")


@dataclass(frozen=True)
class LiteratureSearchResult:
    search_id: str
    searched_at: str
    status: str
    queries: list[str]
    backends: list[str]
    identified_count: int
    deduplicated_count: int
    papers: list[dict[str, Any]]
    source_runs: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "search_id": self.search_id,
            "searched_at": self.searched_at,
            "status": self.status,
            "queries": self.queries,
            "backends": self.backends,
            "counts": {
                "identified": self.identified_count,
                "deduplicated": self.deduplicated_count,
            },
            "papers": self.papers,
            "source_runs": self.source_runs,
        }


class LiteratureBroker:
    def __init__(self, tool_factories: dict[str, Callable[[], Any]] | None = None) -> None:
        self.tool_factories = tool_factories or {
            "openalex": OpenAlexSearchTool,
            "crossref": CrossrefLookupTool,
            "semantic_scholar": SemanticScholarSearchTool,
            "arxiv": ArxivSearchTool,
        }

    async def search(
        self,
        queries: list[str],
        backends: list[str],
        *,
        limit_per_backend: int = 10,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> LiteratureSearchResult:
        clean_queries = list(dict.fromkeys(query.strip() for query in queries if query.strip()))
        clean_backends = [backend for backend in dict.fromkeys(backends) if backend in self.tool_factories]
        tasks = [
            self._search_one(query, backend, limit_per_backend, year_from, year_to)
            for query in clean_queries
            for backend in clean_backends
        ]
        runs = await asyncio.gather(*tasks) if tasks else []
        records = [record for run in runs for record in run.pop("records")]
        papers = deduplicate_papers(records)
        successful = sum(1 for run in runs if run["success"])
        status = "complete" if runs and successful == len(runs) else "partial" if successful else "failed"
        return LiteratureSearchResult(
            search_id=f"search_{uuid4().hex[:12]}",
            searched_at=datetime.now(UTC).isoformat(),
            status=status,
            queries=clean_queries,
            backends=clean_backends,
            identified_count=len(records),
            deduplicated_count=len(papers),
            papers=papers,
            source_runs=runs,
        )

    async def _search_one(
        self,
        query: str,
        backend: str,
        limit: int,
        year_from: int | None,
        year_to: int | None,
    ) -> dict[str, Any]:
        tool = self.tool_factories[backend]()
        try:
            if backend == "openalex":
                result = await tool(query=query, limit=limit, from_year=year_from, to_year=year_to)
            elif backend == "crossref":
                result = await tool(query=query, rows=limit)
            elif backend == "semantic_scholar":
                year = f"{year_from or ''}-{year_to or ''}".strip("-")
                result = await tool(query=query, limit=limit, year=year)
            else:
                result = await tool(query=query, max_results=limit)
        except Exception as exc:
            result = {"success": False, "message": str(exc)}

        records: list[dict[str, Any]] = []
        if result.get("success"):
            try:
                parsed = json.loads(str(result.get("output") or "[]"))
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict):
                            records.append({**item, "backend": backend, "query": query})
            except json.JSONDecodeError:
                result = {**result, "success": False, "message": "backend returned invalid JSON"}
        return {
            "backend": backend,
            "query": query,
            "success": bool(result.get("success")),
            "record_count": len(records),
            "error": "" if result.get("success") else str(result.get("message") or "search failed")[:500],
            "records": records,
        }
