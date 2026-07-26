from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from core.interfaces import StepRecord


def format_trace(trace: List[StepRecord], max_output_len: int = 240) -> str:
    """Create a readable trace summary for delegated runs."""
    if not trace:
        return "No steps executed."

    lines = []
    for idx, step in enumerate(trace, 1):
        action_name = step.action.get("action", "unknown")
        params = step.action.get("params", {})
        observation = step.observation if isinstance(step.observation, dict) else {"value": step.observation}
        output = str(observation.get("output", observation))
        if len(output) > max_output_len:
            output = output[:max_output_len] + f"...[+{len(output) - max_output_len} chars]"
        lines.append(f"Step {idx}: {action_name} {params}")
        lines.append(f"  output: {output}")
    return "\n".join(lines)


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _clip(value: Any, limit: int = 240) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + f"...[+{len(text) - limit} chars]"


def _count_sources(output: Any) -> int:
    if not output:
        return 0
    try:
        parsed = json.loads(str(output))
    except Exception:
        return 0
    if isinstance(parsed, list):
        return sum(1 for item in parsed if isinstance(item, dict) and item.get("source"))
    return 0


def _parse_json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _strict_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "passed"}:
            return True
        if normalized in {"false", "0", "no", "failed"}:
            return False
    return None


def _verification_passed_from_text(value: Any) -> bool | None:
    text = str(value or "")
    match = re.search(r'"verification_passed"\s*:\s*(true|false)', text, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"'verification_passed'\s*:\s*(True|False)", text)
    if not match:
        return None
    return match.group(1).lower() == "true"


def _action_result_observation(step: StepRecord) -> Dict[str, Any]:
    info = _as_dict(step.info)
    result = _as_dict(info.get("last_action_result"))
    if result:
        return result
    return _as_dict(step.observation)


def summarize_trace_for_decision(trace: List[StepRecord]) -> str:
    """Summarize a worker trace for MainAgent decisions without raw outputs."""
    if not trace:
        return json.dumps({"steps": 0, "tools": {}, "failures": [], "searches": []}, ensure_ascii=False)

    tools: Dict[str, Dict[str, int]] = {}
    failures: List[Dict[str, str]] = []
    searches: List[Dict[str, Any]] = []
    finish_result: Dict[str, Any] = {}
    latest_verification: Dict[str, Any] = {}
    last_action = ""

    for idx, step in enumerate(trace, 1):
        action = _as_dict(step.action)
        params = _as_dict(action.get("params"))
        action_name = str(action.get("action", "unknown") or "unknown")
        observation = _action_result_observation(step)
        success = bool(observation.get("success", True))
        error = str(observation.get("error", "") or "")
        output = observation.get("output", "")
        last_action = action_name

        bucket = tools.setdefault(action_name, {"count": 0, "success": 0, "failed": 0})
        bucket["count"] += 1
        if success:
            bucket["success"] += 1
        else:
            bucket["failed"] += 1

        if action_name == "web_search":
            searches.append({
                "step": idx,
                "query": _clip(params.get("query", ""), 160),
                "success": success,
                "source_count": _count_sources(output),
                "error": _clip(error, 220) if error else "",
            })

        if action_name == "verify_artifacts":
            verification_passed = _strict_bool(observation.get("verification_passed"))
            verify_issues = observation.get("issues")
            if verification_passed is None:
                parsed_output = _parse_json_object(output)
                if parsed_output:
                    verification_passed = _strict_bool(parsed_output.get("verification_passed"))
                    verify_issues = parsed_output.get("issues", verify_issues)
            if verification_passed is None:
                verification_passed = _verification_passed_from_text(output)
            latest_verification = {"step": idx}
            if verification_passed is not None:
                latest_verification["verification_passed"] = verification_passed
            if verify_issues is not None:
                latest_verification["issues"] = [
                    _clip(item, 220)
                    for item in list(verify_issues or [])[:8]
                ]

        if not success or error:
            failures.append({
                "step": str(idx),
                "action": action_name,
                "error": _clip(error or observation.get("message", ""), 260),
            })

        info = _as_dict(step.info)
        if info.get("finished"):
            finish_result = _as_dict(info.get("finish_result"))

    digest = {
        "steps": len(trace),
        "last_action": last_action,
        "tools": tools,
        "searches": searches[-8:],
        "failures": failures[-8:],
        "finish": {
            "status": finish_result.get("status", ""),
            "message": _clip(finish_result.get("message", ""), 300),
            "completed_count": len(finish_result.get("completed", []) or []),
            "issues": [_clip(item, 220) for item in list(finish_result.get("issues", []) or [])[:6]],
        },
        "latest_verification": latest_verification,
    }
    return json.dumps(digest, ensure_ascii=False, indent=2)
