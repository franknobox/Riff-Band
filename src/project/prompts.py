from __future__ import annotations

import json
from typing import Any, Dict, List


class GenericMainPromptBuilder:
    """Prompt builder for the generic multi-agent orchestrator."""

    @staticmethod
    def _format_subagent_capabilities(tools: List[Any] | None) -> str:
        names = [str(getattr(tool, "name", "")).strip() for tool in (tools or [])]
        names = [name for name in names if name]
        if not names:
            return "SubAgent 会获得标准执行工具集，可进行联网搜索、记录 findings、写交接笔记、撰写产物和验证。"
        return "SubAgent 默认具备执行工具集；除非要限制权限，否则不要在委派参数中传 `tools`。"

    @staticmethod
    def _format_main_instruction(instruction: str) -> str:
        text = str(instruction or "").strip()
        if not text:
            return ""
        for marker in ("[用户任务]", "[鐢ㄦ埛浠诲姟]"):
            if marker not in text:
                continue
            task_text = text.split(marker, 1)[1].strip()
            for end_marker in ("[联网搜索]", "[鑱旂綉鎼滅储]"):
                if end_marker in task_text:
                    task_text = task_text.split(end_marker, 1)[0].strip()
            return task_text
        return text

    @staticmethod
    def build_prompt(
        instruction: str,
        meta: Dict[str, Any],
        prior_context: str,
        attempt_index: int,
        max_attempts: int,
        sub_models: List[str],
        subtask_history: str = "",
        tools: List[Any] | None = None,
    ) -> str:
        required_sections = meta.get("required_sections", [])
        min_findings = int(meta.get("min_findings", 0))
        report_path = meta.get("report_path", "workspace/output/task_report.md")
        findings_path = meta.get("findings_path", "workspace/output/findings.jsonl")
        scratchpad_path = meta.get("scratchpad_path", "workspace/output/scratchpad/shared.md")
        max_parallel = int(meta.get("max_parallel_subtasks", 3))
        main_instruction = GenericMainPromptBuilder._format_main_instruction(instruction)
        workflow_hints = [str(item) for item in (meta.get("workflow_hints", []) or []) if str(item).strip()]
        completion_requirements = [
            str(item) for item in (meta.get("completion_requirements", []) or []) if str(item).strip()
        ]
        forced_final_decision = bool(meta.get("forced_final_decision", False))
        current_phase = str(meta.get("current_phase", "unknown"))
        next_required_intent = str(meta.get("next_required_intent", "unknown"))
        allowed_actions = [str(item) for item in (meta.get("allowed_actions", []) or []) if str(item).strip()]
        phase_intent_guidance = str(meta.get("phase_intent_guidance", ""))
        phase_labels = {
            "research": "研究阶段",
            "synthesis": "综合/写作阶段",
            "verification": "验证阶段",
            "unknown": "未知阶段",
        }
        intent_labels = {
            "finish_research": "完成研究",
            "draft_report": "撰写主报告",
            "delegate_verification": "委派验证子任务",
            "complete": "完成任务",
            "unknown": "未知意图",
        }
        phase_display = f"{current_phase}（{phase_labels.get(current_phase, current_phase)}）"
        intent_display = f"{next_required_intent}（{intent_labels.get(next_required_intent, next_required_intent)}）"
        schema_rows = [
            'delegate_task: {"task_instruction": "任务类型: research|write|verify|continue\\n期望产出: ...\\n完成标准: ...\\n具体任务: ...", "context": "...", "tools": "optional"}' if "delegate_task" in allowed_actions else "",
            f'delegate_tasks: {{"max_concurrency": {max_parallel}, "tasks": [{{"task_instruction": "任务类型: research\\n期望产出: ...\\n完成标准: ...\\n具体任务: ...", "context": "..."}}]}}' if "delegate_tasks" in allowed_actions else "",
            'continue_task: {"session_id": "...", "task_instruction": "任务类型: continue\\n期望产出: ...\\n完成标准: ...\\n具体任务: ...", "context": "..."}' if "continue_task" in allowed_actions else "",
            'wait_worker_sessions: {"session_ids": ["..."], "timeout_seconds": 30}' if "wait_worker_sessions" in allowed_actions else "",
            'inspect_worker_session: {"session_id": "...", "include_trace": true}' if "inspect_worker_session" in allowed_actions else "",
            'list_worker_sessions: {"include_closed": false}' if "list_worker_sessions" in allowed_actions else "",
            'close_worker_session: {"session_id": "...", "reason": "..."}' if "close_worker_session" in allowed_actions else "",
            f'complete_task: {{"executive_summary": "...", "status": "done|partial|blocked", "artifacts": [{{"type": "report|file|data|note", "path": "...", "description": "..."}}], "verification": ["..."], "open_issues": [], "confidence": "high|medium|low", "report_path": "{report_path}", "findings_path": "{findings_path}", "required_sections": {json.dumps(required_sections, ensure_ascii=False)}, "min_findings": {min_findings}}}' if "complete_task" in allowed_actions else "",
        ]
        action_schema_text = "\n".join(f"- {row}" for row in schema_rows if row)
        if next_required_intent == "delegate_verification":
            action_schema_text += (
                "\n\n验证任务模板：\n"
                "- 使用 action=delegate_task，不要输出 action=verify_artifacts。\n"
                "- task_instruction 必须以 \"任务类型: verify\" 开头，并要求 SubAgent 调用 verify_artifacts。\n"
                f"- context 应包含 report_path={report_path}, findings_path={findings_path}, scratchpad_path={scratchpad_path}。"
            )

        profile_notes: List[str] = []
        if workflow_hints:
            profile_notes.append("工作流提示：\n" + "\n".join(f"- {item}" for item in workflow_hints[:4]))
        if completion_requirements:
            profile_notes.append(
                "完成要求：\n" + "\n".join(f"- {item}" for item in completion_requirements[:4])
            )
        profile_text = "\n\n".join(profile_notes) if profile_notes else "无额外 profile 提示。"
        final_decision_text = (
            "是。当前是强制最终决策轮：禁止再调用 delegate_task、delegate_tasks 或 continue_task；"
            "只能基于已收集结果调用 complete_task，必要时 status 使用 partial/blocked。"
            if forced_final_decision
            else "否。"
        )

        return f"""
你是 MainAgent，一个固定的多智能体工作流协调者。
用户任务：
{main_instruction}

工作原则：
- 你只负责协调：理解任务、拆分/委派、等待和检查 session、综合结果、决定完成状态。
- `delegate_task` 和 `delegate_tasks` 会立即返回 running `session_id`；必须用 `wait_worker_sessions` 或 `inspect_worker_session` 收集结果。
- 能并行时，优先把互相独立的探索/验证任务一次性用 `delegate_tasks` 启动。
- 不要微管理 SubAgent 工具；默认省略 `tools`，系统会自动补齐默认工具、模型和并行限制。
- 委派 SubAgent 时，必须在 `task_instruction` 或 `context` 中写明 `任务类型: research|write|verify|continue`、`期望产出:`、`完成标准:`。
- 并行 SubAgent 的产物都是中间产物；最终报告只能由综合阶段的 `write` 类型 SubAgent 写入主 `report_path`。
- 进入综合阶段时，启动新的 `delegate_task` 写主报告，不要 `continue_task` 到并行 research session，否则会写回 `parallel_runs`。
- 若同一个 session 连续等待仍无结果，应 inspect、拆小任务、改委派策略，或在最后一轮用 `complete_task` 返回 partial/blocked。
- 只有收集了必要结果并完成验证后，才能 `complete_task`。

运行状态：
- 当前轮次: {attempt_index}/{max_attempts}
- 强制最终决策: {final_decision_text}
- 当前阶段: {phase_display}
- 下一步意图: {intent_display}
- 下一步要求: {phase_intent_guidance}
- 本轮只能选择下方 Action schema 中列出的 action。

阶段控制：
- finish_research：只启动、继续、检查或等待 research 子任务。
- draft_report：启动或继续 write 子任务，写入主 report_path；不要验证或完成。
- delegate_verification：输出 delegate_task 或 continue_task 启动 verification 子任务；verify_artifacts 是 SubAgent 工具名，不是 MainAgent action。
- complete：调用 complete_task。

委派历史：
{subtask_history or "尚未委派子任务。"}

最近事件：
{prior_context or "None"}

产物路径：
- report_path: {report_path}
- findings_path: {findings_path}
- scratchpad_path: {scratchpad_path}

SubAgent 能力：
SubAgent 默认具备执行工具集，可进行联网搜索、记录 findings、写交接笔记、撰写产物和验证；除非要限制权限，否则不要在委派参数中传 `tools`。

Profile 提示：
{profile_text}

输出要求：
- 只返回 JSON。
- 每轮只能选择一个 action。
- 不要传 `model`；系统会按 sub_models 顺序轮询分配子任务模型。
- 可省略 `tools`；系统会自动补默认值。

Action schema（仅包含本轮允许的 MainAgent actions）：
{action_schema_text}

返回 JSON 格式：
{{
  "action": "上面 action 之一",
  "reasoning": "简短说明为什么现在做这一步",
  "params": {{}}
}}
""".strip()


class GenericSubPromptBuilder:
    """通用执行子智能体的提示词构造器。"""

    @staticmethod
    def _detect_task_type(task_instruction: str, context: str) -> tuple[str, str]:
        text = f"{task_instruction}\n{context}".lower()
        explicit_markers = ("任务类型:", "任务类型：", "task_type:", "task type:")
        for marker in explicit_markers:
            marker_lower = marker.lower()
            if marker_lower in text:
                after = text.split(marker_lower, 1)[1].strip()
                first_line = after.splitlines()[0].strip()
                for task_type in ("research", "write", "verify", "continue"):
                    if task_type in first_line:
                        return task_type, "MainAgent 在 task_instruction/context 中显式指定。"

        if any(word in text for word in ("继续", "continue", "补齐", "上次", "已有 session", "previous run")):
            return "continue", "未显式指定；根据继续、补齐、上次结果等关键词推断。"
        if any(word in text for word in ("验证", "检查", "verify", "校验", "缺口", "artifact")):
            return "verify", "未显式指定；根据验证、检查、缺口等关键词推断。"
        if any(word in text for word in ("撰写", "写入", "生成报告", "章节", "write", "report section", "产物")):
            return "write", "未显式指定；根据撰写、章节、产物等关键词推断。"
        return "research", "未显式指定；默认按 research 处理。"

    @staticmethod
    def build_prompt(
        task_instruction: str,
        context: str,
        original_question: str,
        action_space: str,
        observation: Any,
        memory: str,
        current_step: int,
        max_steps: int,
    ) -> str:
        remaining_steps = max_steps - current_step
        task_type, task_type_source = GenericSubPromptBuilder._detect_task_type(task_instruction, context)
        return f"""
你是 SubAgent，一个被 MainAgent 委派的执行型子智能体。

已分配任务：
{task_instruction}

任务类型：
- 当前类型: {task_type}
- 类型来源: {task_type_source}
- 优先使用 MainAgent 在 `任务类型:` 中显式指定的类型；若未指定，才按任务文本保守推断。

原始用户请求：
{original_question}

上下文：
{context or "无"}

可用动作：
{action_space}

当前观察：
{observation}

记忆：
{memory or "无"}

总规则：
- 只在已分配任务范围内工作，不要扩展到其他子任务。
- 使用能完成任务的最短工具路径，不要默认执行所有工具。
- 每次工具调用前判断是否仍需要更多证据或操作。
- `write_scratchpad_note` 只在信息会影响其他 SubAgent 或后续继续任务时使用，不是每轮必用。
- 如果证据不足但仍能给出部分结果，使用 status `partial` 并说明缺少什么。
- 只有工具不可用、关键依赖失败或任务无法继续时，才使用 status `blocked`。
- 剩余步骤：{remaining_steps}
- 当剩余步骤小于等于 2 时，停止新的探索，整理已有信息并准备 `finish`。
- 当剩余步骤小于等于 1 时，必须立即调用 `finish`，不得继续调用搜索、读取、写入或验证工具。

任务类型策略：
- research: 目标是收集和压缩信息。最多执行 2 次搜索/读取，然后用 `record_finding` 记录关键发现并 `finish`；除非任务明确要求，不写报告章节。
- write: 目标是产出指定内容。优先读取已有 findings/scratchpad，只写指定章节或文件；除非上下文缺口很明确，否则不做广泛搜索。写完后 `finish`。
- verify: 目标是检查产物是否满足完成标准。只验证报告、发现记录和缺口，不重写正文；验证后 `finish`。
- continue: 目标是补齐上次未完成或有缺口的内容。先读取上下文中的上轮结果/trace，只补缺口，不重复已完成工作，完成后 `finish`。

只返回 JSON。

工具调用格式：
{{"action": "tool_name", "params": {{...}}, "memory": "本步骤获得的信息"}}

结束格式：
{{
  "action": "finish",
  "params": {{
    "status": "done|partial|blocked",
    "message": "完成状态说明",
    "completed": ["已完成事项"],
    "issues": ["剩余问题或阻塞原因"],
    "result": "简短结果"
  }},
  "memory": "给 MainAgent 或后续 SubAgent 的交接笔记"
}}
""".strip()


GBAMainPromptBuilder = GenericMainPromptBuilder
GBASubPromptBuilder = GenericSubPromptBuilder
