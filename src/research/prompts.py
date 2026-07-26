from __future__ import annotations

import json
from typing import Any, Dict, List

from project.prompts import GenericMainPromptBuilder, GenericSubPromptBuilder


class ResearchMainPromptBuilder:
    """Prompt builder for literature-review research mode orchestration."""

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
        report_path = meta.get("report_path", "workspace/output/research_report.md")
        findings_path = meta.get("findings_path", "workspace/output/findings.jsonl")
        scratchpad_path = meta.get("scratchpad_path", "workspace/output/scratchpad/shared.md")
        papers_path = meta.get("papers_path", "workspace/output/papers.jsonl")
        paper_notes_path = meta.get("paper_notes_path", "workspace/output/paper_notes.jsonl")
        claims_path = meta.get("claims_path", "workspace/output/claims.jsonl")
        debate_log_path = meta.get("debate_log_path", "workspace/output/debate_log.md")
        outline_path = meta.get("outline_path", "workspace/output/outline.md")
        review_path = meta.get("review_path", "workspace/output/review_report.md")
        references_bib_path = meta.get("references_bib_path", "workspace/output/references.bib")
        mode = str(meta.get("mode", "academic"))
        research_step_key = str(meta.get("research_step_key", "unknown"))
        research_step_title = str(meta.get("research_step_title", "unknown"))
        research_step_index = int(meta.get("research_step_index", 0) or 0)
        research_step_total = int(meta.get("research_step_total", 0) or 0)
        expected_section = str(
            meta.get("current_step_expected_section")
            or (required_sections[0] if required_sections else "")
        )
        all_required_sections = list(meta.get("all_required_sections", []) or [])
        max_parallel = int(meta.get("max_parallel_subtasks", 3))
        main_instruction = GenericMainPromptBuilder._format_main_instruction(instruction)
        findings_count = int(meta.get("findings_count", 0) or 0)
        papers_count = int(meta.get("papers_count", 0) or 0)
        findings_remaining = int(meta.get("findings_remaining", 0) or 0)
        step_min_papers = int(meta.get("step_min_papers", 0) or 0)
        target_papers = int(meta.get("target_papers_for_literature_review", 0) or 0)
        material_ready = bool(meta.get("material_ready", True))
        material_blocking = bool(meta.get("material_blocking", False))
        material_issues = [str(item) for item in (meta.get("material_issues", []) or [])]
        material_warnings = [str(item) for item in (meta.get("material_warnings", []) or [])]
        material_digest_text = json.dumps(meta.get("material_digest", {}) or {}, ensure_ascii=False, indent=2)

        forced_final_decision = bool(meta.get("forced_final_decision", False))
        current_phase = str(meta.get("current_phase", "unknown"))
        next_required_intent = str(meta.get("next_required_intent", "unknown"))
        allowed_actions = [str(item) for item in (meta.get("allowed_actions", []) or []) if str(item).strip()]
        phase_intent_guidance = str(meta.get("phase_intent_guidance", ""))

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

        final_decision_text = (
            "是。当前是强制最终决策轮：禁止继续委派，只能基于已有材料调用 complete_task，必要时 status 使用 partial/blocked。"
            if forced_final_decision
            else "否。"
        )

        return f"""
你是 ResearchMainAgent，一个文献综述研究流程中的步骤协调器。

 重要边界：
- 整个 Research Mode 的下一步由 ResearchPipeline 决定，不由你决定。
- 你只负责当前 step 内的拆分、委派、等待、综合和完成判断。
- 不要跳到其他 research step，不要改写 ResearchPipeline 的流程。
- 当前研究模式面向{'文献综述' if mode == 'academic' else '通用研究+视觉报告'}；不要生成实验假设，不要设计实验 pipeline。

当前 step brief：
{main_instruction}

Current research step scope:
- step: {research_step_index}/{research_step_total} {research_step_title} ({research_step_key})
- completion_scope: current_step_only
- expected_section_for_this_step: ## {expected_section}
- complete_task.required_sections: {json.dumps(required_sections, ensure_ascii=False)}
- final_report_required_sections_checked_later: {json.dumps(all_required_sections, ensure_ascii=False)}

当前 step gate 统计：
- findings_count: {findings_count}
- papers_count: {papers_count}
- min_findings_for_this_step: {min_findings}
- min_papers_for_this_step: {step_min_papers}
- target_papers_for_literature_review: {target_papers}
- findings_remaining_before_complete: {findings_remaining}
- 如果 findings_remaining_before_complete > 0，普通轮次不要 complete_task；应继续委派或续跑当前 step 的证据收集、record_finding 或 record_paper。
- {'最终目标是生成 LaTeX 文献综述（paper.tex + references.bib）。文献检索阶段要优先扩充 papers.jsonl，标准深度至少几十篇合格论文；正文阶段必须保留可转换为 \\cite{...} 或 \\url{...} 的来源。' if mode == 'academic' else '最终目标是生成视觉化 HTML 报告（report_visual.html）。信息检索阶段要优先扩充 sources.jsonl 和 material_notes.jsonl；正文阶段保留来源链接，并在合适位置插入图表标记（![chart](data:bar|{...}) 和 ![table](data:{...})）。'}

当前材料就绪判断：
- material_ready: {material_ready}
- material_blocking: {material_blocking}
- material_issues: {json.dumps(material_issues, ensure_ascii=False)}
- material_warnings: {json.dumps(material_warnings, ensure_ascii=False)}
- material_digest:
```json
{material_digest_text}
```
- 如果材料摘要显示上游产物为空，不要反复读取同一个空 artifact；要么补足对应材料，要么以 partial/blocked 明确说明缺口。
- {'读取研究产物时优先使用专用工具：read_findings、read_papers、read_paper_notes、read_research_claims、read_research_outline、read_claim_debate_log、read_research_report；不要用 read_sources 读取 output 目录下的 JSONL/MD 产物。' if mode == 'academic' else '读取研究产物时优先使用专用工具：read_findings、read_sources、read_material_notes、read_insights、read_review_notes、read_research_outline、read_research_report；不要用 read_sources 读取 output 目录下的 JSONL/MD 产物。'}

{'文献综述原则' if mode == 'academic' else '研究原则'}：
- 以真实来源和可追溯证据为中心；不编造{'论文、作者、年份' if mode == 'academic' else '资料、数据、来源'}、链接或结论。
- 将任务拆成互相独立的{'综述视角，例如方法论、应用场景、证据强度、争议点、研究空白、未来方向' if mode == 'academic' else '研究视角，例如背景分析、趋势判断、方法对比、应用场景、证据强度、争议点、结论与建议'}。
- 并行探索阶段只收集和压缩证据，优先记录 findings 和 scratchpad。
- {'观点生成阶段输出研究空白、未来方向、可检验研究问题和综述观点，不输出实验假设。' if mode == 'academic' else '洞察生成阶段输出核心洞察、趋势判断、结论建议和关键发现，不输出实验假设。'}
- {'观点辩论阶段检查证据覆盖、相关性、创新性、局限和优先级。' if mode == 'academic' else '洞察审校阶段检查证据覆盖、逻辑一致性、创新性、局限和优先级。'}
- 写作阶段综合已有 findings/scratchpad/session 结果，写入当前 step 要求的主 report_path。
- 验证阶段只检查缺口、来源和章节，不重写正文。

运行状态：
- 当前轮次: {attempt_index}/{max_attempts}
- 强制最终决策: {final_decision_text}
- 当前 MainAgent 内部阶段: {current_phase}
- 下一步意图: {next_required_intent}
- 下一步要求: {phase_intent_guidance}
- 本轮只能选择下方 Action schema 中列出的 action。

产物路径：
- report_path: {report_path}
- findings_path: {findings_path}
- scratchpad_path: {scratchpad_path}
{'- papers_path: {papers_path}' if mode == 'academic' else '- sources_path: {meta.get("sources_path", "workspace/output/sources.jsonl")}'}
{'- paper_notes_path: {paper_notes_path}' if mode == 'academic' else '- material_notes_path: {meta.get("material_notes_path", "workspace/output/material_notes.jsonl")}'}
{'- claims_path: {claims_path}' if mode == 'academic' else '- insights_path: {meta.get("insights_path", "workspace/output/insights.jsonl")}'}
{'- debate_log_path: {debate_log_path}' if mode == 'academic' else '- review_notes_path: {meta.get("review_notes_path", "workspace/output/review_notes.md")}'}
- outline_path: {outline_path}
- review_path: {review_path}
{'- references_bib_path: {references_bib_path}' if mode == 'academic' else '- report_visual_html_path: {meta.get("report_visual_html_path", "workspace/output/report_visual.html")}'}

委派历史：
{subtask_history or "尚未委派子任务。"}

最近事件：
{prior_context or "None"}

输出要求：
- 只返回 JSON。
- 每轮只能选择一个 action。
- 不要传 `model`；系统会按 sub_models 顺序轮询分配子任务模型。
- 默认省略 `tools`，除非当前委派必须限制权限。
- 工具失败换路：同一个工具连续失败后不要原样重试；改用替代工具或缩小查询。例如 Semantic Scholar 429 后转 `arxiv_search`/`crossref_lookup`/`dblp_lookup`，DBLP SSL 失败后转 Crossref、arXiv、web_fetch/read_url 或记录 open issue。
- 文献检索步骤必须优先补足 `min_papers_for_this_step` 和 `min_findings_for_this_step`；每篇合格论文调用 `record_paper`，每条关键发现调用 `record_finding`。

Action schema：
{action_schema_text}

返回 JSON 格式：
{{
  "action": "上面 action 之一",
  "reasoning": "简短说明为什么当前 step 内需要这样做",
  "params": {{}}
}}
""".strip()


class ResearchSubPromptBuilder:
    """Prompt builder for literature-review research-mode workers."""

    @staticmethod
    def _detect_task_type(task_instruction: str, context: str) -> tuple[str, str]:
        return GenericSubPromptBuilder._detect_task_type(task_instruction, context)

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
        task_type, task_type_source = ResearchSubPromptBuilder._detect_task_type(task_instruction, context)
        mode = "visual" if "sources.jsonl" in context and "material_notes.jsonl" in context else "academic"
        is_topic_decomposition = (
            "decompose_topic" in task_instruction
            or "Topic Decomposition" in task_instruction
            or "课题拆解" in task_instruction
            or "研究问题拆解" in task_instruction
        )
        step_specific_rules = (
            """
当前是课题拆解步骤：
- 不需要检索外部来源，也不需要 record_finding。
- 产出研究主问题、3-6 个子问题、纳入/排除标准、中英文关键词、检索式建议和不确定性。
- 只写 scratchpad/plan artifact，不写 research_report.md；写入 `## 研究问题拆解` scratchpad 笔记后 finish。
""".strip()
            if is_topic_decomposition
            else """
当前是证据驱动步骤：
- 如果某个检索工具失败，不要连续原样重试；换用替代工具、缩小查询或记录 open issue。
- Semantic Scholar 429 后优先改用 arxiv_search、crossref_lookup、dblp_lookup、web_fetch/read_url。
- DBLP SSL 或连接失败后不要继续重复 DBLP；改用 Crossref、arXiv 或网页来源。
- 文献检索阶段要优先补足所需 findings；每个可用证据点应调用 record_finding。
""".strip()
        )

        return f"""
你是 ResearchSubAgent，一个{'文献综述' if mode == 'academic' else '通用研究+视觉报告'}研究流程中的执行型子智能体。

已分配任务：
{task_instruction}

任务类型：
- 当前类型: {task_type}
- 类型来源: {task_type_source}

原始研究请求：
{original_question}

上下文：
{context or "无"}

可用动作：
{action_space}

当前观察：
{observation}

记忆：
{memory or "无"}

Step budget:
- current_subagent_step: {current_step}/{max_steps}
- remaining_steps_after_this_decision: {remaining_steps}
- Treat the assigned task as one ResearchPipeline step or subtask, not the whole research report.

当前步骤专用规则：
{step_specific_rules}

总规则：
- 只完成被分配的当前子任务，不扩展到其他 research step。
- 当前系统面向{'文献综述' if mode == 'academic' else '通用研究+视觉报告'}：不要生成实验假设，不要设计实验，不要编造{'文献' if mode == 'academic' else '来源'}。
- 所有关键结论必须连接到 source_url、evidence、本地资料或明确的不确定性说明。
- 优先使用最短工具路径：搜索/读取足够证据后，记录 findings 或写 scratchpad。
- `write_scratchpad_note` 只记录会影响后续综合、{'观点生成、辩论' if mode == 'academic' else '洞察生成、审校'}或写作的信息。
- 如果证据不足但仍能给出部分结果，使用 status `partial` 并说明缺口。
- 只有工具不可用、关键依赖失败或任务无法继续时，才使用 status `blocked`。
- 剩余步骤：{remaining_steps}
- 当剩余步骤小于等于 2 时，停止新的广泛探索，整理已有信息并准备 `finish`。
- 当剩余步骤小于等于 1 时，必须立即调用 `finish`。

{'文献综述任务策略' if mode == 'academic' else '研究任务策略'}：
- {'literature/search' if mode == 'academic' else 'information/search'}: 收集真实来源，记录题名、机构/作者、日期、链接和相关性。
- synthesis: 聚类共识、争议、方法局限、证据强弱和{'研究空白' if mode == 'academic' else '核心洞察'}。
- {'claim_generation' if mode == 'academic' else 'insight_generation'}: 输出{'研究空白、未来方向、可检验研究问题和综述观点' if mode == 'academic' else '核心洞察、趋势判断、结论建议和关键发现'}。
- {'claim_debate' if mode == 'academic' else 'insight_review'}: 批判{'观点' if mode == 'academic' else '洞察'}的证据覆盖、创新性、相关性、局限和优先级。
- write: 只基于已有 findings/scratchpad/session 结果写作，正文保留关键来源链接。{'在 visual_design 阶段，需要在 markdown 中插入图表标记：![chart](data:bar|{...}) 和 ![table](data:{...})。' if mode == 'visual' else ''}
- verify: 检查章节、来源、证据覆盖和 open issues，不重写正文。

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
