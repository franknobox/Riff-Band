from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai4ms.assets import DataAssetService
from ai4ms.db.store import ProjectStore, RevisionConflictError
from ai4ms.delivery import (
    AcademicOutputQualityService,
    DeliveryExportError,
    DeliveryExportService,
)
from ai4ms.knowledge import KnowledgeEvaluationService, KnowledgeRegistry
from ai4ms.literature import LiteratureCoverageAuditor
from ai4ms.literature.service import LiteratureSearchService
from ai4ms.orchestration import AOrchestraStageService
from ai4ms.prompts import PromptCatalog, get_stage_policy
from ai4ms.reporting import build_ai_report_envelope
from ai4ms.runners import (
    AnalysisJobConflictError,
    AnalysisJobService,
    AnalysisRunnerService,
)
from ai4ms.runners.stata import sha256_file
from ai4ms.search import WebResearchService
from ai4ms.services.models import (
    STAGE_DEFINITIONS,
    STAGES_BY_KEY,
    ApprovalDecision,
    AnalysisRerunRequest,
    AnalysisRunRequest,
    CreateProjectRequest,
    DraftRequest,
    EvidenceCandidateReviewRequest,
    EvidenceDiscoveryRequest,
    EvidenceRecordPatchRequest,
    KnowledgeCandidateReviewRequest,
    KnowledgeDiscoveryRequest,
    KnowledgeEvaluationRequest,
    KnowledgeRecordCreateRequest,
    KnowledgeRecordPatchRequest,
    LiteraturePlanReviewRequest,
    LiteratureSearchRequest,
    LiteratureScreeningRequest,
    ProblemQuestionSelectionRequest,
    StageChatRequest,
    StageDecisionRequest,
    StageAssetSectionPatchRequest,
    StageRestoreRequest,
    StageSuggestionDecisionRequest,
    StageSuggestionGenerateRequest,
    StageToolInvokeRequest,
    StageStatus,
    StageUpdateRequest,
    StageWorkspaceUpdateRequest,
    UpdateProjectRequest,
    UserProfileUpdateRequest,
)
from ai4ms.services.stage_generation import (
    StageContentValidationError,
    StageGenerationService,
)
from ai4ms.services.stage_chat import StageChatService
from ai4ms.services.stage_assistant import StageAssistantService
from ai4ms.services.knowledge_jobs import KnowledgeEvaluationJobService


class ProjectNotFoundError(LookupError):
    pass


class StageNotFoundError(LookupError):
    pass


class StageLockedError(RuntimeError):
    pass


class StageRevisionConflictError(RuntimeError):
    pass


STAGE_TEMPLATES: dict[str, dict[str, Any]] = {
    "problem": {"initial_idea": "", "research_object": "", "problem_boundary": "", "objective": "", "questions": [], "question_candidates": [], "problem_diagnostics": [], "selection_tradeoffs": [], "question_selection": {}, "candidate_gaps": [], "counter_searches": [], "unknowns": []},
    "literature": {"topic_summary": "", "query_blocks": [], "databases": [], "languages": [], "inclusion_criteria": [], "exclusion_criteria": [], "screening_questions": [], "counter_searches": [], "literature_plan_review": {}, "sources": [], "papers": [], "search_runs": [], "screening_decisions": [], "evidence_candidates": [], "evidence_library": [], "coverage_audit": {}, "paper_evidence_cards": [], "research_streams": [], "syntheses": [], "method_comparisons": [], "contradictions": [], "gap_candidates": [], "review_outline": [], "recommended_next_steps": [], "unknowns": [], "coverage_limits": []},
    "theory": {"theoretical_lenses": [], "constructs": [], "mechanisms": [], "research_questions": [], "competing_explanations": [], "falsifiable_propositions": [], "contribution_boundary": "", "unknowns": []},
    "design": {"research_question": "", "unit_of_analysis": "", "design_lane": "", "estimand_or_objective": "", "method_options": [], "primary_method_id": "", "assumptions": [], "falsification": [], "threats_to_validity": [], "stopping_conditions": [], "unknowns": []},
    "data": {"data_sources": [], "variables": [], "sample_definition": "", "time_coverage": "", "join_keys": [], "pii_class": "unknown", "privacy_risks": [], "ethics_checks": [], "quality_checks": [], "blocking_issues": [], "unknowns": []},
    "identification": {"design_lane": "", "estimand_or_objective": "", "analysis_sample": "", "unit_of_analysis": "", "variable_roles": [], "model_specifications": [], "diagnostics": [], "analysis_steps": [], "missing_data_plan": "", "multiplicity_plan": "", "robustness_plan": [], "stopping_conditions": [], "execution_engine": "unknown", "code_language": "", "stata_do_file": "", "seed": None, "expected_outputs": [], "reproducibility_requirements": [], "unknowns": []},
    "analysis": {"execution_engine": "unknown", "readiness_summary": "", "expected_outputs": [], "preflight_checks": [], "result_review_checks": [], "runner_status": "not_checked", "approved_analysis_plan_revision": 0, "approved_analysis_plan_hash": "", "do_file": "", "runs": [], "results": [], "blocking_issues": [], "unknowns": []},
    "robustness": {"robustness_matrix": [], "failed_checks": [], "interpretation_limits": [], "next_runs": [], "reproducibility_report": "", "unknowns": []},
    "evidence": {"claims": [], "mechanisms": [], "heterogeneity": [], "limitations": [], "interpretation": "", "unknowns": []},
    "delivery": {"title": "", "document_profile": None, "abstract": "", "keywords": [], "executive_summary": "", "conclusions": [], "policy_implications": [], "outline": [], "manuscript_sections": [], "logic_closure": [], "author_self_review": [], "reference_paper_ids": [], "reference_evidence_ids": [], "approved_claims": [], "references": [], "limitations": [], "reproducibility_notes": [], "disclosure": "", "release_notes": "", "unknowns": [], "exports": [], "visual_report_path": "", "word_report_path": "", "pdf_report_path": "", "stata_package_path": "", "research_package_path": "", "manifest_path": ""},
}


class ProjectService:
    def __init__(
        self,
        store: ProjectStore,
        data_dir: str | Path,
        stage_generation: StageGenerationService | None = None,
        literature_search: LiteratureSearchService | None = None,
        analysis_runner: AnalysisRunnerService | None = None,
        delivery_export: DeliveryExportService | None = None,
        knowledge_evaluation: KnowledgeEvaluationService | None = None,
        stage_chat: StageChatService | None = None,
        research_service: WebResearchService | None = None,
        stage_assistant: StageAssistantService | None = None,
    ):
        self.store = store
        self.data_dir = Path(data_dir)
        self.projects_dir = self.data_dir / "projects"
        self.stage_generation = stage_generation or StageGenerationService(
            orchestrator=AOrchestraStageService(self.projects_dir)
        )
        self.literature_search = literature_search or LiteratureSearchService(self.projects_dir)
        self.analysis_runner = analysis_runner or AnalysisRunnerService()
        self.delivery_export = delivery_export or DeliveryExportService(self.projects_dir)
        self.data_assets = DataAssetService(self.store, self.projects_dir)
        self.knowledge_evaluation = knowledge_evaluation or KnowledgeEvaluationService(
            self.projects_dir
        )
        self.knowledge_evaluation_jobs = KnowledgeEvaluationJobService(
            self.projects_dir,
            self.knowledge_evaluation,
        )
        self.stage_chat = stage_chat or StageChatService(self.projects_dir)
        self.research_service = (
            research_service
            or getattr(self.stage_chat, "research_service", None)
            or WebResearchService(self.projects_dir)
        )
        self.stage_assistant = stage_assistant or StageAssistantService(
            self.projects_dir,
            literature_search=self.literature_search,
            analysis_runner=self.analysis_runner,
        )
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.store.initialize()
        self.analysis_jobs = AnalysisJobService(
            self.projects_dir,
            self.analysis_runner,
            self.get_project,
            self._record_analysis_run,
        )

    def stage_definitions(self) -> list[dict[str, Any]]:
        definitions = []
        for stage in STAGE_DEFINITIONS:
            item = stage.model_dump()
            prompt = PromptCatalog.get(stage.key)
            item["agent_policy"] = get_stage_policy(stage.key).public_dict()
            item["prompt"] = (
                {
                    "prompt_id": prompt.prompt_id,
                    "prompt_version": prompt.version,
                }
                if prompt is not None
                else None
            )
            definitions.append(item)
        return definitions

    def get_user_profile(self) -> dict[str, Any]:
        return self.store.get_user_profile()

    def update_user_profile(
        self, request: UserProfileUpdateRequest
    ) -> dict[str, Any]:
        return self.store.update_user_profile(request.interface_theme)

    def create_project(self, request: CreateProjectRequest) -> dict[str, Any]:
        project = self.store.create_project(request.title, request.initial_idea)
        project_dir = self.projects_dir / project["project_id"]
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (project_dir / "exports").mkdir(parents=True, exist_ok=True)
        return self._enrich(project)

    def list_projects(self) -> list[dict[str, Any]]:
        return self.store.list_projects()

    def get_project(self, project_id: str) -> dict[str, Any]:
        try:
            return self._enrich(self.store.get_project(project_id))
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc

    async def upload_data_asset(
        self,
        project_id: str,
        filename: str,
        media_type: str,
        read,
    ) -> dict[str, Any]:
        self.get_project(project_id)
        return await self.data_assets.upload(
            project_id, filename, media_type, read
        )

    def list_data_assets(self, project_id: str) -> list[dict[str, Any]]:
        self.get_project(project_id)
        return self.store.list_data_assets(project_id)

    def get_stage(self, project_id: str, stage_key: str) -> dict[str, Any]:
        self._require_stage(stage_key)
        try:
            return self.store.get_stage(project_id, stage_key)
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc

    def list_stage_revisions(
        self, project_id: str, stage_key: str
    ) -> list[dict[str, Any]]:
        self._require_stage(stage_key)
        self.get_project(project_id)
        try:
            return self.store.list_stage_revisions(project_id, stage_key)
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc

    def restore_stage_revision(
        self,
        project_id: str,
        stage_key: str,
        request: StageRestoreRequest,
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, stage_key)
        try:
            source = self.store.get_stage_revision(
                project_id, stage_key, request.revision
            )
            content = deepcopy(source["content"])
            workspace = content.get("_workspace")
            if isinstance(workspace, dict):
                workspace["human_confirmed"] = False
                history = workspace.get("sync_history")
                workspace["sync_history"] = [
                    f"从 Revision {request.revision} 恢复为新草稿",
                    *(history if isinstance(history, list) else []),
                ][:100]
            result = self.store.update_stage(
                project_id=project_id,
                stage_key=stage_key,
                content=content,
                change_reason=request.change_reason
                or f"Restored revision {request.revision} as a new draft",
                author_type="human",
                expected_revision=request.expected_revision,
            )
        except RevisionConflictError as exc:
            raise StageRevisionConflictError(str(exc)) from exc
        except KeyError as exc:
            raise StageNotFoundError(
                f"{stage_key} revision {request.revision}"
            ) from exc
        return self._enrich(result)

    def get_knowledge_evaluation(self, project_id: str) -> dict[str, Any]:
        return self.knowledge_evaluation.load(self.get_project(project_id))

    async def evaluate_knowledge(
        self, project_id: str, request: KnowledgeEvaluationRequest
    ) -> dict[str, Any]:
        return await self.knowledge_evaluation.evaluate(
            self.get_project(project_id), request
        )

    def method_registry(
        self,
        goal: str = "",
        query: str = "",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        extras = [
            item["content"]
            for item in self.store.list_knowledge_records("method")
        ]
        return KnowledgeRegistry.method_candidates(
            goal,
            query,
            limit,
            extra_items=extras,
        )

    def formula_registry(
        self,
        query: str = "",
        method_ids: list[str] | None = None,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        formulas = [
            item["content"]
            for item in self.store.list_knowledge_records("formula")
        ]
        methods = [
            item["content"]
            for item in self.store.list_knowledge_records("method")
        ]
        return KnowledgeRegistry.formula_candidates(
            query,
            method_ids or [],
            limit,
            extra_items=formulas,
            extra_methods=methods,
        )

    def list_knowledge_candidates(
        self,
        kind: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.store.list_knowledge_candidates(kind, status)

    def list_knowledge_records(
        self,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        if kind not in {None, "method", "formula"}:
            raise StageContentValidationError(
                f"unsupported knowledge kind: {kind}"
            )
        return self.store.list_knowledge_records(kind)

    async def discover_knowledge_candidates(
        self,
        request: KnowledgeDiscoveryRequest,
    ) -> dict[str, Any]:
        trace = await self.research_service.research(
            "_global_knowledge",
            "literature",
            request.query,
            "on",
        )
        citations = [
            item
            for item in trace.get("citations", [])
            if isinstance(item, dict)
        ][: request.limit]
        report = build_ai_report_envelope(
            project_id="_global_knowledge",
            stage_key="design"
            if request.kind == "method"
            else "identification",
            content={
                "executive_summary": (
                    f"围绕“{request.query}”形成 {len(citations)} 条"
                    f"{'方法' if request.kind == 'method' else '公式'}候选来源；"
                    "候选不会直接进入权威库，必须由研究者补全并批准。"
                ),
                "reasoning_trace": {
                    "problem_framing": request.query,
                    "logic_chain": [],
                    "assumptions": [],
                    "alternatives": [],
                    "uncertainties": [
                        "搜索来源只能证明候选相关性，不能自动证明方法假设或公式推导正确。"
                    ],
                    "human_decisions": [
                        "研究者核定名称、分类、适用条件、假设、诊断、失败规则与来源。"
                    ],
                    "next_verifications": [
                        "回到原始论文或官方文档核对方法定义、公式符号和许可。"
                    ],
                },
            },
            prompt_id="ai4ms.knowledge.discovery",
            prompt_version="1.0.0",
            model="deterministic-search-agent",
            generated_at=str(trace.get("searched_at") or ""),
            source_links=citations,
        )
        trace_for_store = {
            key: trace.get(key)
            for key in (
                "search_id",
                "status",
                "searched_at",
                "queries",
                "source_runs",
                "snapshot_path",
            )
        }
        trace_for_store["ai_report"] = report
        items = []
        for citation in citations:
            fingerprint = self._content_fingerprint(
                {
                    "kind": request.kind,
                    "url": citation.get("url"),
                    "title": citation.get("title"),
                }
            )
            candidate_id = (
                f"KC_{request.kind.upper()}_{fingerprint[:12]}"
            )
            proposed = self._knowledge_candidate_content(
                request.kind,
                request.query,
                citation,
            )
            items.append(
                self.store.create_knowledge_candidate(
                    candidate_id=candidate_id,
                    kind=request.kind,
                    query=request.query,
                    proposed_content=proposed,
                    source_links=[citation],
                    search_trace=trace_for_store,
                )
            )
        return {
            "schema_version": "ai4ms.knowledge-candidate.v1",
            "kind": request.kind,
            "count": len(items),
            "items": items,
            "ai_report": report,
        }

    def review_knowledge_candidate(
        self,
        candidate_id: str,
        request: KnowledgeCandidateReviewRequest,
    ) -> dict[str, Any]:
        try:
            candidate = self.store.get_knowledge_candidate(candidate_id)
        except KeyError as exc:
            raise StageContentValidationError(
                f"knowledge candidate does not exist: {candidate_id}"
            ) from exc
        if int(candidate["revision"]) != request.expected_revision:
            raise StageRevisionConflictError(
                f"knowledge candidate revision changed: expected "
                f"{request.expected_revision}, current {candidate['revision']}"
            )
        proposed = {
            **candidate["proposed_content"],
            **deepcopy(request.edits),
        }
        if request.decision == "approve":
            proposed = self._validate_knowledge_content(
                candidate["kind"],
                proposed,
            )
            identifier = (
                "method_id"
                if candidate["kind"] == "method"
                else "formula_id"
            )
            promoted_record_id = str(
                candidate.get("promoted_record_id") or ""
            ).strip() or self._knowledge_record_id(
                candidate["kind"],
                proposed,
                candidate_id,
            )
            proposed[identifier] = promoted_record_id
            try:
                reviewed, record = self.store.promote_knowledge_candidate(
                    candidate_id=candidate_id,
                    expected_revision=request.expected_revision,
                    reason=request.reason,
                    content=proposed,
                    record_id=promoted_record_id,
                )
            except RevisionConflictError as exc:
                raise StageRevisionConflictError(str(exc)) from exc
            except ValueError as exc:
                raise StageContentValidationError(str(exc)) from exc
            return {"candidate": reviewed, "record": record}
        try:
            reviewed = self.store.review_knowledge_candidate(
                candidate_id=candidate_id,
                decision=request.decision,
                reason=request.reason,
                edits=request.edits,
                expected_revision=request.expected_revision,
                promoted_record_id=None,
            )
        except RevisionConflictError as exc:
            raise StageRevisionConflictError(str(exc)) from exc
        return {"candidate": reviewed, "record": None}

    def create_knowledge_record(
        self,
        request: KnowledgeRecordCreateRequest,
    ) -> dict[str, Any]:
        content = self._validate_knowledge_content(
            request.kind,
            deepcopy(request.content),
        )
        record_id = self._knowledge_record_id(
            request.kind,
            content,
            self._content_fingerprint(content),
        )
        identifier = (
            "method_id" if request.kind == "method" else "formula_id"
        )
        content[identifier] = record_id
        try:
            return self.store.create_knowledge_record(
                record_id=record_id,
                kind=request.kind,
                content=content,
                change_reason=request.reason,
            )
        except ValueError as exc:
            raise StageContentValidationError(str(exc)) from exc

    def patch_knowledge_record(
        self,
        record_id: str,
        request: KnowledgeRecordPatchRequest,
    ) -> dict[str, Any]:
        try:
            current = self.store.get_knowledge_record(record_id)
        except KeyError as exc:
            raise StageContentValidationError(
                f"knowledge record does not exist: {record_id}"
            ) from exc
        content = self._validate_knowledge_content(
            str(current["kind"]),
            deepcopy(request.content),
        )
        identifier = (
            "method_id"
            if current["kind"] == "method"
            else "formula_id"
        )
        if content.get(identifier) not in (None, "", record_id):
            raise StageContentValidationError(
                f"{identifier} is immutable; expected {record_id}"
            )
        content[identifier] = record_id
        try:
            return self.store.update_knowledge_record(
                record_id=record_id,
                content=content,
                expected_revision=request.expected_revision,
                change_reason=request.reason,
            )
        except RevisionConflictError as exc:
            raise StageRevisionConflictError(str(exc)) from exc

    def get_knowledge_record(self, record_id: str) -> dict[str, Any]:
        try:
            return self.store.get_knowledge_record(record_id)
        except KeyError as exc:
            raise StageContentValidationError(
                f"knowledge record does not exist: {record_id}"
            ) from exc

    def list_knowledge_record_revisions(
        self,
        record_id: str,
    ) -> list[dict[str, Any]]:
        try:
            return self.store.list_knowledge_record_revisions(record_id)
        except KeyError as exc:
            raise StageContentValidationError(
                f"knowledge record does not exist: {record_id}"
            ) from exc
    async def submit_knowledge_evaluation(
        self,
        project_id: str,
        request: KnowledgeEvaluationRequest,
    ) -> dict[str, Any]:
        return await self.knowledge_evaluation_jobs.submit(
            self.get_project(project_id),
            request,
        )

    def get_knowledge_evaluation_job(
        self,
        project_id: str,
        job_id: str,
    ) -> dict[str, Any]:
        self.get_project(project_id)
        return self.knowledge_evaluation_jobs.get(project_id, job_id)

    def get_stage_suggestions(
        self,
        project_id: str,
        stage_key: str,
    ) -> dict[str, Any]:
        return self.stage_assistant.load_suggestions(
            self.get_project(project_id),
            stage_key,
        )

    async def generate_stage_suggestions(
        self,
        project_id: str,
        stage_key: str,
        request: StageSuggestionGenerateRequest,
    ) -> dict[str, Any]:
        return await self.stage_assistant.generate_suggestions(
            self.get_project(project_id),
            stage_key,
            request,
        )

    def decide_stage_suggestion(
        self,
        project_id: str,
        stage_key: str,
        suggestion_id: str,
        request: StageSuggestionDecisionRequest,
    ) -> dict[str, Any]:
        return self.stage_assistant.decide_suggestion(
            self.get_project(project_id),
            stage_key,
            suggestion_id,
            request,
        )

    async def invoke_stage_tool(
        self,
        project_id: str,
        stage_key: str,
        request: StageToolInvokeRequest,
    ) -> dict[str, Any]:
        return await self.stage_assistant.invoke_tool(
            self.get_project(project_id),
            stage_key,
            request,
            self.list_analysis_runs(project_id),
        )

    def update_project(self, project_id: str, request: UpdateProjectRequest) -> dict[str, Any]:
        try:
            return self._enrich(
                self.store.update_project(project_id, request.title, request.initial_idea)
            )
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc

    async def create_draft(self, project_id: str, stage_key: str, request: DraftRequest) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, stage_key)
        stage = next(item for item in project["stages"] if item["key"] == stage_key)
        content = deepcopy(STAGE_TEMPLATES[stage_key])
        content.update(stage.get("content") or {})
        if request.generation_mode == "model":
            generated = await self.stage_generation.generate(project, stage_key, request.instruction)
            content.update(generated)
            change_reason = f"Generated model draft for {stage_key}"
        else:
            if stage_key == "problem":
                content.setdefault("initial_idea", project["initial_idea"])
            content["draft_source"] = "structure_template"
            if request.instruction:
                content["draft_instruction"] = request.instruction
            change_reason = "Created structured stage draft"
        if stage_key == "analysis":
            plan_stage = next(item for item in project["stages"] if item["key"] == "identification")
            plan = plan_stage.get("content") or {}
            content.update(
                {
                    "execution_engine": plan.get("execution_engine", "unknown"),
                    "approved_analysis_plan_revision": plan_stage.get("revision", 0),
                    "approved_analysis_plan_hash": plan_stage.get("content_hash", ""),
                    "do_file": plan.get("stata_do_file", ""),
                    "runner_status": "available" if self.analysis_runner.status()["available"] else "unavailable",
                }
            )
        update = StageUpdateRequest(
            content=content,
            change_reason=change_reason,
            author_type="agent",
        )
        return self.update_stage(project_id, stage_key, update)

    def list_stage_chat(
        self,
        project_id: str,
        stage_key: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self._require_stage(stage_key)
        self.get_project(project_id)
        return self.stage_chat.list_messages(project_id, stage_key, limit)

    async def chat_stage(
        self,
        project_id: str,
        stage_key: str,
        request: StageChatRequest,
    ) -> dict[str, Any]:
        self._require_stage(stage_key)
        return await self.stage_chat.chat(
            self.get_project(project_id),
            stage_key,
            request,
        )

    def select_problem_question(
        self,
        project_id: str,
        request: ProblemQuestionSelectionRequest,
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "problem")
        stage = next(item for item in project["stages"] if item["key"] == "problem")
        content = deepcopy(stage.get("content") or {})
        candidates = [
            item
            for item in content.get("question_candidates", [])
            if isinstance(item, dict) and item.get("question_id")
        ]
        candidate = next(
            (
                item
                for item in candidates
                if str(item.get("question_id")) == request.selected_question_id
            ),
            None,
        )
        if candidate is None:
            raise StageContentValidationError(
                f"selected question does not exist: {request.selected_question_id}"
            )
        content["question_selection"] = {
            "selected_question_id": request.selected_question_id,
            "statement": str(candidate.get("statement") or ""),
            "rationale": request.rationale,
            "selected_by": request.actor_type,
            "selected_at": datetime.now(UTC).isoformat(),
            "candidate_fingerprint": self._content_fingerprint(candidates),
        }
        content["selected_research_question"] = str(candidate.get("statement") or "")
        workspace = content.get("_workspace")
        if isinstance(workspace, dict):
            workspace["human_confirmed"] = False
        try:
            result = self.store.update_stage(
                project_id=project_id,
                stage_key="problem",
                content=content,
                change_reason=f"Human selected research question {request.selected_question_id}",
                author_type="human",
                expected_revision=request.expected_revision,
            )
        except RevisionConflictError as exc:
            raise StageRevisionConflictError(str(exc)) from exc
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc
        return self._enrich(result)

    def review_literature_plan(
        self,
        project_id: str,
        request: LiteraturePlanReviewRequest,
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "literature")
        stage = next(item for item in project["stages"] if item["key"] == "literature")
        content = deepcopy(stage.get("content") or {})
        if not content.get("query_blocks"):
            raise StageContentValidationError(
                "literature query plan has no query_blocks to review"
            )
        content["literature_plan_review"] = {
            "status": "approved" if request.decision == "approve" else "changes_requested",
            "reason": request.reason,
            "reviewed_by": request.actor_type,
            "reviewed_at": datetime.now(UTC).isoformat(),
            "plan_fingerprint": LiteratureCoverageAuditor.plan_fingerprint(content),
        }
        workspace = content.get("_workspace")
        if isinstance(workspace, dict):
            workspace["human_confirmed"] = False
        try:
            result = self.store.update_stage(
                project_id=project_id,
                stage_key="literature",
                content=content,
                change_reason=f"Human {request.decision} literature search plan",
                author_type="human",
                expected_revision=request.expected_revision,
            )
        except RevisionConflictError as exc:
            raise StageRevisionConflictError(str(exc)) from exc
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc
        return self._enrich(result)

    def screen_literature_paper(
        self,
        project_id: str,
        paper_id: str,
        request: LiteratureScreeningRequest,
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "literature")
        stage = next(item for item in project["stages"] if item["key"] == "literature")
        content = deepcopy(stage.get("content") or {})
        papers = [
            item for item in content.get("papers", []) if isinstance(item, dict)
        ]
        if paper_id not in {str(item.get("paper_id")) for item in papers}:
            raise StageContentValidationError(f"literature paper does not exist: {paper_id}")
        paper = next(
            item for item in papers if str(item.get("paper_id")) == paper_id
        )
        available_level = LiteratureCoverageAuditor.available_evidence_level(paper)
        level_rank = {"metadata": 0, "abstract": 1, "full_text": 2}
        if level_rank[request.evidence_level] > level_rank[available_level]:
            raise StageContentValidationError(
                f"paper {paper_id} only has {available_level} evidence; "
                f"cannot mark it as {request.evidence_level}"
            )

        decisions = [
            item
            for item in content.get("screening_decisions", [])
            if isinstance(item, dict) and str(item.get("paper_id")) != paper_id
        ]
        decisions.append(
            {
                "paper_id": paper_id,
                "decision": request.decision,
                "reason": request.reason,
                "evidence_level": request.evidence_level,
                "decided_by": request.actor_type,
                "decided_at": datetime.now(UTC).isoformat(),
            }
        )
        content["screening_decisions"] = decisions
        candidates = [
            dict(item)
            for item in content.get("evidence_candidates", [])
            if isinstance(item, dict)
        ]
        candidate = next(
            (
                item
                for item in candidates
                if str(item.get("paper_id") or "") == paper_id
            ),
            None,
        )
        if candidate is None:
            candidate = self._paper_evidence_candidate(
                paper,
                search_id=str(
                    (content.get("search_runs") or [{}])[-1].get("search_id")
                    or "legacy"
                ),
            )
            candidates.append(candidate)
        candidate["revision"] = int(candidate.get("revision") or 1) + 1
        candidate["status"] = {
            "include": "approved",
            "exclude": "rejected",
            "unsure": "changes_requested",
        }[request.decision]
        candidate["review"] = {
            "decision": (
                "approve"
                if request.decision == "include"
                else "reject"
                if request.decision == "exclude"
                else "request_changes"
            ),
            "reason": request.reason,
            "evidence_level": request.evidence_level,
            "reviewed_by": request.actor_type,
            "reviewed_at": datetime.now(UTC).isoformat(),
        }
        content["evidence_candidates"] = candidates
        library = [
            dict(item)
            for item in content.get("evidence_library", [])
            if isinstance(item, dict)
        ]
        if request.decision == "include":
            library = self._promote_evidence_candidate(
                library,
                candidate,
                request.reason,
                request.evidence_level,
            )
        elif request.decision == "exclude":
            for item in library:
                if item.get("source_candidate_id") == candidate["candidate_id"]:
                    item["status"] = "archived"
                    item["revision"] = int(item.get("revision") or 1) + 1
                    item["updated_at"] = datetime.now(UTC).isoformat()
                    item.setdefault("audit_trail", []).append(
                        {
                            "action": "archived_after_screening",
                            "actor_type": "human",
                            "reason": request.reason,
                            "created_at": item["updated_at"],
                        }
                    )
        content["evidence_library"] = library
        for key in (
            "paper_evidence_cards",
            "research_streams",
            "syntheses",
            "method_comparisons",
            "contradictions",
            "gap_candidates",
            "review_outline",
            "recommended_next_steps",
        ):
            content[key] = []
        content["coverage_audit"] = LiteratureCoverageAuditor.audit(
            papers,
            content.get("sources", []),
            decisions,
        )
        content["synthesis_invalidated_at"] = datetime.now(UTC).isoformat()
        workspace = content.get("_workspace")
        if isinstance(workspace, dict):
            workspace["human_confirmed"] = False
        try:
            result = self.store.update_stage(
                project_id=project_id,
                stage_key="literature",
                content=content,
                change_reason=f"Human screened {paper_id} as {request.decision}",
                author_type="human",
                expected_revision=request.expected_revision,
            )
        except RevisionConflictError as exc:
            raise StageRevisionConflictError(str(exc)) from exc
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc
        return self._enrich(result)

    async def search_literature(self, project_id: str, request: LiteratureSearchRequest) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "literature")
        stage = next(item for item in project["stages"] if item["key"] == "literature")
        content = deepcopy(STAGE_TEMPLATES["literature"])
        content.update(stage.get("content") or {})
        query_origin = "explicit_human_request"
        if not request.queries:
            review = content.get("literature_plan_review", {})
            current_fingerprint = LiteratureCoverageAuditor.plan_fingerprint(content)
            if (
                not isinstance(review, dict)
                or review.get("status") != "approved"
                or review.get("plan_fingerprint") != current_fingerprint
            ):
                raise StageContentValidationError(
                    "执行模型生成的检索计划前，研究者必须批准当前 query plan；"
                    "也可以在本次请求中显式提交 queries"
                )
            query_origin = "human_approved_plan"
        search_run = await self.literature_search.search(project_id, content, request)
        content["papers"] = search_run.pop("papers")
        content["sources"] = search_run["source_runs"]
        search_run["query_origin"] = query_origin
        content.setdefault("search_runs", []).append(search_run)
        existing_candidates = [
            dict(item)
            for item in content.get("evidence_candidates", [])
            if isinstance(item, dict)
        ]
        by_id = {
            str(item.get("candidate_id")): item
            for item in existing_candidates
            if item.get("candidate_id")
        }
        for paper in content["papers"]:
            if not isinstance(paper, dict):
                continue
            candidate = self._paper_evidence_candidate(
                paper,
                search_id=str(search_run["search_id"]),
            )
            current = by_id.get(candidate["candidate_id"])
            if current and current.get("status") != "pending":
                continue
            by_id[candidate["candidate_id"]] = candidate
        content["evidence_candidates"] = list(by_id.values())
        content["screening_decisions"] = []
        for key in (
            "paper_evidence_cards",
            "research_streams",
            "syntheses",
            "method_comparisons",
            "contradictions",
            "gap_candidates",
            "review_outline",
            "recommended_next_steps",
        ):
            content[key] = []
        content["coverage_audit"] = LiteratureCoverageAuditor.audit(
            content["papers"],
            content["sources"],
            content["screening_decisions"],
        )
        update = StageUpdateRequest(
            content=content,
            change_reason=f"Executed literature search {search_run['search_id']}",
            author_type="agent",
        )
        return self.update_stage(project_id, "literature", update)

    def list_evidence_candidates(self, project_id: str) -> list[dict[str, Any]]:
        stage = self.get_stage(project_id, "literature")
        return [
            dict(item)
            for item in stage.get("content", {}).get("evidence_candidates", [])
            if isinstance(item, dict)
        ]

    def list_evidence_library(self, project_id: str) -> list[dict[str, Any]]:
        stage = self.get_stage(project_id, "literature")
        return [
            dict(item)
            for item in stage.get("content", {}).get("evidence_library", [])
            if isinstance(item, dict)
        ]

    def get_evidence_record(
        self,
        project_id: str,
        evidence_id: str,
    ) -> dict[str, Any]:
        item = next(
            (
                record
                for record in self.list_evidence_library(project_id)
                if record.get("evidence_id") == evidence_id
            ),
            None,
        )
        if item is None:
            raise StageContentValidationError(
                f"evidence library record does not exist: {evidence_id}"
            )
        return item

    async def discover_evidence_candidates(
        self,
        project_id: str,
        request: EvidenceDiscoveryRequest,
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "literature")
        stage = next(
            item for item in project["stages"] if item["key"] == "literature"
        )
        if int(stage.get("revision") or 0) != request.expected_revision:
            raise StageRevisionConflictError(
                f"stage revision changed: expected {request.expected_revision}, "
                f"current {stage.get('revision', 0)}"
            )
        trace = await self.research_service.research(
            project_id,
            "literature",
            request.query,
            "on",
        )
        citations = [
            item
            for item in trace.get("citations", [])
            if isinstance(item, dict)
        ][: request.limit]
        content = deepcopy(STAGE_TEMPLATES["literature"])
        content.update(stage.get("content") or {})
        candidates = {
            str(item.get("candidate_id")): dict(item)
            for item in content.get("evidence_candidates", [])
            if isinstance(item, dict) and item.get("candidate_id")
        }
        created_ids: list[str] = []
        for citation in citations:
            candidate = self._citation_evidence_candidate(
                citation,
                request.candidate_type,
                str(trace.get("search_id") or ""),
            )
            current = candidates.get(candidate["candidate_id"])
            if current and current.get("status") != "pending":
                continue
            candidates[candidate["candidate_id"]] = candidate
            created_ids.append(candidate["candidate_id"])
        content["evidence_candidates"] = list(candidates.values())
        run = {
            key: trace.get(key)
            for key in (
                "search_id",
                "status",
                "searched_at",
                "queries",
                "source_runs",
                "snapshot_path",
            )
        }
        run.update(
            {
                "candidate_type": request.candidate_type,
                "candidate_ids": created_ids,
                "candidate_count": len(created_ids),
            }
        )
        run["ai_report"] = build_ai_report_envelope(
            project_id=project_id,
            stage_key="literature",
            content={
                "executive_summary": (
                    f"围绕“{request.query}”发现 {len(created_ids)} 条"
                    f"{'文献' if request.candidate_type == 'literature' else '数据研究'}候选；"
                    "所有候选均等待人工审核，尚未进入权威证据库。"
                ),
                "reasoning_trace": {
                    "problem_framing": request.query,
                    "logic_chain": [],
                    "assumptions": [],
                    "alternatives": [],
                    "uncertainties": (
                        ["检索覆盖不完整，需要研究者补充数据库或反向检索。"]
                        if trace.get("status") != "complete"
                        else []
                    ),
                    "human_decisions": [
                        "逐条批准、退回或拒绝候选，并核定证据等级。"
                    ],
                    "next_verifications": [
                        "核对题名、作者/机构、年份、来源链接、许可与可复核定位。"
                    ],
                },
            },
            prompt_id="ai4ms.evidence.discovery",
            prompt_version="1.0.0",
            model="deterministic-search-agent",
            generated_at=str(trace.get("searched_at") or ""),
            source_links=citations,
            evidence_library=content.get("evidence_library", []),
        )
        content.setdefault("evidence_discovery_runs", []).append(run)
        workspace = content.get("_workspace")
        if isinstance(workspace, dict):
            workspace["human_confirmed"] = False
        try:
            result = self.store.update_stage(
                project_id=project_id,
                stage_key="literature",
                content=content,
                change_reason=(
                    f"Agent discovered {len(created_ids)} "
                    f"{request.candidate_type} evidence candidates"
                ),
                author_type="agent",
                expected_revision=request.expected_revision,
            )
        except RevisionConflictError as exc:
            raise StageRevisionConflictError(str(exc)) from exc
        return self._enrich(result)

    def review_evidence_candidate(
        self,
        project_id: str,
        candidate_id: str,
        request: EvidenceCandidateReviewRequest,
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "literature")
        stage = next(
            item for item in project["stages"] if item["key"] == "literature"
        )
        content = deepcopy(stage.get("content") or {})
        candidates = [
            dict(item)
            for item in content.get("evidence_candidates", [])
            if isinstance(item, dict)
        ]
        candidate = next(
            (
                item
                for item in candidates
                if item.get("candidate_id") == candidate_id
            ),
            None,
        )
        if candidate is None:
            raise StageContentValidationError(
                f"evidence candidate does not exist: {candidate_id}"
            )
        self._apply_evidence_edits(candidate, request.edits)
        candidate["revision"] = int(candidate.get("revision") or 1) + 1
        candidate["status"] = {
            "approve": "approved",
            "reject": "rejected",
            "request_changes": "changes_requested",
        }[request.decision]
        candidate["review"] = {
            "decision": request.decision,
            "reason": request.reason,
            "evidence_level": request.evidence_level,
            "reviewed_by": request.actor_type,
            "reviewed_at": datetime.now(UTC).isoformat(),
        }
        library = [
            dict(item)
            for item in content.get("evidence_library", [])
            if isinstance(item, dict)
        ]
        if request.decision == "approve":
            library = self._promote_evidence_candidate(
                library,
                candidate,
                request.reason,
                request.evidence_level,
            )
        content["evidence_candidates"] = candidates
        content["evidence_library"] = library
        workspace = content.get("_workspace")
        if isinstance(workspace, dict):
            workspace["human_confirmed"] = False
        try:
            result = self.store.update_stage(
                project_id=project_id,
                stage_key="literature",
                content=content,
                change_reason=(
                    f"Human {request.decision} evidence candidate {candidate_id}"
                ),
                author_type="human",
                expected_revision=request.expected_revision,
            )
        except RevisionConflictError as exc:
            raise StageRevisionConflictError(str(exc)) from exc
        return self._enrich(result)

    def patch_evidence_record(
        self,
        project_id: str,
        evidence_id: str,
        request: EvidenceRecordPatchRequest,
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "literature")
        stage = next(
            item for item in project["stages"] if item["key"] == "literature"
        )
        content = deepcopy(stage.get("content") or {})
        library = [
            dict(item)
            for item in content.get("evidence_library", [])
            if isinstance(item, dict)
        ]
        record = next(
            (
                item
                for item in library
                if item.get("evidence_id") == evidence_id
            ),
            None,
        )
        if record is None:
            raise StageContentValidationError(
                f"evidence library record does not exist: {evidence_id}"
            )
        self._apply_evidence_edits(record, request.edits)
        now = datetime.now(UTC).isoformat()
        record["revision"] = int(record.get("revision") or 1) + 1
        record["updated_at"] = now
        record["content_hash"] = self._content_fingerprint(
            {
                key: value
                for key, value in record.items()
                if key not in {"content_hash", "audit_trail"}
            }
        )
        record.setdefault("audit_trail", []).append(
            {
                "action": "human_edit",
                "actor_type": request.actor_type,
                "reason": request.reason,
                "created_at": now,
            }
        )
        content["evidence_library"] = library
        try:
            result = self.store.update_stage(
                project_id=project_id,
                stage_key="literature",
                content=content,
                change_reason=f"Human edited evidence record {evidence_id}",
                author_type="human",
                expected_revision=request.expected_revision,
            )
        except RevisionConflictError as exc:
            raise StageRevisionConflictError(str(exc)) from exc
        return self._enrich(result)

    @classmethod
    def _paper_evidence_candidate(
        cls,
        paper: dict[str, Any],
        *,
        search_id: str,
    ) -> dict[str, Any]:
        source_urls = paper.get("source_urls")
        source_urls = source_urls if isinstance(source_urls, list) else []
        url = str(
            paper.get("url")
            or paper.get("source_url")
            or (source_urls[0] if source_urls else "")
            or (
                f"https://doi.org/{paper['doi']}"
                if paper.get("doi")
                else ""
            )
        ).strip()
        fingerprint = cls._content_fingerprint(
            {
                "type": "literature",
                "paper_id": paper.get("paper_id"),
                "doi": paper.get("doi"),
                "url": url,
                "title": paper.get("title"),
            }
        )
        now = datetime.now(UTC).isoformat()
        return {
            "candidate_id": f"EC_{fingerprint[:16]}",
            "candidate_type": "literature",
            "status": "pending",
            "revision": 1,
            "title": str(paper.get("title") or "题名待核验"),
            "authors": list(paper.get("authors") or []),
            "year": paper.get("year"),
            "venue": str(paper.get("venue") or ""),
            "doi": str(paper.get("doi") or ""),
            "url": url,
            "abstract": str(paper.get("abstract") or ""),
            "paper_id": str(paper.get("paper_id") or ""),
            "provider": "+".join(paper.get("backends") or ["academic"]),
            "source_type": "academic",
            "search_id": search_id,
            "source_snapshot": "",
            "source_hash": fingerprint,
            "created_by": "agent",
            "created_at": now,
            "updated_at": now,
            "review": None,
        }

    @classmethod
    def _citation_evidence_candidate(
        cls,
        citation: dict[str, Any],
        candidate_type: str,
        search_id: str,
    ) -> dict[str, Any]:
        fingerprint = cls._content_fingerprint(
            {
                "type": candidate_type,
                "paper_id": citation.get("paper_id"),
                "url": citation.get("url"),
                "title": citation.get("title"),
            }
        )
        now = datetime.now(UTC).isoformat()
        return {
            "candidate_id": f"EC_{fingerprint[:16]}",
            "candidate_type": candidate_type,
            "status": "pending",
            "revision": 1,
            "title": str(citation.get("title") or "来源题名待核验"),
            "authors": [],
            "year": None,
            "venue": str(citation.get("domain") or ""),
            "doi": "",
            "url": str(citation.get("url") or ""),
            "abstract": str(
                citation.get("excerpt") or citation.get("snippet") or ""
            ),
            "summary": str(citation.get("snippet") or ""),
            "paper_id": str(citation.get("paper_id") or ""),
            "provider": str(citation.get("provider") or ""),
            "source_type": str(citation.get("source_type") or "web"),
            "search_id": search_id,
            "source_snapshot": "",
            "source_hash": fingerprint,
            "created_by": "agent",
            "created_at": now,
            "updated_at": now,
            "review": None,
        }

    @classmethod
    def _promote_evidence_candidate(
        cls,
        library: list[dict[str, Any]],
        candidate: dict[str, Any],
        reason: str,
        evidence_level: str,
    ) -> list[dict[str, Any]]:
        if not str(candidate.get("title") or "").strip():
            raise StageContentValidationError(
                "approved evidence requires a verified title"
            )
        if not str(candidate.get("url") or "").strip():
            raise StageContentValidationError(
                "approved evidence requires a stable source URL"
            )
        evidence_id = f"EVLIB_{str(candidate['candidate_id']).removeprefix('EC_')}"
        current = next(
            (
                item
                for item in library
                if item.get("evidence_id") == evidence_id
            ),
            None,
        )
        now = datetime.now(UTC).isoformat()
        reference = {
            key: candidate.get(key)
            for key in (
                "paper_id",
                "title",
                "authors",
                "year",
                "venue",
                "doi",
                "url",
                "provider",
                "dataset_name",
                "license",
                "access_notes",
                "locator",
            )
            if candidate.get(key) not in (None, "", [])
        }
        record = {
            "evidence_id": evidence_id,
            "source_candidate_id": candidate["candidate_id"],
            "evidence_type": (
                "paper"
                if candidate.get("candidate_type") == "literature"
                else "data_study"
            ),
            "status": "active",
            "revision": int(current.get("revision") or 0) + 1
            if current
            else 1,
            "title": candidate.get("title"),
            "authors": candidate.get("authors", []),
            "year": candidate.get("year"),
            "venue": candidate.get("venue", ""),
            "doi": candidate.get("doi", ""),
            "url": candidate.get("url", ""),
            "paper_id": candidate.get("paper_id", ""),
            "abstract": candidate.get("abstract", ""),
            "summary": candidate.get("summary", ""),
            "provider": candidate.get("provider", ""),
            "evidence_level": evidence_level,
            "reference": reference,
            "source_hash": candidate.get("source_hash", ""),
            "approved_by": "human",
            "approved_at": now,
            "updated_at": now,
            "audit_trail": [
                *(
                    current.get("audit_trail", [])
                    if current and isinstance(current.get("audit_trail"), list)
                    else []
                ),
                {
                    "action": "approved_to_evidence_library",
                    "actor_type": "human",
                    "reason": reason,
                    "created_at": now,
                },
            ],
        }
        record["content_hash"] = cls._content_fingerprint(
            {
                key: value
                for key, value in record.items()
                if key not in {"content_hash", "audit_trail"}
            }
        )
        if current is None:
            return [*library, record]
        return [
            record if item.get("evidence_id") == evidence_id else item
            for item in library
        ]

    @staticmethod
    def _apply_evidence_edits(
        target: dict[str, Any],
        edits: dict[str, Any],
    ) -> None:
        allowed = {
            "title",
            "authors",
            "year",
            "venue",
            "doi",
            "url",
            "abstract",
            "summary",
            "dataset_name",
            "provider",
            "license",
            "access_notes",
            "locator",
        }
        unknown = sorted(set(edits) - allowed)
        if unknown:
            raise StageContentValidationError(
                f"unsupported evidence edit fields: {unknown}"
            )
        for key, value in edits.items():
            target[key] = deepcopy(value)
        target["updated_at"] = datetime.now(UTC).isoformat()

    @staticmethod
    def _knowledge_candidate_content(
        kind: str,
        query: str,
        citation: dict[str, Any],
    ) -> dict[str, Any]:
        title = str(citation.get("title") or "候选名称待核验")
        excerpt = str(
            citation.get("excerpt") or citation.get("snippet") or ""
        )[:4000]
        source_url = str(citation.get("url") or "")
        if kind == "method":
            return {
                "method_id": "",
                "family": "待人工分类",
                "name": title,
                "lane": "待人工判断",
                "goal": query,
                "data": "待人工核定",
                "assumptions": "待从原始来源核验",
                "workflow": excerpt or "待从原始来源提取",
                "diagnostics": "待人工补充",
                "robustness": "待人工补充",
                "packages": "",
                "formula_ids": "",
                "failure": "来源与关键假设未核验前不得进入研究设计",
                "description": excerpt,
                "source_urls": [source_url] if source_url else [],
            }
        return {
            "formula_id": "",
            "category": "待人工分类",
            "name": title,
            "latex": "",
            "use_when": query,
            "notation": "待人工定义",
            "assumptions": "待从原始来源核验",
            "diagnostics": "待人工补充",
            "packages": "",
            "warning": "公式、符号和推导尚未人工核验，不得用于分析",
            "description": excerpt,
            "source_urls": [source_url] if source_url else [],
        }

    @staticmethod
    def _validate_knowledge_content(
        kind: str,
        content: dict[str, Any],
    ) -> dict[str, Any]:
        if kind not in {"method", "formula"}:
            raise StageContentValidationError(
                f"unsupported knowledge kind: {kind}"
            )
        required = (
            ("name", "family", "goal", "assumptions", "diagnostics", "failure")
            if kind == "method"
            else (
                "name",
                "category",
                "latex",
                "use_when",
                "assumptions",
                "diagnostics",
                "warning",
            )
        )
        missing = [
            key
            for key in required
            if content.get(key) in (None, "", [])
        ]
        if missing:
            raise StageContentValidationError(
                f"approved {kind} record is missing required fields: {missing}"
            )
        source_urls = content.get("source_urls", [])
        if not isinstance(source_urls, list) or not any(
            str(item).startswith(("https://", "http://"))
            for item in source_urls
        ):
            raise StageContentValidationError(
                f"approved {kind} record requires at least one source URL"
            )
        return content

    @staticmethod
    def _knowledge_record_id(
        kind: str,
        content: dict[str, Any],
        seed: str,
    ) -> str:
        identifier = (
            str(content.get("method_id") or "").strip().upper()
            if kind == "method"
            else str(content.get("formula_id") or "").strip().upper()
        )
        pattern = (
            r"^MUSR_[A-Z0-9_-]{4,27}$"
            if kind == "method"
            else r"^FUSR_[A-Z0-9_-]{4,39}$"
        )
        if identifier:
            if not re.fullmatch(pattern, identifier):
                raise StageContentValidationError(
                    f"invalid {kind} identifier: {identifier}"
                )
            return identifier
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10].upper()
        return f"MUSR_{digest}" if kind == "method" else f"FUSR_{digest}"

    def delivery_quality(self, project_id: str) -> dict[str, Any]:
        return AcademicOutputQualityService.audit(self.get_project(project_id))

    def preflight_analysis_run(self, project_id: str, request: AnalysisRunRequest) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "analysis")
        return self.analysis_runner.preflight(
            project,
            self.projects_dir / project_id,
            request,
        )

    async def submit_analysis_run(self, project_id: str, request: AnalysisRunRequest) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "analysis")
        return await self.analysis_jobs.submit(project_id, request)

    def list_analysis_runs(self, project_id: str) -> list[dict[str, Any]]:
        return self.analysis_jobs.list(project_id)

    def get_analysis_run(self, project_id: str, run_id: str) -> dict[str, Any]:
        return self.analysis_jobs.get(project_id, run_id)

    def get_analysis_run_result(self, project_id: str, run_id: str) -> dict[str, Any]:
        return self.analysis_jobs.result(project_id, run_id)

    def analysis_run_artifact(
        self,
        project_id: str,
        run_id: str,
        artifact_path: str,
    ) -> Path:
        run = self.get_analysis_run_result(project_id, run_id)
        relative = Path(str(artifact_path or ""))
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise AnalysisJobConflictError("unsafe analysis artifact path")
        project_dir = (self.projects_dir / project_id).resolve()
        run_dir = (project_dir / "artifacts" / "runs" / run_id).resolve()
        target = (run_dir / relative).resolve()
        try:
            target.relative_to(run_dir)
        except ValueError as exc:
            raise AnalysisJobConflictError(
                "analysis artifact escapes the run directory"
            ) from exc
        project_relative = target.relative_to(project_dir).as_posix()
        declaration = next(
            (
                item
                for item in run.get("output_artifacts", [])
                if item.get("path") == project_relative
            ),
            None,
        )
        if declaration is None or not target.is_file():
            raise AnalysisJobConflictError(
                "analysis artifact is not declared by the run manifest"
            )
        if (
            int(declaration.get("size", -1)) != target.stat().st_size
            or declaration.get("sha256") != sha256_file(target)
        ):
            raise AnalysisJobConflictError(
                "analysis artifact failed size or SHA-256 verification"
            )
        return target

    async def cancel_analysis_run(self, project_id: str, run_id: str) -> dict[str, Any]:
        return await self.analysis_jobs.cancel(project_id, run_id)

    async def rerun_analysis(
        self,
        project_id: str,
        run_id: str,
        request: AnalysisRerunRequest,
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "analysis")
        return await self.analysis_jobs.rerun(
            project_id,
            run_id,
            timeout_seconds=request.timeout_seconds,
        )

    def _record_analysis_run(self, project_id: str, run: dict[str, Any]) -> dict[str, Any]:
        project = self.get_project(project_id)
        stage = next(item for item in project["stages"] if item["key"] == "analysis")
        content = deepcopy(STAGE_TEMPLATES["analysis"])
        content.update(stage.get("content") or {})
        content.setdefault("runs", []).append(run)
        content["runner_status"] = (
            "available" if run.get("runner_profile", {}).get("available") else "unavailable"
        )
        content["last_preflight"] = run.get("preflight", {})
        if run.get("status") in {"succeeded", "failed"}:
            content.setdefault("results", []).append(
                {
                    "run_id": run["run_id"],
                    "status": run["status"],
                    "exit_code": run.get("exit_code"),
                    "data_signature": run.get("data_signature", ""),
                    "structured_results": run.get("structured_results", []),
                    "output_artifacts": run.get("output_artifacts", []),
                }
            )
        update = StageUpdateRequest(
            content=content,
            change_reason=f"Recorded analysis run {run['run_id']} ({run['status']}:{run['reason_code']})",
            author_type="agent",
        )
        return self.update_stage(project_id, "analysis", update)

    def export_delivery(self, project_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "delivery")
        stage = next(item for item in project["stages"] if item["key"] == "delivery")
        export_record = self.delivery_export.export(project)
        content = deepcopy(STAGE_TEMPLATES["delivery"])
        content.update(stage.get("content") or {})
        content.setdefault("exports", []).append(export_record)
        content["visual_report_path"] = export_record["visual_report_path"]
        content["word_report_path"] = export_record["word_report_path"]
        content["pdf_report_path"] = export_record["pdf_report_path"]
        content["stata_package_path"] = export_record["stata_package_path"]
        content["research_package_path"] = export_record["research_package_path"]
        content["manifest_path"] = export_record["manifest_path"]
        return self.update_stage(
            project_id,
            "delivery",
            StageUpdateRequest(
                content=content,
                change_reason=f"Generated delivery export {export_record['export_id']}",
                author_type="agent",
            ),
        )

    def delivery_artifact(self, project_id: str, export_id: str, kind: str) -> Path:
        project = self.get_project(project_id)
        return self.delivery_export.artifact_path(project, export_id, kind)

    def update_stage(self, project_id: str, stage_key: str, request: StageUpdateRequest) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, stage_key)
        content = deepcopy(request.content)
        workspace = content.get("_workspace")
        if isinstance(workspace, dict):
            workspace["human_confirmed"] = False
        try:
            result = self.store.update_stage(
                project_id=project_id,
                stage_key=stage_key,
                content=content,
                change_reason=request.change_reason,
                author_type=request.author_type,
            )
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc
        return self._enrich(result)

    def update_stage_workspace(
        self,
        project_id: str,
        stage_key: str,
        request: StageWorkspaceUpdateRequest,
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, stage_key)
        stage = next(item for item in project["stages"] if item["key"] == stage_key)
        content = deepcopy(stage.get("content") or {})
        content["_workspace"] = request.workspace.model_dump()
        try:
            result = self.store.update_stage(
                project_id=project_id,
                stage_key=stage_key,
                content=content,
                change_reason=request.change_reason,
                author_type="human",
                expected_revision=request.expected_revision,
            )
        except RevisionConflictError as exc:
            raise StageRevisionConflictError(str(exc)) from exc
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc
        return self._enrich(result)

    def update_stage_asset_section(
        self,
        project_id: str,
        stage_key: str,
        section_key: str,
        request: StageAssetSectionPatchRequest,
    ) -> dict[str, Any]:
        if section_key not in {
            "summary",
            "section-1",
            "section-2",
            "section-3",
            "section-4",
            "section-5",
            "section-6",
        }:
            raise StageContentValidationError(
                f"unknown asset section: {section_key}"
            )
        project = self.get_project(project_id)
        self._ensure_unlocked(project, stage_key)
        stage = next(item for item in project["stages"] if item["key"] == stage_key)
        content = deepcopy(stage.get("content") or {})
        asset_version = content.get("_asset_version")
        if not isinstance(asset_version, dict):
            asset_version = {"schema_version": "1.0", "sections": {}}
        sections = asset_version.get("sections")
        if not isinstance(sections, dict):
            sections = {}
        sections[section_key] = {
            "title": request.title,
            "content": request.content,
        }
        asset_version["schema_version"] = "1.0"
        asset_version["sections"] = sections
        content["_asset_version"] = asset_version
        workspace = content.get("_workspace")
        if isinstance(workspace, dict):
            workspace["human_confirmed"] = False
        try:
            result = self.store.update_stage(
                project_id=project_id,
                stage_key=stage_key,
                content=content,
                change_reason=request.change_reason
                or f"Updated asset section {section_key}",
                author_type="human",
                expected_revision=request.expected_revision,
            )
        except RevisionConflictError as exc:
            raise StageRevisionConflictError(str(exc)) from exc
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc
        return self._enrich(result)

    def decide_stage(self, project_id: str, stage_key: str, request: StageDecisionRequest) -> dict[str, Any]:
        self._require_stage(stage_key)
        project = self.get_project(project_id)
        self._ensure_unlocked(project, stage_key)
        if request.decision is ApprovalDecision.APPROVE:
            stage = next(item for item in project["stages"] if item["key"] == stage_key)
            workspace = stage.get("content", {}).get("_workspace", {})
            if not isinstance(workspace, dict) or workspace.get("human_confirmed") is not True:
                raise StageContentValidationError(
                    "当前 revision 的人工确认尚未保存；请在阶段资产中勾选人工确认并保存新 revision"
                )
            validation_issue = self._stage_validation_issue(
                project,
                stage_key,
                stage.get("content", {}),
            )
            if validation_issue:
                raise StageContentValidationError(validation_issue)
            if stage_key == "delivery":
                exports = stage.get("content", {}).get("exports", [])
                latest = exports[-1]
                self.delivery_export.artifact_path(project, str(latest.get("export_id", "")), "report")
                self.delivery_export.artifact_path(project, str(latest.get("export_id", "")), "word")
                self.delivery_export.artifact_path(project, str(latest.get("export_id", "")), "pdf")
                self.delivery_export.artifact_path(project, str(latest.get("export_id", "")), "stata")
                self.delivery_export.artifact_path(project, str(latest.get("export_id", "")), "package")
        try:
            result = self.store.decide_stage(
                project_id=project_id,
                stage_key=stage_key,
                decision=request.decision,
                reason=request.reason,
                actor_type=request.actor_type,
            )
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc
        return self._enrich(result)

    def _enrich(self, project: dict[str, Any]) -> dict[str, Any]:
        stages = project.get("stages", [])
        approved = sum(1 for stage in stages if stage["status"] == StageStatus.APPROVED.value)
        result = dict(project)
        result["stages"] = [
            {
                **stage,
                "readiness": self._stage_readiness(project, stage),
            }
            for stage in stages
        ]
        result["progress"] = {"approved": approved, "total": len(STAGE_DEFINITIONS)}
        result["data_assets"] = self.store.list_data_assets(str(project["project_id"]))
        result["knowledge_library"] = {
            kind: [
                {
                    **item["content"],
                    "_registry_revision": item["revision"],
                    "_content_hash": item["content_hash"],
                    "_source_candidate_id": item.get("source_candidate_id"),
                }
                for item in self.store.list_knowledge_records(
                    "method" if kind == "methods" else "formula"
                )
            ]
            for kind in ("methods", "formulas")
        }
        return result

    def _stage_readiness(
        self,
        project: dict[str, Any],
        stage: dict[str, Any],
    ) -> dict[str, Any]:
        content = stage.get("content", {})
        workspace = content.get("_workspace", {}) if isinstance(content, dict) else {}
        artifact_saved = int(stage.get("revision", 0) or 0) > 0
        validation_issue = (
            self._stage_validation_issue(project, str(stage["key"]), content)
            if artifact_saved and isinstance(content, dict)
            else "阶段尚无已保存资产"
        )
        checks = {
            "artifact_saved": artifact_saved,
            "contract_valid": artifact_saved and not validation_issue,
            "human_confirmed": (
                isinstance(workspace, dict)
                and workspace.get("human_confirmed") is True
            ),
            "approved": stage.get("status") == StageStatus.APPROVED.value,
        }
        missing_labels = {
            "artifact_saved": "保存阶段资产",
            "contract_valid": "补齐阶段契约内容",
            "human_confirmed": "保存人工确认",
            "approved": "提交并通过人工审批",
        }
        completed = sum(1 for passed in checks.values() if passed)
        return {
            "percent": round(completed / len(checks) * 100),
            "completed": completed,
            "total": len(checks),
            "can_submit": (
                stage.get("status") == StageStatus.NEEDS_REVIEW.value
                and all(checks[key] for key in ("artifact_saved", "contract_valid", "human_confirmed"))
            ),
            "checks": checks,
            "missing": [
                label
                for key, label in missing_labels.items()
                if not checks[key]
            ],
            "validation_issue": validation_issue[:500],
        }

    def _stage_validation_issue(
        self,
        project: dict[str, Any],
        stage_key: str,
        content: dict[str, Any],
    ) -> str:
        try:
            StageGenerationService.validate_stage_content(project, stage_key, content)
            if stage_key == "problem":
                candidates = [
                    item
                    for item in content.get("question_candidates", [])
                    if isinstance(item, dict) and item.get("question_id")
                ]
                if candidates:
                    selection = content.get("question_selection", {})
                    valid_ids = {str(item.get("question_id")) for item in candidates}
                    if (
                        not isinstance(selection, dict)
                        or selection.get("selected_by") != "human"
                        or selection.get("selected_question_id") not in valid_ids
                        or selection.get("candidate_fingerprint")
                        != self._content_fingerprint(candidates)
                    ):
                        raise StageContentValidationError(
                            "G0 批准前，研究者必须从当前候选问题中明确选择一项并保存理由"
                        )
            if stage_key == "literature":
                if not content.get("search_runs"):
                    raise StageContentValidationError(
                        "S1 批准前必须执行至少一次可追溯文献检索"
                    )
                if not content.get("papers"):
                    raise StageContentValidationError(
                        "S1 检索未形成可追溯论文记录，不能进入下一阶段"
                    )
                candidates = [
                    item
                    for item in content.get("evidence_candidates", [])
                    if isinstance(item, dict) and item.get("candidate_id")
                ]
                pending = [
                    str(item["candidate_id"])
                    for item in candidates
                    if item.get("status") in {
                        None,
                        "",
                        "pending",
                        "changes_requested",
                    }
                ]
                if pending:
                    raise StageContentValidationError(
                        "S1 批准前必须完成人工证据候选审核；"
                        f"仍待处理：{pending[:8]}"
                    )
                active_evidence = [
                    item
                    for item in content.get("evidence_library", [])
                    if isinstance(item, dict)
                    and item.get("status", "active") == "active"
                ]
                if not active_evidence:
                    raise StageContentValidationError(
                        "S1 批准前至少需要一条经人工批准的 evidence_library 记录"
                    )
                decisions = [
                    item
                    for item in content.get("screening_decisions", [])
                    if isinstance(item, dict) and item.get("paper_id")
                ]
                if decisions:
                    reviewed = {str(item.get("paper_id")) for item in decisions}
                    paper_ids = {
                        str(item.get("paper_id"))
                        for item in content.get("papers", [])
                        if isinstance(item, dict) and item.get("paper_id")
                    }
                    if reviewed != paper_ids:
                        raise StageContentValidationError(
                            "已启动逐篇筛选；S1 批准前必须完成全部论文的 include/exclude/unsure 决定"
                        )
            if stage_key == "delivery":
                exports = content.get("exports", [])
                if not exports:
                    raise StageContentValidationError(
                        "G5 批准前必须生成 HTML、Word、PDF 与 Stata 复现包"
                    )
                quality = AcademicOutputQualityService.audit(project)
                if quality["counts"]["must_fix"]:
                    raise StageContentValidationError(
                        f"S9 学术输出仍有 {quality['counts']['must_fix']} 项必须修复问题"
                    )
                latest = exports[-1]
                if not isinstance(latest, dict):
                    raise StageContentValidationError("G5 最新导出记录格式无效")
                fingerprint = self.delivery_export.delivery_fingerprint(content)
                if latest.get("source_content_fingerprint") != fingerprint:
                    raise StageContentValidationError(
                        "S9 内容在最近一次导出后已变化，请重新生成交付包"
                    )
        except (StageContentValidationError, DeliveryExportError) as exc:
            return str(exc)
        return ""

    @staticmethod
    def _require_stage(stage_key: str) -> None:
        if stage_key not in STAGES_BY_KEY:
            raise StageNotFoundError(stage_key)

    @staticmethod
    def _content_fingerprint(value: Any) -> str:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _ensure_unlocked(self, project: dict[str, Any], stage_key: str) -> None:
        self._require_stage(stage_key)
        definition = STAGES_BY_KEY[stage_key]
        if definition.position == 1:
            return
        previous = project["stages"][definition.position - 2]
        if previous["status"] != StageStatus.APPROVED.value:
            raise StageLockedError(
                f"stage '{stage_key}' is locked until '{previous['key']}' is approved"
            )
