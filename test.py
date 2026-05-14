from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project.tools.literature_tools import ArxivSearchTool, SemanticScholarSearchTool


def _load_papers(result: dict[str, Any]) -> list[dict[str, Any]]:
    output = result.get("output")
    if not output:
        return []
    try:
        papers = json.loads(output)
    except json.JSONDecodeError:
        return []
    return papers if isinstance(papers, list) else []


def _print_result(name: str, result: dict[str, Any], elapsed: float) -> None:
    papers = _load_papers(result)
    print(f"\n=== {name} ===")
    print(f"elapsed: {elapsed:.2f}s")
    print(f"success: {result.get('success')}")
    print(f"rate_limited: {result.get('rate_limited')}")
    print(f"retryable: {result.get('retryable')}")
    print(f"query_used: {result.get('query_used')}")
    print(f"tried_queries: {len(result.get('tried_queries') or [])}")
    print(f"attempts: {result.get('attempts')}")
    print(f"message: {result.get('message')}")
    print(f"errors: {result.get('errors')}")
    print(f"paper_count: {len(papers)}")

    for index, paper in enumerate(papers[:10], start=1):
        title = paper.get("title") or "(untitled)"
        year = paper.get("year") or paper.get("published") or ""
        citations = paper.get("citation_count")
        source = paper.get("source_url") or paper.get("url") or ""
        extra = []
        if year:
            extra.append(str(year)[:10])
        if citations is not None:
            extra.append(f"citations={citations}")
        suffix = f" ({', '.join(extra)})" if extra else ""
        print(f"{index}. {title}{suffix}")
        if source:
            print(f"   {source}")


async def _run(query: str, limit: int, year: str) -> None:
    print(f"query: {query}")
    print(f"limit: {limit}")
    if year:
        print(f"year: {year}")

    arxiv = ArxivSearchTool()
    semantic = SemanticScholarSearchTool(max_retries=1, retry_base_seconds=0.5)

    started = time.time()
    arxiv_result = await arxiv(query=query, max_results=limit)
    _print_result("arxiv_search", arxiv_result, time.time() - started)

    started = time.time()
    semantic_result = await semantic(query=query, limit=limit, year=year)
    _print_result("semantic_scholar_search", semantic_result, time.time() - started)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test arxiv_search and semantic_scholar_search tools.")
    parser.add_argument(
        "query",
        nargs="?",
        default="RIS ISAC vehicular networks beamforming",
        help="Search query.",
    )
    parser.add_argument("--limit", type=int, default=20, help="Maximum papers to request from each tool.")
    parser.add_argument("--year", default="", help="Optional Semantic Scholar year or range, e.g. 2020-2024.")
    args = parser.parse_args()

    asyncio.run(_run(args.query, args.limit, args.year))


if __name__ == "__main__":
    main()
