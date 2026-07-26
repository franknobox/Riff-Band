from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from pydantic import Field

from base.agent.base_action import BaseAction


class WriteScratchpadNoteTool(BaseAction):
    name: str = "write_scratchpad_note"
    description: str = "追加或替换一条共享 scratchpad 笔记，用于多智能体交接。"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "note_title": {"type": "string"},
                "content": {"type": "string"},
                "replace": {"type": "boolean", "default": False},
            },
            "required": ["note_title", "content"],
            "additionalProperties": False,
        }
    )
    scratchpad_path: Path = Field(default=Path("scratchpad/shared.md"), exclude=True)


    async def __call__(self, note_title: str, content: str, replace: bool = False) -> Dict[str, Any]:
        self.scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
        header = f"## {str(note_title).strip()}"
        body = str(content).strip()
        timestamp = datetime.now(timezone.utc).isoformat()
        block = f"{header}\n\n_Last updated: {timestamp}_\n\n{body}\n"

        existing = (
            self.scratchpad_path.read_text(encoding="utf-8").strip()
            if self.scratchpad_path.exists()
            else "# Shared Scratchpad\n"
        )

        if replace and header in existing:
            before, _, rest = existing.partition(header)
            next_idx = rest.find("\n## ", len(header))
            remainder = rest[next_idx:] if next_idx >= 0 else ""
            updated = f"{before.rstrip()}\n\n{block.rstrip()}\n{remainder}"
        else:
            updated = f"{existing.rstrip()}\n\n{block.rstrip()}\n"

        self.scratchpad_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
        return {
            "success": True,
            "output": f"Scratchpad note '{note_title}' written to {self.scratchpad_path}.",
        }


class ReadScratchpadTool(BaseAction):
    name: str = "read_scratchpad"
    description: str = "读取共享 scratchpad，或读取指定标题的笔记章节。"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "note_title": {"type": "string"},
            },
            "additionalProperties": False,
        }
    )
    scratchpad_path: Path = Field(default=Path("scratchpad/shared.md"), exclude=True)


    async def __call__(self, note_title: str = "") -> Dict[str, Any]:
        if not self.scratchpad_path.exists():
            return {"success": False, "message": f"Scratchpad not found: {self.scratchpad_path}"}

        text = self.scratchpad_path.read_text(encoding="utf-8").strip()
        target = str(note_title).strip()
        if not target:
            return {"success": True, "output": text}

        header = f"## {target}"
        if header not in text:
            return {"success": False, "message": f"Scratchpad note not found: {target}"}

        _, _, rest = text.partition(header)
        next_idx = rest.find("\n## ", len(header))
        snippet = f"{header}{rest[:next_idx] if next_idx >= 0 else rest}".strip()
        return {"success": True, "output": snippet}
