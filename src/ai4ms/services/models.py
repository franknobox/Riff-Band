from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StageStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    BLOCKED = "blocked"


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ApprovalDecision(str, Enum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"


class StageDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    code: str
    position: int
    title: str
    short_title: str
    description: str
    artifact_type: str
    gate: str | None = None


STAGE_DEFINITIONS: tuple[StageDefinition, ...] = (
    StageDefinition(key="problem", code="S0", position=1, title="问题识别", short_title="问题识别", description="澄清研究对象、问题边界、已有认识和候选研究空白。", artifact_type="TopicBrief", gate="G0"),
    StageDefinition(key="literature", code="S1", position=2, title="文献综述", short_title="文献综述", description="检索、筛选并组织论文、研究流派、共识、争议和覆盖限制。", artifact_type="RelatedResearchReport", gate="覆盖检查"),
    StageDefinition(key="theory", code="S2", position=3, title="理论构建", short_title="理论构建", description="形成理论机制、研究问题、竞争解释和可证伪命题。", artifact_type="TheoryModel", gate="G1 前置"),
    StageDefinition(key="design", code="S3", position=4, title="研究设计", short_title="研究设计", description="确认分析单位、主备设计、识别假设、风险和停止条件。", artifact_type="ResearchProtocol", gate="G1"),
    StageDefinition(key="data", code="S4", position=5, title="数据与变量", short_title="数据与变量", description="确认数据合同、变量口径、许可、隐私、伦理和质量风险。", artifact_type="DataContract", gate="G2"),
    StageDefinition(key="identification", code="S5", position=6, title="识别与检验", short_title="识别与检验", description="冻结估计目标、分析计划、模型设定、诊断与代码计划。", artifact_type="AnalysisPlan", gate="G3"),
    StageDefinition(key="analysis", code="S6", position=7, title="结果分析", short_title="结果分析", description="管理获批代码、Runner、运行日志、结果和可复现产物。", artifact_type="RunArtifact", gate="G3 后运行"),
    StageDefinition(key="robustness", code="S7", position=8, title="稳健性检验", short_title="稳健性检验", description="执行替代口径、模型、样本和安慰剂检验，并保留失败结果。", artifact_type="RobustnessReport", gate="G4 前置"),
    StageDefinition(key="evidence", code="S8", position=9, title="机制与异质性", short_title="机制与异质性", description="连接核心主张、机制、异质性、支持证据、反证和解释边界。", artifact_type="ClaimEvidence", gate="G4"),
    StageDefinition(key="delivery", code="S9", position=10, title="结论与政策含义", short_title="结论与政策", description="生成论文草稿、政策含义、引用、HTML 报告和可复现发布包。", artifact_type="ResearchPackage", gate="G5"),
)

STAGES_BY_KEY = {stage.key: stage for stage in STAGE_DEFINITIONS}


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    initial_idea: str = Field(min_length=1, max_length=4000)

    @field_validator("title", "initial_idea")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class UpdateProjectRequest(CreateProjectRequest):
    pass


class UserProfileUpdateRequest(BaseModel):
    interface_theme: Literal["graphite", "blueprint", "paper"]


class StageUpdateRequest(BaseModel):
    content: dict[str, Any]
    change_reason: str = Field(default="", max_length=500)
    author_type: str = Field(default="human", pattern="^(human|agent|import)$")


class ProjectWorkspaceContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(default="", max_length=80)
    icon: str = Field(default="研", max_length=4)
    discipline: str = Field(default="管理科学研究", max_length=160)
    sample_window: str = Field(default="", max_length=160)
    keywords: str = Field(default="", max_length=2000)
    data_sources: list[str] = Field(default_factory=list, max_length=50)
    owner: str = Field(default="当前研究者", max_length=160)
    reviewers: str = Field(default="导师 + 方法审核者", max_length=500)


class StageWorkspaceContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", max_length=500)
    summary: str = Field(default="", max_length=8000)
    objective: str = Field(default="", max_length=8000)
    content: str = Field(default="", max_length=100_000)
    scope: str = Field(default="", max_length=20_000)
    evidence_note: str = Field(default="", max_length=20_000)
    decision: str = Field(default="", max_length=20_000)
    risk: str = Field(default="", max_length=20_000)
    handoff: str = Field(default="", max_length=20_000)
    human_confirmed: bool = False
    sync_history: list[str] = Field(default_factory=list, max_length=100)
    project_context: ProjectWorkspaceContext | None = None

    @field_validator("sync_history")
    @classmethod
    def limit_sync_history_items(cls, values: list[str]) -> list[str]:
        return [str(value).strip()[:1000] for value in values if str(value).strip()]


class StageWorkspaceUpdateRequest(BaseModel):
    workspace: StageWorkspaceContent
    expected_revision: int = Field(ge=0)
    change_reason: str = Field(default="", max_length=500)


class StageAssetSectionPatchRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(max_length=100_000)
    expected_revision: int = Field(ge=1)
    change_reason: str = Field(default="", max_length=500)

    @field_validator("title")
    @classmethod
    def clean_asset_section_title(cls, value: str) -> str:
        return value.strip()


class StageRestoreRequest(BaseModel):
    revision: int = Field(ge=1)
    expected_revision: int = Field(ge=1)
    change_reason: str = Field(default="", max_length=500)


class StageDecisionRequest(BaseModel):
    decision: ApprovalDecision
    reason: str = Field(default="", max_length=1000)
    actor_type: str = Field(default="human", pattern="^human$")


class DraftRequest(BaseModel):
    instruction: str = Field(default="", max_length=2000)
    generation_mode: Literal["template", "model"] = "template"


class StageChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12_000)
    search_mode: Literal["auto", "on", "off"] = "auto"

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message must not be blank")
        return cleaned


class StageToolInvokeRequest(BaseModel):
    tool_id: str = Field(min_length=1, max_length=120)
    query: str = Field(default="", max_length=4000)
    instruction: str = Field(default="", max_length=4000)

    @field_validator("tool_id", "query", "instruction")
    @classmethod
    def strip_stage_tool_text(cls, value: str) -> str:
        return value.strip()


class StageSuggestionGenerateRequest(BaseModel):
    instruction: str = Field(default="", max_length=2000)

    @field_validator("instruction")
    @classmethod
    def strip_suggestion_instruction(cls, value: str) -> str:
        return value.strip()


class StageSuggestionDecisionRequest(BaseModel):
    state: Literal["pending", "accepted", "modified", "rejected"]
    note: str = Field(default="", max_length=2000)

    @field_validator("note")
    @classmethod
    def strip_suggestion_note(cls, value: str) -> str:
        return value.strip()


class ConnectorToolRequest(BaseModel):
    query: str = Field(default="", max_length=12_000)
    tool_name: Literal["search_indicators", "get_observations"] = "search_indicators"
    arguments: dict[str, Any] = Field(default_factory=dict)

    @field_validator("query")
    @classmethod
    def strip_connector_query(cls, value: str) -> str:
        return value.strip()


class ProblemQuestionSelectionRequest(BaseModel):
    selected_question_id: str = Field(pattern=r"^RQ[0-9_-]+$")
    rationale: str = Field(min_length=3, max_length=2000)
    expected_revision: int = Field(ge=1)
    actor_type: str = Field(default="human", pattern="^human$")


class LiteraturePlanReviewRequest(BaseModel):
    decision: Literal["approve", "request_changes"]
    reason: str = Field(min_length=3, max_length=2000)
    expected_revision: int = Field(ge=1)
    actor_type: str = Field(default="human", pattern="^human$")


class LiteratureScreeningRequest(BaseModel):
    decision: Literal["include", "exclude", "unsure"]
    reason: str = Field(min_length=3, max_length=2000)
    evidence_level: Literal["metadata", "abstract", "full_text"]
    expected_revision: int = Field(ge=1)
    actor_type: str = Field(default="human", pattern="^human$")


class EvidenceDiscoveryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    candidate_type: Literal["literature", "data_study"]
    expected_revision: int = Field(ge=0)
    limit: int = Field(default=8, ge=1, le=15)
    actor_type: str = Field(default="agent", pattern="^agent$")

    @field_validator("query")
    @classmethod
    def clean_evidence_query(cls, value: str) -> str:
        return " ".join(value.split())


class EvidenceCandidateReviewRequest(BaseModel):
    decision: Literal["approve", "reject", "request_changes"]
    reason: str = Field(min_length=3, max_length=2000)
    expected_revision: int = Field(ge=1)
    evidence_level: Literal["metadata", "abstract", "full_text", "source_page"]
    edits: dict[str, Any] = Field(default_factory=dict, max_length=30)
    actor_type: str = Field(default="human", pattern="^human$")


class EvidenceRecordPatchRequest(BaseModel):
    edits: dict[str, Any] = Field(min_length=1, max_length=30)
    reason: str = Field(min_length=3, max_length=2000)
    expected_revision: int = Field(ge=1)
    actor_type: str = Field(default="human", pattern="^human$")


KnowledgeAssetKind = Literal["method", "formula"]


class KnowledgeDiscoveryRequest(BaseModel):
    kind: KnowledgeAssetKind
    query: str = Field(min_length=3, max_length=2000)
    limit: int = Field(default=6, ge=1, le=12)
    actor_type: str = Field(default="agent", pattern="^agent$")

    @field_validator("query")
    @classmethod
    def clean_knowledge_query(cls, value: str) -> str:
        return " ".join(value.split())


class KnowledgeCandidateReviewRequest(BaseModel):
    decision: Literal["approve", "reject", "request_changes"]
    reason: str = Field(min_length=3, max_length=2000)
    expected_revision: int = Field(ge=1)
    edits: dict[str, Any] = Field(default_factory=dict, max_length=40)
    actor_type: str = Field(default="human", pattern="^human$")


class KnowledgeRecordCreateRequest(BaseModel):
    kind: KnowledgeAssetKind
    content: dict[str, Any] = Field(min_length=1, max_length=60)
    reason: str = Field(min_length=3, max_length=2000)
    actor_type: str = Field(default="human", pattern="^human$")


class KnowledgeRecordPatchRequest(BaseModel):
    content: dict[str, Any] = Field(min_length=1, max_length=60)
    reason: str = Field(min_length=3, max_length=2000)
    expected_revision: int = Field(ge=1)
    actor_type: str = Field(default="human", pattern="^human$")


class LiteratureSearchRequest(BaseModel):
    queries: list[str] = Field(default_factory=list, max_length=12)
    backends: list[Literal["openalex", "crossref", "semantic_scholar", "arxiv"]] = Field(
        default_factory=lambda: ["openalex", "crossref", "semantic_scholar", "arxiv"],
        min_length=1,
        max_length=4,
    )
    limit_per_backend: int = Field(default=10, ge=1, le=20)
    max_queries: int = Field(default=4, ge=1, le=8)
    year_from: int | None = Field(default=None, ge=1800, le=2100)
    year_to: int | None = Field(default=None, ge=1800, le=2100)

    @field_validator("queries")
    @classmethod
    def clean_queries(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


class KnowledgeCandidateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=4000)
    assumptions: list[str] = Field(default_factory=list, max_length=20)


class KnowledgeEvaluationRequest(BaseModel):
    methods: list[KnowledgeCandidateInput] = Field(min_length=1, max_length=40)
    formulas: list[KnowledgeCandidateInput] = Field(default_factory=list, max_length=80)


class AnalysisRunRequest(BaseModel):
    input_asset_id: str = Field(default="", pattern=r"^(|data_[a-f0-9]{12})$")
    input_artifact_path: str = Field(default="", max_length=500)
    parameters: dict[str, Any] = Field(default_factory=dict)
    seed: int | None = Field(default=None, ge=0)
    timeout_seconds: int = Field(default=3600, ge=1, le=7200)
    requested_by: str = Field(default="human", pattern="^human$")

    @field_validator("input_artifact_path")
    @classmethod
    def clean_input_path(cls, value: str) -> str:
        return value.strip()

    @field_validator("parameters")
    @classmethod
    def limit_parameters(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 50:
            raise ValueError("parameters may contain at most 50 entries")
        return value


class AnalysisRerunRequest(BaseModel):
    timeout_seconds: int | None = Field(default=None, ge=1, le=7200)
