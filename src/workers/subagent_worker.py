from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from agents.sub_agent import SubAgent
from base.engine.async_llm import LLMsConfig, create_llm_instance
from core.runner import AgentRunner
from core.trace import summarize_trace_for_decision
from project.build_project import _build_runtime_components, _resolve_profile
from project.prompts import GenericSubPromptBuilder


def _format_trace(trace) -> str:
    return summarize_trace_for_decision(trace)


def _resolve_prompt_builder(profile_name: str, requested: str = ""):
    name = str(requested or "").strip()
    if name == "ResearchSubPromptBuilder" or str(profile_name or "").strip() == "research_mode":
        try:
            from research.prompts import ResearchSubPromptBuilder

            return ResearchSubPromptBuilder
        except Exception:
            return GenericSubPromptBuilder
    return GenericSubPromptBuilder


async def _run_worker(request: Dict[str, Any]) -> Dict[str, Any]:
    model = str(request.get("model", "")).strip()
    output_dir = Path(str(request.get("output_dir", "workspace/output")))
    sources_dir = Path(str(request.get("sources_dir", "workspace/sources")))
    max_steps = int(request.get("max_subagent_steps", 10) or 10)

    profile = _resolve_profile(
        profile_name=str(request.get("profile_name", "generic") or "generic"),
        report_filename=str(request.get("report_filename", "task_report.md") or "task_report.md"),
        required_sections=list(request.get("required_sections") or []),
        min_findings=int(request.get("min_findings", 0) or 0),
    )
    env, _tools = _build_runtime_components(
        sub_models=[model] if model else [],
        brief_text=str(request.get("original_question", "")),
        sources_dir=sources_dir,
        output_dir=output_dir,
        max_subagent_steps=max_steps,
        profile=profile,
    )
    if hasattr(env, "meta_data") and isinstance(env.meta_data, dict):
        env.meta_data["task_label"] = str(request.get("task_label", "") or "")
        env.meta_data["worker_session_id"] = str(request.get("session_id", "") or "")
        env.meta_data["parallel_task_index"] = int(request.get("parallel_task_index", 0) or 0)

    llm = create_llm_instance(LLMsConfig.default().get(model))
    prompt_builder = _resolve_prompt_builder(
        profile_name=str(request.get("profile_name", "generic") or "generic"),
        requested=str(request.get("sub_prompt_builder", "") or ""),
    )
    agent = SubAgent(
        llm=llm,
        task_instruction=str(request.get("task_instruction", "")),
        context=str(request.get("context", "")),
        original_question=str(request.get("original_question", "")),
        allowed_tools=list(request.get("allowed_tools") or []),
        task_label=str(request.get("task_label", "")),
        prompt_builder=prompt_builder,
    )
    result = await AgentRunner().run(agent, env)
    finish_result = {}
    if result.trace:
        last_info = result.trace[-1].info
        finish_result = last_info.get("finish_result", {}) if last_info.get("finished") else {}

    return {
        "model": model,
        "steps_taken": result.steps,
        "done": result.done,
        "cost": result.cost,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "finish_result": finish_result,
        "trace_summary": _format_trace(result.trace),
        "session_id": str(request.get("session_id", "")),
        "worker_reused": False,
        "worker_state": "closed",
        "allowed_tools": list(request.get("allowed_tools") or []),
    }


def main() -> int:
    if len(sys.argv) != 3:
        sys.stderr.write("Usage: subagent_worker.py <request.json> <result.json>\n")
        return 2

    request_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        result = asyncio.run(_run_worker(request))
    except Exception as exc:
        result = {
            "done": False,
            "steps_taken": 0,
            "cost": 0.0,
            "finish_result": {
                "status": "blocked",
                "message": f"Sub-agent worker failed: {exc}",
                "completed": [],
                "issues": [repr(exc)],
                "result": "",
            },
            "trace_summary": "",
        }
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
