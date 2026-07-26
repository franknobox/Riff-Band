from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict, Set

from pydantic import Field

from base.agent.base_action import BaseAction


class RecordFindingTool(BaseAction):
    name: str = "record_finding"
    description: str = "向 findings.jsonl 追加一条结构化发现。"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "entity": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "city": {"type": "string"},
                "industry": {"type": "string"},
                "finding": {"type": "string"},
                "evidence": {"type": "string"},
                "source_url": {"type": "string"},
                "source_title": {"type": "string"},
                "published_at": {"type": "string"},
                "quote": {"type": "string"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "dedup_key": {"type": "string"},
            },
            "required": ["finding"],
        }
    )
    findings_path: Path = Field(default=Path("findings.jsonl"), exclude=True)


    def _load_existing_dedup_keys(self) -> Set[str]:
        if not self.findings_path.exists():
            return set()

        keys: Set[str] = set()
        with self.findings_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = str(data.get("dedup_key") or "").strip()
                if key:
                    keys.add(key)
        return keys

    async def __call__(
        self,
        finding: str,
        topic: str = "",
        entity: str = "",
        tags: list[str] | None = None,
        city: str = "",
        industry: str = "",
        evidence: str = "",
        source_url: str = "",
        source_title: str = "",
        published_at: str = "",
        quote: str = "",
        confidence: str = "medium",
        dedup_key: str = "",
    ) -> Dict[str, Any]:
        confidence = str(confidence or "medium").lower().strip()
        if confidence not in {"high", "medium", "low"}:
            return {"success": False, "message": "confidence must be one of high|medium|low"}

        key = dedup_key.strip() if isinstance(dedup_key, str) else ""
        if not key:
            raw = (
                f"{topic.strip()}|{entity.strip()}|{city.strip()}|{industry.strip()}|"
                f"{finding.strip()}|{source_url.strip()}|{published_at.strip()}"
            )
            key = sha1(raw.encode("utf-8")).hexdigest()[:16]

        self.findings_path.parent.mkdir(parents=True, exist_ok=True)
        existing_keys = self._load_existing_dedup_keys()
        if key in existing_keys:
            return {"success": True, "output": f"Skipped duplicate finding with dedup_key={key}"}

        record = {
            "topic": topic,
            "entity": entity,
            "tags": [str(item) for item in (tags or [])],
            "city": city,
            "industry": industry,
            "finding": finding,
            "evidence": evidence,
            "source_url": source_url,
            "source_title": source_title,
            "published_at": published_at,
            "quote": quote,
            "confidence": confidence,
            "dedup_key": key,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        with self.findings_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        scope = topic or entity or city or industry or "generic_scope"
        return {"success": True, "output": f"Recorded finding for {scope} ({key})"}


class ReadFindingsTool(BaseAction):
    name: str = "read_findings"
    description: str = "Read structured records from the runtime findings.jsonl artifact."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional keyword filter."},
                "limit": {"type": "integer", "default": 20},
            },
            "additionalProperties": False,
        }
    )
    findings_path: Path = Field(default=Path("findings.jsonl"), exclude=True)


    async def __call__(self, query: str = "", limit: int = 20) -> Dict[str, Any]:
        if not self.findings_path.exists():
            return {"success": False, "message": f"Findings file not found: {self.findings_path}"}

        q = str(query or "").strip().lower()
        max_rows = max(1, int(limit or 20))
        rows: list[Dict[str, Any]] = []
        malformed = 0

        for line in self.findings_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(row, dict):
                continue
            if q and q not in json.dumps(row, ensure_ascii=False).lower():
                continue
            rows.append(row)
            if len(rows) >= max_rows:
                break

        return {
            "success": True,
            "output": json.dumps(
                {
                    "path": str(self.findings_path),
                    "count": len(rows),
                    "malformed_skipped": malformed,
                    "findings": rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
        }
