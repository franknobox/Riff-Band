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

from project.tools.literature_tools import ArxivSearchTool


def _papers_from_tool(result: dict[str, Any]) -> list[dict[str, Any]]:
    output = result.get("output")
    if not output:
        return []
    try:
        value = json.loads(output)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


async def _run_current_tool(query: str, limit: int) -> tuple[dict[str, Any], float]:
    started = time.time()
    result = await ArxivSearchTool()(query=query, max_results=limit)
    return result, time.time() - started


def _run_arxiv_library(query: str, limit: int) -> tuple[dict[str, Any], float]:
    started = time.time()
    try:
        import arxiv  # type: ignore
    except ImportError:
        return {
            "success": False,
            "message": "Python package 'arxiv' is not installed. Install with: python -m pip install arxiv",
        }, time.time() - started

    try:
        client = arxiv.Client(page_size=limit, delay_seconds=3, num_retries=2)
        search = arxiv.Search(
            query=query,
            max_results=limit,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        papers = []
        for item in client.results(search):
            papers.append(
                {
                    "title": item.title,
                    "authors": [str(author) for author in item.authors],
                    "published": item.published.isoformat() if item.published else "",
                    "updated": item.updated.isoformat() if item.updated else "",
                    "summary": item.summary,
                    "arxiv_id": item.entry_id.rsplit("/", 1)[-1] if item.entry_id else "",
                    "source_url": item.entry_id,
                    "pdf_url": item.pdf_url,
                }
            )
            if len(papers) >= limit:
                break
        return {
            "success": True,
            "backend": "arxiv_library",
            "output": json.dumps(papers, ensure_ascii=False, indent=2),
        }, time.time() - started
    except Exception as exc:
        return {
            "success": False,
            "message": f"{type(exc).__name__}: {exc}",
        }, time.time() - started


def _print_result(name: str, result: dict[str, Any], elapsed: float) -> None:
    papers = _papers_from_tool(result)
    print(f"\n=== {name} ===")
    print(f"elapsed: {elapsed:.2f}s")
    print(f"success: {result.get('success')}")
    print(f"rate_limited: {result.get('rate_limited')}")
    print(f"retryable: {result.get('retryable')}")
    print(f"message: {result.get('message')}")
    print(f"errors: {result.get('errors')}")
    print(f"paper_count: {len(papers)}")
    for index, paper in enumerate(papers[:10], start=1):
        print(f"{index}. {paper.get('title') or '(untitled)'}")
        if paper.get("source_url"):
            print(f"   {paper['source_url']}")


async def main_async(query: str, limit: int) -> None:
    print(f"query: {query}")
    print(f"limit: {limit}")

    current_result, current_elapsed = await _run_current_tool(query, limit)
    _print_result("current ArxivSearchTool urllib API", current_result, current_elapsed)

    library_result, library_elapsed = _run_arxiv_library(query, limit)
    _print_result("arxiv Python library", library_result, library_elapsed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare current arxiv_search with the optional arxiv Python library.")
    parser.add_argument(
        "query",
        nargs="?",
        default="RIS ISAC vehicular networks beamforming",
        help="Search query.",
    )
    parser.add_argument("--limit", type=int, default=10, help="Maximum papers to request.")
    args = parser.parse_args()
    asyncio.run(main_async(args.query, args.limit))


if __name__ == "__main__":
    main()
