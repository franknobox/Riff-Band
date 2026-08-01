from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any


AI_REPORT_SCHEMA_VERSION = "ai4ms.ai-report.v1"
INLINE_ASSET_MARKER = re.compile(
    r"\[(paper|claim|evidence):([A-Za-z0-9_.:-]+)\]"
)


def build_ai_report_envelope(
    *,
    project_id: str,
    stage_key: str,
    content: dict[str, Any],
    prompt_id: str,
    prompt_version: str,
    model: str,
    generated_at: str | None = None,
    source_links: list[dict[str, Any]] | None = None,
    evidence_library: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the public, auditable AI-output contract used across AI4MS.

    The rationale is intentionally limited to concise research-facing logic,
    evidence references, alternatives and falsifiers. It is not a model's
    hidden token-level chain of thought.
    """

    trace = content.get("reasoning_trace")
    trace = trace if isinstance(trace, dict) else {}
    evidence_by_id = {
        str(item.get("evidence_id")): item
        for item in evidence_library or []
        if isinstance(item, dict)
        and item.get("status", "active") == "active"
        and item.get("evidence_id")
    }
    referenced = _referenced_ids(content)
    approved_links = [
        _evidence_link(project_id, evidence_by_id[evidence_id])
        for evidence_id in sorted(referenced["evidence"] & set(evidence_by_id))
    ]
    limitations = _string_list(
        content.get("limitations")
        or content.get("coverage_limits")
        or content.get("interpretation_limits")
        or trace.get("uncertainties")
    )
    summary = _summary(content, trace, stage_key)
    timestamp = generated_at or datetime.now(UTC).isoformat()
    return {
        "schema_version": AI_REPORT_SCHEMA_VERSION,
        "paradigm": "evidence_linked_management_science",
        "report_kind": "stage_research_report",
        "stage_key": stage_key,
        "title": _title(content, stage_key),
        "executive_summary": summary,
        "auditable_rationale": {
            "kind": "research_facing_logic",
            "private_chain_of_thought": False,
            "problem_framing": str(trace.get("problem_framing") or "").strip(),
            "logic_chain": [
                dict(item)
                for item in trace.get("logic_chain", [])
                if isinstance(item, dict)
            ],
            "assumptions": _string_list(trace.get("assumptions")),
            "alternatives": _string_list(trace.get("alternatives")),
            "uncertainties": _string_list(trace.get("uncertainties")),
            "human_decisions": _string_list(trace.get("human_decisions")),
            "next_verifications": _string_list(trace.get("next_verifications")),
        },
        "source_links": [
            _public_source(item)
            for item in source_links or []
            if isinstance(item, dict) and item.get("url")
        ],
        "evidence_library_links": approved_links,
        "asset_references": {
            "paper_ids": sorted(referenced["paper"]),
            "claim_ids": sorted(referenced["claim"]),
            "evidence_ids": sorted(referenced["evidence"]),
            "method_ids": sorted(referenced["method"]),
            "formula_ids": sorted(referenced["formula"]),
            "run_ids": sorted(referenced["run"]),
        },
        "limitations": limitations,
        "human_control": {
            "review_required": True,
            "editable": True,
            "approval_status": "pending",
            "prohibited_agent_actions": [
                "approve_stage",
                "promote_candidate_to_authority",
                "publish_research_output",
            ],
        },
        "provenance": {
            "project_id": project_id,
            "prompt_id": prompt_id,
            "prompt_version": prompt_version,
            "model": model,
            "generated_at": timestamp,
        },
    }


def validate_ai_report_envelope(
    envelope: Any,
    *,
    stage_key: str | None = None,
) -> None:
    if not isinstance(envelope, dict):
        raise ValueError("ai_report must be an object")
    if envelope.get("schema_version") != AI_REPORT_SCHEMA_VERSION:
        raise ValueError(
            f"ai_report.schema_version must be {AI_REPORT_SCHEMA_VERSION}"
        )
    if envelope.get("paradigm") != "evidence_linked_management_science":
        raise ValueError("ai_report.paradigm is invalid")
    if stage_key and envelope.get("stage_key") != stage_key:
        raise ValueError("ai_report.stage_key does not match the stage")
    rationale = envelope.get("auditable_rationale")
    if not isinstance(rationale, dict):
        raise ValueError("ai_report.auditable_rationale is required")
    if rationale.get("private_chain_of_thought") is not False:
        raise ValueError(
            "ai_report must expose only research-facing rationale, never private chain of thought"
        )
    human_control = envelope.get("human_control")
    if (
        not isinstance(human_control, dict)
        or human_control.get("review_required") is not True
        or human_control.get("editable") is not True
    ):
        raise ValueError("ai_report must remain human-reviewable and editable")


def _referenced_ids(content: Any) -> dict[str, set[str]]:
    found = {
        "paper": set(),
        "claim": set(),
        "evidence": set(),
        "method": set(),
        "formula": set(),
        "run": set(),
    }

    def visit(value: Any, parent_key: str = "") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                visit(item, str(key))
            return
        if isinstance(value, list):
            for item in value:
                visit(item, parent_key)
            return
        if not isinstance(value, str):
            return
        for kind, identifier in INLINE_ASSET_MARKER.findall(value):
            found[kind].add(identifier)
        normalized = parent_key.casefold()
        singular = {
            "paper_id": "paper",
            "claim_id": "claim",
            "evidence_id": "evidence",
            "method_id": "method",
            "formula_id": "formula",
            "run_id": "run",
        }
        plural = {
            "paper_ids": "paper",
            "citation_paper_ids": "paper",
            "reference_paper_ids": "paper",
            "claim_ids": "claim",
            "evidence_ids": "evidence",
            "citation_evidence_ids": "evidence",
            "reference_evidence_ids": "evidence",
            "method_ids": "method",
            "formula_ids": "formula",
            "run_ids": "run",
        }
        kind = singular.get(normalized) or plural.get(normalized)
        if kind and value.strip():
            found[kind].add(value.strip())

    visit(content)
    return found


def _title(content: dict[str, Any], stage_key: str) -> str:
    for key in ("title", "topic_summary", "research_question", "research_object"):
        value = str(content.get(key) or "").strip()
        if value:
            return value[:240]
    return f"AI4MS {stage_key} 阶段研究报告"


def _summary(
    content: dict[str, Any],
    trace: dict[str, Any],
    stage_key: str,
) -> str:
    for key in (
        "executive_summary",
        "abstract",
        "interpretation",
        "readiness_summary",
        "reproducibility_report",
        "contribution_boundary",
        "problem_boundary",
    ):
        value = str(content.get(key) or "").strip()
        if value:
            return value[:3000]
    framing = str(trace.get("problem_framing") or "").strip()
    return framing[:3000] or f"{stage_key} 阶段结构化草稿，等待研究者审核。"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        text
        for item in value
        if (text := str(item or "").strip())
    ]


def _public_source(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in (
            "citation_id",
            "title",
            "url",
            "provider",
            "source_type",
            "retrieved_at",
            "paper_id",
        )
        if item.get(key) not in (None, "")
    }


def _evidence_link(project_id: str, item: dict[str, Any]) -> dict[str, Any]:
    evidence_id = str(item.get("evidence_id") or "")
    return {
        "evidence_id": evidence_id,
        "title": str(item.get("title") or ""),
        "evidence_type": str(item.get("evidence_type") or ""),
        "paper_id": str(item.get("paper_id") or ""),
        "status": str(item.get("status") or ""),
        "revision": int(item.get("revision") or 1),
        "api_url": (
            f"/api/v1/projects/{project_id}/evidence-library/{evidence_id}"
        ),
    }
