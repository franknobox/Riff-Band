from __future__ import annotations

import asyncio
import html
import json
import os
import re
from urllib.parse import parse_qs, unquote, urlparse
from typing import Any, Dict, List

from pydantic import Field

from base.agent.base_action import BaseAction


if os.getenv("WEB_SEARCH_HTTP_PROXY"):
    os.environ["HTTP_PROXY"] = os.getenv("WEB_SEARCH_HTTP_PROXY", "")
if os.getenv("WEB_SEARCH_HTTPS_PROXY") or os.getenv("WEB_SEARCH_HTTP_PROXY"):
    os.environ["HTTPS_PROXY"] = os.getenv("WEB_SEARCH_HTTPS_PROXY") or os.getenv("WEB_SEARCH_HTTP_PROXY", "")


class WebSearchTool(BaseAction):
    name: str = "web_search"
    description: str = "通过 Serper 搜索联网证据片段，并在失败时回退到 DuckDuckGo。"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "k": {"type": "integer", "default": 5},
                "gl": {"type": "string", "default": "us"},
                "hl": {"type": "string", "default": "en"},
            },
            "required": ["query"],
            "additionalProperties": False,
        }
    )


    async def __call__(self, query: str, k: int = 5, gl: str = "us", hl: str = "en") -> Dict[str, Any]:
        del gl, hl
        k = max(1, int(k))

        serper_result = await self._serper_search(query, k)
        if serper_result["success"]:
            serper_result["backend"] = "serper"
            return serper_result

        ddgs_result = await self._ddgs_search(query, k)
        if ddgs_result["success"]:
            ddgs_result["backend"] = "ddgs"
            return ddgs_result

        ddg_html_result = await self._duckduckgo_html_search(query, k)
        if ddg_html_result["success"]:
            ddg_html_result["backend"] = "duckduckgo_html"
            return ddg_html_result

        wiki_result = await self._wikipedia_search(query, k)
        if wiki_result["success"]:
            wiki_result["backend"] = "wikipedia"
            return wiki_result

        return {
            "success": False,
            "message": (
                f"Both search backends failed. Serper: {serper_result.get('message', '')}; "
                f"DuckDuckGo: {ddgs_result.get('message', '')}; "
                f"DuckDuckGo HTML: {ddg_html_result.get('message', '')}; "
                f"Wikipedia: {wiki_result.get('message', '')}"
            ),
        }

    def _query_terms(self, query: str) -> List[str]:
        text = str(query or "")
        terms = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]{3,}", text)
        return [term.lower() for term in terms if term.strip()]

    def _is_relevant(self, query: str, text: str) -> bool:
        terms = self._query_terms(query)
        if not terms:
            return True
        haystack = str(text or "").lower()
        return any(term in haystack for term in terms)

    async def _serper_search(self, query: str, k: int) -> Dict[str, Any]:
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            return {"success": False, "message": "SERPER_API_KEY is not configured."}

        try:
            import aiohttp
        except ImportError:
            return {"success": False, "message": "aiohttp is required for Serper search."}

        payload = {"q": query, "num": k}
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
        }

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    "https://google.serper.dev/search",
                    json=payload,
                    headers=headers,
                ) as resp:
                    text = await resp.text()
                    if resp.status >= 400:
                        return {"success": False, "message": f"Serper HTTP {resp.status}: {text[:200]}"}
                    data = json.loads(text)
        except Exception as exc:
            return {"success": False, "message": f"Serper search failed: {exc}"}

        snippets = []
        for item in (data.get("organic") or [])[:k]:
            snippet = item.get("snippet")
            link = item.get("link")
            if snippet:
                snippets.append({"content": str(snippet), "source": str(link or "")})

        if not snippets:
            return {"success": False, "message": "Serper returned no usable text results."}

        return {"success": True, "output": json.dumps(snippets, ensure_ascii=False, indent=2)}

    async def _ddgs_search(self, query: str, k: int) -> Dict[str, Any]:
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS  # type: ignore
            except ImportError:
                return {
                    "success": False,
                    "message": "DuckDuckGo backend is unavailable. Install `ddgs` or `duckduckgo-search`.",
                }

        try:
            def sync_search():
                with DDGS() as ddgs:
                    try:
                        return list(ddgs.text(query=query, max_results=k))
                    except TypeError:
                        return list(ddgs.text(keywords=query, max_results=k))
            results = await asyncio.to_thread(sync_search)

        except Exception as exc:
            return {"success": False, "message": f"DDGS search failed: {str(exc)}"}

        snippets = []
        for item in (results or [])[:k]:
            body = item.get("body")
            href = item.get("href")
            if body and self._is_relevant(query, f"{body} {href or ''}"):
                snippets.append({"content": str(body), "source": str(href or "")})

        if not snippets:
            return {"success": False, "message": "DDGS no results"}

        return {"success": True, "output": json.dumps(snippets, ensure_ascii=False, indent=2)}

    async def _duckduckgo_html_search(self, query: str, k: int) -> Dict[str, Any]:
        try:
            import aiohttp
        except ImportError:
            return {"success": False, "message": "aiohttp is required for DuckDuckGo HTML fallback."}

        errors = []
        try:
            timeout = aiohttp.ClientTimeout(total=25)
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
                )
            }
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                try:
                    async with session.post(
                        "https://html.duckduckgo.com/html/",
                        data={"q": query},
                    ) as resp:
                        text = await resp.text()
                        if resp.status >= 400:
                            errors.append(f"HTTP {resp.status}: {text[:120]}")
                except Exception as exc:
                    errors.append(str(exc))
                    text = ""

                snippets = []
                blocks = re.findall(
                    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
                    r'(?:<a[^>]+class="result__snippet"[^>]*>(.*?)</a>|<div[^>]+class="result__snippet"[^>]*>(.*?)</div>)',
                    text,
                    flags=re.S,
                )
                for href, title, snippet_a, snippet_div in blocks:
                    title_text = re.sub(r"<[^>]+>", " ", title)
                    snippet_text = re.sub(r"<[^>]+>", " ", snippet_a or snippet_div or "")
                    content = html.unescape(" ".join(f"{title_text} {snippet_text}".split()))
                    link = html.unescape(href)
                    parsed = urlparse(link)
                    if parsed.path.endswith("/l/"):
                        link = unquote(parse_qs(parsed.query).get("uddg", [link])[0])
                    if content and self._is_relevant(query, content):
                        snippets.append({"content": content, "source": link})
                    if len(snippets) >= k:
                        return {"success": True, "output": json.dumps(snippets, ensure_ascii=False, indent=2)}
                if snippets:
                    return {"success": True, "output": json.dumps(snippets, ensure_ascii=False, indent=2)}
        except Exception as exc:
            errors.append(str(exc))

        return {"success": False, "message": "; ".join(errors) if errors else "DuckDuckGo HTML no results."}

    async def _wikipedia_search(self, query: str, k: int) -> Dict[str, Any]:
        try:
            import aiohttp
        except ImportError:
            return {"success": False, "message": "aiohttp is required for Wikipedia fallback."}

        endpoints = [
            ("zh", "https://zh.wikipedia.org/w/api.php"),
            ("en", "https://en.wikipedia.org/w/api.php"),
        ]
        errors = []
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                for lang, endpoint in endpoints:
                    params = {
                        "action": "opensearch",
                        "search": query,
                        "limit": k,
                        "namespace": 0,
                        "format": "json",
                    }
                    try:
                        async with session.get(endpoint, params=params) as resp:
                            text = await resp.text()
                            if resp.status >= 400:
                                errors.append(f"{lang}: HTTP {resp.status}: {text[:120]}")
                                continue
                            data = json.loads(text)
                    except Exception as exc:
                        errors.append(f"{lang}: {exc}")
                        continue
                    titles = data[1] if len(data) > 1 and isinstance(data[1], list) else []
                    descriptions = data[2] if len(data) > 2 and isinstance(data[2], list) else []
                    links = data[3] if len(data) > 3 and isinstance(data[3], list) else []
                    snippets = []
                    for idx, title in enumerate(titles[:k]):
                        desc = descriptions[idx] if idx < len(descriptions) else ""
                        link = links[idx] if idx < len(links) else ""
                        content = str(desc or title or "").strip()
                        combined = f"{title} {desc} {link}"
                        if content and self._is_relevant(query, combined):
                            snippets.append({"content": content, "source": str(link or "")})
                    if snippets:
                        return {"success": True, "output": json.dumps(snippets, ensure_ascii=False, indent=2)}
        except Exception as exc:
            errors.append(str(exc))

        return {"success": False, "message": "; ".join(errors) if errors else "Wikipedia fallback no results."}
    
