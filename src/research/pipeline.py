from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

from config import AgentConfig
from base.engine.async_llm import LLMsConfig
from base.engine.logs import LogLevel, logger
from project import build_agent_project, build_single_agent_project
from research.artifacts import (
    ResearchArtifacts,
    append_jsonl,
    ensure_text_artifact,
    export_html,
    export_latex,
    export_visual_html,
    read_jsonl,
)
from research.gates import ResearchGatekeeper
from research.prompts import ResearchMainPromptBuilder, ResearchSubPromptBuilder
from research.schema import ResearchArtifact, ResearchRequest, ResearchResult, ResearchStepResult
from research.skills import ResearchSkillRegistry
from research.steps import RESEARCH_STEPS, VISUAL_STEPS, ResearchStep, required_report_sections


@dataclass(frozen=True)
class ResearchPipelineOptions:
    execute_agents: bool = True


@dataclass(frozen=True)
class ResearchDepthRuntime:
    max_attempts: int
    max_subagent_steps: int
    max_parallel_subtasks: int
    subagent_process_timeout_seconds: int
    report_length_target: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "max_subagent_steps": self.max_subagent_steps,
            "max_parallel_subtasks": self.max_parallel_subtasks,
            "subagent_process_timeout_seconds": self.subagent_process_timeout_seconds,
            "report_length_target": self.report_length_target,
        }


@dataclass(frozen=True)
class MaterialReadiness:
    """Snapshot of whether existing artifacts can support the next step."""

    ready: bool
    blocking: bool
    issues: list[str]
    warnings: list[str]
    digest: dict[str, Any]


class ResearchPipeline:
    """Fixed research-mode workflow.

    The pipeline owns phase order, artifact paths, and quality gates. Agent
    projects are used as executors for each step rather than as the source of
    control flow.
    """

    def __init__(
        self,
        request: ResearchRequest,
        config: AgentConfig,
        options: ResearchPipelineOptions | None = None,
        progress_callback: Callable[[str], None] | None = None,
        cancel_event: asyncio.Event | None = None,
    ):
        self.request = request
        self.config = config
        self.mode = str(request.mode or "academic").strip().lower()
        # visual mode defaults to html output
        if self.mode == "visual" and request.output_format == "latex":
            request.output_format = "html"
        self.options = options or ResearchPipelineOptions()
        self.progress_callback = progress_callback
        self.cancel_event = cancel_event
        self.artifacts = ResearchArtifacts.create(config.workspace_dir.resolve(), request, mode=self.mode)
        self.skills = ResearchSkillRegistry(mode=self.mode)
        self.gates = ResearchGatekeeper(self.artifacts, mode=self.mode)
        self.step_results: list[ResearchStepResult] = []
        self.pipeline_issues: list[str] = []

    def _resolve_steps(self) -> tuple[ResearchStep, ...]:
        return VISUAL_STEPS if self.mode == "visual" else RESEARCH_STEPS

    async def run(self) -> ResearchResult:
        steps = self._resolve_steps()
        can_execute = self.options.execute_agents and self._has_llm_config()
        self._emit_progress(
            f"Research run start topic={self.request.topic!r} "
            f"mode={self.mode} steps={len(steps)} agent_execution={can_execute} "
            f"run_dir={self.artifacts.run_dir}"
        )
        if not can_execute:
            self._write_offline_scaffold("LLM configuration is unavailable; generated research scaffold only.")

        for step in steps:
            self._raise_if_cancelled()
            if can_execute:
                result = await self._run_agent_step(step)
            else:
                result = self._offline_step_result(step)
            self.step_results.append(result)
            self._raise_if_cancelled()
            step_index = list(steps).index(step) + 1
            self._emit_progress(
                f"Step {step_index}/{len(steps)} finished "
                f"key={step.key} status={result.status} issues={len(result.issues)}"
            )
            if can_execute and self._should_stop_after_step(step, result):
                message = (
                    f"stopped after critical step {step.key} because status={result.status}; "
                    "downstream research steps were not executed to avoid cascading blocked results"
                )
                self.pipeline_issues.append(message)
                self._emit_progress(message)
                break

        self._derive_structured_artifacts()
        self._export_requested_format()

        min_findings = self._min_findings()
        min_papers = self._min_sources() if self.mode == "visual" else self._min_papers()
        final_gate = self.gates.check_final(
            min_findings=min_findings,
            min_papers=min_papers,
            output_format=self.request.output_format,
        )
        step_records = [item.model_dump() for item in self.step_results]
        self.artifacts.write_manifest(self.request, step_records)

        status = "done" if final_gate.passed else "partial"
        issues = [*self.pipeline_issues, *final_gate.issues]
        if not can_execute:
            issues.insert(0, "LLM configuration unavailable; no live agent execution was performed")
        self._emit_progress(
            f"Research run complete status={status} "
            f"final_gate_passed={final_gate.passed} issues={len(issues)}"
        )

        report_path = self._primary_report_path()
        summary = (
            "Research pipeline completed."
            if status == "done"
            else "Research pipeline produced partial artifacts; see open_issues and manifest for gaps."
        )
        return ResearchResult(
            status=status,
            summary=summary,
            report_path=report_path,
            artifacts=self.artifacts.to_artifacts(self.request.output_format, mode=self.mode),
            steps=self.step_results,
            open_issues=issues,
            metadata={
                "topic": self.request.topic,
                "depth": self.request.depth,
                "output_format": self.request.output_format,
                "trigger": self.request.trigger,
                "mode": self.mode,
                "profile_name": self.config.profile_name,
                "run_dir": str(self.artifacts.run_dir),
                "manifest_path": str(self.artifacts.manifest),
                "agent_execution": can_execute,
                "gate_stats": final_gate.stats,
                "min_findings": min_findings,
                "min_papers": min_papers,
                "pipeline_issues": self.pipeline_issues,
            },
        )

    def _should_stop_after_step(self, step: ResearchStep, result: ResearchStepResult) -> bool:
        if result.status == "done":
            return False
        if self.mode == "visual":
            critical_steps = {
                "information_search",
                "material_reading",
                "knowledge_synthesis",
                "insight_generation",
                "outline_build",
                "section_draft",
            }
        else:
            critical_steps = {
                "literature_search",
                "paper_enrichment",
                "knowledge_synthesis",
                "claim_generation",
                "outline_build",
                "section_draft",
            }
        return step.key in critical_steps

    async def _run_agent_step(self, step: ResearchStep) -> ResearchStepResult:
        self._raise_if_cancelled()
        steps = self._resolve_steps()
        skill_text = self.skills.load_text(step.skill)
        readiness = self._assess_material_readiness(step)
        brief = self._build_step_brief(step, skill_text, readiness)
        step_required_sections = [step.expected_section] if step.report_required else []
        step_min_findings = self._step_min_findings(step)
        step_min_papers = self._step_min_papers(step)
        step_metadata = self._step_runtime_metadata(step, readiness)
        step_index = int(step_metadata["research_step_index"])
        executor = "multi-agent" if step.parallel_hint else "single-agent"
        runtime = self._depth_runtime()
        self._emit_progress(
            f"Step {step_index}/{len(steps)} start "
            f"key={step.key} title={step.title!r} executor={executor} "
            f"expected_section={step.expected_section!r} min_findings={step_min_findings} "
            f"min_papers={step_min_papers} "
            f"material_ready={readiness.ready} blocking={readiness.blocking} "
            f"issues={readiness.issues}"
        )

        if readiness.blocking:
            gate = self.gates.check_step(self._depth_adjusted_step(step))
            return ResearchStepResult(
                step=step.key,
                status="blocked",
                summary=f"{step.title} skipped because required upstream material is not ready.",
                artifacts=self._step_artifacts(step),
                issues=[*readiness.issues, *readiness.warnings, *gate.issues],
                metadata={
                    "gate_stats": gate.stats,
                    "material_readiness": readiness.digest,
                },
            )

        try:
            if step.parallel_hint:
                project = build_agent_project(
                    main_model=self.config.main_model,
                    sub_models=self.config.sub_models,
                    brief_text=brief,
                    sources_dir=self.config.sources_dir,
                    output_dir=self.artifacts.run_dir,
                    max_attempts=runtime.max_attempts,
                    max_subagent_steps=runtime.max_subagent_steps,
                    max_parallel_subtasks=runtime.max_parallel_subtasks,
                    subagent_process_timeout_seconds=runtime.subagent_process_timeout_seconds,
                    profile_name="research_mode",
                    report_filename=self.artifacts.report_md.name,
                    required_sections=step_required_sections,
                    min_findings=step_min_findings,
                    main_prompt_builder=ResearchMainPromptBuilder,
                    sub_prompt_builder=ResearchSubPromptBuilder,
                    runtime_metadata=step_metadata,
                )
            else:
                project = build_single_agent_project(
                    main_model=self.config.main_model,
                    sub_models=self.config.sub_models,
                    brief_text=brief,
                    sources_dir=self.config.sources_dir,
                    output_dir=self.artifacts.run_dir,
                    max_subagent_steps=runtime.max_subagent_steps,
                    max_parallel_subtasks=runtime.max_parallel_subtasks,
                    subagent_process_timeout_seconds=runtime.subagent_process_timeout_seconds,
                    profile_name="research_mode",
                    report_filename=self.artifacts.report_md.name,
                    required_sections=step_required_sections,
                    min_findings=step_min_findings,
                    sub_prompt_builder=ResearchSubPromptBuilder,
                    runtime_metadata=step_metadata,
                )

            try:
                async for message in project.stream(cancel_event=self.cancel_event):
                    if type(message).__name__ == "TaskCancelled":
                        self._cancel_project_workers(project)
                        raise asyncio.CancelledError
                    self._log_step_message(step, message)
            except asyncio.CancelledError:
                self._cancel_project_workers(project)
                raise
        except Exception as exc:
            gate = self.gates.check_step(self._depth_adjusted_step(step))
            self._emit_progress(
                f"Step {step_index}/{len(self._resolve_steps())} blocked "
                f"key={step.key} error={exc}"
            )
            return ResearchStepResult(
                step=step.key,
                status="blocked",
                summary=f"{step.title} failed: {exc}",
                artifacts=self._step_artifacts(step),
                issues=[str(exc), *gate.issues],
                metadata={
                    "gate_stats": gate.stats,
                    "material_readiness": readiness.digest,
                },
            )

        gate = self.gates.check_step(self._depth_adjusted_step(step))
        self._emit_progress(
            f"Step {step_index}/{len(self._resolve_steps())} gate "
            f"key={step.key} passed={gate.passed} issues={gate.issues}"
        )
        return ResearchStepResult(
            step=step.key,
            status="done" if gate.passed else "partial",
            summary=f"{step.title} executed.",
            artifacts=self._step_artifacts(step),
            issues=[*readiness.warnings, *gate.issues],
            metadata={
                "gate_stats": gate.stats,
                "material_readiness": readiness.digest,
            },
        )

    def _raise_if_cancelled(self) -> None:
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise asyncio.CancelledError

    def _cancel_project_workers(self, project: Any) -> None:
        main_agent = getattr(project, "main_agent", None)
        for tool in getattr(main_agent, "tools", []) or []:
            process_manager = getattr(tool, "process_manager", None)
            cancel_all = getattr(process_manager, "cancel_all", None)
            if callable(cancel_all):
                try:
                    cancel_all()
                except Exception as exc:
                    self._emit_progress(f"Worker hard cancel failed: {exc}")

    def _emit_progress(self, message: str) -> None:
        text = f"[ResearchPipeline] {message}"
        logger.log_to_file(LogLevel.INFO, text)
        if self.progress_callback is not None:
            self.progress_callback(message)

    def _log_step_message(self, step: ResearchStep, message: Any) -> None:
        name = type(message).__name__
        prefix = f"[ResearchPipeline] step={step.key} event={name}"
        if name == "SubAgentStart":
            logger.log_to_file(
                LogLevel.INFO,
                (
                    f"{prefix} label={getattr(message, 'label', '')} "
                    f"model={getattr(message, 'model', '')} "
                    f"max_steps={getattr(message, 'max_steps', '')}"
                ),
            )
            return
        if name == "SubAgentStepEnd":
            logger.log_to_file(
                LogLevel.INFO,
                (
                    f"{prefix} label={getattr(message, 'agent_label', '')} "
                    f"step={getattr(message, 'current_step', '')}/{getattr(message, 'max_steps', '')} "
                    f"action={getattr(message, 'action_taken', '')} "
                    f"done={getattr(message, 'done', False)}"
                ),
            )
            return
        if name == "SubAgentResult":
            logger.log_to_file(
                LogLevel.INFO,
                (
                    f"{prefix} label={getattr(message, 'label', '')} "
                    f"steps={getattr(message, 'steps_taken', '')} "
                    f"done={getattr(message, 'done', False)} "
                    f"finish_status={getattr(message, 'finish_status', '')} "
                    f"issues={getattr(message, 'finish_issues', [])}"
                ),
            )
            return
        if name == "OrchestratorThinking":
            logger.log_to_file(
                LogLevel.INFO,
                (
                    f"{prefix} attempt={getattr(message, 'attempt', '')}/"
                    f"{getattr(message, 'max_attempts', '')}"
                ),
            )
            return
        if name == "OrchestratorDecision":
            logger.log_to_file(
                LogLevel.INFO,
                (
                    f"{prefix} action={getattr(message, 'action', '')} "
                    f"reasoning={str(getattr(message, 'reasoning', ''))[:300]}"
                ),
            )
            return
        if name == "WorkerSpawned":
            logger.log_to_file(
                LogLevel.INFO,
                (
                    f"{prefix} session_id={getattr(message, 'session_id', '')} "
                    f"label={getattr(message, 'label', '')} "
                    f"model={getattr(message, 'model', '')}"
                ),
            )
            return
        if name == "WorkerCompleted":
            logger.log_to_file(
                LogLevel.INFO,
                (
                    f"{prefix} session_id={getattr(message, 'session_id', '')} "
                    f"status={getattr(message, 'status', '')}"
                ),
            )
            return
        if name == "TaskComplete":
            logger.log_to_file(
                LogLevel.INFO,
                (
                    f"{prefix} success={getattr(message, 'success', False)} "
                    f"quality_gate_passed={getattr(message, 'quality_gate_passed', False)} "
                    f"attempts={getattr(message, 'attempts', '')}"
                ),
            )

    def _build_step_brief(self, step: ResearchStep, skill_text: str, readiness: MaterialReadiness) -> str:
        digest_text = json.dumps(readiness.digest, ensure_ascii=False, indent=2)
        depth_policy = self._depth_policy_text()
        report_requirement = (
            f"- 必须写入或更新 markdown 报告章节: ## {step.expected_section}"
            if step.report_required
            else (
                f"- 本步骤只写 scratchpad/plan artifact，不写 research_report.md；"
                f"必须在 scratchpad 中写入或更新: ## {step.expected_section}"
            )
        )
        if self.mode == "visual":
            artifact_paths = f"""- report_path: {self.artifacts.report_md}
- report_visual_html_path: {self.artifacts.report_visual_html}
- findings_path: {self.artifacts.findings}
- scratchpad_path: {self.artifacts.scratchpad}
- sources_path: {self.artifacts.sources}
- material_notes_path: {self.artifacts.material_notes}
- insights_path: {self.artifacts.insights}
- review_notes_path: {self.artifacts.review_notes}
- outline_path: {self.artifacts.outline}
- review_path: {self.artifacts.review}"""
            final_goal = f"""当前研究型任务的最终目标是一份视觉化 HTML 报告：report_visual.html；markdown 报告是中间稿。
- 信息检索阶段要优先形成足够大的合格资料池；当前深度目标为至少 {self._min_papers()} 条 sources.jsonl 记录和至少 {self._min_findings()} 条结构化 findings。
- 正文写作阶段必须写出完整的通用研究报告，并保留来源 URL。在 visual_design 阶段，需要在 markdown 中插入图表标记：
  ![chart](data:bar|{{\"title\":\"...\",\"categories\":[],\"values\":[]}})
  ![table](data:{{\"headers\":[],\"rows\":[]}})
- 优先使用专用 artifact 工具读取研究产物：read_findings、read_sources、read_material_notes、read_insights、read_review_notes、read_research_outline、read_research_report。
- 不要用 read_sources 读取 findings.jsonl、sources.jsonl、material_notes.jsonl、insights.jsonl、outline.md、review_notes.md 或 research_report.md。"""
        else:
            artifact_paths = f"""- report_path: {self.artifacts.report_md}
- paper_tex_path: {self.artifacts.paper_tex}
- references_bib_path: {self.artifacts.references_bib}
- findings_path: {self.artifacts.findings}
- scratchpad_path: {self.artifacts.scratchpad}
- papers_path: {self.artifacts.papers}
- paper_notes_path: {self.artifacts.paper_notes}
- claims_path: {self.artifacts.claims}
- debate_log_path: {self.artifacts.debate_log}
- outline_path: {self.artifacts.outline}
- review_path: {self.artifacts.review}"""
            final_goal = f"""当前研究型任务的最终目标是一篇可引用的 LaTeX 文献综述：paper.tex + references.bib；markdown 报告是中间稿。
- 文献检索阶段要优先形成足够大的合格论文池；当前深度目标为至少 {self._min_papers()} 篇 papers.jsonl 记录和至少 {self._min_findings()} 条结构化 findings。
- 正文写作阶段必须写出“Abstract/Introduction/Related Work/Literature Synthesis/Research Gaps/Future Directions/Conclusion”等论文式内容，并保留来源 URL 或 citation key。
- 优先使用专用 artifact 工具读取研究产物：read_findings、read_papers、read_paper_notes、read_research_claims、read_research_outline、read_claim_debate_log、read_research_report。
- 不要用 read_sources 读取 findings.jsonl、papers.jsonl、paper_notes.jsonl、claims.jsonl、outline.md、debate_log.md 或 research_report.md。"""

        return f"""
任务类型: research
研究模式: 固定状态机 step 执行
当前步骤: {step.title} ({step.key})

[研究主题]
{self.request.topic}

[深度]
{self.request.depth}

[Depth Policy]
{depth_policy}

[输出格式]
{self.request.output_format}

[约束]
{self.request.constraints or "无"}

[用户指定来源]
{json.dumps(self.request.sources, ensure_ascii=False)}

[产物路径]
{artifact_paths}

[进入本步骤前的材料就绪判断]
- ready: {readiness.ready}
- blocking: {readiness.blocking}
- issues: {json.dumps(readiness.issues, ensure_ascii=False)}
- warnings: {json.dumps(readiness.warnings, ensure_ascii=False)}

[材料摘要]
```json
{digest_text}
```

[本步骤 Skill]
{skill_text}

[硬性要求]
- 只执行当前步骤，不要跳到后续步骤。
{report_requirement}
- {final_goal}
- 如果材料摘要显示上游材料缺失，不要反复读取同一空产物；应在本步骤输出中明确缺口，或基于已有材料产出 partial。
- 尽量使用 record_finding 记录带 source_url 或 evidence 的结构化发现。
- 重要中间结论写入 scratchpad，供后续步骤复用。
- 不要编造来源；来源不确定时明确标注不确定。
""".strip()

    def _step_runtime_metadata(self, step: ResearchStep, readiness: MaterialReadiness | None = None) -> dict[str, Any]:
        steps = self._resolve_steps()
        step_index = list(steps).index(step) + 1
        readiness = readiness or self._assess_material_readiness(step)
        runtime = self._depth_runtime()
        meta: dict[str, Any] = {
            "mode": self.mode,
            "research_depth": self.request.depth,
            "research_step_key": step.key,
            "research_step_title": step.title,
            "research_step_index": step_index,
            "research_step_total": len(steps),
            "current_step_expected_section": step.expected_section,
            "all_required_sections": required_report_sections(self.mode),
            "current_step_requires_report_section": bool(step.report_required),
            "step_min_findings": self._step_min_findings(step),
            "step_min_papers": self._step_min_papers(step),
            "target_papers_for_literature_review": self._min_papers(),
            "research_completion_scope": "current_step_only",
            "require_flow_integrity": False,
            "require_verification_passed": False,
            "depth_runtime_limits": runtime.to_dict(),
            "report_length_target": runtime.report_length_target,
            "material_ready": readiness.ready,
            "material_blocking": readiness.blocking,
            "material_issues": list(readiness.issues),
            "material_warnings": list(readiness.warnings),
            "material_digest": readiness.digest,
        }
        if self.mode == "visual":
            meta["sources_path"] = str(self.artifacts.sources)
            meta["material_notes_path"] = str(self.artifacts.material_notes)
            meta["insights_path"] = str(self.artifacts.insights)
            meta["review_notes_path"] = str(self.artifacts.review_notes)
            meta["report_visual_html_path"] = str(self.artifacts.report_visual_html)
        else:
            meta["references_bib_path"] = str(self.artifacts.references_bib)
            meta["paper_notes_path"] = str(self.artifacts.paper_notes)
        return meta

    def _assess_material_readiness(self, step: ResearchStep) -> MaterialReadiness:
        digest = self._material_digest()
        issues: list[str] = []
        warnings: list[str] = []
        blocking = False

        findings_count = int(digest["findings"]["count"])
        papers_count = int(digest["papers"]["count"])
        paper_notes_count = int(digest["paper_notes"]["count"])
        claims_count = int(digest["claims"]["count"])
        sources_count = int(digest.get("sources", {}).get("count", 0))
        material_notes_count = int(digest.get("material_notes", {}).get("count", 0))
        insights_count = int(digest.get("insights", {}).get("count", 0))
        review_notes_chars = int(digest.get("review_notes", {}).get("chars", 0))
        outline_chars = int(digest["outline"]["chars"])
        debate_chars = int(digest["debate_log"]["chars"])
        report_chars = int(digest["report"]["chars"])
        scratchpad_chars = int(digest["scratchpad"]["chars"])
        traceable_findings = int(digest["findings"]["traceable_count"])

        if step.key == "literature_search":
            if findings_count:
                warnings.append("literature_search starts with existing findings; avoid duplicating the same evidence.")
            min_papers = self._step_min_papers(step)
            if papers_count < min_papers:
                warnings.append(
                    f"literature_search should collect at least {min_papers} qualified papers for a literature review; current papers={papers_count}."
                )
        elif step.key == "information_search":
            if findings_count:
                warnings.append("information_search starts with existing findings; avoid duplicating the same evidence.")
            min_sources = self._step_min_papers(step)
            if sources_count < min_sources:
                warnings.append(
                    f"information_search should collect at least {min_sources} qualified sources; current sources={sources_count}."
                )
        elif step.key == "paper_enrichment":
            if papers_count == 0:
                issues.append("paper_enrichment requires papers from literature_search, but papers.jsonl is empty.")
                blocking = True
            elif paper_notes_count == 0:
                warnings.append("paper_enrichment should create paper_notes.jsonl from abstracts/web/PDF before synthesis.")
        elif step.key == "material_reading":
            if sources_count == 0:
                issues.append("material_reading requires sources from information_search, but sources.jsonl is empty.")
                blocking = True
            elif material_notes_count == 0:
                warnings.append("material_reading should create material_notes.jsonl from sources before synthesis.")
        elif step.key == "knowledge_synthesis":
            if findings_count == 0:
                issues.append("knowledge_synthesis requires findings, but findings.jsonl is empty.")
                blocking = True
            if self.mode == "visual":
                if sources_count == 0:
                    warnings.append("sources.jsonl is empty; synthesize from findings and mark source coverage as weak.")
                if material_notes_count == 0:
                    warnings.append("material_notes.jsonl is empty; synthesis will be abstract-level and should mark evidence depth as weak.")
            else:
                if papers_count == 0:
                    warnings.append("papers.jsonl is empty; synthesize from findings and mark citation coverage as weak.")
                if paper_notes_count == 0:
                    warnings.append("paper_notes.jsonl is empty; synthesis will be abstract/metadata-level and should mark evidence depth as weak.")
        elif step.key == "claim_generation":
            if findings_count == 0:
                issues.append("claim_generation requires structured findings, but findings.jsonl is empty.")
                blocking = True
            elif traceable_findings == 0:
                warnings.append("No finding has source_url or evidence; generated claims must remain provisional.")
            if scratchpad_chars == 0:
                warnings.append("scratchpad synthesis is missing; use findings directly and record assumptions.")
        elif step.key == "insight_generation":
            if findings_count == 0:
                issues.append("insight_generation requires structured findings, but findings.jsonl is empty.")
                blocking = True
            if scratchpad_chars == 0:
                warnings.append("scratchpad synthesis is missing; use findings directly and record assumptions.")
        elif step.key == "claim_debate":
            if claims_count == 0:
                issues.append("claim_debate requires candidate claims from claim_generation, but claims.jsonl is empty.")
                blocking = True
            if findings_count == 0:
                issues.append("claim_debate requires evidence findings, but findings.jsonl is empty.")
                blocking = True
        elif step.key == "insight_review":
            if insights_count == 0:
                issues.append("insight_review requires insights from insight_generation, but insights.jsonl is empty.")
                blocking = True
            if findings_count == 0:
                issues.append("insight_review requires evidence findings, but findings.jsonl is empty.")
                blocking = True
        elif step.key == "outline_build":
            if self.mode == "visual":
                if insights_count == 0:
                    issues.append("outline_build requires insights, but insights.jsonl is empty.")
                    blocking = True
            else:
                if claims_count == 0:
                    issues.append("outline_build requires candidate claims/gaps, but claims.jsonl is empty.")
                    blocking = True
            if findings_count == 0:
                issues.append("outline_build requires findings, but findings.jsonl is empty.")
                blocking = True
            if self.mode == "visual":
                if not review_notes_chars:
                    warnings.append("review_notes.md is empty; outline should mark insight priorities as provisional.")
            elif debate_chars == 0:
                warnings.append("debate_log.md is empty; outline should mark claim priorities as provisional.")
        elif step.key == "section_draft":
            if outline_chars == 0:
                issues.append("section_draft requires outline.md from outline_build, but outline is empty or missing.")
                blocking = True
            if findings_count == 0:
                issues.append("section_draft requires findings for evidence-backed writing, but findings.jsonl is empty.")
                blocking = True
            if self.mode == "visual":
                if insights_count == 0:
                    warnings.append("insights.jsonl is empty; draft should avoid unsupported strong claims.")
                if sources_count == 0:
                    warnings.append("sources.jsonl is empty; draft must cite source_url from findings and mark source gap.")
                if material_notes_count == 0:
                    warnings.append("material_notes.jsonl is empty; draft should avoid detailed claims that require full reading.")
            else:
                if claims_count == 0:
                    warnings.append("claims.jsonl is empty; draft should avoid unsupported strong claims.")
                if papers_count == 0:
                    warnings.append("papers.jsonl is empty; draft must cite source_url from findings and mark bibliography gap.")
                if paper_notes_count == 0:
                    warnings.append("paper_notes.jsonl is empty; draft should avoid detailed claims that require full paper reading.")
        elif step.key == "multi_agent_review":
            if report_chars == 0:
                issues.append("multi_agent_review requires research_report.md, but the report is empty or missing.")
                blocking = True
            if findings_count == 0:
                warnings.append("findings.jsonl is empty; review should flag evidence coverage as missing.")
        elif step.key == "visual_design":
            if report_chars == 0:
                issues.append("visual_design requires section_draft output (research_report.md), but report is empty.")
                blocking = True
            if outline_chars == 0:
                warnings.append("outline.md is empty; visual design may lack section structure.")
            if insights_count == 0:
                warnings.append("insights.jsonl is empty; visual design may lack insight-driven charts.")
            if findings_count == 0:
                warnings.append("findings.jsonl is empty; visual design evidence coverage may be weak.")
        elif step.key == "quality_review":
            if report_chars == 0:
                issues.append("quality_review requires research_report.md, but the report is empty or missing.")
                blocking = True
            if findings_count == 0:
                warnings.append("findings.jsonl is empty; review should flag evidence coverage as missing.")

        digest["readiness"] = {
            "step": step.key,
            "ready": not blocking,
            "blocking": blocking,
            "issues": issues,
            "warnings": warnings,
        }
        return MaterialReadiness(
            ready=not blocking,
            blocking=blocking,
            issues=issues,
            warnings=warnings,
            digest=digest,
        )

    def _material_digest(self) -> dict[str, Any]:
        findings = read_jsonl(self.artifacts.findings)
        papers = read_jsonl(self.artifacts.papers)
        paper_notes = read_jsonl(self.artifacts.paper_notes)
        claims = read_jsonl(self.artifacts.claims)
        sources = read_jsonl(self.artifacts.sources)
        material_notes = read_jsonl(self.artifacts.material_notes)
        insights = read_jsonl(self.artifacts.insights)
        review_notes = read_jsonl(self.artifacts.review_notes)
        report_text = self._read_artifact_text(self.artifacts.report_md)
        scratchpad_text = self._read_artifact_text(self.artifacts.scratchpad)
        debate_text = self._read_artifact_text(self.artifacts.debate_log)
        outline_text = self._read_artifact_text(self.artifacts.outline)
        review_text = self._read_artifact_text(self.artifacts.review)

        digest: dict[str, Any] = {
            "findings": {
                "path": str(self.artifacts.findings),
                "count": len(findings),
                "traceable_count": self._count_traceable_findings(findings),
                "sample": self._sample_rows(findings, ["finding", "evidence", "source_url"], limit=5),
            },
            "papers": {
                "path": str(self.artifacts.papers),
                "count": len(papers),
                "sample": self._sample_rows(papers, ["title", "year", "source_url", "relevance"], limit=5),
            },
            "paper_notes": {
                "path": str(self.artifacts.paper_notes),
                "count": len(paper_notes),
                "sample": self._sample_rows(
                    paper_notes,
                    ["title", "problem", "method", "main_findings", "limitations", "evidence_source"],
                    limit=5,
                ),
            },
            "claims": {
                "path": str(self.artifacts.claims),
                "count": len(claims),
                "sample": self._sample_rows(claims, ["claim", "claim_type", "priority", "source_urls"], limit=5),
            },
            "report": {
                "path": str(self.artifacts.report_md),
                "exists": self.artifacts.report_md.exists(),
                "chars": len(report_text),
                "sections": self._existing_report_sections(report_text),
            },
            "scratchpad": {
                "path": str(self.artifacts.scratchpad),
                "exists": self.artifacts.scratchpad.exists(),
                "chars": len(scratchpad_text),
                "headings": self._markdown_headings(scratchpad_text, limit=8),
            },
            "debate_log": {
                "path": str(self.artifacts.debate_log),
                "exists": self.artifacts.debate_log.exists(),
                "chars": len(debate_text),
                "headings": self._markdown_headings(debate_text, limit=8),
            },
            "outline": {
                "path": str(self.artifacts.outline),
                "exists": self.artifacts.outline.exists(),
                "chars": len(outline_text),
                "headings": self._markdown_headings(outline_text, limit=12),
            },
            "review": {
                "path": str(self.artifacts.review),
                "exists": self.artifacts.review.exists(),
                "chars": len(review_text),
                "headings": self._markdown_headings(review_text, limit=8),
            },
        }
        if self.mode == "visual":
            digest["sources"] = {
                "path": str(self.artifacts.sources),
                "count": len(sources),
                "sample": self._sample_rows(sources, ["title", "source_type", "source_url", "relevance"], limit=5),
            }
            digest["material_notes"] = {
                "path": str(self.artifacts.material_notes),
                "count": len(material_notes),
                "sample": self._sample_rows(
                    material_notes,
                    ["title", "problem", "method", "main_findings", "limitations", "evidence_source"],
                    limit=5,
                ),
            }
            digest["insights"] = {
                "path": str(self.artifacts.insights),
                "count": len(insights),
                "sample": self._sample_rows(insights, ["insight", "insight_type", "priority", "source_urls"], limit=5),
            }
            digest["review_notes"] = {
                "path": str(self.artifacts.review_notes),
                "exists": self.artifacts.review_notes.exists(),
                "chars": len(self._read_artifact_text(self.artifacts.review_notes)),
                "headings": self._markdown_headings(self._read_artifact_text(self.artifacts.review_notes), limit=8),
            }
        return digest

    @staticmethod
    def _read_artifact_text(path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _sample_rows(rows: list[dict[str, Any]], fields: list[str], limit: int) -> list[dict[str, Any]]:
        sample: list[dict[str, Any]] = []
        for row in rows[: max(0, int(limit))]:
            item: dict[str, Any] = {}
            for field in fields:
                value = row.get(field, "")
                if isinstance(value, str) and len(value) > 240:
                    value = value[:237] + "..."
                item[field] = value
            sample.append(item)
        return sample

    @staticmethod
    def _count_traceable_findings(findings: list[dict[str, Any]]) -> int:
        return sum(
            1
            for row in findings
            if str(row.get("source_url", "") or "").strip()
            or str(row.get("evidence", "") or "").strip()
        )

    @staticmethod
    def _existing_report_sections(report_text: str) -> list[str]:
        return [line[3:].strip() for line in report_text.splitlines() if line.startswith("## ")]

    @staticmethod
    def _markdown_headings(text: str, limit: int) -> list[str]:
        headings = [line.lstrip("#").strip() for line in text.splitlines() if line.startswith("#")]
        return headings[: max(0, int(limit))]

    def _offline_step_result(self, step: ResearchStep) -> ResearchStepResult:
        gate = self.gates.check_step(step)
        return ResearchStepResult(
            step=step.key,
            status="partial",
            summary=f"{step.title} scaffolded without live agent execution.",
            artifacts=self._step_artifacts(step),
            issues=["live agent execution skipped", *gate.issues],
            metadata={"gate_stats": gate.stats},
        )

    def _write_offline_scaffold(self, reason: str) -> None:
        lines = [f"# Research Report: {self.request.topic}", ""]
        for step in self._resolve_steps():
            lines.extend(
                [
                    f"## {step.expected_section}",
                    "",
                    f"待执行。{reason}",
                    "",
                ]
            )
        self.artifacts.report_md.write_text("\n".join(lines), encoding="utf-8")
        self.artifacts.scratchpad.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts.scratchpad.write_text(
            f"# Research Scratchpad\n\nTopic: {self.request.topic}\n\n{reason}\n",
            encoding="utf-8",
        )
        append_jsonl(
            self.artifacts.findings,
            {
                "topic": self.request.topic,
                "finding": "Research pipeline scaffold created; live evidence collection pending.",
                "evidence": reason,
                "confidence": "low",
            },
        )

    def _derive_structured_artifacts(self) -> None:
        report_text = self.artifacts.report_md.read_text(encoding="utf-8") if self.artifacts.report_md.exists() else ""
        if self.mode == "visual":
            ensure_text_artifact(self.artifacts.review_notes, "洞察审校与优先级评估", self._extract_section(report_text, "洞察审校与优先级评估"))
            ensure_text_artifact(self.artifacts.outline, "结构化报告大纲", self._extract_section(report_text, "结构化报告大纲"))
            ensure_text_artifact(self.artifacts.review, "质量审校意见", self._extract_section(report_text, "质量审校意见"))

            if not self.artifacts.sources.exists():
                self.artifacts.sources.write_text("", encoding="utf-8")
            if not self.artifacts.material_notes.exists():
                self.artifacts.material_notes.write_text("", encoding="utf-8")
            if not self.artifacts.insights.exists():
                append_jsonl(
                    self.artifacts.insights,
                    {
                        "topic": self.request.topic,
                        "insight": self._extract_section(report_text, "洞察、结论与趋势判断")[:1000],
                        "status": "candidate" if "洞察、结论与趋势判断" in report_text else "pending",
                    },
                )
        else:
            ensure_text_artifact(self.artifacts.debate_log, "观点辩论与优先级评估", self._extract_section(report_text, "观点辩论与优先级评估"))
            ensure_text_artifact(self.artifacts.outline, "结构化论文大纲", self._extract_section(report_text, "结构化论文大纲"))
            ensure_text_artifact(self.artifacts.review, "多视角审稿意见", self._extract_section(report_text, "多视角审稿意见"))

            if not self.artifacts.papers.exists():
                self.artifacts.papers.write_text("", encoding="utf-8")
            if not self.artifacts.paper_notes.exists():
                self.artifacts.paper_notes.write_text("", encoding="utf-8")
            if not self.artifacts.claims.exists():
                append_jsonl(
                    self.artifacts.claims,
                    {
                        "topic": self.request.topic,
                        "claim": self._extract_section(report_text, "研究空白、未来方向与可检验问题")[:1000],
                        "status": "candidate" if "研究空白、未来方向与可检验问题" in report_text else "pending",
                    },
                )

    def _export_requested_format(self) -> None:
        if self.mode == "visual":
            if self.request.output_format != "html":
                self._emit_progress(
                    f"visual mode overrides output_format={self.request.output_format} to html"
                )
            if not self._read_artifact_text(self.artifacts.report_md).strip():
                message = "visual HTML export skipped because canonical markdown report is missing or empty"
                self.pipeline_issues.append(message)
                self._emit_progress(message)
                return
            try:
                export_visual_html(
                    self.artifacts.report_md,
                    self.artifacts.report_visual_html,
                    self.request.topic,
                    artifacts=self.artifacts,
                )
            except ValueError as exc:
                self.pipeline_issues.append(str(exc))
                self._emit_progress(f"visual HTML export skipped: {exc}")
        elif self.request.output_format == "latex":
            export_latex(
                self.artifacts.report_md,
                self.artifacts.paper_tex,
                self.request.topic,
                papers_path=self.artifacts.papers,
                bib_path=self.artifacts.references_bib,
            )
        elif self.request.output_format == "html":
            export_html(self.artifacts.report_md, self.artifacts.report_html, self.request.topic)

    def _primary_report_path(self) -> str:
        if self.mode == "visual":
            if self.artifacts.report_visual_html.exists() and self.artifacts.report_visual_html.stat().st_size > 0:
                return str(self.artifacts.report_visual_html)
            return str(self.artifacts.report_md)
        if self.request.output_format == "latex":
            return str(self.artifacts.paper_tex)
        if self.request.output_format == "html":
            return str(self.artifacts.report_html)
        return str(self.artifacts.report_md)

    def _step_artifacts(self, step: ResearchStep) -> list[ResearchArtifact]:
        artifacts = [ResearchArtifact(type="report_section", path=str(self.artifacts.report_md), description=step.expected_section)]
        if step.key == "literature_search":
            artifacts.append(ResearchArtifact(type="papers", path=str(self.artifacts.papers), description="Literature records"))
        elif step.key == "information_search":
            artifacts.append(ResearchArtifact(type="sources", path=str(self.artifacts.sources), description="Information source records"))
        elif step.key == "paper_enrichment":
            artifacts.append(ResearchArtifact(type="paper_notes", path=str(self.artifacts.paper_notes), description="Lightweight structured paper notes"))
        elif step.key == "material_reading":
            artifacts.append(ResearchArtifact(type="material_notes", path=str(self.artifacts.material_notes), description="Lightweight structured material notes"))
        elif step.key == "claim_generation":
            artifacts.append(ResearchArtifact(type="claims", path=str(self.artifacts.claims), description="Candidate claims, research gaps, and future directions"))
        elif step.key == "insight_generation":
            artifacts.append(ResearchArtifact(type="insights", path=str(self.artifacts.insights), description="Generated insights, trends, and conclusions"))
        elif step.key == "claim_debate":
            artifacts.append(ResearchArtifact(type="debate", path=str(self.artifacts.debate_log), description="Debate log"))
        elif step.key == "insight_review":
            artifacts.append(ResearchArtifact(type="review_notes", path=str(self.artifacts.review_notes), description="Insight review notes"))
        elif step.key == "outline_build":
            artifacts.append(ResearchArtifact(type="outline", path=str(self.artifacts.outline), description="Structured outline"))
        elif step.key == "multi_agent_review":
            artifacts.append(ResearchArtifact(type="review", path=str(self.artifacts.review), description="Review report"))
        elif step.key == "quality_review":
            artifacts.append(ResearchArtifact(type="review", path=str(self.artifacts.review), description="Quality review report"))
        elif step.key == "visual_design":
            artifacts.append(ResearchArtifact(type="html", path=str(self.artifacts.report_visual_html), description="Visual HTML report"))
        return artifacts

    def _depth_runtime(self) -> ResearchDepthRuntime:
        if self.request.depth == "quick":
            return ResearchDepthRuntime(
                max_attempts=min(max(1, int(self.config.max_attempts or 1)), 1),
                max_subagent_steps=min(max(1, int(self.config.max_subagent_steps or 1)), 4),
                max_parallel_subtasks=min(max(1, int(self.config.max_parallel_subtasks or 1)), 3),
                subagent_process_timeout_seconds=min(
                    max(30, int(self.config.subagent_process_timeout_seconds or 30)),
                    90,
                ),
                report_length_target="concise",
            )
        return ResearchDepthRuntime(
            max_attempts=max(1, int(self.config.max_attempts or 1)),
            max_subagent_steps=max(1, int(self.config.max_subagent_steps or 1)),
            max_parallel_subtasks=max(1, int(self.config.max_parallel_subtasks or 1)),
            subagent_process_timeout_seconds=max(30, int(self.config.subagent_process_timeout_seconds or 30)),
            report_length_target="full" if self.request.depth == "deep" else "standard",
        )

    def _depth_policy_text(self) -> str:
        if self.request.depth == "quick":
            return (
                "quick mode: optimize for a fast demo run. Keep each step concise, "
                "prefer the strongest available evidence over exhaustive coverage, "
                "avoid spawning unnecessary subtasks, and write a short report section "
                "instead of a long-form report."
            )
        if self.request.depth == "deep":
            return (
                "deep mode: prioritize broader evidence coverage, richer synthesis, "
                "and stricter completeness when runtime limits allow it."
            )
        return "standard mode: balance coverage, runtime, and report completeness."

    def _step_min_findings(self, step: ResearchStep) -> int:
        value = int(step.min_findings or 0)
        if self.request.depth == "quick" and value > 0:
            return min(value, 3)
        return value

    def _step_min_papers(self, step: ResearchStep) -> int:
        value = int(step.min_papers or 0)
        if self.request.depth == "quick" and value > 0:
            return min(value, 5)
        return value

    def _depth_adjusted_step(self, step: ResearchStep) -> ResearchStep:
        return replace(
            step,
            min_findings=self._step_min_findings(step),
            min_papers=self._step_min_papers(step),
        )

    def _min_findings(self) -> int:
        return {"quick": 3, "standard": 12, "deep": 20}.get(self.request.depth, 12)

    def _min_papers(self) -> int:
        return {"quick": 5, "standard": 30, "deep": 50}.get(self.request.depth, 30)

    def _min_sources(self) -> int:
        return {"quick": 4, "standard": 15, "deep": 25}.get(self.request.depth, 15)

    def _has_llm_config(self) -> bool:
        try:
            LLMsConfig.default().get(self.config.main_model)
        except Exception:
            return False
        return True

    @staticmethod
    def _extract_section(report_text: str, title: str) -> str:
        marker = f"## {title}"
        if marker not in report_text:
            return "待补充。"
        after = report_text.split(marker, 1)[1].strip()
        next_idx = after.find("\n## ")
        if next_idx >= 0:
            after = after[:next_idx].strip()
        return after or "待补充。"
