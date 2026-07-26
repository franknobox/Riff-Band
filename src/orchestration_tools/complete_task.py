from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, ClassVar, Dict, List

from pydantic import Field

from base.agent.base_action import BaseAction


class CompleteTaskTool(BaseAction):
    """Finalize the orchestration with optional artifact-specific quality checks."""

    name: str = "complete_task"
    description: str = "验证交付物并说明剩余问题后，结束整体任务。"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "executive_summary": {"type": "string", "description": "简短最终总结"},
                "status": {"type": "string", "description": "done | partial | blocked"},
                "report_path": {"type": "string", "description": "生成报告路径"},
                "confidence": {"type": "string", "description": "high | medium | low"},
                "artifacts": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Delivered artifacts such as files, reports, data, or notes",
                },
                "verification": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "完成前执行过的检查",
                },
                "open_issues": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "partial 或 blocked 状态下的已知剩余问题",
                },
                "findings_path": {"type": "string", "description": "可选 findings jsonl 路径"},
                "required_sections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required markdown section titles",
                },
                "min_findings": {"type": "integer", "description": "Minimum finding records required"},
                "orchestration": {
                    "type": "object",
                    "description": "Coordinator runtime state used for orchestration-level quality checks",
                },
            },
            "required": ["executive_summary", "confidence"],
            "additionalProperties": False,
        }
    )

    RESEARCH_PROFILES: ClassVar[set[str]] = {
        "general_research",
        "policy_research",
        "company_research",
        "supply_chain",
        "financial_metrics",
        "news_signals",
    }
    SECTION_ALIASES: ClassVar[Dict[str, List[str]]] = {
        "Executive Summary": ["执行摘要", "摘要"],
        "City Comparison": ["城市比较", "城市比较（深圳/广州/香港/东莞/佛山）"],
        "Policy Drivers and Constraints": ["政策驱动与约束", "政策驱动和约束", "政策驱动"],
        "Key Findings": ["关键发现", "主要发现"],
        "Actionable Recommendations": ["行动建议", "可执行建议", "建议"],
    }

    @staticmethod
    def _count_headings(text: str) -> int:
        return sum(1 for line in text.splitlines() if line.strip().startswith("## "))

    @classmethod
    def _has_required_section(cls, report_text: str, title: str) -> bool:
        candidates = [title, *cls.SECTION_ALIASES.get(str(title), [])]
        return any(f"## {candidate}" in report_text for candidate in candidates if str(candidate).strip())

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
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    rows.append(item)
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
        text = report_file.read_text(encoding="utf-8")
        if "http://" in text or "https://" in text:
            return 0
        urls = cls._extract_source_urls(findings_rows)
        if not urls:
            return 0
        section = ["## 参考来源", ""]
        section.extend(f"- {url}" for url in urls[:20])
        report_file.write_text(text.rstrip() + "\n\n" + "\n".join(section) + "\n", encoding="utf-8")
        return min(len(urls), 20)

    @staticmethod
    def _is_done_entry(entry: Dict[str, Any]) -> bool:
        status = str(entry.get("status", "") or "").strip().lower()
        worker_state = str(entry.get("worker_state", "") or "").strip().lower()
        profile = str(entry.get("profile", "") or "").strip()
        if profile == "verification" and entry.get("latest_verification_passed") is not True:
            return False
        if profile in {"report_drafting", "verification"} and entry.get("latest_verification_passed") is False:
            return False
        return status == "done" and worker_state != "running"

    @staticmethod
    def _task_fingerprint(entry: Dict[str, Any]) -> str:
        instruction = str(entry.get("instruction", "") or "")
        text = instruction.lower()
        text = re.sub(r"session_id\s*[:=]\s*\S+", " ", text)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text)
        profile = str(entry.get("profile", "") or "").strip().lower()
        return f"{profile}:{text}"

    @classmethod
    def _orchestration_issues(cls, orchestration: Dict[str, Any], status: str) -> List[str]:
        if not orchestration or status != "done":
            return []

        entries = [
            item for item in orchestration.get("task_entries", []) or []
            if isinstance(item, dict) and not bool(item.get("superseded", False))
        ]
        if not entries:
            return []

        issues: List[str] = []
        require_flow = bool(orchestration.get("require_flow_integrity", True))
        require_verification = bool(orchestration.get("require_verification_passed", True))
        check_duplicates = bool(orchestration.get("check_duplicate_delegation", True))

        if require_flow:
            running = [
                str(item.get("session_id") or item.get("instruction") or "")[:120]
                for item in entries
                if str(item.get("worker_state", "") or "").strip().lower() == "running"
            ]
            if running:
                issues.append(f"orchestration has running subtasks: {running[:5]}")

            incomplete = [
                str(item.get("instruction", "") or "")[:120]
                for item in entries
                if not cls._is_done_entry(item)
            ]
            if incomplete:
                issues.append(f"orchestration has unfinished subtasks: {incomplete[:5]}")

            research_entries = [
                item for item in entries
                if str(item.get("profile", "") or "general_research") in cls.RESEARCH_PROFILES
            ]
            write_entries = [
                item for item in entries
                if str(item.get("profile", "") or "") == "report_drafting"
            ]
            verification_entries = [
                item for item in entries
                if str(item.get("profile", "") or "") == "verification"
            ]
            if not research_entries:
                issues.append("orchestration missing research phase subtask")
            if not write_entries:
                issues.append("orchestration missing synthesis/write phase subtask")
            if not verification_entries:
                issues.append("orchestration missing verification phase subtask")

        if require_verification:
            verification_entries = [
                item for item in entries
                if str(item.get("profile", "") or "") == "verification"
            ]
            passed_verifications = [
                item for item in verification_entries
                if (
                    cls._is_done_entry(item)
                    and item.get("latest_verification_passed") is True
                    and not list(item.get("issues", []) or [])
                )
            ]
            if not passed_verifications:
                issues.append("verification has not passed")

        if check_duplicates:
            seen: Dict[str, List[str]] = {}
            for item in entries:
                key = cls._task_fingerprint(item)
                if not key or key.endswith(":"):
                    continue
                session_id = str(item.get("session_id", "") or "").strip()
                label = session_id or str(item.get("instruction", "") or "")[:80]
                seen.setdefault(key, [])
                if label and label not in seen[key]:
                    seen[key].append(label)
            duplicates = [labels for labels in seen.values() if len(labels) > 1]
            if duplicates:
                issues.append(f"duplicate delegated subtasks detected: {duplicates[:5]}")

        return issues

    async def __call__(
        self,
        executive_summary: str,
        confidence: str,
        status: str = "done",
        report_path: str = "",
        artifacts: List[Dict[str, Any]] | None = None,
        verification: List[str] | None = None,
        open_issues: List[str] | None = None,
        findings_path: str = "",
        required_sections: List[str] | None = None,
        min_findings: int = 5,
        orchestration: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        issues: List[str] = []
        artifacts = list(artifacts or [])
        verification = [str(item).strip() for item in (verification or []) if str(item).strip()]
        open_issues = [str(item).strip() for item in (open_issues or []) if str(item).strip()]
        status = str(status or "done").lower().strip()
        if status not in {"done", "partial", "blocked"}:
            issues.append("status must be one of done|partial|blocked")
        confidence = str(confidence).lower().strip()
        if confidence not in {"high", "medium", "low"}:
            issues.append("confidence must be one of high|medium|low")

        orchestration_data = dict(orchestration or {})
        if bool(orchestration_data.get("research_step_mode", False)):
            if not executive_summary.strip():
                issues.append("executive_summary cannot be empty")
            if status == "done" and open_issues:
                issues.append("status is done but open_issues is not empty")
            passed = not issues and status == "done"
            return {
                "success": passed,
                "done": passed,
                "status": status,
                "executive_summary": executive_summary,
                "report_path": report_path,
                "confidence": confidence,
                "artifacts": artifacts,
                "verification": verification,
                "open_issues": open_issues,
                "findings_path": findings_path,
                "findings_count": 0,
                "quality_gate_passed": passed,
                "issues": issues,
                "orchestration": orchestration_data,
                "step_gate_deferred": True,
            }

        findings_rows: List[Dict[str, Any]] = []
        path_for_findings = findings_path.strip()
        if path_for_findings:
            findings_file = Path(path_for_findings)
            findings_rows = self._read_findings(findings_file)

        text = ""
        if report_path:
            report_file = Path(report_path)
            if not report_file.exists():
                issues.append(f"report file not found: {report_path}")
            else:
                self._ensure_report_sources(report_file, findings_rows)
                text = report_file.read_text(encoding="utf-8").strip()
                if not text:
                    issues.append("report file is empty")
                if self._count_headings(text) < 3:
                    issues.append("report contains fewer than 3 level-2 sections")
                if "http://" not in text and "https://" not in text:
                    issues.append("report does not contain explicit source links")

        required = [item.strip() for item in (required_sections or []) if str(item).strip()]
        if required and report_path and text:
            missing = [title for title in required if not self._has_required_section(text, title)]
            if missing:
                issues.append(f"missing required sections: {missing}")

        if not executive_summary.strip():
            issues.append("executive_summary cannot be empty")

        if path_for_findings:
            if len(findings_rows) < int(min_findings):
                issues.append(f"findings count is {len(findings_rows)} < min_findings {int(min_findings)}")

            evidence_coverage = 0
            for row in findings_rows:
                has_source = bool(str(row.get("source_url", "")).strip()) or bool(str(row.get("evidence", "")).strip())
                if has_source:
                    evidence_coverage += 1
            if findings_rows and evidence_coverage < max(1, int(len(findings_rows) * 0.8)):
                issues.append("less than 80% findings include source_url or evidence")

        if status == "done" and open_issues:
            issues.append("status is done but open_issues is not empty")

        issues.extend(self._orchestration_issues(dict(orchestration or {}), status))

        passed = not issues and status == "done"
        return {
            "success": passed,
            "done": passed,
            "status": status,
            "executive_summary": executive_summary,
            "report_path": report_path,
            "confidence": confidence,
            "artifacts": artifacts,
            "verification": verification,
            "open_issues": open_issues,
            "findings_path": findings_path,
            "findings_count": len(findings_rows),
            "quality_gate_passed": passed,
            "issues": issues,
            "orchestration": dict(orchestration or {}),
        }
