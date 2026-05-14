from __future__ import annotations

import json
from dataclasses import dataclass
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
    read_jsonl,
)
from research.gates import ResearchGatekeeper
from research.prompts import ResearchMainPromptBuilder, ResearchSubPromptBuilder
from research.schema import ResearchArtifact, ResearchRequest, ResearchResult, ResearchStepResult
from research.skills import ResearchSkillRegistry
from research.steps import RESEARCH_STEPS, ResearchStep, required_report_sections


@dataclass(frozen=True)
class ResearchPipelineOptions:
    execute_agents: bool = True


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
    ):
        self.request = request
        self.config = config
        self.options = options or ResearchPipelineOptions()
        self.progress_callback = progress_callback
        self.artifacts = ResearchArtifacts.create(config.workspace_dir.resolve(), request)
        self.skills = ResearchSkillRegistry()
        self.gates = ResearchGatekeeper(self.artifacts)
        self.step_results: list[ResearchStepResult] = []

    async def run(self) -> ResearchResult:
        can_execute = self.options.execute_agents and self._has_llm_config()
        self._emit_progress(
            f"Research run start topic={self.request.topic!r} "
            f"steps={len(RESEARCH_STEPS)} agent_execution={can_execute} "
            f"run_dir={self.artifacts.run_dir}"
        )
        if not can_execute:
            self._write_offline_scaffold("LLM configuration is unavailable; generated research scaffold only.")

        for step in RESEARCH_STEPS:
            if can_execute:
                result = await self._run_agent_step(step)
            else:
                result = self._offline_step_result(step)
            self.step_results.append(result)
            step_index = list(RESEARCH_STEPS).index(step) + 1
            self._emit_progress(
                f"Step {step_index}/{len(RESEARCH_STEPS)} finished "
                f"key={step.key} status={result.status} issues={len(result.issues)}"
            )

        self._derive_structured_artifacts()
        self._export_requested_format()

        min_findings = self._min_findings()
        min_papers = self._min_papers()
        final_gate = self.gates.check_final(
            min_findings=min_findings,
            min_papers=min_papers,
            output_format=self.request.output_format,
        )
        step_records = [item.model_dump() for item in self.step_results]
        self.artifacts.write_manifest(self.request, step_records)

        status = "done" if final_gate.passed else "partial"
        issues = list(final_gate.issues)
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
            artifacts=self.artifacts.to_artifacts(self.request.output_format),
            steps=self.step_results,
            open_issues=issues,
            metadata={
                "topic": self.request.topic,
                "depth": self.request.depth,
                "output_format": self.request.output_format,
                "trigger": self.request.trigger,
                "mode": self.config.mode,
                "profile_name": self.config.profile_name,
                "run_dir": str(self.artifacts.run_dir),
                "manifest_path": str(self.artifacts.manifest),
                "agent_execution": can_execute,
                "gate_stats": final_gate.stats,
                "min_papers": min_papers,
            },
        )

    async def _run_agent_step(self, step: ResearchStep) -> ResearchStepResult:
        skill_text = self.skills.load_text(step.skill)
        readiness = self._assess_material_readiness(step)
        brief = self._build_step_brief(step, skill_text, readiness)
        step_required_sections = [step.expected_section] if step.report_required else []
        step_min_findings = int(step.min_findings or 0)
        step_min_papers = int(step.min_papers or 0)
        step_metadata = self._step_runtime_metadata(step, readiness)
        step_index = int(step_metadata["research_step_index"])
        executor = "multi-agent" if step.parallel_hint else "single-agent"
        self._emit_progress(
            f"Step {step_index}/{len(RESEARCH_STEPS)} start "
            f"key={step.key} title={step.title!r} executor={executor} "
            f"expected_section={step.expected_section!r} min_findings={step_min_findings} "
            f"min_papers={step_min_papers} "
            f"material_ready={readiness.ready} blocking={readiness.blocking} "
            f"issues={readiness.issues}"
        )

        if readiness.blocking:
            gate = self.gates.check_step(step)
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
                    max_attempts=self.config.max_attempts,
                    max_subagent_steps=self.config.max_subagent_steps,
                    max_parallel_subtasks=self.config.max_parallel_subtasks,
                    subagent_process_timeout_seconds=self.config.subagent_process_timeout_seconds,
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
                    max_subagent_steps=self.config.max_subagent_steps,
                    max_parallel_subtasks=self.config.max_parallel_subtasks,
                    subagent_process_timeout_seconds=self.config.subagent_process_timeout_seconds,
                    profile_name="research_mode",
                    report_filename=self.artifacts.report_md.name,
                    required_sections=step_required_sections,
                    min_findings=step_min_findings,
                    sub_prompt_builder=ResearchSubPromptBuilder,
                    runtime_metadata=step_metadata,
                )

            async for message in project.stream():
                self._log_step_message(step, message)
        except Exception as exc:
            gate = self.gates.check_step(step)
            self._emit_progress(
                f"Step {step_index}/{len(RESEARCH_STEPS)} blocked "
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

        gate = self.gates.check_step(step)
        self._emit_progress(
            f"Step {step_index}/{len(RESEARCH_STEPS)} gate "
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
        prompt_digest = self._prompt_material_digest(step.key, readiness.digest)
        digest_text = json.dumps(prompt_digest, ensure_ascii=False, indent=2)
        report_requirement = (
            f"- 必须写入或更新 markdown 报告章节: ## {step.expected_section}"
            if step.report_required
            else (
                f"- 本步骤只写 scratchpad/plan artifact，不写 research_report.md；"
                f"必须在 scratchpad 中写入或更新: ## {step.expected_section}"
            )
        )

        return f"""
任务类型: research
研究模式: 固定状态机 step 执行
当前步骤: {step.title} ({step.key})

[研究主题]
{self.request.topic}

[深度]
{self.request.depth}

[输出格式]
{self.request.output_format}

[约束]
{self.request.constraints or "无"}

[用户指定来源]
{json.dumps(self.request.sources, ensure_ascii=False)}

[产物路径]
- report_path: {self.artifacts.report_md}
- paper_tex_path: {self.artifacts.paper_tex}
- references_bib_path: {self.artifacts.references_bib}
- findings_path: {self.artifacts.findings}
- scratchpad_path: {self.artifacts.scratchpad}
- candidates_path: {self.artifacts.candidates}
- shortlist_path: {self.artifacts.shortlist}
- papers_path: {self.artifacts.papers}
- paper_notes_path: {self.artifacts.paper_notes}
- paper_cards_path: {self.artifacts.paper_cards}
- synthesis_digest_path: {self.artifacts.synthesis_digest}
- outline_context_path: {self.artifacts.outline_context}
- claims_path: {self.artifacts.claims}
- debate_log_path: {self.artifacts.debate_log}
- outline_path: {self.artifacts.outline}
- review_path: {self.artifacts.review}

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
- 当前研究型任务的最终目标是一篇可引用的 LaTeX 文献综述：paper.tex + references.bib；markdown 报告是中间稿。
- 文献检索阶段要优先形成足够大的合格论文池；标准深度目标为至少 {self._min_papers()} 篇 papers.jsonl 记录和至少 {self._min_findings()} 条结构化 findings。
- 正文写作阶段必须写出“Abstract/Introduction/Related Work/Literature Synthesis/Research Gaps/Future Directions/Conclusion”等论文式内容，并保留来源 URL 或 citation key。
- 优先使用专用 artifact 工具读取研究产物：read_findings、read_papers、read_paper_notes、read_paper_cards、read_research_claims、read_research_outline、read_claim_debate_log、read_research_report。
- 不要用 read_sources 读取 findings.jsonl、candidates.jsonl、shortlist.jsonl、papers.jsonl、paper_notes.jsonl、paper_cards.jsonl、claims.jsonl、outline.md、debate_log.md 或 research_report.md。
- 如果材料摘要显示上游材料缺失，不要反复读取同一空产物；应在本步骤输出中明确缺口，或基于已有材料产出 partial。
- 尽量使用 record_finding 记录带 source_url 或 evidence 的结构化发现。
- 重要中间结论写入 scratchpad，供后续步骤复用。
- 不要编造来源；来源不确定时明确标注不确定。
""".strip()

    def _step_runtime_metadata(self, step: ResearchStep, readiness: MaterialReadiness | None = None) -> dict[str, Any]:
        step_index = list(RESEARCH_STEPS).index(step) + 1
        readiness = readiness or self._assess_material_readiness(step)
        prompt_digest = self._prompt_material_digest(step.key, readiness.digest)
        return {
            "research_step_key": step.key,
            "research_step_title": step.title,
            "research_step_index": step_index,
            "research_step_total": len(RESEARCH_STEPS),
            "current_step_expected_section": step.expected_section,
            "all_required_sections": required_report_sections(),
            "current_step_requires_report_section": bool(step.report_required),
            "step_min_findings": int(step.min_findings or 0),
            "step_min_papers": int(step.min_papers or 0),
            "target_papers_for_literature_review": self._min_papers(),
            "research_completion_scope": "current_step_only",
            "require_flow_integrity": False,
            "require_verification_passed": False,
            "material_ready": readiness.ready,
            "material_blocking": readiness.blocking,
            "material_issues": list(readiness.issues),
            "material_warnings": list(readiness.warnings),
            "material_digest": prompt_digest,
            "references_bib_path": str(self.artifacts.references_bib),
            "candidates_path": str(self.artifacts.candidates),
            "shortlist_path": str(self.artifacts.shortlist),
            "paper_notes_path": str(self.artifacts.paper_notes),
            "paper_cards_path": str(self.artifacts.paper_cards),
            "synthesis_digest_path": str(self.artifacts.synthesis_digest),
            "outline_context_path": str(self.artifacts.outline_context),
        }

    def _assess_material_readiness(self, step: ResearchStep) -> MaterialReadiness:
        digest = self._material_digest()
        issues: list[str] = []
        warnings: list[str] = []
        blocking = False

        findings_count = int(digest["findings"]["count"])
        papers_count = int(digest["papers"]["count"])
        paper_notes_count = int(digest["paper_notes"]["count"])
        paper_cards_count = int(digest["paper_cards"]["count"])
        synthesis_chars = int(digest["synthesis_digest"]["chars"])
        claims_count = int(digest["claims"]["count"])
        outline_chars = int(digest["outline"]["chars"])
        debate_chars = int(digest["debate_log"]["chars"])
        report_chars = int(digest["report"]["chars"])
        scratchpad_chars = int(digest["scratchpad"]["chars"])
        direct_isac_findings = int(digest["findings"]["direct_isac_count"])

        if step.key == "literature_search":
            if findings_count:
                warnings.append("literature_search starts with existing findings; avoid duplicating the same evidence.")
            if papers_count < int(step.min_papers or 0):
                warnings.append(
                    f"literature_search should collect at least {step.min_papers} qualified papers for a literature review; current papers={papers_count}."
                )
        elif step.key == "paper_enrichment":
            if papers_count == 0:
                issues.append("paper_enrichment requires papers from literature_search, but papers.jsonl is empty.")
                blocking = True
            elif paper_notes_count == 0:
                warnings.append("paper_enrichment should run batch_paper_enrichment to create abstract-level paper_notes.jsonl before synthesis.")
            elif paper_notes_count < min(int(step.min_papers or 0), papers_count):
                warnings.append(
                    f"paper_enrichment should enrich top relevant papers; paper_notes={paper_notes_count}, expected={min(int(step.min_papers or 0), papers_count)}."
                )
            if paper_cards_count == 0:
                warnings.append("paper_enrichment should also create paper_cards.jsonl knowledge cards for final LaTeX drafting.")
        elif step.key == "knowledge_synthesis":
            if paper_cards_count == 0:
                issues.append("knowledge_synthesis requires paper_cards.jsonl from paper_enrichment, but it is empty.")
                blocking = True
            if synthesis_chars == 0:
                warnings.append("knowledge_synthesis should run batch_knowledge_synthesis to create synthesis_digest.json.")
        elif step.key == "claim_generation":
            if synthesis_chars == 0:
                issues.append("claim_generation requires synthesis_digest.json from knowledge_synthesis, but it is empty.")
                blocking = True
            elif findings_count and direct_isac_findings == 0:
                warnings.append("No finding directly mentions ISAC/通信感知一体化/通感; generated claims must mark relevance uncertainty.")
            if scratchpad_chars == 0:
                warnings.append("scratchpad synthesis is missing; use findings directly and record assumptions.")
        elif step.key == "claim_debate":
            if claims_count == 0:
                issues.append("claim_debate requires candidate claims from claim_generation, but claims.jsonl is empty.")
                blocking = True
            if findings_count == 0:
                issues.append("claim_debate requires evidence findings, but findings.jsonl is empty.")
                blocking = True
        elif step.key == "outline_build":
            if claims_count == 0:
                issues.append("outline_build requires candidate claims/gaps, but claims.jsonl is empty.")
                blocking = True
            if synthesis_chars == 0:
                issues.append("outline_build requires synthesis_digest.json, but it is empty.")
                blocking = True
            if debate_chars == 0:
                warnings.append("debate_log.md is empty; outline should mark claim priorities as provisional.")
        elif step.key == "section_draft":
            if outline_chars == 0:
                issues.append("section_draft requires outline.md from outline_build, but outline is empty or missing.")
                blocking = True
            if findings_count == 0:
                issues.append("section_draft requires findings for evidence-backed writing, but findings.jsonl is empty.")
                blocking = True
            if claims_count == 0:
                warnings.append("claims.jsonl is empty; draft should avoid unsupported strong claims.")
            if papers_count == 0:
                warnings.append("papers.jsonl is empty; draft must cite source_url from findings and mark bibliography gap.")
            if paper_notes_count == 0:
                warnings.append("paper_notes.jsonl is empty; draft should avoid detailed claims that require full paper reading.")
            if paper_cards_count == 0:
                warnings.append("paper_cards.jsonl is empty; final LaTeX should avoid detailed per-paper comparison tables.")
        elif step.key == "multi_agent_review":
            if report_chars == 0:
                issues.append("multi_agent_review requires research_report.md, but the report is empty or missing.")
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
        candidates = read_jsonl(self.artifacts.candidates)
        shortlist = read_jsonl(self.artifacts.shortlist)
        papers = read_jsonl(self.artifacts.papers)
        paper_notes = read_jsonl(self.artifacts.paper_notes)
        paper_cards = read_jsonl(self.artifacts.paper_cards)
        claims = read_jsonl(self.artifacts.claims)
        synthesis_text = self._read_artifact_text(self.artifacts.synthesis_digest)
        report_text = self._read_artifact_text(self.artifacts.report_md)
        scratchpad_text = self._read_artifact_text(self.artifacts.scratchpad)
        debate_text = self._read_artifact_text(self.artifacts.debate_log)
        outline_text = self._read_artifact_text(self.artifacts.outline)
        review_text = self._read_artifact_text(self.artifacts.review)
        outline_context = self._build_outline_context(
            synthesis_text=synthesis_text,
            claims=claims,
            debate_text=debate_text,
            paper_cards=paper_cards,
        )
        self._write_outline_context(outline_context)

        return {
            "findings": {
                "path": str(self.artifacts.findings),
                "count": len(findings),
                "direct_isac_count": self._count_direct_isac_findings(findings),
                "sample": self._sample_rows(findings, ["finding", "evidence", "source_url"], limit=5),
            },
            "papers": {
                "path": str(self.artifacts.papers),
                "count": len(papers),
                "sample": self._sample_rows(papers, ["title", "year", "source_url", "relevance"], limit=5),
            },
            "candidates": {
                "path": str(self.artifacts.candidates),
                "count": len(candidates),
                "sample": self._sample_rows(candidates, ["title", "year", "source_url", "candidate_backend"], limit=5),
            },
            "shortlist": {
                "path": str(self.artifacts.shortlist),
                "count": len(shortlist),
                "sample": self._sample_rows(shortlist, ["title", "screening_score", "screening_reasons"], limit=5),
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
            "paper_cards": {
                "path": str(self.artifacts.paper_cards),
                "count": len(paper_cards),
                "sample": self._sample_rows(
                    paper_cards,
                    ["title", "problem", "method", "key_result", "limitations", "evidence_level"],
                    limit=5,
                ),
            },
            "synthesis_digest": {
                "path": str(self.artifacts.synthesis_digest),
                "exists": self.artifacts.synthesis_digest.exists(),
                "chars": len(synthesis_text),
                "summary": self._synthesis_digest_summary(synthesis_text),
            },
            "outline_context": outline_context,
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

    def _prompt_material_digest(self, step_key: str, digest: dict[str, Any]) -> dict[str, Any]:
        """Return a step-scoped compact digest for prompts.

        The full readiness digest is useful for gates and logs, but putting the
        same large artifact samples into both the step brief and prompt metadata
        can exceed model limits.  The prompt only needs the materials that can
        steer the current step.
        """

        def slim_block(name: str, sample_limit: int = 0) -> dict[str, Any]:
            block = dict(digest.get(name, {}) or {})
            sample = list(block.get("sample", []) or [])
            if sample_limit <= 0:
                block.pop("sample", None)
            else:
                block["sample"] = self._truncate_sample_rows(sample[:sample_limit], limit=140)
            return block

        base = {
            "findings": slim_block("findings", 3),
            "papers": slim_block("papers", 3),
            "paper_cards": slim_block("paper_cards", 3),
            "synthesis_digest": digest.get("synthesis_digest", {}),
            "claims": slim_block("claims", 3),
            "report": digest.get("report", {}),
            "scratchpad": digest.get("scratchpad", {}),
            "outline": digest.get("outline", {}),
            "debate_log": digest.get("debate_log", {}),
            "readiness": digest.get("readiness", {}),
        }

        if step_key == "knowledge_synthesis":
            base["paper_cards"] = slim_block("paper_cards", 8)
            base["paper_notes"] = slim_block("paper_notes", 3)
            base["findings"] = slim_block("findings", 8)
            base["synthesis_digest"] = digest.get("synthesis_digest", {})
        elif step_key == "outline_build":
            base = {
                "counts": {
                    name: int((digest.get(name, {}) or {}).get("count", 0) or 0)
                    for name in ["findings", "papers", "paper_notes", "paper_cards", "claims"]
                },
                "outline_context": digest.get("outline_context", {}),
                "synthesis_digest": {
                    "path": (digest.get("synthesis_digest", {}) or {}).get("path", ""),
                    "exists": (digest.get("synthesis_digest", {}) or {}).get("exists", False),
                    "chars": (digest.get("synthesis_digest", {}) or {}).get("chars", 0),
                    "full_content_in_prompt": False,
                },
                "report": digest.get("report", {}),
                "readiness": digest.get("readiness", {}),
                "prompt_policy": (
                    "Use outline_context as the only outline-generation context. Do not inject or read the full "
                    "synthesis_digest.json, full candidates/shortlist, full paper_cards, or full subtask history."
                ),
            }
        elif step_key == "section_draft":
            base["paper_cards"] = slim_block("paper_cards", 10)
            base["claims"] = slim_block("claims", 6)
            base["findings"] = slim_block("findings", 8)
        elif step_key in {"literature_search", "paper_enrichment"}:
            base["candidates"] = slim_block("candidates", 0)
            base["shortlist"] = slim_block("shortlist", 0)
            base["paper_notes"] = slim_block("paper_notes", 0)
        else:
            base["paper_notes"] = slim_block("paper_notes", 2)
        return base

    def _build_outline_context(
        self,
        synthesis_text: str,
        claims: list[dict[str, Any]],
        debate_text: str,
        paper_cards: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create a compact Step 6 context while preserving full artifacts on disk."""

        synthesis_summary = self._synthesis_digest_summary(synthesis_text)
        representative_cards = self._representative_paper_cards(paper_cards, limit=8)
        context = {
            "path": str(self.artifacts.outline_context),
            "source_artifacts": {
                "synthesis_digest": str(self.artifacts.synthesis_digest),
                "claims": str(self.artifacts.claims),
                "debate_log": str(self.artifacts.debate_log),
                "paper_cards": str(self.artifacts.paper_cards),
            },
            "policy": {
                "full_synthesis_digest_preserved": True,
                "full_synthesis_digest_in_prompt": False,
                "full_tool_output_in_prompt": False,
                "full_subtask_history_in_prompt": False,
            },
            "topic_clusters": synthesis_summary.get("clusters", []),
            "research_gaps": synthesis_summary.get("research_gaps", []),
            "claims_summary": self._truncate_sample_rows(
                self._sample_rows(
                    claims,
                    ["claim", "claim_type", "priority", "evidence_basis", "source_urls"],
                    limit=8,
                ),
                limit=220,
            ),
            "debate_decisions": self._debate_decision_summary(debate_text, limit=12),
            "representative_paper_cards": representative_cards,
            "outline_requirements": [
                "生成标准文献综述论文大纲，而不是实验论文大纲。",
                "必须包含摘要、研究背景/目的与意义、研究现状、方法与主题综合、研究空白与未来方向、结论。",
                "章节设计应基于主题簇、research gaps、claims、debate 决策和代表论文卡片。",
                "不要基于原始检索列表直接生成大纲。",
            ],
        }
        return context

    def _write_outline_context(self, context: dict[str, Any]) -> None:
        self.artifacts.outline_context.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts.outline_context.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")

    def _representative_paper_cards(self, paper_cards: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        for row in paper_cards:
            title = str(row.get("title", "") or "").strip()
            if not title or title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())
            selected.append(
                {
                    "title": title[:180],
                    "year": row.get("year", ""),
                    "source_url": row.get("source_url", ""),
                    "problem": str(row.get("problem", "") or "")[:220],
                    "method": str(row.get("method", "") or "")[:220],
                    "key_result": str(row.get("key_result") or row.get("main_findings") or "")[:260],
                    "limitations": str(row.get("limitations", "") or "")[:180],
                    "evidence_level": row.get("evidence_level", row.get("evidence_source", "")),
                }
            )
            if len(selected) >= max(1, int(limit or 8)):
                break
        return selected

    @staticmethod
    def _debate_decision_summary(text: str, limit: int = 12) -> list[str]:
        decisions: list[str] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            lowered = line.lower()
            if any(token in lowered for token in ["keep", "revise", "downgrade", "remove", "保留", "修订", "降级", "移除"]):
                decisions.append(line[:260])
            if len(decisions) >= max(1, int(limit or 12)):
                break
        if not decisions and text.strip():
            decisions = [line.strip()[:260] for line in text.splitlines() if line.strip()][: max(1, int(limit or 12))]
        return decisions

    @staticmethod
    def _truncate_sample_rows(rows: list[dict[str, Any]], limit: int = 140) -> list[dict[str, Any]]:
        trimmed: list[dict[str, Any]] = []
        max_len = max(40, int(limit or 140))
        for row in rows:
            item: dict[str, Any] = {}
            for key, value in row.items():
                if isinstance(value, str):
                    item[key] = value[: max_len - 3].rstrip() + "..." if len(value) > max_len else value
                elif isinstance(value, list):
                    item[key] = value[:5]
                else:
                    item[key] = value
            trimmed.append(item)
        return trimmed

    @staticmethod
    def _read_artifact_text(path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _synthesis_digest_summary(text: str) -> dict[str, Any]:
        if not text.strip():
            return {}
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return {"invalid_json": True, "chars": len(text)}
        if not isinstance(value, dict):
            return {"invalid_json": True, "chars": len(text)}
        clusters = value.get("clusters", []) if isinstance(value.get("clusters"), list) else []
        gaps = value.get("research_gaps", []) if isinstance(value.get("research_gaps"), list) else []
        return {
            "cluster_count": len(clusters),
            "research_gap_count": len(gaps),
            "clusters": [
                {
                    "cluster": item.get("cluster", ""),
                    "paper_count": item.get("paper_count", 0),
                    "representative_titles": list(item.get("representative_titles", []) or [])[:3],
                }
                for item in clusters[:8]
                if isinstance(item, dict)
            ],
            "research_gaps": [
                {
                    "gap": str(item.get("gap", "") or "")[:220],
                    "cluster": item.get("cluster", ""),
                    "source_urls": list(item.get("source_urls", []) or [])[:3],
                }
                for item in gaps[:8]
                if isinstance(item, dict)
            ],
        }

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
    def _count_direct_isac_findings(findings: list[dict[str, Any]]) -> int:
        keywords = ("isac", "integrated sensing", "通信感知一体化", "通感一体化", "感知")
        count = 0
        for row in findings:
            text = json.dumps(row, ensure_ascii=False).lower()
            if any(keyword.lower() in text for keyword in keywords):
                count += 1
        return count

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
        for step in RESEARCH_STEPS:
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
        ensure_text_artifact(self.artifacts.debate_log, "观点辩论与优先级评估", self._extract_section(report_text, "观点辩论与优先级评估"))
        ensure_text_artifact(self.artifacts.outline, "结构化论文大纲", self._extract_section(report_text, "结构化论文大纲"))
        ensure_text_artifact(self.artifacts.review, "多视角审稿意见", self._extract_section(report_text, "多视角审稿意见"))

        if not self.artifacts.papers.exists():
            self.artifacts.papers.write_text("", encoding="utf-8")
        if not self.artifacts.candidates.exists():
            self.artifacts.candidates.write_text("", encoding="utf-8")
        if not self.artifacts.shortlist.exists():
            self.artifacts.shortlist.write_text("", encoding="utf-8")
        if not self.artifacts.paper_notes.exists():
            self.artifacts.paper_notes.write_text("", encoding="utf-8")
        if not self.artifacts.paper_cards.exists():
            self.artifacts.paper_cards.write_text("", encoding="utf-8")
        if not self.artifacts.synthesis_digest.exists():
            self.artifacts.synthesis_digest.write_text("", encoding="utf-8")
        if not self.artifacts.outline_context.exists():
            self.artifacts.outline_context.write_text("{}", encoding="utf-8")
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
        if self.request.output_format == "latex":
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
        if self.request.output_format == "latex":
            return str(self.artifacts.paper_tex)
        if self.request.output_format == "html":
            return str(self.artifacts.report_html)
        return str(self.artifacts.report_md)

    def _step_artifacts(self, step: ResearchStep) -> list[ResearchArtifact]:
        artifacts = [ResearchArtifact(type="report_section", path=str(self.artifacts.report_md), description=step.expected_section)]
        if step.key == "literature_search":
            artifacts.append(ResearchArtifact(type="candidates", path=str(self.artifacts.candidates), description="Raw literature candidates"))
            artifacts.append(ResearchArtifact(type="shortlist", path=str(self.artifacts.shortlist), description="Screened literature shortlist"))
            artifacts.append(ResearchArtifact(type="papers", path=str(self.artifacts.papers), description="Literature records"))
        elif step.key == "paper_enrichment":
            artifacts.append(ResearchArtifact(type="paper_notes", path=str(self.artifacts.paper_notes), description="Lightweight structured paper notes"))
            artifacts.append(ResearchArtifact(type="paper_cards", path=str(self.artifacts.paper_cards), description="Structured paper knowledge cards"))
        elif step.key == "knowledge_synthesis":
            artifacts.append(ResearchArtifact(type="synthesis_digest", path=str(self.artifacts.synthesis_digest), description="Clustered synthesis digest"))
            artifacts.append(ResearchArtifact(type="outline_context", path=str(self.artifacts.outline_context), description="Compact context prepared for outline generation"))
            artifacts.append(ResearchArtifact(type="findings", path=str(self.artifacts.findings), description="Cross-paper research gap findings"))
        elif step.key == "claim_generation":
            artifacts.append(ResearchArtifact(type="claims", path=str(self.artifacts.claims), description="Candidate claims, research gaps, and future directions"))
        elif step.key == "claim_debate":
            artifacts.append(ResearchArtifact(type="debate", path=str(self.artifacts.debate_log), description="Debate log"))
        elif step.key == "outline_build":
            artifacts.append(ResearchArtifact(type="outline_context", path=str(self.artifacts.outline_context), description="Compact context used for outline generation"))
            artifacts.append(ResearchArtifact(type="outline", path=str(self.artifacts.outline), description="Structured outline"))
        elif step.key == "multi_agent_review":
            artifacts.append(ResearchArtifact(type="review", path=str(self.artifacts.review), description="Review report"))
        return artifacts

    def _min_findings(self) -> int:
        return {"quick": 8, "standard": 12, "deep": 20}.get(self.request.depth, 12)

    def _min_papers(self) -> int:
        return {"quick": 10, "standard": 30, "deep": 50}.get(self.request.depth, 30)

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
