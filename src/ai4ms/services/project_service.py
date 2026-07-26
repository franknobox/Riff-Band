from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ai4ms.assets import DataAssetService
from ai4ms.db.store import ProjectStore, RevisionConflictError
from ai4ms.delivery import DeliveryExportError, DeliveryExportService
from ai4ms.knowledge import KnowledgeEvaluationService
from ai4ms.literature.service import LiteratureSearchService
from ai4ms.orchestration import AOrchestraStageService
from ai4ms.prompts import PromptCatalog, get_stage_policy
from ai4ms.runners import (
    AnalysisJobConflictError,
    AnalysisJobService,
    AnalysisRunnerService,
)
from ai4ms.runners.stata import sha256_file
from ai4ms.services.models import (
    STAGE_DEFINITIONS,
    STAGES_BY_KEY,
    ApprovalDecision,
    AnalysisRerunRequest,
    AnalysisRunRequest,
    CreateProjectRequest,
    DraftRequest,
    KnowledgeEvaluationRequest,
    LiteratureSearchRequest,
    StageChatRequest,
    StageDecisionRequest,
    StageAssetSectionPatchRequest,
    StageRestoreRequest,
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


class ProjectNotFoundError(LookupError):
    pass


class StageNotFoundError(LookupError):
    pass


class StageLockedError(RuntimeError):
    pass


class StageRevisionConflictError(RuntimeError):
    pass


STAGE_TEMPLATES: dict[str, dict[str, Any]] = {
    "problem": {"initial_idea": "", "research_object": "", "problem_boundary": "", "objective": "", "questions": [], "candidate_gaps": [], "counter_searches": [], "unknowns": []},
    "literature": {"topic_summary": "", "query_blocks": [], "databases": [], "languages": [], "inclusion_criteria": [], "exclusion_criteria": [], "screening_questions": [], "counter_searches": [], "sources": [], "papers": [], "search_runs": [], "research_streams": [], "syntheses": [], "gap_candidates": [], "recommended_next_steps": [], "unknowns": [], "coverage_limits": []},
    "theory": {"theoretical_lenses": [], "constructs": [], "mechanisms": [], "research_questions": [], "competing_explanations": [], "falsifiable_propositions": [], "contribution_boundary": "", "unknowns": []},
    "design": {"research_question": "", "unit_of_analysis": "", "design_lane": "", "estimand_or_objective": "", "method_options": [], "primary_method_id": "", "assumptions": [], "falsification": [], "threats_to_validity": [], "stopping_conditions": [], "unknowns": []},
    "data": {"data_sources": [], "variables": [], "sample_definition": "", "time_coverage": "", "join_keys": [], "pii_class": "unknown", "privacy_risks": [], "ethics_checks": [], "quality_checks": [], "blocking_issues": [], "unknowns": []},
    "identification": {"design_lane": "", "estimand_or_objective": "", "analysis_sample": "", "unit_of_analysis": "", "variable_roles": [], "model_specifications": [], "diagnostics": [], "analysis_steps": [], "missing_data_plan": "", "multiplicity_plan": "", "robustness_plan": [], "stopping_conditions": [], "execution_engine": "unknown", "code_language": "", "stata_do_file": "", "seed": None, "expected_outputs": [], "reproducibility_requirements": [], "unknowns": []},
    "analysis": {"execution_engine": "unknown", "readiness_summary": "", "expected_outputs": [], "preflight_checks": [], "result_review_checks": [], "runner_status": "not_checked", "approved_analysis_plan_revision": 0, "approved_analysis_plan_hash": "", "do_file": "", "runs": [], "results": [], "blocking_issues": [], "unknowns": []},
    "robustness": {"robustness_matrix": [], "failed_checks": [], "interpretation_limits": [], "next_runs": [], "reproducibility_report": "", "unknowns": []},
    "evidence": {"claims": [], "mechanisms": [], "heterogeneity": [], "limitations": [], "interpretation": "", "unknowns": []},
    "delivery": {"title": "", "executive_summary": "", "conclusions": [], "policy_implications": [], "outline": [], "reference_paper_ids": [], "approved_claims": [], "references": [], "limitations": [], "reproducibility_notes": [], "disclosure": "", "release_notes": "", "unknowns": [], "exports": [], "visual_report_path": "", "research_package_path": ""},
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
        self.stage_chat = stage_chat or StageChatService(self.projects_dir)
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

    async def search_literature(self, project_id: str, request: LiteratureSearchRequest) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "literature")
        stage = next(item for item in project["stages"] if item["key"] == "literature")
        content = deepcopy(STAGE_TEMPLATES["literature"])
        content.update(stage.get("content") or {})
        search_run = await self.literature_search.search(project_id, content, request)
        content["papers"] = search_run.pop("papers")
        content["sources"] = search_run["source_runs"]
        content.setdefault("search_runs", []).append(search_run)
        update = StageUpdateRequest(
            content=content,
            change_reason=f"Executed literature search {search_run['search_id']}",
            author_type="agent",
        )
        return self.update_stage(project_id, "literature", update)

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
            if stage_key == "literature":
                if not content.get("search_runs"):
                    raise StageContentValidationError(
                        "S1 批准前必须执行至少一次可追溯文献检索"
                    )
                if not content.get("papers"):
                    raise StageContentValidationError(
                        "S1 检索未形成可追溯论文记录，不能进入下一阶段"
                    )
            if stage_key == "delivery":
                exports = content.get("exports", [])
                if not exports:
                    raise StageContentValidationError(
                        "G5 批准前必须生成 HTML 报告与研究包"
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
