from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any


def normalize_doi(value: Any) -> str:
    doi = str(value or "").strip().lower()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
    return doi.removeprefix("doi:").strip()


def normalize_title(value: Any) -> str:
    title = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", title)


def canonical_paper_key(record: dict[str, Any]) -> str:
    doi = normalize_doi(record.get("doi"))
    if doi:
        return f"doi:{doi}"
    title = normalize_title(record.get("title"))
    authors = record.get("authors") if isinstance(record.get("authors"), list) else []
    first_author = normalize_title(authors[0] if authors else "")
    year = str(record.get("year") or "").strip()
    return f"fallback:{title}:{first_author}:{year}"


def stable_paper_id(record: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_paper_key(record).encode("utf-8")).hexdigest()[:16]
    return f"paper_{digest}"


def deduplicate_papers(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for raw in records:
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        item = dict(raw)
        item["doi"] = normalize_doi(item.get("doi"))
        backend = str(item.pop("backend", "") or "").strip()
        query = str(item.pop("query", "") or "").strip()
        key = canonical_paper_key(item)
        if key not in merged:
            item["paper_id"] = stable_paper_id(item)
            item["backends"] = [backend] if backend else []
            item["matched_queries"] = [query] if query else []
            item["source_urls"] = [item.get("source_url")] if item.get("source_url") else []
            merged[key] = item
            continue
        current = merged[key]
        if backend and backend not in current["backends"]:
            current["backends"].append(backend)
        if query and query not in current["matched_queries"]:
            current["matched_queries"].append(query)
        source_url = item.get("source_url")
        if source_url and source_url not in current["source_urls"]:
            current["source_urls"].append(source_url)
        for field in ("abstract", "venue"):
            if len(str(item.get(field) or "")) > len(str(current.get(field) or "")):
                current[field] = item[field]
        if len(item.get("authors") or []) > len(current.get("authors") or []):
            current["authors"] = item["authors"]
        for field in ("citation_count", "reference_count"):
            try:
                current[field] = max(int(current.get(field) or 0), int(item.get(field) or 0))
            except (TypeError, ValueError):
                pass
        if not current.get("doi") and item.get("doi"):
            current["doi"] = item["doi"]
    return sorted(
        merged.values(),
        key=lambda item: (int(item.get("citation_count") or 0), int(item.get("year") or 0)),
        reverse=True,
    )
