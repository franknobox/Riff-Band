from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import Field

from base.agent.base_agent import BaseAgent
from base.engine.logs import LogLevel, logger
from core.interfaces import TaskContext
from core.utils import indent_text, parse_json_response
from orchestration_tools.taskplan import TaskPlanExecutor


class MainAgent(BaseAgent):
    """Main coordinator agent that decides delegation and completion."""

    name: str = Field(default="MainAgent")
    description: str = Field(default="Coordinates delegated tasks and decides task completion")
    sub_models: List[str] = Field(default_factory=list)
    tools: List[Any] = Field(default_factory=list)
    subagent_tools: List[Any] = Field(default_factory=list)
    prompt_builder: Any = Field(default=None)
    max_attempts: int = Field(default=6)
    instruction: str = Field(default="")
    meta: Dict[str, Any] = Field(default_factory=dict)
    attempt: int = Field(default=0)
    context: str = Field(default="")
    history: List[Dict[str, Any]] = Field(default_factory=list)
    task_entries: List[Dict[str, Any]] = Field(default_factory=list)
    task_plan_executor: TaskPlanExecutor = Field(default_factory=TaskPlanExecutor)
    latest_plan_task_ids: List[str] = Field(default_factory=list)
    next_sub_model_index: int = Field(default=0)
    RESEARCH_PROFILES: ClassVar[set[str]] = {
        "general_research",
        "policy_research",
        "company_research",
        "supply_chain",
        "financial_metrics",
        "news_signals",
    }

    class Config:
        arbitrary_types_allowed = True

    def reset(self, task_context: TaskContext) -> None:
        self.instruction = task_context.instruction
        self.meta = task_context.meta_data or {}
        self.attempt = 0
        self.context = ""
        self.history = []
        self.task_entries = []
        self.task_plan_executor.reset()
        self.latest_plan_task_ids = []
        self.next_sub_model_index = 0

    def soft_reset(self, instruction: str) -> None:
        """Reset per-turn state while preserving accumulated task entries
        and task plan state across conversation turns."""
        self.instruction = instruction
        self.attempt = 0
        self.context = ""
        self.history = []
        self.latest_plan_task_ids = []

    def get_usage_cost(self) -> float:
        return self.llm.get_usage_summary().get("total_cost", 0.0)

    # ── state persistence ────────────────────────────────────────

    def dump_state(self) -> Dict[str, Any]:
        """Serialize runtime state for session persistence."""
        return {
            "instruction": self.instruction,
            "meta": dict(self.meta),
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "context": self.context,
            "history": list(self.history),
            "task_entries": list(self.task_entries),
            "task_plan_executor": self.task_plan_executor.dump(),
            "next_sub_model_index": self.next_sub_model_index,
        }

    def load_state(self, data: Dict[str, Any]) -> None:
        """Restore runtime state from a previously dumped payload."""
        self.instruction = str(data.get("instruction", ""))
        self.meta = dict(data.get("meta", {}) or {})
        self.attempt = int(data.get("attempt", 0))
        self.max_attempts = int(data.get("max_attempts", self.max_attempts))
        self.context = str(data.get("context", ""))
        self.history = list(data.get("history", []) or [])
        self.task_entries = list(data.get("task_entries", []) or [])
        plan_data = data.get("task_plan_executor")
        if isinstance(plan_data, dict):
            self.task_plan_executor.restore(plan_data)
        self.latest_plan_task_ids = []
        self.next_sub_model_index = int(data.get("next_sub_model_index", 0) or 0)

    def _infer_profile(self, task_instruction: str) -> str:
        text = (task_instruction or "").lower()
        if any(item in text for item in ["policy", "regulation", "government"]):
            return "policy_research"
        if any(item in text for item in ["company", "competitor", "firm"]):
            return "company_research"
        if any(item in text for item in ["supply chain", "value chain", "upstream", "downstream"]):
            return "supply_chain"
        if any(item in text for item in ["finance", "financial", "valuation", "revenue"]):
            return "financial_metrics"
        if any(item in text for item in ["news", "sentiment", "public opinion"]):
            return "news_signals"
        if any(item in text for item in ["任务类型: verify", "任务类型：verify", "verify", "verification", "quality gate", "qa", "validate", "check"]):
            return "verification"
        if any(item in text for item in ["任务类型: write", "任务类型：write", "report", "summary", "write section", "draft"]):
            return "report_drafting"
        return "general_research"

    def _current_phase(self) -> str:
        if self._is_research_step_mode():
            return "research_step"
        if not self._phase_entries_done(self.RESEARCH_PROFILES):
            return "research"
        if not self._phase_entries_done({"report_drafting"}):
            return "synthesis"
        if not self._phase_entries_done({"verification"}):
            return "verification"
        return "verification"

    def _effective_task_entries(self) -> List[Dict[str, Any]]:
        return [item for item in self.task_entries if not bool(item.get("superseded", False))]

    def _phase_entries_done(self, profiles: set[str]) -> bool:
        entries = [
            item for item in self._effective_task_entries()
            if str(item.get("profile", "general_research") or "general_research") in profiles
        ]
        return bool(entries) and all(self._is_done_result(item) for item in entries)

    def _is_done_result(self, entry: Dict[str, Any]) -> bool:
        if bool(entry.get("superseded", False)):
            return True
        status = str(entry.get("status", "") or "").strip().lower()
        worker_state = str(entry.get("worker_state", "") or "").strip().lower()
        profile = str(entry.get("profile", "") or "").strip()
        if profile == "verification" and entry.get("latest_verification_passed") is not True:
            return False
        if profile in {"report_drafting", "verification"} and entry.get("latest_verification_passed") is False:
            return False
        return status == "done" and worker_state != "running"

    @staticmethod
    def _latest_verification_from_trace(trace_summary: Any) -> Dict[str, Any]:
        if isinstance(trace_summary, dict):
            digest = trace_summary
        else:
            try:
                digest = json.loads(str(trace_summary or "{}"))
            except json.JSONDecodeError:
                return {}
        latest = digest.get("latest_verification", {}) if isinstance(digest, dict) else {}
        if not isinstance(latest, dict) or not latest:
            return {}
        if "verification_passed" not in latest:
            return {}
        return {
            "passed": bool(latest.get("verification_passed", False)),
            "issues": [str(item) for item in list(latest.get("issues", []) or [])],
            "step": latest.get("step", ""),
        }

    @staticmethod
    def _format_trace_summary(trace_summary: Any) -> str:
        if isinstance(trace_summary, dict):
            digest = trace_summary
        else:
            try:
                digest = json.loads(str(trace_summary or "{}"))
            except json.JSONDecodeError:
                text = str(trace_summary or "").strip()
                return text[:400] + ("..." if len(text) > 400 else "")
        if not isinstance(digest, dict) or not digest:
            return ""

        lines = [
            f"steps={digest.get('steps', 0)}",
            f"last_action={digest.get('last_action', '')}",
        ]

        tool_parts: List[str] = []
        tools = digest.get("tools", {})
        if isinstance(tools, dict):
            for name, stats in tools.items():
                if not isinstance(stats, dict):
                    continue
                count = stats.get("count", 0)
                failed = stats.get("failed", 0)
                if failed:
                    tool_parts.append(f"{name} x{count} failed={failed}")
                else:
                    tool_parts.append(f"{name} x{count}")
        if tool_parts:
            lines.append(f"tools={', '.join(tool_parts[:8])}")

        failures = digest.get("failures", [])
        if failures:
            failure_texts = []
            for failure in list(failures or [])[:3]:
                if isinstance(failure, dict):
                    action = failure.get("action", "")
                    error = failure.get("error", "")
                    failure_texts.append(f"{action}: {error}")
                else:
                    failure_texts.append(str(failure))
            lines.append(f"failures={failure_texts}")
        else:
            lines.append("failures=none")

        finish = digest.get("finish", {})
        if isinstance(finish, dict) and finish:
            lines.append(
                "finish="
                f"status={finish.get('status', '')}, "
                f"issues={list(finish.get('issues', []) or [])[:3]}"
            )

        latest_verification = digest.get("latest_verification", {})
        if isinstance(latest_verification, dict) and "verification_passed" in latest_verification:
            lines.append(
                "latest_verification="
                f"passed={latest_verification.get('verification_passed')}, "
                f"issues={list(latest_verification.get('issues', []) or [])[:3]}"
            )

        return "\n".join(lines)

    def _task_fingerprint(self, instruction: str, profile: str) -> str:
        text = str(instruction or "").lower()
        text = re.sub(r"session_id\s*[:=]\s*\S+", " ", text)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text)
        return f"{str(profile or '').strip().lower()}:{text}"

    def _task_entries_for_profile(self, profiles: set[str]) -> List[Dict[str, Any]]:
        return [
            item for item in self._effective_task_entries()
            if str(item.get("profile", "") or "general_research") in profiles
        ]

    def _is_research_step_mode(self) -> bool:
        return (
            str(self.meta.get("profile_name", "") or "").strip() == "research_mode"
            and str(self.meta.get("research_completion_scope", "") or "").strip() == "current_step_only"
        )

    def _has_running_entries(self) -> bool:
        return any(
            str(item.get("worker_state", "") or "").strip().lower() == "running"
            for item in self._effective_task_entries()
        )

    @staticmethod
    def _jsonl_count(path_value: Any) -> int:
        path_text = str(path_value or "").strip()
        if not path_text:
            return 0
        path = Path(path_text)
        if not path.exists():
            return 0
        count = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                count += 1
        return count

    @staticmethod
    def _read_text_path(path_value: Any) -> str:
        path_text = str(path_value or "").strip()
        if not path_text:
            return ""
        path = Path(path_text)
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def _report_has_current_step_section(self) -> bool:
        section = str(self.meta.get("current_step_expected_section", "") or "").strip()
        if not section:
            return False
        report_text = self._read_text_path(self.meta.get("report_path", ""))
        return f"## {section}" in report_text

    def _research_artifact_stats(self) -> Dict[str, int]:
        findings_count = self._jsonl_count(self.meta.get("findings_path", ""))
        papers_count = self._jsonl_count(self.meta.get("papers_path", ""))
        claims_count = self._jsonl_count(self.meta.get("claims_path", ""))
        outline_chars = len(self._read_text_path(self.meta.get("outline_path", "")))
        min_findings = int(self.meta.get("min_findings", 0) or 0)
        return {
            "findings_count": findings_count,
            "papers_count": papers_count,
            "claims_count": claims_count,
            "outline_chars": outline_chars,
            "min_findings": min_findings,
            "findings_remaining": max(0, min_findings - findings_count),
        }

    def _should_complete_claim_generation_from_artifacts(self, forced_final_decision: bool = False) -> bool:
        if forced_final_decision or not self._is_research_step_mode():
            return False
        if str(self.meta.get("research_step_key", "") or "").strip() != "claim_generation":
            return False
        if self._has_running_entries():
            return False
        stats = self._research_artifact_stats()
        return stats["claims_count"] >= 4 and self._report_has_current_step_section()

    def _should_complete_outline_build_from_artifacts(self, forced_final_decision: bool = False) -> bool:
        if forced_final_decision or not self._is_research_step_mode():
            return False
        if str(self.meta.get("research_step_key", "") or "").strip() != "outline_build":
            return False
        if self._has_running_entries():
            return False
        stats = self._research_artifact_stats()
        return stats["outline_chars"] >= 200 and self._report_has_current_step_section()

    def _next_required_intent(self) -> str:
        if self._is_research_step_mode():
            if self._has_running_entries():
                return "wait_current_step"
            if not self._effective_task_entries():
                return "execute_current_step"
            return "complete_current_step"
        if not self._phase_entries_done(self.RESEARCH_PROFILES):
            return "finish_research"
        if not self._phase_entries_done({"report_drafting"}):
            return "draft_report"
        if not self._phase_entries_done({"verification"}):
            return "delegate_verification"
        return "complete"

    def _allowed_actions_for_phase(self, forced_final_decision: bool = False) -> List[str]:
        if forced_final_decision:
            return ["complete_task"]
        intent = self._next_required_intent()
        inspect_actions = ["wait_worker_sessions", "inspect_worker_session", "list_worker_sessions", "close_worker_session"]
        if self._is_research_step_mode():
            if intent == "wait_current_step":
                return ["wait_worker_sessions", *inspect_actions, "complete_task"]
            if intent == "execute_current_step":
                return ["delegate_task", "delegate_tasks", *inspect_actions]
            return ["complete_task", "delegate_task", "delegate_tasks", "continue_task", *inspect_actions]
        if intent == "finish_research":
            return ["delegate_task", "delegate_tasks", "continue_task", *inspect_actions]
        if intent == "draft_report":
            return ["delegate_task", *inspect_actions]
        if intent == "delegate_verification":
            return ["delegate_task", "continue_task", *inspect_actions]
        return ["complete_task", "inspect_worker_session", "list_worker_sessions"]

    def _phase_intent_guidance(self, forced_final_decision: bool = False) -> str:
        if forced_final_decision:
            return "强制最终决策轮：只能调用 complete_task，并由质量门决定 done/partial/blocked。"
        intent = self._next_required_intent()
        if self._is_research_step_mode():
            if intent == "wait_current_step":
                return "当前 Research step 有运行中的子任务：优先等待或检查会话；不要进入报告型综合/验证阶段。"
            if intent == "execute_current_step":
                return "当前 Research step 尚未执行：只委派当前 step 内的 research/write/review 子任务，不规划后续 step。"
            return "当前 Research step 已有执行结果：若 expected_section 和本步产物已满足，直接 complete_task；不足时只补当前 step。"
        if intent == "finish_research":
            return (
                "下一步必须完成研究阶段：只能启动、继续、检查或等待 research 子任务；"
                "不要启动 write/verify，也不要调用 complete_task。"
            )
        if intent == "draft_report":
            return (
                "下一步必须撰写主报告：启动或继续 write/report_drafting 子任务写入主 report_path；"
                "不要启动 verification，也不要调用 complete_task。"
            )
        if intent == "delegate_verification":
            return (
                "下一步必须委派验证子任务：输出 action=delegate_task 或 continue_task，"
                "让 verification SubAgent 调用 verify_artifacts 并返回 verification_passed=true；"
                "不要输出 action=verify_artifacts，也不要调用 complete_task。"
            )
        return "验证已通过：现在可以调用 complete_task。"

    def _phase_guidance(self) -> str:
        phase = self._current_phase()
        if self._is_research_step_mode():
            return (
                "Research Mode 当前 step：外层 ResearchPipeline 负责全局步骤推进；"
                "MainAgent 只协调本 step 的委派、等待和完成判断，不执行报告型 synthesis/verification 阶段机。"
            )
        if phase == "research":
            return (
                "阶段 1 / 研究：收集证据、记录 findings、写入共享 scratchpad 笔记。"
                "必须等待所有 research 子任务 status=done；partial、failed、blocked 或 running 都不能进入综合阶段。"
            )
        if phase == "synthesis":
            return (
                "阶段 2 / 综合：把 findings 和 scratchpad 笔记整合为产物或报告章节。"
                "必须启动新的 write 类型 delegate_task 写入主 report_path；"
                "必须等待所有 write 子任务 status=done 后才能进入验证阶段。"
            )
        return (
            "阶段 3 / 验证：围绕报告、findings 和 scratchpad 执行验证任务；"
            "必须等待所有 verification 子任务 status=done，调用 complete_task 前必须修复关键问题。"
        )

    def _format_subtask_history(self) -> str:
        def clip(value: Any, limit: int) -> str:
            text = str(value or "")
            if len(text) <= limit:
                return text
            return text[:limit] + f"... [truncated {len(text) - limit} chars]"

        if not self.task_entries:
            return "尚未委派子任务。"

        if str(self.meta.get("research_step_key", "") or "").strip() == "outline_build":
            effective = self._effective_task_entries()
            compact = [
                "outline_build 阶段禁用完整子任务历史注入；只保留状态计数，避免把完整 tool output、trace 或 synthesis_digest 带入 prompt。",
                f"delegated_subtasks={len(self.task_entries)}",
                f"done_count={sum(1 for item in effective if item['status'] == 'done')}",
            ]
            recent = self.task_entries[-3:]
            for entry in recent:
                compact.append(
                    (
                        f"- status={entry.get('status', '')} "
                        f"steps={entry.get('steps_taken', 0)} "
                        f"tools={list(entry.get('tools', []) or [])[:6]} "
                        f"message={clip(entry.get('message', ''), 180)}"
                    )
                )
            return "\n".join(compact)

        lines: List[str] = []
        completed_items: List[str] = []
        issues: List[str] = []
        for entry in self.task_entries[-12:]:
            block = [
                (
                    f"[Attempt {entry['attempt']}] status={entry['status']} "
                    f"model={entry.get('model', 'unknown')} steps={entry.get('steps_taken', 0)}"
                ),
                f"task_instruction={clip(entry.get('instruction', ''), 500)}",
                f"profile={entry.get('profile', 'general_research')}",
            ]
            if entry.get("session_id"):
                block.append(f"session_id={entry['session_id']} rounds={entry.get('session_rounds', 1)}")
                block.append(
                    f"subagent_reused={entry.get('worker_reused', False)} "
                    f"subagent_state={entry.get('worker_state', '')}"
                )
            if entry.get("superseded"):
                block.append(f"superseded_by={entry.get('superseded_by', '')}")
            if entry.get("message"):
                block.append(f"message={clip(entry['message'], 400)}")
            if entry.get("completed"):
                completed = list(entry["completed"] or [])[:8]
                block.append(f"completed={completed}")
                completed_items.extend(completed)
            if entry.get("issues"):
                entry_issues = [clip(item, 300) for item in list(entry["issues"] or [])[:6]]
                block.append(f"issues={entry_issues}")
                issues.extend(entry_issues)
            if entry.get("latest_verification_passed") is not None:
                block.append(f"latest_verification_passed={entry.get('latest_verification_passed')}")
                latest_issues = [
                    clip(item, 300)
                    for item in list(entry.get("latest_verification_issues", []) or [])[:6]
                ]
                if latest_issues:
                    block.append(f"latest_verification_issues={latest_issues}")
                    issues.extend(latest_issues)
            if entry.get("result"):
                block.append(f"result={clip(entry['result'], 1200)}")
            if entry.get("trace_summary"):
                trace_summary = self._format_trace_summary(entry.get("trace_summary"))
                if trace_summary:
                    block.append("trace_summary:")
                    block.append(indent_text(clip(trace_summary, 800), "  "))
            lines.append("\n".join(block))

        summary = [
            f"delegated_subtasks={len(self.task_entries)}",
            f"done_count={sum(1 for item in self._effective_task_entries() if item['status'] == 'done')}",
        ]
        if completed_items:
            summary.append(f"all_completed={completed_items[:20]}")
        if issues:
            summary.append(f"all_issues={issues[:20]}")
        lines.append("\n".join(summary))

        return clip("\n\n".join(lines), 24000)

    def _next_sub_model(self) -> str:
        if not self.sub_models:
            return ""
        index = self.next_sub_model_index % len(self.sub_models)
        model = self.sub_models[index]
        self.next_sub_model_index = (index + 1) % len(self.sub_models)
        return model

    def _model_for_existing_session(self, session_id: str) -> str:
        session_id = str(session_id or "").strip()
        if not session_id:
            return ""
        for entry in reversed(self.task_entries):
            if str(entry.get("session_id", "") or "").strip() == session_id:
                model = str(entry.get("model", "") or "").strip()
                if model in self.sub_models:
                    return model
        return ""

    def _should_start_literature_parallel_search(self, forced_final_decision: bool = False) -> bool:
        if forced_final_decision or not self._is_research_step_mode():
            return False
        if str(self.meta.get("research_step_key", "") or "").strip() != "literature_search":
            return False
        if self._next_required_intent() != "execute_current_step":
            return False
        return not self._effective_task_entries()

    def _should_start_paper_enrichment(self, forced_final_decision: bool = False) -> bool:
        if forced_final_decision or not self._is_research_step_mode():
            return False
        if str(self.meta.get("research_step_key", "") or "").strip() != "paper_enrichment":
            return False
        if self._next_required_intent() != "execute_current_step":
            return False
        return not self._effective_task_entries()

    def _should_start_knowledge_synthesis(self, forced_final_decision: bool = False) -> bool:
        if forced_final_decision or not self._is_research_step_mode():
            return False
        if str(self.meta.get("research_step_key", "") or "").strip() != "knowledge_synthesis":
            return False
        if self._next_required_intent() != "execute_current_step":
            return False
        return not self._effective_task_entries()

    def _should_start_claim_generation(self, forced_final_decision: bool = False) -> bool:
        if forced_final_decision or not self._is_research_step_mode():
            return False
        if str(self.meta.get("research_step_key", "") or "").strip() != "claim_generation":
            return False
        if self._next_required_intent() != "execute_current_step":
            return False
        return not self._effective_task_entries()

    def _should_start_claim_debate(self, forced_final_decision: bool = False) -> bool:
        if forced_final_decision or not self._is_research_step_mode():
            return False
        if str(self.meta.get("research_step_key", "") or "").strip() != "claim_debate":
            return False
        if self._next_required_intent() != "execute_current_step":
            return False
        return not self._effective_task_entries()

    def _should_start_outline_build(self, forced_final_decision: bool = False) -> bool:
        if forced_final_decision or not self._is_research_step_mode():
            return False
        if str(self.meta.get("research_step_key", "") or "").strip() != "outline_build":
            return False
        if self._next_required_intent() != "execute_current_step":
            return False
        return not self._effective_task_entries()

    def _extract_research_topic(self) -> str:
        text = str(self.instruction or "")
        for pattern in [
            r"\[研究主题\]\s*(.+?)(?:\n\[|\Z)",
            r"\[鐮旂┒涓婚\]\s*(.+?)(?:\n\[|\Z)",
        ]:
            match = re.search(pattern, text, flags=re.S)
            if match:
                topic = re.sub(r"\s+", " ", match.group(1)).strip()
                if topic:
                    return topic
        return re.sub(r"\s+", " ", text).strip()[:160]

    def _read_research_scratchpad(self) -> str:
        path_text = str(self.meta.get("scratchpad_path", "") or "").strip()
        if not path_text:
            return ""
        path = Path(path_text)
        if not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    @staticmethod
    def _clean_search_term(value: str) -> str:
        text = re.sub(r"^[\s\-*+\d.、]+", "", str(value or "")).strip()
        text = re.sub(r"^(中文关键词|英文关键词|关键词|检索式|查询|query|search terms?)[:：]\s*", "", text, flags=re.I)
        text = text.strip(" `\"'“”[]()")
        return re.sub(r"\s+", " ", text).strip()

    def _add_search_term(self, terms: List[str], seen: set[str], value: str, limit: int) -> bool:
        term = self._clean_search_term(value)
        if not term or len(term) < 2:
            return False
        if term.lower() in {"赋能", "empowerment", "应用", "applications"}:
            return False
        key = term.lower()
        if key in seen:
            return False
        seen.add(key)
        terms.append(term)
        return len(terms) >= limit

    def _extract_search_terms_from_scratchpad(self, limit: int = 32) -> List[str]:
        text = self._read_research_scratchpad()
        if not text.strip():
            return []
        terms: List[str] = []
        seen: set[str] = set()
        keyword_markers = (
            "关键词",
            "检索词",
            "检索式",
            "查询",
            "search",
            "keyword",
            "query",
        )
        active_search_block = False
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                active_search_block = False
                continue
            if line.startswith("#"):
                active_search_block = False
                continue
            lower = line.lower()
            is_marker_line = any(marker in lower for marker in keyword_markers)
            if re.match(r"^(检索式|查询|search queries?|queries?)[:：]\s*$", line, flags=re.I):
                active_search_block = True
                continue

            if active_search_block and re.match(r"^[-*+\d.、]\s+", line):
                if self._add_search_term(terms, seen, line, limit):
                    return terms
                continue

            active_search_block = active_search_block and re.match(r"^[-*+\d.、]\s+", line) is not None
            if not is_marker_line:
                continue

            candidates = re.split(r"[,，;；]|(?:\s+\|\s+)", line)
            for candidate in candidates:
                if self._add_search_term(terms, seen, candidate, limit):
                    return terms
        return terms

    def _academic_queries_from_terms(self, terms: List[str], limit: int = 12) -> List[str]:
        raw_terms = [str(term).strip() for term in terms if str(term).strip()]
        joined = " ".join(raw_terms)
        lower = joined.lower()
        queries: List[str] = []
        seen: set[str] = set()

        def add(query: str) -> None:
            text = re.sub(r"\s+", " ", str(query or "")).strip()
            if not text:
                return
            key = text.lower()
            if key in seen:
                return
            seen.add(key)
            queries.append(text)

        for term in raw_terms:
            term_lower = term.lower()
            if any(token in term_lower for token in ["intelligent reflecting surface", "reconfigurable intelligent surface", "integrated sensing", "isac", "ris"]):
                add(term)

        mentions_ris = any(token in joined for token in ["智能反射面", "智能反射表面", "可重构智能表面"]) or any(
            token in lower for token in ["ris", "intelligent reflecting surface", "reconfigurable intelligent surface"]
        )
        mentions_isac = any(token in joined for token in ["通信感知一体化", "通感一体化", "感知通信一体化"]) or any(
            token in lower for token in ["isac", "integrated sensing and communication"]
        )
        if mentions_ris and mentions_isac:
            add('"reconfigurable intelligent surface" "integrated sensing and communication"')
            add('"intelligent reflecting surface" "integrated sensing and communication"')
            add('"RIS" "ISAC"')
            add('"RIS-assisted" "integrated sensing and communication"')
            add('"reconfigurable intelligent surface" "ISAC" beamforming')
            add('"intelligent reflecting surface" "joint sensing and communication"')
            add('"reconfigurable intelligent surface" survey "integrated sensing and communication"')
        elif mentions_ris:
            add('"reconfigurable intelligent surface" wireless communication')
            add('"intelligent reflecting surface" survey')
        elif mentions_isac:
            add('"integrated sensing and communication" survey')
            add('"ISAC" beamforming')

        for term in raw_terms:
            if len(queries) >= limit:
                break
            if re.search(r"[A-Za-z]", term) and len(term.split()) >= 3:
                add(term)
        return queries[:limit]

    def _literature_search_task_params(self) -> Dict[str, Any]:
        topic = self._extract_research_topic()
        min_papers = int(self.meta.get("step_min_papers", 0) or self.meta.get("target_papers_for_literature_review", 30) or 30)
        min_findings = int(self.meta.get("min_findings", 0) or 0)
        plan_terms = self._extract_search_terms_from_scratchpad()
        queries = self._academic_queries_from_terms(plan_terms)
        if not queries:
            queries = [
                f"{topic}",
                '"reconfigurable intelligent surface" "integrated sensing and communication"',
                '"RIS" "ISAC"',
                '"reconfigurable intelligent surface" "ISAC" beamforming',
                '"intelligent reflecting surface" "joint sensing and communication"',
                '"reconfigurable intelligent surface" survey "integrated sensing and communication"',
            ]

        query_text = "\n".join(f"- {query}" for query in queries)
        return {
            "task_instruction": (
                "任务类型: research\n"
                f"期望产出: 基于 Step 1 的检索式和研究主题顺序检索，立即记录候选论文到 candidates.jsonl，再筛选出至少 {min_papers} 篇合格论文进入 papers.jsonl/shortlist.jsonl。\n"
                "完成标准: 先调用 batch_literature_search；该工具会按 OpenAlex -> Semantic Scholar -> arXiv -> Crossref -> DBLP 检索、写入 candidates、筛选 shortlist。Step 2 只负责检索、筛选和去重，不写跨论文 findings。\n"
                "具体任务: 使用组合后的学术 query，而不是单个宽泛关键词。同一工具失败后由 batch 工具自动切换下一检索源。"
            ),
            "context": (
                f"研究主题: {topic}\n"
                f"目标论文数: {min_papers}\n"
                f"目标 findings 数: {min_findings}（Step 2 不写 findings；Step 3 负责聚类与研究空白 findings）\n"
                f"主检索 query:\n{query_text}\n"
                "第一步必须调用 batch_literature_search，参数 queries 使用上述列表，target_papers 使用目标论文数，per_query_limit 建议 8-10，record_findings=false。"
            ),
            "tools": [
                "batch_literature_search",
                "literature_screen",
                "read_papers",
                "write_scratchpad_note",
                "write_report_section",
            ],
        }

    def _paper_enrichment_task_params(self) -> Dict[str, Any]:
        topic = self._extract_research_topic()
        target_notes = int(self.meta.get("step_min_papers", 0) or self.meta.get("target_papers_for_literature_review", 30) or 30)
        terms = self._extract_search_terms_from_scratchpad()
        return {
            "task_instruction": (
                "任务类型: research\n"
                "期望产出: 从 papers.jsonl/shortlist.jsonl 中选择前 N 篇高相关论文，基于摘要或元数据生成 paper_notes.jsonl 和 paper_cards.jsonl。"
                "本阶段只做每篇论文的结构化阅读卡片，不做最终跨论文综合。\n"
                "完成标准: 第一步必须调用 batch_paper_enrichment；随后只补充必要的 write_scratchpad_note 和 write_report_section。"
            ),
            "context": (
                f"研究主题: {topic}\n"
                f"目标 paper_notes 数: {target_notes}\n"
                "priority_terms:\n"
                + "\n".join(f"- {term}" for term in terms[:20])
                + "\n"
                "batch_paper_enrichment 会按摘要可用性、主题词匹配、RIS/ISAC 相关性和年份排序，并写入 knowledge-card 风格的 paper_cards.jsonl。"
            ),
            "tools": [
                "batch_paper_enrichment",
                "read_paper_notes",
                "read_paper_cards",
                "write_scratchpad_note",
                "write_report_section",
            ],
        }

    def _knowledge_synthesis_task_params(self) -> Dict[str, Any]:
        topic = self._extract_research_topic()
        return {
            "task_instruction": (
                "任务类型: research\n"
                "期望产出: 基于 paper_cards.jsonl 聚类文献主题、识别 research gaps，生成 synthesis_digest.json，并写入当前报告章节。\n"
                "完成标准: 第一步必须调用 batch_knowledge_synthesis；该工具会读取 paper_cards/paper_notes，生成 synthesis_digest.json，并把跨论文研究空白写入 findings.jsonl。"
            ),
            "context": (
                f"研究主题: {topic}\n"
                "本阶段不生成大纲，不写最终正文，不需要实验上下文。输出应服务于 Step 4/5 claims/debate 和 Step 6 outline。"
            ),
            "tools": [
                "batch_knowledge_synthesis",
                "read_synthesis_digest",
                "read_paper_cards",
                "read_findings",
                "write_scratchpad_note",
                "write_report_section",
            ],
        }

    def _claim_generation_task_params(self) -> Dict[str, Any]:
        topic = self._extract_research_topic()
        return {
            "task_instruction": (
                "任务类型: research\n"
                "期望产出: 4-8 个文献综述用研究空白、未来方向、局限性和综述观点，并写入 claims.jsonl。\n"
                "完成标准: 第一步必须调用 batch_claim_generation；随后写入报告章节 ## 研究空白、未来方向与可检验问题。"
            ),
            "context": (
                f"研究主题: {topic}\n"
                "优先使用 synthesis_digest.json 中的 research gaps，再结合 paper_notes.jsonl 和 findings.jsonl 中已有证据；不要调用 read_sources，不要输出 Invalid action。"
            ),
            "tools": [
                "batch_claim_generation",
                "read_synthesis_digest",
                "read_research_claims",
                "write_report_section",
                "write_scratchpad_note",
            ],
        }

    def _claim_debate_task_params(self) -> Dict[str, Any]:
        topic = self._extract_research_topic()
        return {
            "task_instruction": (
                "任务类型: research\n"
                "期望产出: 对 claims.jsonl 中的候选观点进行批量证据压力测试，生成 debate_log.md，"
                "并写入报告章节 ## 观点辩论与优先级评估。\n"
                "完成标准: 第一步必须调用 batch_claim_debate；不要逐条反复调用 record_claim_debate。"
            ),
            "context": (
                f"研究主题: {topic}\n"
                "batch_claim_debate 会读取 claims.jsonl 和 findings.jsonl，批量给出 keep/revise/downgrade/remove "
                "倾向和证据风险，并负责写入 debate_log.md 与当前 step 报告章节。"
            ),
            "tools": [
                "batch_claim_debate",
                "read_claim_debate_log",
                "read_research_claims",
                "write_report_section",
                "write_scratchpad_note",
            ],
        }

    def _outline_build_task_params(self) -> Dict[str, Any]:
        topic = self._extract_research_topic()
        digest = self.meta.get("material_digest", {}) if isinstance(self.meta.get("material_digest", {}), dict) else {}
        outline_context = digest.get("outline_context", {}) if isinstance(digest.get("outline_context", {}), dict) else {}
        context_text = json.dumps(outline_context, ensure_ascii=False, indent=2)
        if len(context_text) > 10000:
            context_text = context_text[:10000] + f"... [truncated {len(context_text) - 10000} chars]"
        return {
            "task_instruction": (
                "任务类型: write\n"
                "期望产出: 基于压缩 outline_context 生成标准文献综述论文大纲 outline.md，"
                "并写入报告章节 ## 结构化论文大纲。\n"
                "完成标准: 只使用 outline_context 中的主题簇、research gaps、claims 摘要、debate 决策和少量代表 paper cards；"
                "调用 build_research_outline 写入 outline.md，再调用 write_report_section 写入当前章节。"
            ),
            "context": (
                f"研究主题: {topic}\n"
                f"outline_context_path: {self.meta.get('outline_context_path', '')}\n"
                "禁止读取或注入完整 synthesis_digest.json、完整 paper_cards.jsonl、完整 subtask history 或完整工具输出。\n"
                "大纲必须包含：摘要、研究背景/目的与意义、研究现状、方法与主题综合、研究空白与未来方向、结论。\n"
                "outline_context:\n"
                f"{context_text}"
            ),
            "tools": [
                "build_research_outline",
                "write_report_section",
                "write_scratchpad_note",
            ],
        }

    def _apply_delegate_defaults(
        self,
        params: Dict[str, Any],
        parallel_mode: bool = False,
        assign_model: bool = True,
    ) -> Dict[str, Any]:
        fixed = dict(params or {})
        instruction = str(fixed.get("task_instruction", "")).strip()
        profile = self._infer_profile(instruction)

        default_worker_tools = list(self.meta.get("default_worker_tools", []) or [])
        if not fixed.get("tools"):
            fixed["tools"] = default_worker_tools

        if parallel_mode and fixed.get("tools"):
            forbidden = set(str(item) for item in (self.meta.get("parallel_forbidden_tools", []) or []))
            fixed["tools"] = [t for t in fixed["tools"] if str(t) not in forbidden]

        if assign_model:
            fixed["model"] = self._next_sub_model()
        if "context" not in fixed:
            fixed["context"] = ""
        fixed["worker_profile"] = profile
        return fixed

    def _apply_continue_defaults(self, params: Dict[str, Any]) -> Dict[str, Any]:
        fixed = dict(params or {})
        fixed["session_id"] = str(fixed.get("session_id", "")).strip()
        inherited_model = self._model_for_existing_session(fixed["session_id"])
        fixed = self._apply_delegate_defaults(
            fixed,
            parallel_mode=False,
            assign_model=not bool(inherited_model),
        )
        if inherited_model:
            fixed["model"] = inherited_model
        fixed["session_id"] = str(fixed.get("session_id", "")).strip()
        return fixed

    def _apply_delegate_tasks_defaults(self, params: Dict[str, Any]) -> Dict[str, Any]:
        fixed = dict(params or {})
        tasks = fixed.get("tasks") or []
        selected_tasks: List[Dict[str, Any]] = []
        for item in tasks:
            if not isinstance(item, dict):
                continue
            selected = self._apply_delegate_defaults(
                item,
                parallel_mode=True,
            )
            selected_tasks.append(selected)
        fixed["tasks"] = selected_tasks
        fixed["max_concurrency"] = int(self.meta.get("max_parallel_subtasks", 3))
        return fixed

    def _tool_params(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Remove main-agent bookkeeping fields before calling action tools."""
        delegate_keys = {"task_instruction", "context", "model", "tools", "result_schema"}
        if action_name in {"delegate_task", "continue_task"}:
            allowed = set(delegate_keys)
            if action_name == "continue_task":
                allowed.add("session_id")
            return {k: v for k, v in dict(params or {}).items() if k in allowed}
        if action_name == "delegate_tasks":
            cleaned = dict(params or {})
            task_allowed = set(delegate_keys)
            cleaned["tasks"] = [
                {k: v for k, v in dict(item).items() if k in task_allowed}
                for item in (cleaned.get("tasks") or [])
                if isinstance(item, dict)
            ]
            return {k: v for k, v in cleaned.items() if k in {"tasks", "max_concurrency"}}
        return params

    def _quality_gate_orchestration(self) -> Dict[str, Any]:
        research_step_mode = self._is_research_step_mode()
        return {
            "task_entries": list(self.task_entries),
            "current_phase": self._current_phase(),
            "require_flow_integrity": bool(self.meta.get("require_flow_integrity", not research_step_mode)),
            "require_verification_passed": bool(self.meta.get("require_verification_passed", not research_step_mode)),
            "check_duplicate_delegation": bool(self.meta.get("check_duplicate_delegation", True)),
            "research_step_mode": research_step_mode,
        }

    def _blocked_by_phase(self, action_name: str, params: Dict[str, Any], forced_final_decision: bool = False) -> str:
        if forced_final_decision:
            return ""
        if self._is_research_step_mode():
            if action_name == "complete_task" and self._has_running_entries():
                return "complete_task blocked: current Research step still has running subtasks; wait or inspect them first."
            if action_name == "complete_task":
                stats = self._research_artifact_stats()
                if stats["findings_remaining"] > 0:
                    return (
                        "complete_task blocked: current Research step has "
                        f"{stats['findings_count']} findings, below min_findings "
                        f"{stats['min_findings']}; delegate or continue current-step evidence collection first."
                    )
            return ""
        phase = self._current_phase()

        requested_profiles: List[str] = []
        if action_name == "continue_task":
            session_id = str(params.get("session_id", "") or "").strip()
            existing = next(
                (
                    item for item in self.task_entries
                    if str(item.get("session_id", "") or "").strip() == session_id
                ),
                None,
            )
            requested_profiles.append(
                str(existing.get("profile", "") or "").strip()
                if existing
                else self._infer_profile(str(params.get("task_instruction", "") or ""))
            )
        elif action_name == "delegate_task":
            requested_profiles.append(self._infer_profile(str(params.get("task_instruction", "") or "")))
        elif action_name == "delegate_tasks":
            requested_profiles.extend(
                self._infer_profile(str(item.get("task_instruction", "") or ""))
                for item in (params.get("tasks") or [])
                if isinstance(item, dict)
            )
        elif action_name == "complete_task":
            if not self._phase_entries_done(self.RESEARCH_PROFILES):
                return "complete_task blocked: research phase is not fully done; continue or retry unfinished research subtasks first."
            if not self._phase_entries_done({"report_drafting"}):
                return "complete_task blocked: synthesis/write phase is not fully done; delegate a write subtask first."
            if not self._phase_entries_done({"verification"}):
                return "complete_task blocked: verification phase is not fully done; delegate a verify subtask first."
            return ""

        if not requested_profiles:
            return ""

        if phase == "research":
            invalid = [p for p in requested_profiles if p not in self.RESEARCH_PROFILES]
            if invalid:
                return (
                    "delegation blocked: current phase is research; all research subtasks must be status=done "
                    "before starting write, verification, or completion."
                )
        elif phase == "synthesis":
            if action_name == "continue_task":
                return (
                    "continue_task blocked: synthesis phase must start a fresh write "
                    "delegate_task for the main report_path instead of continuing a research session."
                )
            invalid = [p for p in requested_profiles if p != "report_drafting"]
            if invalid:
                return "delegation blocked: current phase is synthesis; start or finish a write subtask before verification/completion."
        elif phase == "verification":
            invalid = [p for p in requested_profiles if p != "verification"]
            if invalid:
                return "delegation blocked: current phase is verification; run verification subtasks before completion."
        return ""

    def _phase_guard_result(self, requested_action: str, params: Dict[str, Any], message: str) -> Dict[str, Any]:
        return {
            "success": False,
            "phase_guard_blocked": True,
            "requested_action": requested_action,
            "message": message,
            "current_phase": self._current_phase(),
            "next_required_intent": self._next_required_intent(),
            "allowed_actions": self._allowed_actions_for_phase(),
            "phase_guidance": self._phase_guidance(),
            "params": params,
        }

    def _rewrite_delegate_to_continue_if_retry(
        self,
        action_name: str,
        params: Dict[str, Any],
    ) -> tuple[str, Dict[str, Any], str]:
        if action_name != "delegate_task":
            return action_name, params, ""
        if not bool(self.meta.get("prefer_continue_for_retry", True)):
            return action_name, params, ""

        instruction = str(params.get("task_instruction", "") or "")
        context = str(params.get("context", "") or "")
        override_text = f"{instruction}\n{context}".lower()
        if any(token in override_text for token in ["force_new_session", "new_session", "重新开始", "新开session"]):
            return action_name, params, ""

        profile = self._infer_profile(instruction)
        if profile not in self.RESEARCH_PROFILES:
            return action_name, params, ""

        fingerprint = self._task_fingerprint(instruction, profile)
        candidate: Dict[str, Any] | None = None
        for entry in reversed(self.task_entries):
            if bool(entry.get("superseded", False)):
                continue
            session_id = str(entry.get("session_id", "") or "").strip()
            if not session_id:
                continue
            if str(entry.get("worker_state", "") or "").strip().lower() == "running":
                continue
            entry_fingerprint = str(entry.get("fingerprint", "") or "").strip()
            if not entry_fingerprint:
                entry_fingerprint = self._task_fingerprint(
                    str(entry.get("instruction", "")),
                    str(entry.get("profile", "")),
                )
                entry["fingerprint"] = entry_fingerprint
            if entry_fingerprint != fingerprint:
                continue
            if self._is_done_result(entry):
                continue
            candidate = entry
            break

        if not candidate:
            return action_name, params, ""

        issues = list(candidate.get("issues", []) or [])
        prior_message = str(candidate.get("message", "") or "").strip()
        prior_result = str(candidate.get("result", "") or "").strip()
        continuation_notes = [
            "Continue the existing partial research session instead of starting a duplicate session.",
            f"Previous status: {candidate.get('status', '')}",
        ]
        if prior_message:
            continuation_notes.append(f"Previous message: {prior_message}")
        if issues:
            continuation_notes.append(f"Previous issues: {issues}")
        if prior_result:
            continuation_notes.append(f"Previous partial result: {prior_result[:1200]}")

        merged_context = context.strip()
        continuation_context = "\n".join(continuation_notes)
        if merged_context:
            merged_context = f"{merged_context}\n\n{continuation_context}"
        else:
            merged_context = continuation_context

        rewritten = dict(params)
        rewritten["session_id"] = str(candidate.get("session_id", "") or "").strip()
        rewritten["context"] = merged_context
        if not rewritten.get("model") and candidate.get("model"):
            rewritten["model"] = candidate.get("model")
        if not rewritten.get("tools") and candidate.get("tools"):
            rewritten["tools"] = candidate.get("tools")

        reason = (
            "delegate_task rewritten to continue_task because an unfinished research session "
            f"with the same fingerprint already exists: {rewritten['session_id']}"
        )
        return "continue_task", rewritten, reason

    async def step(self, observation, history, **kwargs) -> tuple[Dict[str, Any], str]:
        self.attempt += 1
        subtask_history = self._format_subtask_history()

        if self.prompt_builder is None:
            raise ValueError("MainAgent requires prompt_builder")

        prompt_meta = dict(self.meta)
        forced_final_decision = bool(kwargs.get("forced_final_decision", False))
        if self._should_complete_claim_generation_from_artifacts(forced_final_decision):
            report_path = str(self.meta.get("report_path", "") or "")
            findings_path = str(self.meta.get("findings_path", "") or "")
            required_sections = list(self.meta.get("required_sections", []) or [])
            action_name = "complete_task"
            params = {
                "executive_summary": "claim_generation artifacts already meet the step gate: claims.jsonl has enough claims and the expected report section exists.",
                "status": "done",
                "artifacts": [
                    {"type": "data", "path": str(self.meta.get("claims_path", "") or ""), "description": "Candidate literature-review claims"},
                    {"type": "report", "path": report_path, "description": "Current step report section"},
                ],
                "verification": ["claims.jsonl count >= 4", "current expected report section exists"],
                "open_issues": [],
                "confidence": "high",
                "report_path": report_path,
                "findings_path": findings_path,
                "required_sections": required_sections,
                "min_findings": int(self.meta.get("min_findings", 0) or 0),
            }
            decision = {
                "action": action_name,
                "reasoning": "claim_generation step artifacts are already sufficient, so complete the current step instead of continuing or retrying worker sessions.",
                "params": params,
            }
            response = json.dumps(decision, ensure_ascii=False)
        elif self._should_complete_outline_build_from_artifacts(forced_final_decision):
            report_path = str(self.meta.get("report_path", "") or "")
            findings_path = str(self.meta.get("findings_path", "") or "")
            required_sections = list(self.meta.get("required_sections", []) or [])
            action_name = "complete_task"
            params = {
                "executive_summary": "outline_build artifacts already meet the step gate: outline.md is populated and the expected report section exists.",
                "status": "done",
                "artifacts": [
                    {"type": "file", "path": str(self.meta.get("outline_path", "") or ""), "description": "Compact literature-review outline"},
                    {"type": "file", "path": str(self.meta.get("outline_context_path", "") or ""), "description": "Compressed outline context"},
                    {"type": "report", "path": report_path, "description": "Current step report section"},
                ],
                "verification": ["outline.md is populated", "current expected report section exists"],
                "open_issues": [],
                "confidence": "high",
                "report_path": report_path,
                "findings_path": findings_path,
                "required_sections": required_sections,
                "min_findings": int(self.meta.get("min_findings", 0) or 0),
            }
            decision = {
                "action": action_name,
                "reasoning": "outline_build step artifacts are already sufficient, so complete the current step instead of continuing or retrying worker sessions.",
                "params": params,
            }
            response = json.dumps(decision, ensure_ascii=False)
        elif self._should_start_literature_parallel_search(forced_final_decision):
            action_name = "delegate_task"
            params = self._literature_search_task_params()
            decision = {
                "action": action_name,
                "reasoning": (
                    "literature_search step uses a deterministic single search task: "
                    "use Step 1 search expressions as academic queries and batch-record papers immediately."
                ),
                "params": params,
            }
            response = json.dumps(decision, ensure_ascii=False)
        elif self._should_start_paper_enrichment(forced_final_decision):
            action_name = "delegate_task"
            params = self._paper_enrichment_task_params()
            decision = {
                "action": action_name,
                "reasoning": (
                    "paper_enrichment step uses a deterministic batch enrichment task: "
                    "rank papers and write abstract-level paper_notes immediately."
                ),
                "params": params,
            }
            response = json.dumps(decision, ensure_ascii=False)
        elif self._should_start_knowledge_synthesis(forced_final_decision):
            action_name = "delegate_task"
            params = self._knowledge_synthesis_task_params()
            decision = {
                "action": action_name,
                "reasoning": (
                    "knowledge_synthesis step uses a deterministic batch synthesis task: "
                    "cluster paper cards, write synthesis_digest, and record cross-paper gaps."
                ),
                "params": params,
            }
            response = json.dumps(decision, ensure_ascii=False)
        elif self._should_start_claim_generation(forced_final_decision):
            action_name = "delegate_task"
            params = self._claim_generation_task_params()
            decision = {
                "action": action_name,
                "reasoning": (
                    "claim_generation step uses a deterministic batch claim task: "
                    "generate review claims from paper_notes and findings, then write the step section."
                ),
                "params": params,
            }
            response = json.dumps(decision, ensure_ascii=False)
        elif self._should_start_claim_debate(forced_final_decision):
            action_name = "delegate_task"
            params = self._claim_debate_task_params()
            decision = {
                "action": action_name,
                "reasoning": (
                    "claim_debate step uses a deterministic batch debate task: "
                    "review generated claims, write debate_log, then write the step section."
                ),
                "params": params,
            }
            response = json.dumps(decision, ensure_ascii=False)
        elif self._should_start_outline_build(forced_final_decision):
            action_name = "delegate_task"
            params = self._outline_build_task_params()
            decision = {
                "action": action_name,
                "reasoning": (
                    "outline_build step uses compact outline_context only: "
                    "generate a literature-review outline without injecting full synthesis/tool history."
                ),
                "params": params,
            }
            response = json.dumps(decision, ensure_ascii=False)
        else:
            action_name = ""
            params: Dict[str, Any] = {}
            decision: Dict[str, Any] = {}
            response = ""

        prompt_meta["current_phase"] = self._current_phase()
        prompt_meta["next_required_intent"] = self._next_required_intent()
        prompt_meta["allowed_actions"] = self._allowed_actions_for_phase(forced_final_decision)
        prompt_meta["phase_intent_guidance"] = self._phase_intent_guidance(forced_final_decision)
        prompt_meta["phase_guidance"] = self._phase_guidance()
        prompt_meta["forced_final_decision"] = forced_final_decision
        if self._is_research_step_mode():
            prompt_meta.update(self._research_artifact_stats())
        if not decision:
            prompt = self.prompt_builder.build_prompt(
                instruction=self.instruction,
                meta=prompt_meta,
                prior_context=self.context,
                attempt_index=self.attempt,
                max_attempts=self.max_attempts,
                sub_models=self.sub_models,
                subtask_history=subtask_history,
                tools=self.subagent_tools,
            )
            logger.log_to_file(LogLevel.INFO, f"[MainAgent] Prompt:\n{prompt}\n")

            response = await self.llm(prompt)
            decision = parse_json_response(response)
            action_name = decision.get("action")
            params = decision.get("params", {})
        else:
            logger.log_to_file(
                LogLevel.INFO,
                f"[MainAgent] Deterministic {self.meta.get('research_step_key')} delegation selected; skipped LLM planning prompt.\n",
            )
        if forced_final_decision and action_name != "complete_task":
            report_path = str(self.meta.get("report_path", "") or "")
            findings_path = str(self.meta.get("findings_path", "") or "")
            action_name = "complete_task"
            # Let CompleteTaskTool quality gate decide the actual status
            params = {
                "executive_summary": "已进入最终决策轮，基于已收集的 SubAgent 结果进行收尾。",
                "status": "done",
                "artifacts": [
                    {"type": "report", "path": report_path, "description": "最终综合报告"}
                ],
                "verification": ["forced final decision prevented additional delegation"],
                "open_issues": [],
                "confidence": "medium",
                "report_path": report_path,
                "findings_path": findings_path,
                "required_sections": list(self.meta.get("required_sections", []) or []),
                "min_findings": int(self.meta.get("min_findings", 0) or 0),
            }
            decision = {
                "action": action_name,
                "reasoning": "forced_final_decision 禁止继续委派，已强制转为 complete_task。",
                "params": params,
            }

        if action_name == "delegate_task":
            params = self._apply_delegate_defaults(params, parallel_mode=False)
            self.latest_plan_task_ids = []
        elif action_name == "continue_task":
            params = self._apply_continue_defaults(params)
            self.latest_plan_task_ids = []
        elif action_name in {"list_worker_sessions", "inspect_worker_session", "wait_worker_sessions", "close_worker_session"}:
            self.latest_plan_task_ids = []
        elif action_name == "delegate_tasks":
            params = self._apply_delegate_tasks_defaults(params)
            self.latest_plan_task_ids = []
        else:
            self.latest_plan_task_ids = []

        # 调用__call__
        action_name, params, rewrite_reason = self._rewrite_delegate_to_continue_if_retry(action_name, params)
        if rewrite_reason:
            params = self._apply_continue_defaults(params)
            decision = dict(decision)
            decision["action"] = action_name
            decision["params"] = params
            decision["reasoning"] = (
                str(decision.get("reasoning", "") or "").strip()
                + f"\n{rewrite_reason}"
            ).strip()

        allowed_actions = self._allowed_actions_for_phase(forced_final_decision)
        if action_name not in allowed_actions:
            phase_block = (
                f"action {action_name} blocked by phase intent {self._next_required_intent()}; "
                f"allowed actions: {allowed_actions}"
            )
        else:
            phase_block = self._blocked_by_phase(action_name, params, forced_final_decision=forced_final_decision)
        if phase_block:
            result = self._phase_guard_result(action_name, params, phase_block)
            guard_params = {"requested_action": action_name, "params": params}
            self._update_context("phase_guard", guard_params, result)
            logger.log_to_file(
                LogLevel.INFO,
                f"[MainAgent] Parsed decision:\n{json.dumps(decision, ensure_ascii=False, indent=2)}\n",
            )
            return {
                "action": "phase_guard",
                "params": guard_params,
                "result": result,
                "subtask_history": subtask_history,
            }, response

        if action_name == "delegate_task":
            task_ids = self.task_plan_executor.create_or_extend([params])
            self.latest_plan_task_ids = task_ids
            if task_ids:
                self.task_plan_executor.mark_running(task_ids[0])
        elif action_name == "delegate_tasks":
            task_ids = self.task_plan_executor.create_or_extend(params.get("tasks") or [])
            self.latest_plan_task_ids = task_ids
            for task_id in task_ids:
                self.task_plan_executor.mark_running(task_id)

        if action_name == "complete_task":
            params = dict(params or {})
            params["orchestration"] = self._quality_gate_orchestration()

        tool = next((item for item in self.tools if item.name == action_name), None)
        if tool is None:
            raise ValueError(f"Unknown action from MainAgent: {action_name}")

        result = await tool(**self._tool_params(action_name, params))
        self._update_context(action_name, params, result)

        logger.log_to_file(
            LogLevel.INFO,
            f"[MainAgent] Parsed decision:\n{json.dumps(decision, ensure_ascii=False, indent=2)}\n",
        )
        return {
            "action": action_name,
            "params": params,
            "result": result,
            "subtask_history": subtask_history,
        }, response

    def _append_task_entry(self, base_params: Dict[str, Any], task_result: Dict[str, Any]) -> None:
        finish_result = task_result.get("finish_result", {})
        worker_state = str(task_result.get("worker_state", "") or "").strip().lower()
        status = str(finish_result.get("status", "") or "").strip().lower()
        if not status:
            status = worker_state or "partial"
        entry = {
            "attempt": self.attempt,
            "status": status,
            "instruction": base_params.get("task_instruction", ""),
            "model": base_params.get("model", "unknown"),
            "profile": self._infer_profile(str(base_params.get("task_instruction", ""))),
            "tools": base_params.get("tools", []),
            "steps_taken": task_result.get("steps_taken", 0),
            "message": finish_result.get("message", ""),
            "completed": finish_result.get("completed", []),
            "issues": finish_result.get("issues", []),
            "result": finish_result.get("result", ""),
            "trace_summary": task_result.get("trace_summary", ""),
            "session_id": task_result.get("session_id", ""),
            "session_rounds": task_result.get("session_rounds", 1),
            "worker_reused": task_result.get("worker_reused", False),
            "worker_state": worker_state,
        }
        latest_verification = self._latest_verification_from_trace(entry.get("trace_summary", ""))
        if latest_verification:
            entry["latest_verification_passed"] = latest_verification["passed"]
            entry["latest_verification_issues"] = latest_verification["issues"]
            entry["latest_verification_step"] = latest_verification["step"]
            if (
                entry["profile"] in {"report_drafting", "verification"}
                and not latest_verification["passed"]
                and latest_verification["issues"]
            ):
                existing_issues = [str(item) for item in list(entry.get("issues", []) or [])]
                for issue in latest_verification["issues"]:
                    if issue not in existing_issues:
                        existing_issues.append(issue)
                entry["issues"] = existing_issues
        entry["fingerprint"] = self._task_fingerprint(str(entry.get("instruction", "")), str(entry.get("profile", "")))
        session_id = str(entry.get("session_id", "") or "").strip()
        if session_id:
            for idx, existing in enumerate(self.task_entries):
                if str(existing.get("session_id", "") or "").strip() == session_id:
                    merged = dict(existing)
                    merged.update({key: value for key, value in entry.items() if value not in ("", [], {})})
                    merged["status"] = status
                    merged["worker_state"] = worker_state
                    merged["fingerprint"] = merged.get("fingerprint") or entry["fingerprint"]
                    self.task_entries[idx] = merged
                    self._mark_superseded_retries(merged)
                    return
        self.task_entries.append(entry)
        self._mark_superseded_retries(entry)

    def _mark_superseded_retries(self, new_entry: Dict[str, Any]) -> None:
        if not self._is_done_result(new_entry):
            return
        fingerprint = str(new_entry.get("fingerprint", "") or "").strip()
        session_id = str(new_entry.get("session_id", "") or "").strip()
        if not fingerprint:
            return
        for existing in self.task_entries:
            if existing is new_entry:
                continue
            if str(existing.get("session_id", "") or "").strip() == session_id:
                continue
            existing_fingerprint = str(existing.get("fingerprint", "") or "").strip()
            if not existing_fingerprint:
                existing_fingerprint = self._task_fingerprint(
                    str(existing.get("instruction", "")),
                    str(existing.get("profile", "")),
                )
                existing["fingerprint"] = existing_fingerprint
            if existing_fingerprint != fingerprint:
                continue
            if self._is_done_result(existing):
                continue
            existing["superseded"] = True
            existing["superseded_by"] = session_id

    def _mark_matching_plan_finished(self, item: Dict[str, Any]) -> None:
        finish = item.get("finish_result", {}) or {}
        status = str(finish.get("status", "") or "").strip().lower()
        if not status or status == "running":
            return
        instruction = str(item.get("task_instruction", "") or "")
        model = str(item.get("model", "") or "")
        for task_id, spec in self.task_plan_executor.task_map.items():
            record = self.task_plan_executor.runtime.get(task_id)
            if record is None or record.state.value != "running":
                continue
            if spec.task_instruction == instruction and (not model or spec.model == model):
                self.task_plan_executor.mark_finished(task_id, finish)
                return

    def _update_context(self, action: str, params: Dict[str, Any], result: Dict[str, Any]) -> None:
        summary = [f"[attempt {self.attempt}] action={action}"]
        event_summary: List[str] = []

        if action == "delegate_task":
            self._append_task_entry(params, result)
            finish = result.get("finish_result", {})
            if self.latest_plan_task_ids and finish.get("status") != "running":
                self.task_plan_executor.mark_finished(self.latest_plan_task_ids[0], finish)
            summary.append(f"status={finish.get('status', 'partial')}")
            summary.append(f"tools={params.get('tools', [])}")
            if result.get("session_id"):
                summary.append(f"session_id={result.get('session_id')}")

        if action == "continue_task":
            self._append_task_entry(params, result)
            finish = result.get("finish_result", {})
            summary.append(f"status={finish.get('status', 'partial')}")
            summary.append(f"continued_session={result.get('session_id', '')}")
            summary.append(f"tools={params.get('tools', [])}")

        if action == "list_worker_sessions":
            summary.append(f"subagent_session_count={result.get('count', 0)}")

        if action == "inspect_worker_session":
            inspected = (result.get("session", {}) or {}).get("session_id", params.get("session_id", ""))
            summary.append(f"inspected_session={inspected}")

        if action == "wait_worker_sessions":
            for item in result.get("results", []) or []:
                self._append_task_entry(
                    {
                        "task_instruction": item.get("task_instruction", ""),
                        "model": item.get("model", ""),
                        "tools": item.get("allowed_tools", []),
                    },
                    item,
                )
                self._mark_matching_plan_finished(item)
            summary.append(f"wait_summary={result.get('summary', {})}")
            event_type = str(params.get("_event_type", "") or "").strip()
            if event_type in {"auto_wait", "final_wait", "forced_synthesis_wait"}:
                wait_summary = result.get("summary", {}) if isinstance(result, dict) else {}
                label = {
                    "auto_wait": "auto_wait",
                    "final_wait": "final_wait",
                    "forced_synthesis_wait": "forced_synthesis_wait",
                }.get(event_type, "worker_wait")
                event_summary.extend(
                    [
                        f"[attempt {self.attempt}] event={label}",
                        f"waited_for={wait_summary.get('waited_for', [])}",
                        f"completed={wait_summary.get('completed', 0)}",
                        f"still_running={wait_summary.get('still_running', 0)}",
                    ]
                )
                if wait_summary.get("merged_findings"):
                    event_summary.append(f"merged_findings={wait_summary.get('merged_findings')}")
                if wait_summary.get("merged_scratchpads"):
                    event_summary.append(f"merged_scratchpads={wait_summary.get('merged_scratchpads')}")

        if action == "close_worker_session":
            summary.append(f"closed_session={result.get('session_id', params.get('session_id', ''))}")

        if action == "delegate_tasks":
            for idx, item in enumerate(result.get("results", []) or []):
                task_params = (params.get("tasks") or [{}])[idx] if idx < len(params.get("tasks") or []) else {}
                self._append_task_entry(task_params, item)
                if idx < len(self.latest_plan_task_ids) and item.get("finish_result", {}).get("status") != "running":
                    self.task_plan_executor.mark_finished(
                        self.latest_plan_task_ids[idx],
                        item.get("finish_result", {}),
                    )
            summary.append(f"batch_summary={result.get('summary', {})}")

        if action == "complete_task":
            summary.append(f"report_path={params.get('report_path', '')}")
            summary.append(f"confidence={params.get('confidence', '')}")
            if not result.get("quality_gate_passed", False):
                summary.append(f"quality_issues={result.get('issues', [])}")
                event_summary.extend(
                    [
                        f"[attempt {self.attempt}] event=quality_gate_issue",
                        f"issues={result.get('issues', [])}",
                    ]
                )

        if action == "phase_guard":
            summary.append(f"requested_action={params.get('requested_action', '')}")
            summary.append(f"blocked_reason={result.get('message', '')}")
            event_summary.extend(
                [
                    f"[attempt {self.attempt}] event=phase_guard",
                    f"requested_action={params.get('requested_action', '')}",
                    f"blocked_reason={result.get('message', '')}",
                ]
            )

        if event_summary:
            self.context = ("\n".join(event_summary) + "\n\n" + self.context)[:6000]
        self.history.append({"attempt": self.attempt, "action": action, "result": result})

    async def run(self, request: Optional[str] = None) -> str:
        return request or ""


# Backward compatibility alias
MainOrchestratorAgent = MainAgent
