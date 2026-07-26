from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable


def parse_json_response(resp: str) -> Dict[str, Any]:
    """Parse JSON that may be wrapped in markdown fences."""
    if not resp:
        raise ValueError("Empty response")

    text = resp.strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]

    return json.loads(text)


def indent_text(text: str, prefix: str = "  ") -> str:
    """Indent multi-line text for prompt formatting."""
    return "\n".join(f"{prefix}{line}" for line in text.strip().splitlines())


def format_tool_descriptions(tools: Iterable[Any]) -> str:
    """Render available tools into a readable block."""
    items = list(tools)
    if not items:
        return "无可用工具。"

    parts = []
    for tool in items:
        params = getattr(tool, "parameters", None) or {}
        parts.append(
            f"{tool.name}: {tool.description}\nParameters: {json.dumps(params, ensure_ascii=False, indent=2)}"
        )
    return "\n\n".join(parts)


def format_tools_description(tools: Iterable[Any]) -> str:
    """Backward-compatible alias for older imports."""
    return format_tool_descriptions(tools)
