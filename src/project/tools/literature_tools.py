from __future__ import annotations

import asyncio
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List

from pydantic import Field

from base.agent.base_action import BaseAction


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _http_get_text(url: str, headers: dict[str, str] | None = None, timeout: int = 30) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Riff-Band research tool/0.1",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _http_get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 30) -> dict[str, Any]:
    text = _http_get_text(url, headers=headers, timeout=timeout)
    value = json.loads(text)
    return value if isinstance(value, dict) else {}


def _strip_html(text: str) -> str:
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _slug_key(text: str, max_len: int = 48) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", str(text).lower()).strip("-")
    return (slug[:max_len].strip("-") or "ref")


def _bibtex_escape(value: Any) -> str:
    text = str(value or "")
    return text.replace("\\", "\\textbackslash{}").replace("{", "\\{").replace("}", "\\}")


def _short_text(value: Any, limit: int = 600) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    max_len = max(0, int(limit or 0))
    if max_len and len(text) > max_len:
        return text[: max_len - 3].rstrip() + "..."
    return text


_QUERY_STOPWORDS = {
    "and",
    "or",
    "the",
    "for",
    "with",
    "from",
    "into",
    "via",
    "using",
    "based",
    "survey",
    "review",
    "paper",
    "study",
    "studies",
    "system",
    "systems",
    "network",
    "networks",
    "communication",
    "communications",
}


def _query_match_units(query: str) -> list[str]:
    text = str(query or "").strip()
    if not text:
        return []
    units: list[str] = []
    for quoted in re.findall(r'"([^"]{2,})"', text):
        cleaned = re.sub(r"\s+", " ", quoted).strip().lower()
        if cleaned:
            units.append(cleaned)
    unquoted = re.sub(r'"[^"]+"', " ", text)
    for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", unquoted):
        lower = token.lower()
        if lower in _QUERY_STOPWORDS:
            continue
        units.append(lower)
    return list(dict.fromkeys(units))


def _record_matches_query(record: dict[str, Any], query: str) -> bool:
    units = _query_match_units(query)
    if not units:
        return True
    haystack = " ".join(
        str(record.get(field, "") or "")
        for field in ("title", "abstract", "summary", "venue", "publication_types")
    ).lower()
    if not haystack:
        return False
    phrase_units = [unit for unit in units if " " in unit]
    if phrase_units and any(unit in haystack for unit in phrase_units):
        return True
    token_units = [unit for unit in units if " " not in unit]
    required = 1 if len(token_units) <= 2 else 2
    return sum(1 for unit in token_units if unit in haystack) >= required


def _compact_literature_records(papers: list[dict[str, Any]], backend: str) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for paper in papers:
        external_ids = paper.get("external_ids", {}) if isinstance(paper.get("external_ids"), dict) else {}
        item = {
            "title": paper.get("title", ""),
            "authors": list(paper.get("authors", []) or [])[:8],
            "year": paper.get("year") or str(paper.get("published", ""))[:4],
            "venue": paper.get("venue", ""),
            "source_url": paper.get("source_url", ""),
            "doi": paper.get("doi") or external_ids.get("DOI", ""),
            "arxiv_id": paper.get("arxiv_id") or external_ids.get("ArXiv", ""),
            "paper_id": paper.get("paper_id", ""),
            "citation_count": paper.get("citation_count", ""),
            "reference_count": paper.get("reference_count", ""),
            "publication_types": paper.get("publication_types", []) or [],
            "abstract": _short_text(paper.get("abstract") or paper.get("summary"), 600),
            "backend": backend,
        }
        compact.append({key: value for key, value in item.items() if value not in ("", [], None)})
    return compact


def _abstract_from_openalex_index(index: Any) -> str:
    if not isinstance(index, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for word, raw_positions in index.items():
        if not isinstance(raw_positions, list):
            continue
        for pos in raw_positions:
            try:
                positions.append((int(pos), str(word)))
            except (TypeError, ValueError):
                continue
    positions.sort(key=lambda item: item[0])
    return " ".join(word for _pos, word in positions)


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in str(text or ""))


def _research_query_candidates(query: str) -> list[str]:
    q = str(query or "").strip()
    return [q] if q else []

def _arxiv_query_candidates(query: str) -> list[str]:
    return _research_query_candidates(query)


class ArxivSearchTool(BaseAction):
    name: str = "arxiv_search"
    description: str = "Search arXiv papers via the public arXiv API."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 20},
                "sort_by": {
                    "type": "string",
                    "enum": ["relevance", "lastUpdatedDate", "submittedDate"],
                    "default": "relevance",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        }
    )


    async def __call__(
        self,
        query: str,
        max_results: int = 20,
        sort_by: str = "relevance",
    ) -> Dict[str, Any]:
        q = str(query or "").strip()
        if not q:
            return {"success": False, "message": "query must not be empty"}
        max_results = max(1, min(int(max_results or 20), 50))
        sort_by = sort_by if sort_by in {"relevance", "lastUpdatedDate", "submittedDate"} else "relevance"

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        papers_by_id: dict[str, dict[str, Any]] = {}
        query_used = q
        tried_queries: list[str] = []
        errors: list[str] = []
        rate_limited = False
        for candidate in _arxiv_query_candidates(q):
            tried_queries.append(candidate)
            params = urllib.parse.urlencode(
                {
                    "search_query": f"all:{candidate}",
                    "start": 0,
                    "max_results": max_results,
                    "sortBy": sort_by,
                    "sortOrder": "descending",
                }
            )
            url = f"https://export.arxiv.org/api/query?{params}"
            text = ""
            for attempt in range(2):
                try:
                    text = await asyncio.to_thread(_http_get_text, url, None, 8)
                    break
                except urllib.error.HTTPError as exc:
                    errors.append(f"{candidate}: HTTP {exc.code} {exc.reason}")
                    if exc.code == 429:
                        rate_limited = True
                        break
                    if attempt < 1:
                        await asyncio.sleep(1)
                        continue
                    break
                except Exception as exc:
                    errors.append(f"{candidate}: {exc}")
                    break
            if not text:
                if rate_limited and not papers_by_id:
                    break
                continue

            try:
                root = ET.fromstring(text)
            except ET.ParseError as exc:
                errors.append(f"{candidate}: invalid XML {exc}")
                continue

            current: list[dict[str, Any]] = []
            for entry in root.findall("atom:entry", ns):
                links = []
                for link in entry.findall("atom:link", ns):
                    href = link.attrib.get("href", "")
                    if href:
                        links.append(href)
                paper_id = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
                current.append(
                    {
                        "title": " ".join((entry.findtext("atom:title", default="", namespaces=ns) or "").split()),
                        "authors": [
                            (author.findtext("atom:name", default="", namespaces=ns) or "").strip()
                            for author in entry.findall("atom:author", ns)
                        ],
                        "published": (entry.findtext("atom:published", default="", namespaces=ns) or "").strip(),
                        "updated": (entry.findtext("atom:updated", default="", namespaces=ns) or "").strip(),
                        "summary": " ".join((entry.findtext("atom:summary", default="", namespaces=ns) or "").split()),
                        "arxiv_id": paper_id.rsplit("/", 1)[-1] if paper_id else "",
                        "source_url": paper_id or (links[0] if links else ""),
                        "links": links,
                    }
                )
            if current:
                query_used = candidate
                for paper in current:
                    key = str(paper.get("arxiv_id") or paper.get("source_url") or paper.get("title"))
                    papers_by_id.setdefault(key, paper)
                if len(papers_by_id) >= max_results:
                    break

        papers = list(papers_by_id.values())[:max_results]
        if not papers and errors:
            return {
                "success": False,
                "retryable": True,
                "rate_limited": rate_limited,
                "message": "arXiv search failed for all query candidates: " + "; ".join(errors[:5]),
                "tried_queries": tried_queries,
            }

        return {
            "success": True,
            "backend": "arxiv",
            "query_used": query_used,
            "tried_queries": tried_queries,
            "rate_limited": rate_limited,
            "errors": errors[:5],
            "result_mode": "compact",
            "record_count": len(papers),
            "output": json.dumps(_compact_literature_records(papers, "arxiv"), ensure_ascii=False, indent=2),
        }


class SemanticScholarSearchTool(BaseAction):
    name: str = "semantic_scholar_search"
    description: str = "Search papers via the Semantic Scholar Graph API."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
                "year": {"type": "string", "description": "Optional year or range, e.g. 2020-2024."},
            },
            "required": ["query"],
            "additionalProperties": False,
        }
    )
    api_key_env: str = Field(default="SEMANTIC_SCHOLAR_API_KEY", exclude=True)
    max_retries: int = Field(default=2, exclude=True)
    retry_base_seconds: float = Field(default=1.0, exclude=True)


    async def __call__(self, query: str, limit: int = 20, year: str = "") -> Dict[str, Any]:
        q = str(query or "").strip()
        if not q:
            return {"success": False, "message": "query must not be empty"}
        limit = max(1, min(int(limit or 20), 100))
        fields = ",".join(
            [
                "title",
                "abstract",
                "year",
                "authors",
                "url",
                "venue",
                "citationCount",
                "referenceCount",
                "externalIds",
                "publicationTypes",
            ]
        )
        headers = {}
        try:
            import os

            api_key = os.getenv(self.api_key_env)
            if api_key:
                headers["x-api-key"] = api_key
        except Exception:
            pass

        attempts = max(1, int(self.max_retries or 0) + 1)
        last_error = ""
        total_attempts = 0
        tried_queries: list[str] = []
        papers_by_id: dict[str, dict[str, Any]] = {}
        rate_limited = False

        for candidate in _research_query_candidates(q):
            tried_queries.append(candidate)
            params: dict[str, Any] = {"query": candidate, "limit": limit, "fields": fields}
            if str(year or "").strip():
                params["year"] = str(year).strip()
            url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(params)
            data: dict[str, Any] = {}
            for attempt in range(attempts):
                total_attempts += 1
                try:
                    text = await asyncio.to_thread(_http_get_text, url, headers, 30)
                    data = json.loads(text)
                    last_error = ""
                    break
                except urllib.error.HTTPError as exc:
                    last_error = f"HTTP Error {exc.code}: {exc.reason}"
                    if exc.code == 429:
                        rate_limited = True
                    if exc.code != 429 or attempt >= attempts - 1:
                        break
                    retry_after = ""
                    try:
                        retry_after = str(exc.headers.get("Retry-After", "") or "").strip()
                    except Exception:
                        retry_after = ""
                    delay = min(float(retry_after), 8.0) if retry_after.isdigit() else min(self.retry_base_seconds * (2 ** attempt), 8.0)
                    await asyncio.sleep(delay)
                except Exception as exc:
                    last_error = str(exc)
                    break

            for item in data.get("data", []) if isinstance(data, dict) else []:
                if not isinstance(item, dict):
                    continue
                paper = {
                    "paper_id": item.get("paperId", ""),
                    "title": item.get("title", ""),
                    "authors": [author.get("name", "") for author in item.get("authors", []) if isinstance(author, dict)],
                    "year": item.get("year", ""),
                    "venue": item.get("venue", ""),
                    "abstract": item.get("abstract", ""),
                    "source_url": item.get("url", ""),
                    "citation_count": item.get("citationCount", 0),
                    "reference_count": item.get("referenceCount", 0),
                    "external_ids": item.get("externalIds", {}) or {},
                    "publication_types": item.get("publicationTypes", []) or [],
                }
                key = str(paper.get("paper_id") or paper.get("source_url") or paper.get("title"))
                if key:
                    papers_by_id.setdefault(key, paper)
            if len(papers_by_id) >= limit:
                break
            if rate_limited and not papers_by_id:
                break

        papers = sorted(
            papers_by_id.values(),
            key=lambda item: int(item.get("citation_count", 0) or 0),
            reverse=True,
        )[:limit]
        if not papers and last_error:
            message = f"Semantic Scholar search failed: {last_error}"
            if rate_limited or "429" in last_error:
                message += "; rate limited after retries. Try arxiv_search, crossref_lookup, dblp_lookup, or reduce query volume."
            return {
                "success": False,
                "rate_limited": rate_limited or "429" in last_error,
                "retryable": any(code in last_error for code in ["429", "500", "502", "503", "504"]),
                "attempts": total_attempts,
                "tried_queries": tried_queries,
                "message": message,
            }

        return {
            "success": True,
            "backend": "semantic_scholar",
            "tried_queries": tried_queries,
            "attempts": total_attempts,
            "result_mode": "compact",
            "record_count": len(papers),
            "output": json.dumps(_compact_literature_records(papers, "semantic_scholar"), ensure_ascii=False, indent=2),
        }


class OpenAlexSearchTool(BaseAction):
    name: str = "openalex_search"
    description: str = "Search academic works via the OpenAlex Works API."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
                "from_year": {"type": "integer"},
                "to_year": {"type": "integer"},
            },
            "required": ["query"],
            "additionalProperties": False,
        }
    )


    async def __call__(
        self,
        query: str,
        limit: int = 20,
        from_year: int | None = None,
        to_year: int | None = None,
    ) -> Dict[str, Any]:
        q = str(query or "").strip()
        if not q:
            return {"success": False, "message": "query must not be empty"}
        limit = max(1, min(int(limit or 20), 50))
        filters = []
        if from_year:
            filters.append(f"from_publication_date:{int(from_year)}-01-01")
        if to_year:
            filters.append(f"to_publication_date:{int(to_year)}-12-31")
        fetch_limit = min(50, max(limit, limit * 3))
        params: dict[str, Any] = {
            "search": q,
            "per-page": fetch_limit,
            "sort": "cited_by_count:desc",
        }
        if filters:
            params["filter"] = ",".join(filters)
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
        try:
            data = await asyncio.to_thread(_http_get_json, url, None, 30)
        except Exception as exc:
            return {"success": False, "retryable": True, "message": f"OpenAlex search failed: {exc}"}

        records: list[dict[str, Any]] = []
        for item in data.get("results", []) if isinstance(data, dict) else []:
            if not isinstance(item, dict):
                continue
            authors = []
            for authorship in item.get("authorships", []) or []:
                author = authorship.get("author", {}) if isinstance(authorship, dict) else {}
                name = str(author.get("display_name", "") or "").strip()
                if name:
                    authors.append(name)
            primary = item.get("primary_location", {}) if isinstance(item.get("primary_location"), dict) else {}
            source = primary.get("source", {}) if isinstance(primary.get("source"), dict) else {}
            ids = item.get("ids", {}) if isinstance(item.get("ids"), dict) else {}
            doi = str(item.get("doi") or ids.get("doi") or "").replace("https://doi.org/", "")
            record = {
                "paper_id": item.get("id", ""),
                "title": item.get("display_name", ""),
                "authors": authors[:8],
                "year": item.get("publication_year", ""),
                "venue": source.get("display_name", ""),
                "source_url": primary.get("landing_page_url") or ids.get("openalex") or item.get("id", ""),
                "doi": doi,
                "abstract": _abstract_from_openalex_index(item.get("abstract_inverted_index")),
                "citation_count": item.get("cited_by_count", 0),
                "reference_count": item.get("referenced_works_count", 0),
                "publication_types": [item.get("type", "")] if item.get("type") else [],
                "external_ids": {"OpenAlex": item.get("id", ""), "DOI": doi},
            }
            if not _record_matches_query(record, q):
                continue
            records.append(record)
            if len(records) >= limit:
                break
        return {
            "success": True,
            "backend": "openalex",
            "result_mode": "compact",
            "record_count": len(records),
            "output": json.dumps(_compact_literature_records(records, "openalex"), ensure_ascii=False, indent=2),
        }


class WebFetchTool(BaseAction):
    name: str = "web_fetch"
    description: str = "Fetch a URL and return readable text with optional HTML stripping."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "max_chars": {"type": "integer", "default": 12000},
                "strip_html": {"type": "boolean", "default": True},
            },
            "required": ["url"],
            "additionalProperties": False,
        }
    )


    async def __call__(self, url: str, max_chars: int = 12000, strip_html: bool = True) -> Dict[str, Any]:
        target = str(url or "").strip()
        if not target.startswith(("http://", "https://")):
            return {"success": False, "message": "url must start with http:// or https://"}
        max_chars = max(500, min(int(max_chars or 12000), 50000))
        try:
            text = await asyncio.to_thread(_http_get_text, target, None, 30)
        except Exception as exc:
            return {"success": False, "message": f"web fetch failed: {exc}"}
        if strip_html:
            text = _strip_html(text)
        return {
            "success": True,
            "backend": "web_fetch",
            "output": json.dumps({"url": target, "text": text[:max_chars]}, ensure_ascii=False, indent=2),
        }


class ReadUrlTool(WebFetchTool):
    name: str = "read_url"
    description: str = "Alias of web_fetch: fetch a URL and return readable text."


class CrossrefLookupTool(BaseAction):
    name: str = "crossref_lookup"
    description: str = "Look up publication metadata through the Crossref Works API by DOI or query."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "doi": {"type": "string"},
                "rows": {"type": "integer", "default": 5},
            },
            "additionalProperties": False,
        }
    )


    async def __call__(self, query: str = "", doi: str = "", rows: int = 5) -> Dict[str, Any]:
        doi_text = str(doi or "").strip()
        rows = max(1, min(int(rows or 5), 20))
        if doi_text:
            url = "https://api.crossref.org/works/" + urllib.parse.quote(doi_text)
        else:
            q = str(query or "").strip()
            if not q:
                return {"success": False, "message": "query or doi must be provided"}
            url = "https://api.crossref.org/works?" + urllib.parse.urlencode({"query.bibliographic": q, "rows": rows})
        try:
            data = await asyncio.to_thread(_http_get_json, url, None, 30)
        except Exception as exc:
            return {"success": False, "message": f"Crossref lookup failed: {exc}"}

        message = data.get("message", {}) if isinstance(data, dict) else {}
        items = [message] if doi_text and isinstance(message, dict) else message.get("items", [])
        records = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            authors = []
            for author in item.get("author", []) or []:
                if not isinstance(author, dict):
                    continue
                name = " ".join(part for part in [author.get("given", ""), author.get("family", "")] if part).strip()
                if name:
                    authors.append(name)
            published = item.get("published-print") or item.get("published-online") or item.get("issued") or {}
            year = ""
            date_parts = published.get("date-parts", []) if isinstance(published, dict) else []
            if date_parts and date_parts[0]:
                year = str(date_parts[0][0])
            records.append(
                {
                    "title": (item.get("title") or [""])[0],
                    "authors": authors,
                    "year": year,
                    "venue": (item.get("container-title") or [""])[0],
                    "doi": item.get("DOI", ""),
                    "source_url": item.get("URL", ""),
                    "type": item.get("type", ""),
                    "publisher": item.get("publisher", ""),
                }
            )
        return {"success": True, "backend": "crossref", "output": json.dumps(records, ensure_ascii=False, indent=2)}


class DblpLookupTool(BaseAction):
    name: str = "dblp_lookup"
    description: str = "Search DBLP publication metadata by title, author, or keyword."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
            "additionalProperties": False,
        }
    )


    async def __call__(self, query: str, limit: int = 5) -> Dict[str, Any]:
        q = str(query or "").strip()
        if not q:
            return {"success": False, "message": "query must not be empty"}
        limit = max(1, min(int(limit or 5), 20))
        url = "https://dblp.org/search/publ/api?" + urllib.parse.urlencode({"q": q, "format": "json", "h": limit})
        try:
            data = await asyncio.to_thread(_http_get_json, url, None, 30)
        except Exception as exc:
            return {"success": False, "message": f"DBLP lookup failed: {exc}"}
        hits = (((data.get("result", {}) or {}).get("hits", {}) or {}).get("hit", []) or [])
        records = []
        for hit in hits if isinstance(hits, list) else []:
            info = hit.get("info", {}) if isinstance(hit, dict) else {}
            authors_raw = info.get("authors", {}).get("author", []) if isinstance(info.get("authors"), dict) else []
            if isinstance(authors_raw, dict):
                authors_raw = [authors_raw]
            authors = [str(author.get("text", author)) for author in authors_raw]
            records.append(
                {
                    "title": info.get("title", ""),
                    "authors": authors,
                    "year": info.get("year", ""),
                    "venue": info.get("venue", ""),
                    "source_url": info.get("url", ""),
                    "doi": info.get("doi", ""),
                    "type": info.get("type", ""),
                }
            )
        return {"success": True, "backend": "dblp", "output": json.dumps(records, ensure_ascii=False, indent=2)}


class BibtexExportTool(BaseAction):
    name: str = "bibtex_export"
    description: str = "Export papers.jsonl records or provided paper metadata to a BibTeX references file."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "papers": {"type": "array", "items": {"type": "object"}},
                "output_path": {"type": "string"},
                "append": {"type": "boolean", "default": False},
            },
            "additionalProperties": False,
        }
    )
    papers_path: Path = Field(default=Path("papers.jsonl"), exclude=True)
    default_output_path: Path = Field(default=Path("references.bib"), exclude=True)


    async def __call__(
        self,
        papers: list[dict[str, Any]] | None = None,
        output_path: str = "",
        append: bool = False,
    ) -> Dict[str, Any]:
        rows = papers if papers is not None else _read_jsonl(self.papers_path)
        if not rows:
            return {"success": False, "message": "no paper records available for BibTeX export"}
        out = Path(str(output_path).strip()) if str(output_path or "").strip() else self.default_output_path
        entries = []
        used_keys: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title", "")).strip()
            if not title:
                continue
            authors = row.get("authors", []) or []
            first_author = authors[0] if authors else "ref"
            year = str(row.get("year", "") or row.get("published", "") or "n.d.")[:4]
            key_base = _slug_key(f"{first_author}-{year}-{title}")
            key = key_base
            suffix = 2
            while key in used_keys:
                key = f"{key_base}-{suffix}"
                suffix += 1
            used_keys.add(key)
            fields = {
                "title": title,
                "author": " and ".join(str(author) for author in authors),
                "year": year if year.isdigit() else "",
                "journal": row.get("venue", ""),
                "doi": row.get("doi", "") or (row.get("external_ids", {}) or {}).get("DOI", ""),
                "url": row.get("source_url", ""),
            }
            body = "\n".join(
                f"  {name} = {{{_bibtex_escape(value)}}},"
                for name, value in fields.items()
                if str(value or "").strip()
            )
            entries.append(f"@article{{{key},\n{body}\n}}")
        if not entries:
            return {"success": False, "message": "no valid paper records with titles"}
        out.parent.mkdir(parents=True, exist_ok=True)
        existing = out.read_text(encoding="utf-8").rstrip() + "\n\n" if append and out.exists() else ""
        out.write_text(existing + "\n\n".join(entries) + "\n", encoding="utf-8")
        return {"success": True, "output": json.dumps({"path": str(out), "entries": len(entries)}, ensure_ascii=False)}


class LocalPdfExtractTool(BaseAction):
    name: str = "local_pdf_extract"
    description: str = "Extract text from a local PDF file when pypdf is available, with a safe fallback for text-like PDFs."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_pages": {"type": "integer", "default": 3},
                "max_chars": {"type": "integer", "default": 12000},
            },
            "required": ["path"],
            "additionalProperties": False,
        }
    )
    root_dir: Path = Field(default=Path("."), exclude=True)


    async def __call__(self, path: str, max_pages: int = 3, max_chars: int = 12000) -> Dict[str, Any]:
        raw = str(path or "").strip()
        if not raw:
            return {"success": False, "message": "path must not be empty"}
        pdf_path = Path(raw)
        if not pdf_path.is_absolute():
            pdf_path = self.root_dir / pdf_path
        if not pdf_path.exists() or not pdf_path.is_file():
            return {"success": False, "message": f"PDF file not found: {pdf_path}"}
        max_chars = max(500, min(int(max_chars or 12000), 50000))
        max_pages = max(1, min(int(max_pages or 3), 25))
        text = ""
        backend = "binary_fallback"
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(pdf_path))
            parts = []
            for page in reader.pages[:max_pages]:
                parts.append(page.extract_text() or "")
            text = "\n".join(parts)
            backend = "pypdf"
        except Exception:
            raw_bytes = pdf_path.read_bytes()[: max_chars * 4]
            text = raw_bytes.decode("utf-8", errors="ignore") or raw_bytes.decode("latin-1", errors="ignore")
        text = re.sub(r"\s+", " ", text).strip()[:max_chars]
        return {
            "success": True,
            "backend": backend,
            "output": json.dumps({"path": str(pdf_path), "text": text}, ensure_ascii=False, indent=2),
        }


class NoveltyCheckTool(BaseAction):
    name: str = "novelty_check"
    description: str = "Check whether a claim appears covered by recorded papers and findings using keyword overlap."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "papers_path": {"type": "string"},
                "findings_path": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["claim"],
            "additionalProperties": False,
        }
    )
    default_papers_path: Path = Field(default=Path("papers.jsonl"), exclude=True)
    default_findings_path: Path = Field(default=Path("findings.jsonl"), exclude=True)


    async def __call__(
        self,
        claim: str,
        papers_path: str = "",
        findings_path: str = "",
        top_k: int = 5,
    ) -> Dict[str, Any]:
        claim_text = str(claim or "").strip()
        if not claim_text:
            return {"success": False, "message": "claim must not be empty"}
        papers_file = Path(papers_path) if str(papers_path or "").strip() else self.default_papers_path
        findings_file = Path(findings_path) if str(findings_path or "").strip() else self.default_findings_path
        rows = _read_jsonl(papers_file) + _read_jsonl(findings_file)
        claim_terms = {term for term in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", claim_text.lower())}
        matches = []
        for row in rows:
            blob = json.dumps(row, ensure_ascii=False).lower()
            terms = set(re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", blob))
            overlap = sorted(claim_terms & terms)
            score = len(overlap) / max(1, len(claim_terms))
            if overlap:
                matches.append({"score": round(score, 3), "overlap": overlap[:12], "record": row})
        matches.sort(key=lambda item: item["score"], reverse=True)
        top_k = max(1, min(int(top_k or 5), 20))
        status = "covered" if matches and matches[0]["score"] >= 0.5 else "possibly_novel" if rows else "uncertain_no_corpus"
        return {
            "success": True,
            "output": json.dumps(
                {
                    "status": status,
                    "claim_terms": sorted(claim_terms),
                    "matches": matches[:top_k],
                    "note": "Heuristic overlap check only; use literature APIs and human review for final novelty decisions.",
                },
                ensure_ascii=False,
                indent=2,
            ),
        }


class CitationAuditTool(BaseAction):
    name: str = "citation_audit"
    description: str = "Audit report citations against findings and basic citation requirements."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "report_path": {"type": "string"},
                "findings_path": {"type": "string"},
                "required_sections": {"type": "array", "items": {"type": "string"}},
                "min_citations": {"type": "integer", "default": 1},
            },
            "additionalProperties": False,
        }
    )
    default_report_path: Path = Field(default=Path("report.md"), exclude=True)
    default_findings_path: Path = Field(default=Path("findings.jsonl"), exclude=True)


    def _resolve_path(self, raw: str, default: Path) -> Path:
        text = str(raw or "").strip()
        return Path(text) if text else default

    async def __call__(
        self,
        report_path: str = "",
        findings_path: str = "",
        required_sections: list[str] | None = None,
        min_citations: int = 1,
    ) -> Dict[str, Any]:
        report_file = self._resolve_path(report_path, self.default_report_path)
        findings_file = self._resolve_path(findings_path, self.default_findings_path)
        issues: list[str] = []

        report_text = report_file.read_text(encoding="utf-8") if report_file.exists() else ""
        findings = _read_jsonl(findings_file)
        report_urls = sorted(set(re.findall(r"https?://[^\s)\]>\"']+", report_text)))
        finding_urls = sorted(
            {
                str(row.get("source_url", "")).strip()
                for row in findings
                if str(row.get("source_url", "")).strip()
            }
        )
        finding_evidence_count = sum(
            1
            for row in findings
            if str(row.get("source_url", "")).strip() or str(row.get("evidence", "")).strip()
        )
        required = [str(item).strip() for item in (required_sections or []) if str(item).strip()]
        missing_sections = [title for title in required if f"## {title}" not in report_text]

        if not report_text.strip():
            issues.append("report is missing or empty")
        if missing_sections:
            issues.append(f"missing report sections: {missing_sections}")
        if len(report_urls) < max(0, int(min_citations or 0)):
            issues.append(f"report has {len(report_urls)} URL citations; minimum is {int(min_citations or 0)}")
        if findings and finding_evidence_count < len(findings):
            issues.append("some findings lack source_url or evidence")
        if report_urls and finding_urls:
            unmatched = [url for url in report_urls if url not in finding_urls]
        else:
            unmatched = []

        stats = {
            "report_path": str(report_file),
            "findings_path": str(findings_file),
            "report_exists": report_file.exists(),
            "findings_exists": findings_file.exists(),
            "report_citation_urls": report_urls,
            "findings_source_urls": finding_urls,
            "findings_count": len(findings),
            "findings_with_evidence": finding_evidence_count,
            "missing_sections": missing_sections,
            "report_urls_not_in_findings": unmatched,
        }
        return {
            "success": True,
            "output": json.dumps(
                {
                    "passed": not issues,
                    "issues": issues,
                    "stats": stats,
                },
                ensure_ascii=False,
                indent=2,
            ),
        }
