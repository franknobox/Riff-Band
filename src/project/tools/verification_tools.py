from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from pydantic import Field

from base.agent.base_action import BaseAction


class VerifyArtifactsTool(BaseAction):
    name: str = "verify_artifacts"
    description: str = "最终完成前检查报告、findings 和 scratchpad 的完整性。"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "report_path": {"type": "string"},
                "findings_path": {"type": "string"},
                "scratchpad_path": {"type": "string"},
                "required_sections": {"type": "array", "items": {"type": "string"}},
                "min_findings": {"type": "integer"},
            },
            "additionalProperties": False,
        }
    )
    default_report_path: Path = Field(default=Path("report.md"), exclude=True)
    default_findings_path: Path = Field(default=Path("findings.jsonl"), exclude=True)
    default_scratchpad_path: Path = Field(default=Path("scratchpad/shared.md"), exclude=True)
    section_aliases: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "Executive Summary": ["执行摘要", "摘要"],
            "City Comparison": ["城市比较", "城市比较（深圳/广州/香港/东莞/佛山）"],
            "Policy Drivers and Constraints": ["政策驱动与约束", "政策驱动和约束", "政策驱动"],
            "Key Findings": ["关键发现", "主要发现"],
            "Actionable Recommendations": ["行动建议", "可执行建议", "建议"],
        },
        exclude=True,
    )


    @staticmethod
    def _read_findings(path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict):
                    rows.append(data)
        return rows

    @staticmethod
    def _extract_source_urls(findings_rows: List[Dict[str, Any]]) -> List[str]:
        urls: List[str] = []
        seen: set[str] = set()
        for row in findings_rows:
            candidates = [
                str(row.get("source_url", "") or ""),
                str(row.get("source", "") or ""),
                str(row.get("evidence", "") or ""),
            ]
            for value in candidates:
                for url in re.findall(r"https?://[^\s\]\)\"'，。；,;]+", value):
                    cleaned = url.rstrip(".。")
                    if cleaned and cleaned not in seen:
                        seen.add(cleaned)
                        urls.append(cleaned)
        return urls

    @classmethod
    def _ensure_report_sources(cls, report_file: Path, findings_rows: List[Dict[str, Any]]) -> int:
        if not report_file.exists():
            return 0
        report_text = report_file.read_text(encoding="utf-8")
        if "http://" in report_text or "https://" in report_text:
            return 0
        urls = cls._extract_source_urls(findings_rows)
        if not urls:
            return 0
        section = ["## 参考来源", ""]
        section.extend(f"- {url}" for url in urls[:20])
        updated = report_text.rstrip() + "\n\n" + "\n".join(section) + "\n"
        report_file.write_text(updated, encoding="utf-8")
        return min(len(urls), 20)

    def _resolve_path(self, raw_path: str, default_path: Path) -> Path:
        candidate = Path(raw_path.strip()) if raw_path.strip() else default_path
        if candidate.exists():
            return candidate
        if raw_path.strip() and default_path.exists():
            return default_path
        return candidate

    def _has_required_section(self, report_text: str, title: str) -> bool:
        candidates = [title, *self.section_aliases.get(str(title), [])]
        return any(f"## {candidate}" in report_text for candidate in candidates if str(candidate).strip())

    async def __call__(
        self,
        report_path: str = "",
        findings_path: str = "",
        scratchpad_path: str = "",
        required_sections: List[str] | None = None,
        min_findings: int = 0,
    ) -> Dict[str, Any]:
        report_file = self._resolve_path(report_path, self.default_report_path)
        findings_file = self._resolve_path(findings_path, self.default_findings_path)
        scratchpad_file = self._resolve_path(scratchpad_path, self.default_scratchpad_path)
        findings_rows = self._read_findings(findings_file)
        added_sources = self._ensure_report_sources(report_file, findings_rows)

        issues: List[str] = []
        stats: Dict[str, Any] = {
            "report_exists": report_file.exists(),
            "findings_exists": findings_file.exists(),
            "scratchpad_exists": scratchpad_file.exists(),
            "report_path": str(report_file),
            "findings_path": str(findings_file),
            "scratchpad_path": str(scratchpad_file),
            "sources_appended": added_sources,
        }

        report_text = report_file.read_text(encoding="utf-8").strip() if report_file.exists() else ""
        if not report_text:
            issues.append("报告不存在或为空")
        else:
            stats["report_sections"] = [
                line[3:].strip() for line in report_text.splitlines() if line.strip().startswith("## ")
            ]
            required = [str(item).strip() for item in (required_sections or []) if str(item).strip()]
            missing = [title for title in required if not self._has_required_section(report_text, title)]
            if missing:
                issues.append(f"缺少报告章节: {missing}")
            if "http://" not in report_text and "https://" not in report_text:
                issues.append("报告缺少明确来源链接")

        stats["findings_count"] = len(findings_rows)
        if int(min_findings or 0) > 0 and len(findings_rows) < int(min_findings):
            issues.append(f"findings 数量为 {len(findings_rows)}，小于最小要求 {int(min_findings)}")

        if findings_rows:
            evidence_coverage = sum(
                1
                for row in findings_rows
                if str(row.get("source_url", "")).strip() or str(row.get("evidence", "")).strip()
            )
            stats["findings_with_evidence"] = evidence_coverage
            if evidence_coverage < max(1, int(len(findings_rows) * 0.8)):
                issues.append("少于 80% 的 findings 包含 source_url 或 evidence")
        else:
            issues.append("没有记录 findings")

        scratchpad_text = scratchpad_file.read_text(encoding="utf-8").strip() if scratchpad_file.exists() else ""
        stats["scratchpad_chars"] = len(scratchpad_text)
        if not scratchpad_text:
            issues.append("scratchpad 不存在或为空")

        passed = not issues
        summary = json.dumps(
            {
                "verification_passed": passed,
                "issues": issues,
                "stats": stats,
            },
            ensure_ascii=False,
            indent=2,
        )
        return {
            "success": True,
            "output": summary,
            "verification_passed": passed,
            "issues": issues,
            "stats": stats,
        }
