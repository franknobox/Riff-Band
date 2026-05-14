from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from pydantic import Field

from base.agent.base_action import BaseAction


class WriteReportSectionTool(BaseAction):
    name: str = "write_report_section"
    description: str = "写入或替换一个 markdown 报告章节。"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "section_title": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["section_title", "content"],
        }
    )
    report_path: Path = Field(default=Path("report.md"), exclude=True)
    report_title: str = Field(default="Task Analysis Report", exclude=True)

    class Config:
        arbitrary_types_allowed = True

    @staticmethod
    def _build_default_report_header(title: str) -> str:
        safe_title = str(title or "Task Analysis Report").strip() or "Task Analysis Report"
        return f"# {safe_title}\n"

    @staticmethod
    def _strip_duplicate_section_heading(section_title: str, content: str) -> str:
        text = str(content or "").strip()
        title = str(section_title or "").strip().lstrip("#").strip()
        if not title or not text:
            return text
        lines = text.splitlines()
        if lines and lines[0].strip().lstrip("#").strip() == title:
            return "\n".join(lines[1:]).strip()
        return text

    async def __call__(self, section_title: str, content: str) -> Dict[str, Any]:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        clean_title = str(section_title or "").strip().lstrip("#").strip()
        if not clean_title:
            return {"success": False, "message": "section_title must not be empty"}
        header = f"## {clean_title}"
        normalized_content = self._strip_duplicate_section_heading(clean_title, content)
        existing = (
            self.report_path.read_text(encoding="utf-8")
            if self.report_path.exists()
            else self._build_default_report_header(self.report_title)
        )
        if header in existing:
            before, _, rest = existing.partition(header)
            next_idx = rest.find("\n## ", len(header))
            remainder = rest[next_idx:] if next_idx >= 0 else ""
            updated = f"{before}{header}\n\n{normalized_content}\n{remainder}"
        else:
            updated = f"{existing.rstrip()}\n\n{header}\n\n{normalized_content}\n"
        self.report_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
        return {"success": True, "output": f"Updated section '{clean_title}'."}
