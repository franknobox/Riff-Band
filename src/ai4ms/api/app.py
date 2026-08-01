from __future__ import annotations

import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from ai4ms.assets import DataAssetError
from ai4ms.connectors import DataCommonsConnector, MCPConnectorError
from ai4ms.db import ProjectStore
from ai4ms.delivery import DeliveryExportError
from ai4ms.domains import MANAGEMENT_SCIENCE_PROFILE
from ai4ms.inference import (
    InferenceUnavailableError,
    OpenAICompatibleGateway,
    inference_status,
)
from ai4ms.knowledge import (
    KnowledgeEvaluationOutputError,
    KnowledgeEvaluationService,
    KnowledgeRegistry,
)
from ai4ms.literature.service import LiteratureSearchInputError, LiteratureSearchService
from ai4ms.prompts import PromptCatalog
from ai4ms.runners import (
    AnalysisJobConflictError,
    AnalysisJobNotFoundError,
    AnalysisRunnerService,
    AnalysisRunBlockedError,
)
from ai4ms.search import WebResearchService
from ai4ms.services.models import (
    AnalysisRerunRequest,
    AnalysisRunRequest,
    ConnectorToolRequest,
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
    StageAssetSectionPatchRequest,
    StageDecisionRequest,
    StageRestoreRequest,
    StageSuggestionDecisionRequest,
    StageSuggestionGenerateRequest,
    StageToolInvokeRequest,
    StageUpdateRequest,
    StageWorkspaceUpdateRequest,
    UpdateProjectRequest,
    UserProfileUpdateRequest,
)
from ai4ms.services.project_service import (
    ProjectNotFoundError,
    ProjectService,
    StageLockedError,
    StageNotFoundError,
    StageRevisionConflictError,
)
from ai4ms.services.stage_generation import (
    StageContentValidationError,
    StageGenerationNotSupportedError,
    StageGenerationOutputError,
    StageGenerationService,
)
from ai4ms.services.stage_chat import StageChatService
from ai4ms.services.stage_assistant import (
    StageAssistantError,
    StageAssistantService,
    StageSuggestionOutputError,
)
from ai4ms.services.knowledge_jobs import KnowledgeEvaluationJobNotFoundError


REPO_ROOT = Path(__file__).resolve().parents[3]
LOGGER = logging.getLogger("ai4ms.api")
load_dotenv(REPO_ROOT / ".env", override=False)
load_dotenv(REPO_ROOT / ".env.stata-runner.local", override=True)


def _web_root() -> Path | None:
    configured = os.environ.get("AI4MS_WEB_ROOT", "").strip()
    candidates = [
        Path(configured) if configured else None,
        REPO_ROOT / "src" / "web" / "dist",
        REPO_ROOT / "src" / "web" / "out",
    ]
    return next((path for path in candidates if path is not None and path.exists()), None)


def _default_data_dir() -> Path:
    configured = os.environ.get("AI4MS_DATA_DIR", "").strip()
    return Path(configured) if configured else REPO_ROOT / "workspace" / "ai4ms"


def create_app(
    data_dir: str | Path | None = None,
    stage_generation: StageGenerationService | None = None,
    literature_search: LiteratureSearchService | None = None,
    analysis_runner: AnalysisRunnerService | None = None,
    knowledge_evaluation: KnowledgeEvaluationService | None = None,
    stage_chat: StageChatService | None = None,
    data_commons: DataCommonsConnector | None = None,
    research_service: WebResearchService | None = None,
    stage_assistant: StageAssistantService | None = None,
) -> FastAPI:
    resolved_data_dir = Path(data_dir) if data_dir is not None else _default_data_dir()
    web_root = _web_root()
    connector = data_commons or DataCommonsConnector()
    resolved_research_service = research_service or WebResearchService(
        resolved_data_dir / "projects",
        data_commons=connector,
    )
    resolved_stage_chat = stage_chat or StageChatService(
        resolved_data_dir / "projects",
        research_service=resolved_research_service,
    )
    service = ProjectService(
        ProjectStore(resolved_data_dir / "ai4ms.db"),
        resolved_data_dir,
        stage_generation=stage_generation,
        literature_search=literature_search,
        analysis_runner=analysis_runner,
        knowledge_evaluation=knowledge_evaluation,
        stage_chat=resolved_stage_chat,
        research_service=resolved_research_service,
        stage_assistant=stage_assistant,
    )

    app = FastAPI(
        title="AI4MS 科研工作台 API",
        version="0.5.0",
        description="面向管理科学的本地优先 AI 科研工作台。",
    )
    app.state.project_service = service
    app.state.data_commons = connector
    app.state.research_service = resolved_research_service
    app.state.web_root = web_root

    origins = [item.strip() for item in os.environ.get("AI4MS_CORS_ORIGINS", "*").split(",") if item.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_service(request: Request) -> ProjectService:
        return request.app.state.project_service

    @app.exception_handler(ProjectNotFoundError)
    async def project_not_found(_request: Request, exc: ProjectNotFoundError):
        return _json_error(status.HTTP_404_NOT_FOUND, "project_not_found", str(exc))

    @app.exception_handler(StageNotFoundError)
    async def stage_not_found(_request: Request, exc: StageNotFoundError):
        return _json_error(status.HTTP_404_NOT_FOUND, "stage_not_found", str(exc))

    @app.exception_handler(StageLockedError)
    async def stage_locked(_request: Request, exc: StageLockedError):
        return _json_error(status.HTTP_409_CONFLICT, "stage_locked", str(exc))

    @app.exception_handler(StageRevisionConflictError)
    async def stage_revision_conflict(_request: Request, exc: StageRevisionConflictError):
        return _json_error(status.HTTP_409_CONFLICT, "revision_conflict", str(exc))

    @app.exception_handler(MCPConnectorError)
    async def mcp_connector_error(_request: Request, exc: MCPConnectorError):
        return _json_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "mcp_connector_unavailable",
            str(exc),
        )

    @app.exception_handler(StageGenerationNotSupportedError)
    async def generation_not_supported(_request: Request, exc: StageGenerationNotSupportedError):
        return _json_error(status.HTTP_409_CONFLICT, "model_generation_not_supported", str(exc))

    @app.exception_handler(InferenceUnavailableError)
    async def inference_unavailable(_request: Request, exc: InferenceUnavailableError):
        return _json_error(status.HTTP_503_SERVICE_UNAVAILABLE, "inference_unavailable", str(exc))

    @app.exception_handler(StageGenerationOutputError)
    async def invalid_model_output(_request: Request, exc: StageGenerationOutputError):
        return _json_error(status.HTTP_502_BAD_GATEWAY, "invalid_model_output", str(exc))

    @app.exception_handler(KnowledgeEvaluationOutputError)
    async def invalid_knowledge_evaluation(_request: Request, exc: KnowledgeEvaluationOutputError):
        return _json_error(status.HTTP_502_BAD_GATEWAY, "invalid_knowledge_evaluation", str(exc))

    @app.exception_handler(StageSuggestionOutputError)
    async def invalid_stage_suggestions(_request: Request, exc: StageSuggestionOutputError):
        return _json_error(
            status.HTTP_502_BAD_GATEWAY,
            "invalid_stage_suggestions",
            str(exc),
        )

    @app.exception_handler(StageAssistantError)
    async def stage_assistant_error(_request: Request, exc: StageAssistantError):
        code = (
            status.HTTP_404_NOT_FOUND
            if exc.code in {"stage_not_found", "suggestion_not_found"}
            else status.HTTP_409_CONFLICT
        )
        return _json_error(code, exc.code, str(exc))

    @app.exception_handler(KnowledgeEvaluationJobNotFoundError)
    async def knowledge_job_not_found(
        _request: Request,
        exc: KnowledgeEvaluationJobNotFoundError,
    ):
        return _json_error(
            status.HTTP_404_NOT_FOUND,
            "knowledge_evaluation_job_not_found",
            str(exc),
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        incident_id = f"err_{uuid4().hex[:12]}"
        LOGGER.exception(
            "Unhandled AI4MS API error incident=%s method=%s path=%s",
            incident_id,
            request.method,
            request.url.path,
        )
        return _json_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            f"服务端处理失败，请重试；错误编号：{incident_id}",
        )

    @app.exception_handler(LiteratureSearchInputError)
    async def invalid_literature_search(_request: Request, exc: LiteratureSearchInputError):
        return _json_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_literature_search", str(exc))

    @app.exception_handler(StageContentValidationError)
    async def invalid_stage_content(_request: Request, exc: StageContentValidationError):
        return _json_error(status.HTTP_409_CONFLICT, "invalid_stage_content", str(exc))

    @app.exception_handler(DeliveryExportError)
    async def invalid_delivery_export(_request: Request, exc: DeliveryExportError):
        return _json_error(status.HTTP_409_CONFLICT, "delivery_export_failed", str(exc))

    @app.exception_handler(DataAssetError)
    async def invalid_data_asset(_request: Request, exc: DataAssetError):
        return _json_error(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.code, str(exc))

    @app.exception_handler(AnalysisJobNotFoundError)
    async def analysis_job_not_found(_request: Request, exc: AnalysisJobNotFoundError):
        return _json_error(status.HTTP_404_NOT_FOUND, "analysis_job_not_found", str(exc))

    @app.exception_handler(AnalysisJobConflictError)
    async def analysis_job_conflict(_request: Request, exc: AnalysisJobConflictError):
        return _json_error(status.HTTP_409_CONFLICT, "analysis_job_conflict", str(exc))

    @app.exception_handler(AnalysisRunBlockedError)
    async def analysis_run_blocked(_request: Request, exc: AnalysisRunBlockedError):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "code": "analysis_preflight_blocked",
                    "message": str(exc),
                },
                "preflight": exc.preflight,
            },
        )

    @app.get("/", include_in_schema=False)
    async def web_workbench():
        if web_root is None:
            raise HTTPException(status_code=503, detail="web workbench assets are unavailable")
        index = web_root / "index.html"
        if not index.exists():
            raise HTTPException(status_code=503, detail="web workbench assets are unavailable")
        return FileResponse(index)

    @app.get("/healthz", tags=["system"])
    async def healthz():
        return {"status": "ok", "service": "ai4ms-workbench", "version": app.version}

    @app.get("/api/v1/meta/stages", tags=["meta"])
    async def stage_definitions(request: Request):
        return {"items": get_service(request).stage_definitions()}

    @app.get("/api/v1/meta/domain-profile", tags=["meta"])
    async def domain_profile():
        return MANAGEMENT_SCIENCE_PROFILE.model_dump()

    @app.get("/api/v1/meta/inference", tags=["meta"])
    async def model_inference_status():
        return inference_status()

    @app.post("/api/v1/meta/inference/probe", tags=["meta"])
    async def probe_model_inference():
        result = await OpenAICompatibleGateway(max_tokens=256).generate(
            "You are a connectivity probe for the AI4MS research workbench.",
            "Reply with AI4MS_READY and nothing else.",
        )
        return {
            "status": "ok",
            "configured": True,
            "model": result.model,
            "usage": result.usage,
        }

    @app.post("/api/v1/meta/search/probe", tags=["meta"])
    async def probe_web_search(request: Request):
        research: WebResearchService = request.app.state.research_service
        result = await research.probe_search()
        if result["status"] != "ok":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "serper_search_unavailable",
                    "message": result["error"],
                },
            )
        return result

    @app.get("/api/v1/connectors", tags=["connectors"])
    async def list_connectors(request: Request):
        return {"items": [request.app.state.data_commons.status()]}

    @app.get("/api/v1/connectors/datacommons/tools", tags=["connectors"])
    async def list_datacommons_tools(request: Request):
        connector_service: DataCommonsConnector = request.app.state.data_commons
        return {"items": await connector_service.list_tools()}

    @app.post("/api/v1/connectors/datacommons/query", tags=["connectors"])
    async def query_datacommons(
        payload: ConnectorToolRequest,
        request: Request,
    ):
        connector_service: DataCommonsConnector = request.app.state.data_commons
        if payload.arguments:
            return await connector_service.call_tool(
                payload.tool_name,
                payload.arguments,
            )
        if payload.tool_name == "search_indicators" and payload.query:
            return await connector_service.search_indicators(payload.query)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "query is required for search_indicators; "
                "arguments are required for get_observations"
            ),
        )

    @app.get("/api/v1/meta/prompts", tags=["meta"])
    async def prompt_registry(response: Response):
        manifest = PromptCatalog.manifest()
        version = manifest["registry_version"]
        response.headers["ETag"] = f'W/"prompts-{version}"'
        response.headers["X-AI4MS-Prompt-Registry-Version"] = version
        return manifest

    @app.get("/api/v1/knowledge/methods", tags=["knowledge"])
    async def method_registry(
        request: Request,
        goal: str = "",
        q: str = "",
        limit: int = 10,
    ):
        return {
            "items": get_service(request).method_registry(goal, q, limit)
        }

    @app.get("/api/v1/knowledge/data-sources", tags=["knowledge"])
    async def data_source_registry(q: str = "", limit: int = 12):
        return {"items": KnowledgeRegistry.data_source_candidates(q, limit)}

    @app.get("/api/v1/knowledge/formulas", tags=["knowledge"])
    async def formula_registry(
        request: Request,
        q: str = "",
        method_id: list[str] | None = None,
        limit: int = 12,
    ):
        return {
            "items": get_service(request).formula_registry(
                q,
                method_id or [],
                limit,
            )
        }

    @app.get("/api/v1/knowledge/candidates", tags=["knowledge-governance"])
    async def list_knowledge_candidates(
        request: Request,
        kind: str | None = None,
        candidate_status: str | None = None,
    ):
        return {
            "items": get_service(request).list_knowledge_candidates(
                kind,
                candidate_status,
            )
        }

    @app.post(
        "/api/v1/knowledge/candidates/discover",
        tags=["knowledge-governance"],
    )
    async def discover_knowledge_candidates(
        payload: KnowledgeDiscoveryRequest,
        request: Request,
    ):
        return await get_service(request).discover_knowledge_candidates(
            payload
        )

    @app.patch(
        "/api/v1/knowledge/candidates/{candidate_id}/review",
        tags=["knowledge-governance"],
    )
    async def review_knowledge_candidate(
        candidate_id: str,
        payload: KnowledgeCandidateReviewRequest,
        request: Request,
    ):
        return get_service(request).review_knowledge_candidate(
            candidate_id,
            payload,
        )

    @app.post(
        "/api/v1/knowledge/records",
        tags=["knowledge-governance"],
        status_code=status.HTTP_201_CREATED,
    )
    async def create_knowledge_record(
        payload: KnowledgeRecordCreateRequest,
        request: Request,
    ):
        return get_service(request).create_knowledge_record(payload)

    @app.get(
        "/api/v1/knowledge/records",
        tags=["knowledge-governance"],
    )
    async def list_knowledge_records(
        request: Request,
        kind: str | None = None,
    ):
        return {
            "items": get_service(request).list_knowledge_records(kind)
        }

    @app.get(
        "/api/v1/knowledge/records/{record_id}",
        tags=["knowledge-governance"],
    )
    async def get_knowledge_record(record_id: str, request: Request):
        return get_service(request).get_knowledge_record(record_id)

    @app.patch(
        "/api/v1/knowledge/records/{record_id}",
        tags=["knowledge-governance"],
    )
    async def patch_knowledge_record(
        record_id: str,
        payload: KnowledgeRecordPatchRequest,
        request: Request,
    ):
        return get_service(request).patch_knowledge_record(
            record_id,
            payload,
        )

    @app.get(
        "/api/v1/knowledge/records/{record_id}/revisions",
        tags=["knowledge-governance"],
    )
    async def list_knowledge_record_revisions(
        record_id: str,
        request: Request,
    ):
        return {
            "items": get_service(
                request
            ).list_knowledge_record_revisions(record_id)
        }

    @app.get("/api/v1/knowledge/diagnostics", tags=["knowledge"])
    async def diagnostic_registry(
        response: Response,
        q: str = "",
        family: str = "",
        level: str = "",
        stage: str = "",
        limit: int = 100,
    ):
        registry = KnowledgeRegistry.diagnostic_registry()
        items = KnowledgeRegistry.diagnostic_rules(
            q, family, level, stage, limit
        )
        version = registry["registry_version"]
        response.headers["ETag"] = f'W/"diagnostics-{version}"'
        response.headers["X-AI4MS-Registry-Version"] = version
        return {
            "schema_version": registry["schema_version"],
            "registry_version": version,
            "published_at": registry["published_at"],
            "authority": registry["authority"],
            "count": len(items),
            "total": len(registry["rules"]),
            "items": items,
        }

    @app.get("/api/v1/knowledge/diagnostics/{rule_id}", tags=["knowledge"])
    async def diagnostic_rule(rule_id: str, response: Response):
        registry = KnowledgeRegistry.diagnostic_registry()
        item = KnowledgeRegistry.diagnostic_rule(rule_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"diagnostic rule not found: {rule_id}",
            )
        version = registry["registry_version"]
        response.headers["ETag"] = f'W/"diagnostics-{version}-{item["id"]}"'
        response.headers["X-AI4MS-Registry-Version"] = version
        return {
            "schema_version": registry["schema_version"],
            "registry_version": version,
            "item": item,
        }

    @app.get("/api/v1/profile", tags=["profile"])
    async def get_user_profile(request: Request):
        return get_service(request).get_user_profile()

    @app.patch("/api/v1/profile", tags=["profile"])
    async def update_user_profile(
        payload: UserProfileUpdateRequest, request: Request
    ):
        return get_service(request).update_user_profile(payload)

    @app.get("/api/v1/runners/stata", tags=["runners"])
    async def stata_runner_status(request: Request):
        return get_service(request).analysis_runner.status()

    @app.get("/api/v1/projects", tags=["projects"])
    async def list_projects(request: Request):
        return {"items": get_service(request).list_projects()}

    @app.post("/api/v1/projects", tags=["projects"], status_code=status.HTTP_201_CREATED)
    async def create_project(payload: CreateProjectRequest, request: Request):
        return get_service(request).create_project(payload)

    @app.get("/api/v1/projects/{project_id}", tags=["projects"])
    async def get_project(project_id: str, request: Request):
        return get_service(request).get_project(project_id)

    @app.get("/api/v1/projects/{project_id}/assets/data", tags=["data-assets"])
    async def list_data_assets(project_id: str, request: Request):
        return {"items": get_service(request).list_data_assets(project_id)}

    @app.post(
        "/api/v1/projects/{project_id}/assets/data",
        tags=["data-assets"],
        status_code=status.HTTP_201_CREATED,
    )
    async def upload_data_asset(
        project_id: str,
        request: Request,
        file: UploadFile = File(...),
    ):
        try:
            return await get_service(request).upload_data_asset(
                project_id,
                file.filename or "",
                file.content_type or "application/octet-stream",
                file.read,
            )
        finally:
            await file.close()

    @app.patch("/api/v1/projects/{project_id}", tags=["projects"])
    async def update_project(project_id: str, payload: UpdateProjectRequest, request: Request):
        return get_service(request).update_project(project_id, payload)

    @app.get("/api/v1/projects/{project_id}/stages/current", tags=["stages"])
    async def get_current_stage(project_id: str, request: Request):
        project = get_service(request).get_project(project_id)
        stage = next(item for item in project["stages"] if item["key"] == project["current_stage"])
        return stage

    @app.get("/api/v1/projects/{project_id}/stages/{stage_key}", tags=["stages"])
    async def get_stage(project_id: str, stage_key: str, request: Request):
        return get_service(request).get_stage(project_id, stage_key)

    @app.get(
        "/api/v1/projects/{project_id}/stages/{stage_key}/revisions",
        tags=["stages"],
    )
    async def list_stage_revisions(project_id: str, stage_key: str, request: Request):
        return {
            "items": get_service(request).list_stage_revisions(project_id, stage_key)
        }

    @app.post(
        "/api/v1/projects/{project_id}/stages/{stage_key}/restore",
        tags=["stages"],
    )
    async def restore_stage_revision(
        project_id: str,
        stage_key: str,
        payload: StageRestoreRequest,
        request: Request,
    ):
        return get_service(request).restore_stage_revision(
            project_id, stage_key, payload
        )

    @app.put("/api/v1/projects/{project_id}/stages/{stage_key}", tags=["stages"])
    async def update_stage(project_id: str, stage_key: str, payload: StageUpdateRequest, request: Request):
        return get_service(request).update_stage(project_id, stage_key, payload)

    @app.patch("/api/v1/projects/{project_id}/stages/{stage_key}/workspace", tags=["stages"])
    async def update_stage_workspace(
        project_id: str,
        stage_key: str,
        payload: StageWorkspaceUpdateRequest,
        request: Request,
    ):
        return get_service(request).update_stage_workspace(project_id, stage_key, payload)

    @app.patch(
        "/api/v1/projects/{project_id}/stages/{stage_key}/asset-sections/{section_key}",
        tags=["stages"],
    )
    async def update_stage_asset_section(
        project_id: str,
        stage_key: str,
        section_key: str,
        payload: StageAssetSectionPatchRequest,
        request: Request,
    ):
        return get_service(request).update_stage_asset_section(
            project_id, stage_key, section_key, payload
        )

    @app.post("/api/v1/projects/{project_id}/stages/{stage_key}/draft", tags=["stages"])
    async def create_stage_draft(project_id: str, stage_key: str, payload: DraftRequest, request: Request):
        return await get_service(request).create_draft(project_id, stage_key, payload)

    @app.get(
        "/api/v1/projects/{project_id}/stages/{stage_key}/chat",
        tags=["stage-chat"],
    )
    async def list_stage_chat(
        project_id: str,
        stage_key: str,
        request: Request,
        limit: int = 50,
    ):
        return {
            "items": get_service(request).list_stage_chat(
                project_id,
                stage_key,
                max(1, min(limit, 200)),
            )
        }

    @app.post(
        "/api/v1/projects/{project_id}/stages/{stage_key}/chat",
        tags=["stage-chat"],
    )
    async def chat_stage(
        project_id: str,
        stage_key: str,
        payload: StageChatRequest,
        request: Request,
    ):
        return await get_service(request).chat_stage(project_id, stage_key, payload)

    @app.post(
        "/api/v1/projects/{project_id}/stages/problem/question-selection",
        tags=["problem"],
    )
    async def select_problem_question(
        project_id: str,
        payload: ProblemQuestionSelectionRequest,
        request: Request,
    ):
        return get_service(request).select_problem_question(project_id, payload)

    @app.post(
        "/api/v1/projects/{project_id}/stages/literature/plan-review",
        tags=["literature"],
    )
    async def review_literature_plan(
        project_id: str,
        payload: LiteraturePlanReviewRequest,
        request: Request,
    ):
        return get_service(request).review_literature_plan(project_id, payload)

    @app.post(
        "/api/v1/projects/{project_id}/stages/{stage_key}/tools/invoke",
        tags=["stage-tools"],
    )
    async def invoke_stage_tool(
        project_id: str,
        stage_key: str,
        payload: StageToolInvokeRequest,
        request: Request,
    ):
        return await get_service(request).invoke_stage_tool(
            project_id,
            stage_key,
            payload,
        )

    @app.get(
        "/api/v1/projects/{project_id}/stages/{stage_key}/suggestions",
        tags=["stage-suggestions"],
    )
    async def get_stage_suggestions(
        project_id: str,
        stage_key: str,
        request: Request,
    ):
        return get_service(request).get_stage_suggestions(project_id, stage_key)

    @app.post(
        "/api/v1/projects/{project_id}/stages/{stage_key}/suggestions",
        tags=["stage-suggestions"],
    )
    async def generate_stage_suggestions(
        project_id: str,
        stage_key: str,
        payload: StageSuggestionGenerateRequest,
        request: Request,
    ):
        return await get_service(request).generate_stage_suggestions(
            project_id,
            stage_key,
            payload,
        )

    @app.post(
        "/api/v1/projects/{project_id}/stages/{stage_key}/suggestions/{suggestion_id}/decision",
        tags=["stage-suggestions"],
    )
    async def decide_stage_suggestion(
        project_id: str,
        stage_key: str,
        suggestion_id: str,
        payload: StageSuggestionDecisionRequest,
        request: Request,
    ):
        return get_service(request).decide_stage_suggestion(
            project_id,
            stage_key,
            suggestion_id,
            payload,
        )

    @app.post("/api/v1/projects/{project_id}/stages/literature/search", tags=["literature"])
    async def search_literature(project_id: str, payload: LiteratureSearchRequest, request: Request):
        return await get_service(request).search_literature(project_id, payload)

    @app.patch(
        "/api/v1/projects/{project_id}/stages/literature/papers/{paper_id}/screening",
        tags=["literature"],
    )
    async def screen_literature_paper(
        project_id: str,
        paper_id: str,
        payload: LiteratureScreeningRequest,
        request: Request,
    ):
        return get_service(request).screen_literature_paper(
            project_id, paper_id, payload
        )

    @app.get(
        "/api/v1/projects/{project_id}/evidence-candidates",
        tags=["evidence-library"],
    )
    async def list_evidence_candidates(project_id: str, request: Request):
        return {
            "items": get_service(request).list_evidence_candidates(project_id)
        }

    @app.post(
        "/api/v1/projects/{project_id}/evidence-candidates/discover",
        tags=["evidence-library"],
    )
    async def discover_evidence_candidates(
        project_id: str,
        payload: EvidenceDiscoveryRequest,
        request: Request,
    ):
        return await get_service(request).discover_evidence_candidates(
            project_id,
            payload,
        )

    @app.patch(
        "/api/v1/projects/{project_id}/evidence-candidates/{candidate_id}/review",
        tags=["evidence-library"],
    )
    async def review_evidence_candidate(
        project_id: str,
        candidate_id: str,
        payload: EvidenceCandidateReviewRequest,
        request: Request,
    ):
        return get_service(request).review_evidence_candidate(
            project_id,
            candidate_id,
            payload,
        )

    @app.get(
        "/api/v1/projects/{project_id}/evidence-library",
        tags=["evidence-library"],
    )
    async def list_evidence_library(project_id: str, request: Request):
        return {
            "items": get_service(request).list_evidence_library(project_id)
        }

    @app.get(
        "/api/v1/projects/{project_id}/evidence-library/{evidence_id}",
        tags=["evidence-library"],
    )
    async def get_evidence_record(
        project_id: str,
        evidence_id: str,
        request: Request,
    ):
        return get_service(request).get_evidence_record(
            project_id,
            evidence_id,
        )

    @app.patch(
        "/api/v1/projects/{project_id}/evidence-library/{evidence_id}",
        tags=["evidence-library"],
    )
    async def patch_evidence_record(
        project_id: str,
        evidence_id: str,
        payload: EvidenceRecordPatchRequest,
        request: Request,
    ):
        return get_service(request).patch_evidence_record(
            project_id,
            evidence_id,
            payload,
        )

    @app.get(
        "/api/v1/projects/{project_id}/knowledge/evaluation",
        tags=["knowledge"],
    )
    async def get_knowledge_evaluation(project_id: str, request: Request):
        return get_service(request).get_knowledge_evaluation(project_id)

    @app.post(
        "/api/v1/projects/{project_id}/knowledge/evaluation",
        tags=["knowledge"],
    )
    async def evaluate_knowledge(
        project_id: str,
        payload: KnowledgeEvaluationRequest,
        request: Request,
    ):
        return await get_service(request).evaluate_knowledge(project_id, payload)

    @app.post(
        "/api/v1/projects/{project_id}/knowledge/evaluation/jobs",
        tags=["knowledge"],
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def submit_knowledge_evaluation(
        project_id: str,
        payload: KnowledgeEvaluationRequest,
        request: Request,
    ):
        return await get_service(request).submit_knowledge_evaluation(
            project_id,
            payload,
        )

    @app.get(
        "/api/v1/projects/{project_id}/knowledge/evaluation/jobs/{job_id}",
        tags=["knowledge"],
    )
    async def get_knowledge_evaluation_job(
        project_id: str,
        job_id: str,
        request: Request,
    ):
        return get_service(request).get_knowledge_evaluation_job(
            project_id,
            job_id,
        )

    @app.post("/api/v1/projects/{project_id}/stages/analysis/preflight", tags=["runners"])
    async def preflight_analysis_run(project_id: str, payload: AnalysisRunRequest, request: Request):
        return get_service(request).preflight_analysis_run(project_id, payload)

    @app.get("/api/v1/projects/{project_id}/stages/analysis/runs", tags=["runners"])
    async def list_analysis_runs(project_id: str, request: Request, limit: int = 20):
        return {
            "items": get_service(request).list_analysis_runs(project_id)[
                : max(1, min(limit, 100))
            ]
        }

    @app.post(
        "/api/v1/projects/{project_id}/stages/analysis/runs",
        tags=["runners"],
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def submit_analysis_run(project_id: str, payload: AnalysisRunRequest, request: Request):
        return await get_service(request).submit_analysis_run(project_id, payload)

    @app.get(
        "/api/v1/projects/{project_id}/stages/analysis/runs/{run_id}",
        tags=["runners"],
    )
    async def get_analysis_run(project_id: str, run_id: str, request: Request):
        return get_service(request).get_analysis_run(project_id, run_id)

    @app.get(
        "/api/v1/projects/{project_id}/stages/analysis/runs/{run_id}/result",
        tags=["runners"],
    )
    async def get_analysis_run_result(project_id: str, run_id: str, request: Request):
        return get_service(request).get_analysis_run_result(project_id, run_id)

    @app.get(
        "/api/v1/projects/{project_id}/stages/analysis/runs/{run_id}/artifacts/{artifact_path:path}",
        tags=["runners"],
    )
    async def get_analysis_run_artifact(
        project_id: str,
        run_id: str,
        artifact_path: str,
        request: Request,
    ):
        path = get_service(request).analysis_run_artifact(
            project_id, run_id, artifact_path
        )
        media_type = (
            "text/plain; charset=utf-8"
            if path.suffix.lower() in {".log", ".smcl", ".txt", ".csv"}
            else None
        )
        return FileResponse(
            path,
            media_type=media_type,
            filename=path.name,
            content_disposition_type="inline",
        )

    @app.post(
        "/api/v1/projects/{project_id}/stages/analysis/runs/{run_id}/cancel",
        tags=["runners"],
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def cancel_analysis_run(project_id: str, run_id: str, request: Request):
        return await get_service(request).cancel_analysis_run(project_id, run_id)

    @app.post(
        "/api/v1/projects/{project_id}/stages/analysis/runs/{run_id}/rerun",
        tags=["runners"],
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def rerun_analysis(
        project_id: str,
        run_id: str,
        payload: AnalysisRerunRequest,
        request: Request,
    ):
        return await get_service(request).rerun_analysis(project_id, run_id, payload)

    @app.post("/api/v1/projects/{project_id}/stages/delivery/export", tags=["delivery"])
    async def export_delivery(project_id: str, request: Request):
        return get_service(request).export_delivery(project_id)

    @app.get(
        "/api/v1/projects/{project_id}/stages/delivery/quality",
        tags=["delivery"],
    )
    async def get_delivery_quality(project_id: str, request: Request):
        return get_service(request).delivery_quality(project_id)

    @app.get("/api/v1/projects/{project_id}/exports/{export_id}/report", tags=["delivery"])
    async def get_visual_report(project_id: str, export_id: str, request: Request):
        path = get_service(request).delivery_artifact(project_id, export_id, "report")
        return FileResponse(
            path,
            media_type="text/html; charset=utf-8",
            filename=path.name,
            content_disposition_type="inline",
        )

    @app.get("/api/v1/projects/{project_id}/exports/{export_id}/word", tags=["delivery"])
    async def download_word_report(project_id: str, export_id: str, request: Request):
        path = get_service(request).delivery_artifact(project_id, export_id, "word")
        return FileResponse(
            path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=f"{project_id}-{export_id}.docx",
        )

    @app.get("/api/v1/projects/{project_id}/exports/{export_id}/pdf", tags=["delivery"])
    async def download_pdf_report(project_id: str, export_id: str, request: Request):
        path = get_service(request).delivery_artifact(project_id, export_id, "pdf")
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=f"{project_id}-{export_id}.pdf",
        )

    @app.get("/api/v1/projects/{project_id}/exports/{export_id}/stata", tags=["delivery"])
    async def download_stata_package(project_id: str, export_id: str, request: Request):
        path = get_service(request).delivery_artifact(project_id, export_id, "stata")
        return FileResponse(
            path,
            media_type="application/zip",
            filename=f"{project_id}-{export_id}-stata.zip",
        )

    @app.get("/api/v1/projects/{project_id}/exports/{export_id}/package", tags=["delivery"])
    async def download_research_package(project_id: str, export_id: str, request: Request):
        path = get_service(request).delivery_artifact(project_id, export_id, "package")
        return FileResponse(path, media_type="application/zip", filename=f"{project_id}-{export_id}.zip")

    @app.get("/api/v1/projects/{project_id}/exports/{export_id}/manifest", tags=["delivery"])
    async def get_delivery_manifest(project_id: str, export_id: str, request: Request):
        path = get_service(request).delivery_artifact(project_id, export_id, "manifest")
        return FileResponse(path, media_type="application/json; charset=utf-8", filename=path.name)

    @app.post("/api/v1/projects/{project_id}/stages/{stage_key}/decisions", tags=["approvals"])
    async def decide_stage(project_id: str, stage_key: str, payload: StageDecisionRequest, request: Request):
        return get_service(request).decide_stage(project_id, stage_key, payload)

    if web_root is not None:
        app.mount("/", StaticFiles(directory=web_root, html=True), name="web")

    return app


def _json_error(status_code: int, code: str, message: str):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


app = create_app()


def _entry() -> None:
    import uvicorn

    host = os.environ.get("AI4MS_HOST", "0.0.0.0")
    port = int(os.environ.get("AI4MS_PORT", "8000"))
    uvicorn.run("ai4ms.api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    _entry()
