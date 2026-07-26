from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from pydantic import Field

from base.agent.base_action import BaseAction
from project.tools.common import read_source_text, safe_resolve, tokenize


class ListSourcesTool(BaseAction):
    name: str = "list_sources"
    description: str = "列出所有本地资料文件。"
    parameters: Dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}, "required": []})
    sources_dir: Path = Field(default=Path("."), exclude=True)


    async def __call__(self) -> Dict[str, Any]:
        files = sorted(
            str(path.relative_to(self.sources_dir)) for path in self.sources_dir.rglob("*") if path.is_file()
        )
        return {"success": True, "output": json.dumps(files, ensure_ascii=False, indent=2)}


# 搜索文件内容
class SearchSourcesTool(BaseAction):
    name: str = "search_sources"
    description: str = "按文件名和内容重合度搜索本地资料文件。"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
            "additionalProperties": False,
        }
    )
    sources_dir: Path = Field(default=Path("."), exclude=True)


    async def __call__(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        q = (query or "").strip()
        if not q:
            return {"success": False, "message": "问题不能为空"}

        query_tokens = tokenize(q)
        if not query_tokens:
            return {"success": False, "message": "查询内容没有可搜索的关键词。"}

        candidates: List[Dict[str, Any]] = []
        for path in self.sources_dir.rglob("*"):
            if not path.is_file():
                continue

            rel = str(path.relative_to(self.sources_dir))
            file_tokens = tokenize(rel)
            overlap_file = len(query_tokens & file_tokens)
            try:
                text = read_source_text(path)
                
                content_tokens = tokenize(text[:20000])
                overlap_content = len(query_tokens & content_tokens)
                preview = text[:400].replace("\n", " ").strip()
            except Exception:
                overlap_content = 0
                preview = ""

            score = overlap_content * 2 + overlap_file * 3
            if score <= 0:
                continue

            candidates.append(
                {
                    "path": rel,
                    "score": score,
                    "file_type": path.suffix.lower().lstrip("."),
                    "overlap_content": overlap_content,
                    "overlap_file": overlap_file,
                    "preview": preview,
                }
            )

        if not candidates:
            return {"success": True, "output": json.dumps([], ensure_ascii=False)}

        candidates.sort(key=lambda x: (x["score"], x["overlap_file"], x["overlap_content"]), reverse=True)
        top = candidates[: max(1, int(top_k))]
        return {"success": True, "output": json.dumps(top, ensure_ascii=False, indent=2)}


class ReadSourceTool(BaseAction):
    name: str = "read_source"
    description: str = "读取一个本地资料文件。"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }
    )
    sources_dir: Path = Field(default=Path("."), exclude=True)


    async def __call__(self, path: str) -> Dict[str, Any]:
        target, error = safe_resolve(self.sources_dir, path)
        if error:
            return {"success": False, "message": error}

        try:
            text = read_source_text(target)
        except Exception as exc:
            return {"success": False, "message": str(exc)}
        return {"success": True, "output": text}


class ReadSourcesTool(BaseAction):
    name: str = "read_sources"
    description: str = "一次读取多个本地资料文件。"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "paths": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["paths"],
            "additionalProperties": False,
        }
    )
    sources_dir: Path = Field(default=Path("."), exclude=True)


    async def __call__(self, paths: List[str]) -> Dict[str, Any]:
        if not isinstance(paths, list) or not paths:
            return {"success": False, "message": "paths must be a non-empty array of file paths"}

        results: List[Dict[str, Any]] = []
        for rel in paths:
            rel = str(rel)
            target, error = safe_resolve(self.sources_dir, rel)
            if error:
                results.append({"path": rel, "success": False, "error": error})
                continue
            try:
                content = read_source_text(target)
                results.append(
                    {
                        "path": rel,
                        "success": True,
                        "file_type": target.suffix.lower().lstrip("."),
                        "content": content,
                    }
                )
            except Exception as exc:
                results.append({"path": rel, "success": False, "error": str(exc)})

        return {"success": True, "output": json.dumps(results, ensure_ascii=False, indent=2)}
