export type StageStatus =
  | "not_started"
  | "in_progress"
  | "needs_review"
  | "approved"
  | "blocked";

export type ApprovalDecision = "approve" | "request_changes" | "reject";

export interface ProjectSummary {
  project_id: string;
  title: string;
  initial_idea: string;
  status: "active" | "completed" | "archived";
  current_stage: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectStage {
  project_id: string;
  key: string;
  code: string;
  position: number;
  title: string;
  short_title: string;
  description: string;
  artifact_type: string;
  gate: string | null;
  status: StageStatus;
  revision: number;
  revision_id: string | null;
  content_hash: string | null;
  author_type: string | null;
  change_reason: string | null;
  revision_created_at: string | null;
  approved_at: string | null;
  updated_at: string;
  content: Record<string, unknown>;
  readiness: StageReadiness;
}

export interface StageToolPolicy {
  tool_id: string;
  purpose: string;
  risk_level: "R0" | "R1" | "R2" | "R3" | "R4" | "R5";
  call_when: string[];
  preconditions: string[];
  allowed_actions: string[];
  forbidden_actions: string[];
  failure_action: string;
  requires_human_confirmation: boolean;
}

export interface StageDefinition {
  key: string;
  code: string;
  position: number;
  title: string;
  short_title: string;
  description: string;
  artifact_type: string;
  gate: string | null;
  agent_policy: {
    stage_id: string;
    stage_key: string;
    title: string;
    principal_agent: string;
    mission: string;
    tools: StageToolPolicy[];
    human_decisions: string[];
    stop_conditions: string[];
  };
}

export interface StageReadiness {
  percent: number;
  completed: number;
  total: number;
  can_submit: boolean;
  checks: {
    artifact_saved: boolean;
    contract_valid: boolean;
    human_confirmed: boolean;
    approved: boolean;
  };
  missing: string[];
  validation_issue: string;
}

export interface StageRevision {
  revision_id: string;
  project_id: string;
  stage_key: string;
  revision: number;
  change_reason: string;
  author_type: string;
  content_hash: string;
  created_at: string;
}

export interface ApprovalEvent {
  approval_id: string;
  project_id: string;
  stage_key: string;
  revision: number;
  decision: ApprovalDecision;
  reason: string;
  actor_type: "human";
  created_at: string;
}

export interface Project extends ProjectSummary {
  stages: ProjectStage[];
  approvals: ApprovalEvent[];
  progress: { approved: number; total: number };
  data_assets: DataAsset[];
}

export interface DeliveryExportRecord {
  export_id: string;
  generated_at: string;
  source_delivery_revision: number;
  source_delivery_hash: string;
  source_content_fingerprint: string;
  visual_report_path: string;
  word_report_path: string;
  pdf_report_path: string;
  stata_package_path: string;
  research_package_path: string;
  manifest_path: string;
  file_count: number;
  word_sha256: string;
  pdf_sha256: string;
  stata_package_sha256: string;
  package_sha256: string;
}

export interface DataAssetColumn {
  name: string;
  label: string;
  storage_type: string;
  display_format: string;
  value_label: string;
}

export interface DataAsset {
  asset_id: string;
  project_id: string;
  original_name: string;
  stored_path: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
  metadata: {
    format: "stata_dta";
    format_version: string;
    data_label: string;
    time_stamp: string;
    row_count: number;
    column_count: number;
    columns: DataAssetColumn[];
    parsed_at: string;
  };
}

export interface RunnerStatus {
  available: boolean;
  engine: "stata";
  mode: "batch";
  transport?: "local_process" | "http_local_runner";
  executable_name: string;
  version: string;
  edition: string;
  os: string;
  locale: string;
  license_mode: string;
  license_confirmed: boolean;
  max_concurrency: number;
  reason: string;
}

export interface StructuredResult {
  result_id: string;
  kind: "estimate" | "diagnostic" | "test" | "summary";
  specification_id: string;
  term: string;
  label: string;
  estimate: number | null;
  std_error: number | null;
  statistic: number | null;
  p_value: number | null;
  ci_lower: number | null;
  ci_upper: number | null;
  sample_size: number | null;
  status: "observed" | "passed" | "failed" | "inconclusive";
  unit: string;
  source_file: string;
}

export interface AnalysisRun {
  run_id: string;
  status: "blocked" | "failed" | "succeeded" | "canceled";
  reason_code: string;
  exit_code: number | null;
  requested_at: string;
  input_asset_id: string;
  input_artifact_path: string;
  data_signature: string;
  structured_results: StructuredResult[];
  logs: string[];
  output_artifacts: Array<{ path: string; size: number; sha256: string }>;
  runner_error?: string;
}

export type AnalysisJobStatus =
  | "queued"
  | "running"
  | "canceling"
  | "succeeded"
  | "failed"
  | "canceled"
  | "interrupted";

export interface AnalysisJob {
  run_id: string;
  project_id: string;
  status: AnalysisJobStatus;
  reason_code: string;
  created_at: string;
  started_at: string;
  finished_at: string;
  timeout_seconds: number;
  cancel_requested: boolean;
  parent_run_id: string;
  request: {
    input_asset_id: string;
    input_artifact_path: string;
    parameters: Record<string, unknown>;
    seed: number | null;
    timeout_seconds: number;
    requested_by: "human";
  };
  run_manifest_path: string;
  error?: string;
}

export interface AnalysisPreflight {
  status: "ready" | "blocked";
  reason_code: string;
  analysis_plan_revision: number;
  do_file_sha256?: string;
  input_asset_id: string;
  input_artifact_path: string;
  input_sha256: string;
  input_metadata: DataAsset["metadata"] | Record<string, never>;
  required_variables: string[];
  missing_variables: string[];
  checks: Record<string, boolean>;
  issues: Array<{ code: string; line?: number; message: string }>;
}

export interface StageWorkspacePayload {
  title: string;
  summary: string;
  objective: string;
  content: string;
  scope: string;
  evidence_note: string;
  decision: string;
  risk: string;
  handoff: string;
  human_confirmed: boolean;
  sync_history: string[];
  project_context?: {
    code: string;
    icon: string;
    discipline: string;
    sample_window: string;
    keywords: string;
    data_sources: string[];
    owner: string;
    reviewers: string;
  } | null;
}

export interface KnowledgeCandidate {
  candidate_id: string;
  name: string;
  description: string;
  assumptions: string[];
}

export interface KnowledgeAssessment {
  candidate_id: string;
  score: number;
  rationale: string;
  missing_information: string[];
}

export interface KnowledgeEvaluation {
  evaluation_id: string;
  project_id: string;
  status: "not_evaluated" | "current" | "stale" | "invalid";
  context_hash: string;
  model: string;
  evaluated_at: string;
  summary: string;
  methods: KnowledgeAssessment[];
  formulas: KnowledgeAssessment[];
  usage: Record<string, unknown>;
  ai_report: AIReportEnvelope | null;
}

export interface AIReportEnvelope {
  schema_version: "ai4ms.ai-report.v1";
  paradigm: "evidence_linked_management_science";
  report_kind: string;
  stage_key: string;
  title: string;
  executive_summary: string;
  auditable_rationale: {
    kind: "research_facing_logic";
    private_chain_of_thought: false;
    problem_framing: string;
    logic_chain: Array<Record<string, unknown>>;
    assumptions: string[];
    alternatives: string[];
    uncertainties: string[];
    human_decisions: string[];
    next_verifications: string[];
  };
  source_links: Array<{
    citation_id?: string;
    title?: string;
    url: string;
    provider?: string;
    source_type?: string;
    retrieved_at?: string;
    paper_id?: string;
  }>;
  evidence_library_links: Array<{
    evidence_id: string;
    title: string;
    evidence_type: string;
    paper_id: string;
    status: string;
    revision: number;
    api_url: string;
  }>;
  asset_references: {
    paper_ids: string[];
    claim_ids: string[];
    evidence_ids: string[];
    method_ids: string[];
    formula_ids: string[];
    run_ids: string[];
  };
  limitations: string[];
  human_control: {
    review_required: true;
    editable: true;
    approval_status: string;
    prohibited_agent_actions: string[];
  };
  provenance: {
    project_id: string;
    prompt_id: string;
    prompt_version: string;
    model: string;
    generated_at: string;
  };
}

export type EvidenceCandidateStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "changes_requested";

export interface EvidenceCandidate {
  candidate_id: string;
  candidate_type: "literature" | "data_study";
  status: EvidenceCandidateStatus;
  revision: number;
  title: string;
  authors: string[];
  year: number | null;
  venue: string;
  doi: string;
  url: string;
  abstract: string;
  summary?: string;
  paper_id: string;
  provider: string;
  source_type: string;
  search_id: string;
  source_snapshot: string;
  source_hash: string;
  created_by: "agent";
  created_at: string;
  updated_at: string;
  review: {
    decision: "approve" | "reject" | "request_changes";
    reason: string;
    evidence_level: EvidenceLevel;
    reviewed_by: "human";
    reviewed_at: string;
  } | null;
}

export type EvidenceLevel =
  | "metadata"
  | "abstract"
  | "full_text"
  | "source_page";

export interface EvidenceLibraryRecord {
  evidence_id: string;
  source_candidate_id: string;
  evidence_type: "paper" | "data_study";
  status: "active" | "archived";
  revision: number;
  title: string;
  authors: string[];
  year: number | null;
  venue: string;
  doi: string;
  url: string;
  paper_id: string;
  abstract: string;
  summary: string;
  provider: string;
  evidence_level: EvidenceLevel;
  source_hash: string;
  approved_by: "human";
  approved_at: string;
  updated_at: string;
  content_hash: string;
  audit_trail: Array<{
    action: string;
    actor_type: "human";
    reason: string;
    created_at: string;
  }>;
}

export type KnowledgeAssetKind = "method" | "formula";

export interface KnowledgeGovernanceCandidate {
  candidate_id: string;
  kind: KnowledgeAssetKind;
  revision: number;
  status: EvidenceCandidateStatus;
  query: string;
  proposed_content: Record<string, unknown>;
  source_links: SearchCitation[];
  search_trace: Record<string, unknown> & {
    ai_report?: AIReportEnvelope;
  };
  review: {
    decision: "approve" | "reject" | "request_changes";
    reason: string;
    reviewed_by: "human";
    reviewed_at: string;
  } | null;
  promoted_record_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeGovernanceRecord {
  record_id: string;
  kind: KnowledgeAssetKind;
  revision: number;
  status: "active" | "archived";
  source_candidate_id: string | null;
  content: Record<string, unknown>;
  content_hash: string;
  change_reason: string;
  author_type: "human";
  created_at: string;
  updated_at: string;
  revision_created_at: string;
}

export interface KnowledgeRecordRevision {
  revision_id: string;
  record_id: string;
  kind: KnowledgeAssetKind;
  revision: number;
  content_hash: string;
  change_reason: string;
  author_type: "human";
  created_at: string;
}

export interface KnowledgeEvaluationJob {
  job_id: string;
  project_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  created_at: string;
  started_at: string;
  finished_at: string;
  error: string;
  result: KnowledgeEvaluation | null;
}

export type SuggestionDecision = "pending" | "accepted" | "modified" | "rejected";

export interface StageSuggestion {
  suggestion_id: string;
  title: string;
  reason: string;
  before: string;
  after: string;
  target: "summary" | "objective" | "content" | "scope" | "evidence_note" | "decision" | "risk" | "handoff";
  tool_id: string;
  state: SuggestionDecision;
  decision_note?: string;
  decided_at: string;
}

export interface StageSuggestionSet {
  suggestion_set_id: string;
  project_id: string;
  stage_key: string;
  stage_revision: number;
  status: "not_generated" | "current" | "stale" | "invalid";
  context_hash: string;
  model: string;
  generated_at: string;
  summary: string;
  suggestions: StageSuggestion[];
  usage: Record<string, unknown>;
}

export interface StageToolRun {
  tool_run_id: string;
  project_id: string;
  stage_key: string;
  stage_revision: number;
  tool_id: string;
  risk_level: StageToolPolicy["risk_level"];
  status: "completed" | "failed" | "confirmation_required";
  summary: string;
  result: Record<string, unknown>;
  started_at: string;
  finished_at: string;
}

export type ChatSearchMode = "auto" | "on" | "off";

export interface SearchCitation {
  citation_id: string;
  title: string;
  url: string;
  domain: string;
  snippet: string;
  excerpt: string;
  provider: string;
  source_type: "official_data" | "official" | "academic" | "web";
  is_official: boolean;
  paper_id: string;
  retrieved_at: string;
}

export interface SearchSourceRun {
  provider: string;
  query?: string;
  success: boolean;
  record_count: number;
  error: string;
}

export interface SearchTrace {
  search_id: string;
  status: "skipped" | "complete" | "partial" | "failed";
  mode: ChatSearchMode;
  searched: boolean;
  searched_at: string;
  queries: string[];
  citations: SearchCitation[];
  source_runs: SearchSourceRun[];
  snapshot_path: string;
}

export interface StageChatMessage {
  message_id: string;
  project_id: string;
  stage_key: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  model: string;
  usage: Record<string, unknown>;
  citations: SearchCitation[];
  search: SearchTrace | null;
  ai_report: AIReportEnvelope | null;
}

export interface StageChatTurn {
  user_message: StageChatMessage;
  assistant_message: StageChatMessage;
}

export type InterfaceTheme = "graphite" | "blueprint" | "paper";

export interface UserProfile {
  profile_id: string;
  interface_theme: InterfaceTheme;
  created_at: string;
  updated_at: string;
}

export interface DiagnosticRule {
  id: string;
  family: string;
  name: string;
  appliesTo: string;
  trigger: string;
  evidence: string;
  action: string;
  level: "阻塞" | "警告" | "记录";
  stage: "S4" | "S5" | "S6" | "S7";
  implementation: string;
}

export interface DiagnosticRegistry {
  schema_version: string;
  registry_version: string;
  published_at: string;
  authority: "ai4ms-backend";
  count: number;
  total: number;
  items: DiagnosticRule[];
}

export type LiteratureScreeningDecision = "include" | "exclude" | "unsure";
export type LiteratureEvidenceLevel = "metadata" | "abstract" | "full_text";

export interface AcademicOutputQualityIssue {
  rule_id: string;
  severity: "must_fix" | "should_improve" | "note";
  dimension: string;
  location: string;
  finding: string;
  required_action: string;
}

export interface AcademicOutputQuality {
  schema_version: string;
  delivery_revision: number;
  delivery_content_hash: string;
  status: "needs_revision" | "ready_with_advisories" | "ready";
  counts: {
    must_fix: number;
    should_improve: number;
    note: number;
  };
  issues: AcademicOutputQualityIssue[];
  traceability: {
    section_count: number;
    cited_paper_ids: string[];
    cited_claim_ids: string[];
    cited_evidence_ids: string[];
    reference_paper_ids: string[];
    reference_evidence_ids: string[];
    approved_evidence_library_ids: string[];
    problem_question_count: number;
  };
}

interface ApiErrorPayload {
  error?: { code?: string; message?: string };
  detail?: string | Array<{ msg?: string }> | { code?: string; message?: string };
}

const DEFAULT_API_ROOT = process.env.NODE_ENV === "development"
  ? "http://127.0.0.1:8000/api/v1"
  : "/api/v1";
const API_ROOT = (process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_ROOT).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code = "api_error",
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload;
    const validationMessage = Array.isArray(payload.detail)
      ? payload.detail.map((item) => item.msg).filter(Boolean).join("；")
      : typeof payload.detail === "object"
        ? payload.detail?.message
        : payload.detail;
    const detailCode = (
      payload.detail
      && !Array.isArray(payload.detail)
      && typeof payload.detail === "object"
    ) ? payload.detail.code : undefined;
    throw new ApiError(
      payload.error?.message || validationMessage || `API 请求失败（${response.status}）`,
      response.status,
      payload.error?.code || detailCode,
    );
  }
  return response.json() as Promise<T>;
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const response = await request<{ items: ProjectSummary[] }>("/projects");
  return response.items;
}

export function getUserProfile(): Promise<UserProfile> {
  return request<UserProfile>("/profile");
}

export function updateUserProfile(
  interfaceTheme: InterfaceTheme,
): Promise<UserProfile> {
  return request<UserProfile>("/profile", {
    method: "PATCH",
    body: JSON.stringify({ interface_theme: interfaceTheme }),
  });
}

export function getDiagnosticRegistry(): Promise<DiagnosticRegistry> {
  return request<DiagnosticRegistry>("/knowledge/diagnostics?limit=100");
}

export function getProject(projectId: string): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(projectId)}`);
}

export function createProject(title: string, initialIdea: string): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify({ title, initial_idea: initialIdea }),
  });
}

export function updateProject(projectId: string, title: string, initialIdea: string): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(projectId)}`, {
    method: "PATCH",
    body: JSON.stringify({ title, initial_idea: initialIdea }),
  });
}

export function saveStage(
  projectId: string,
  stageKey: string,
  content: Record<string, unknown>,
  changeReason: string,
): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}`, {
    method: "PUT",
    body: JSON.stringify({ content, change_reason: changeReason, author_type: "human" }),
  });
}

export function saveStageWorkspace(
  projectId: string,
  stageKey: string,
  workspace: StageWorkspacePayload,
  expectedRevision: number,
  changeReason: string,
): Promise<Project> {
  return request<Project>(
    `/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}/workspace`,
    {
      method: "PATCH",
      body: JSON.stringify({
        workspace,
        expected_revision: expectedRevision,
        change_reason: changeReason,
      }),
    },
  );
}

export function patchStageAssetSection(
  projectId: string,
  stageKey: string,
  sectionKey: string,
  title: string,
  content: string,
  expectedRevision: number,
): Promise<Project> {
  return request<Project>(
    `/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}/asset-sections/${encodeURIComponent(sectionKey)}`,
    {
      method: "PATCH",
      body: JSON.stringify({
        title,
        content,
        expected_revision: expectedRevision,
        change_reason: `人工修改资产章节：${title}`,
      }),
    },
  );
}

export async function listStageRevisions(
  projectId: string,
  stageKey: string,
): Promise<StageRevision[]> {
  const response = await request<{ items: StageRevision[] }>(
    `/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}/revisions`,
  );
  return response.items;
}

export function restoreStageRevision(
  projectId: string,
  stageKey: string,
  revision: number,
  expectedRevision: number,
): Promise<Project> {
  return request<Project>(
    `/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}/restore`,
    {
      method: "POST",
      body: JSON.stringify({
        revision,
        expected_revision: expectedRevision,
        change_reason: `从 Revision ${revision} 恢复为新草稿`,
      }),
    },
  );
}

export function createStageDraft(
  projectId: string,
  stageKey: string,
  instruction: string,
  generationMode: "template" | "model" = "model",
): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}/draft`, {
    method: "POST",
    body: JSON.stringify({ instruction, generation_mode: generationMode }),
  });
}

export async function listStageChat(
  projectId: string,
  stageKey: string,
): Promise<StageChatMessage[]> {
  const response = await request<{ items: StageChatMessage[] }>(
    `/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}/chat`,
  );
  return response.items;
}

export function sendStageChat(
  projectId: string,
  stageKey: string,
  message: string,
  searchMode: ChatSearchMode = "auto",
): Promise<StageChatTurn> {
  return request<StageChatTurn>(
    `/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}/chat`,
    {
      method: "POST",
      body: JSON.stringify({ message, search_mode: searchMode }),
    },
  );
}

export function searchLiterature(projectId: string, queries: string[] = []): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(projectId)}/stages/literature/search`, {
    method: "POST",
    body: JSON.stringify({ queries }),
  });
}

export function selectProblemQuestion(
  projectId: string,
  selectedQuestionId: string,
  rationale: string,
  expectedRevision: number,
): Promise<Project> {
  return request<Project>(
    `/projects/${encodeURIComponent(projectId)}/stages/problem/question-selection`,
    {
      method: "POST",
      body: JSON.stringify({
        selected_question_id: selectedQuestionId,
        rationale,
        expected_revision: expectedRevision,
        actor_type: "human",
      }),
    },
  );
}

export async function getStageDefinitions(): Promise<StageDefinition[]> {
  const payload = await request<{ items: StageDefinition[] }>("/meta/stages");
  return payload.items;
}

export function invokeStageTool(
  projectId: string,
  stageKey: string,
  toolId: string,
  query = "",
  instruction = "",
): Promise<StageToolRun> {
  return request<StageToolRun>(
    `/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}/tools/invoke`,
    {
      method: "POST",
      body: JSON.stringify({ tool_id: toolId, query, instruction }),
    },
  );
}

export function reviewLiteraturePlan(
  projectId: string,
  decision: "approve" | "request_changes",
  reason: string,
  expectedRevision: number,
): Promise<Project> {
  return request<Project>(
    `/projects/${encodeURIComponent(projectId)}/stages/literature/plan-review`,
    {
      method: "POST",
      body: JSON.stringify({
        decision,
        reason,
        expected_revision: expectedRevision,
        actor_type: "human",
      }),
    },
  );
}

export function getStageSuggestions(
  projectId: string,
  stageKey: string,
): Promise<StageSuggestionSet> {
  return request<StageSuggestionSet>(
    `/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}/suggestions`,
  );
}

export function generateStageSuggestions(
  projectId: string,
  stageKey: string,
  instruction = "",
): Promise<StageSuggestionSet> {
  return request<StageSuggestionSet>(
    `/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}/suggestions`,
    {
      method: "POST",
      body: JSON.stringify({ instruction }),
    },
  );
}

export function screenLiteraturePaper(
  projectId: string,
  paperId: string,
  decision: LiteratureScreeningDecision,
  reason: string,
  evidenceLevel: LiteratureEvidenceLevel,
  expectedRevision: number,
): Promise<Project> {
  return request<Project>(
    `/projects/${encodeURIComponent(projectId)}/stages/literature/papers/${encodeURIComponent(paperId)}/screening`,
    {
      method: "PATCH",
      body: JSON.stringify({
        decision,
        reason,
        evidence_level: evidenceLevel,
        expected_revision: expectedRevision,
        actor_type: "human",
      }),
    },
  );
}

export async function listEvidenceCandidates(
  projectId: string,
): Promise<EvidenceCandidate[]> {
  const response = await request<{ items: EvidenceCandidate[] }>(
    `/projects/${encodeURIComponent(projectId)}/evidence-candidates`,
  );
  return response.items;
}

export function discoverEvidenceCandidates(
  projectId: string,
  query: string,
  candidateType: "literature" | "data_study",
  expectedRevision: number,
  limit = 8,
): Promise<Project> {
  return request<Project>(
    `/projects/${encodeURIComponent(projectId)}/evidence-candidates/discover`,
    {
      method: "POST",
      body: JSON.stringify({
        query,
        candidate_type: candidateType,
        expected_revision: expectedRevision,
        limit,
        actor_type: "agent",
      }),
    },
  );
}

export function decideStageSuggestion(
  projectId: string,
  stageKey: string,
  suggestionId: string,
  state: SuggestionDecision,
  note = "",
): Promise<StageSuggestionSet> {
  return request<StageSuggestionSet>(
    `/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}/suggestions/${encodeURIComponent(suggestionId)}/decision`,
    {
      method: "POST",
      body: JSON.stringify({ state, note }),
    },
  );
}

export function reviewEvidenceCandidate(
  projectId: string,
  candidateId: string,
  decision: "approve" | "reject" | "request_changes",
  reason: string,
  evidenceLevel: EvidenceLevel,
  expectedRevision: number,
  edits: Record<string, unknown> = {},
): Promise<Project> {
  return request<Project>(
    `/projects/${encodeURIComponent(projectId)}/evidence-candidates/${encodeURIComponent(candidateId)}/review`,
    {
      method: "PATCH",
      body: JSON.stringify({
        decision,
        reason,
        evidence_level: evidenceLevel,
        expected_revision: expectedRevision,
        edits,
        actor_type: "human",
      }),
    },
  );
}

export async function listEvidenceLibrary(
  projectId: string,
): Promise<EvidenceLibraryRecord[]> {
  const response = await request<{ items: EvidenceLibraryRecord[] }>(
    `/projects/${encodeURIComponent(projectId)}/evidence-library`,
  );
  return response.items;
}

export function patchEvidenceRecord(
  projectId: string,
  evidenceId: string,
  edits: Record<string, unknown>,
  reason: string,
  expectedRevision: number,
): Promise<Project> {
  return request<Project>(
    `/projects/${encodeURIComponent(projectId)}/evidence-library/${encodeURIComponent(evidenceId)}`,
    {
      method: "PATCH",
      body: JSON.stringify({
        edits,
        reason,
        expected_revision: expectedRevision,
        actor_type: "human",
      }),
    },
  );
}

export async function listKnowledgeGovernanceCandidates(
  kind?: KnowledgeAssetKind,
  status?: EvidenceCandidateStatus,
): Promise<KnowledgeGovernanceCandidate[]> {
  const parameters = new URLSearchParams();
  if (kind) parameters.set("kind", kind);
  if (status) parameters.set("candidate_status", status);
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  const response = await request<{ items: KnowledgeGovernanceCandidate[] }>(
    `/knowledge/candidates${suffix}`,
  );
  return response.items;
}

export function discoverKnowledgeCandidates(
  kind: KnowledgeAssetKind,
  query: string,
  limit = 6,
): Promise<{
  schema_version: string;
  kind: KnowledgeAssetKind;
  count: number;
  items: KnowledgeGovernanceCandidate[];
  ai_report: AIReportEnvelope;
}> {
  return request("/knowledge/candidates/discover", {
    method: "POST",
    body: JSON.stringify({ kind, query, limit, actor_type: "agent" }),
  });
}

export function reviewKnowledgeCandidate(
  candidateId: string,
  decision: "approve" | "reject" | "request_changes",
  reason: string,
  expectedRevision: number,
  edits: Record<string, unknown>,
): Promise<{
  candidate: KnowledgeGovernanceCandidate;
  record: KnowledgeGovernanceRecord | null;
}> {
  return request(
    `/knowledge/candidates/${encodeURIComponent(candidateId)}/review`,
    {
      method: "PATCH",
      body: JSON.stringify({
        decision,
        reason,
        expected_revision: expectedRevision,
        edits,
        actor_type: "human",
      }),
    },
  );
}

export async function listKnowledgeGovernanceRecords(
  kind?: KnowledgeAssetKind,
): Promise<KnowledgeGovernanceRecord[]> {
  const suffix = kind ? `?kind=${encodeURIComponent(kind)}` : "";
  const response = await request<{ items: KnowledgeGovernanceRecord[] }>(
    `/knowledge/records${suffix}`,
  );
  return response.items;
}

export function createKnowledgeRecord(
  kind: KnowledgeAssetKind,
  content: Record<string, unknown>,
  reason: string,
): Promise<KnowledgeGovernanceRecord> {
  return request("/knowledge/records", {
    method: "POST",
    body: JSON.stringify({ kind, content, reason, actor_type: "human" }),
  });
}

export function getKnowledgeRecord(
  recordId: string,
): Promise<KnowledgeGovernanceRecord> {
  return request(`/knowledge/records/${encodeURIComponent(recordId)}`);
}

export function patchKnowledgeRecord(
  recordId: string,
  content: Record<string, unknown>,
  reason: string,
  expectedRevision: number,
): Promise<KnowledgeGovernanceRecord> {
  return request(`/knowledge/records/${encodeURIComponent(recordId)}`, {
    method: "PATCH",
    body: JSON.stringify({
      content,
      reason,
      expected_revision: expectedRevision,
      actor_type: "human",
    }),
  });
}

export async function listKnowledgeRecordRevisions(
  recordId: string,
): Promise<KnowledgeRecordRevision[]> {
  const response = await request<{ items: KnowledgeRecordRevision[] }>(
    `/knowledge/records/${encodeURIComponent(recordId)}/revisions`,
  );
  return response.items;
}

export function getDeliveryQuality(projectId: string): Promise<AcademicOutputQuality> {
  return request<AcademicOutputQuality>(
    `/projects/${encodeURIComponent(projectId)}/stages/delivery/quality`,
  );
}

export function getKnowledgeEvaluation(projectId: string): Promise<KnowledgeEvaluation> {
  return request<KnowledgeEvaluation>(
    `/projects/${encodeURIComponent(projectId)}/knowledge/evaluation`,
  );
}

export function evaluateKnowledge(
  projectId: string,
  methods: KnowledgeCandidate[],
  formulas: KnowledgeCandidate[],
): Promise<KnowledgeEvaluation> {
  return request<KnowledgeEvaluation>(
    `/projects/${encodeURIComponent(projectId)}/knowledge/evaluation`,
    {
      method: "POST",
      body: JSON.stringify({ methods, formulas }),
    },
  );
}

export function submitKnowledgeEvaluation(
  projectId: string,
  methods: KnowledgeCandidate[],
  formulas: KnowledgeCandidate[],
): Promise<KnowledgeEvaluationJob> {
  return request<KnowledgeEvaluationJob>(
    `/projects/${encodeURIComponent(projectId)}/knowledge/evaluation/jobs`,
    {
      method: "POST",
      body: JSON.stringify({ methods, formulas }),
    },
  );
}

export function getKnowledgeEvaluationJob(
  projectId: string,
  jobId: string,
): Promise<KnowledgeEvaluationJob> {
  return request<KnowledgeEvaluationJob>(
    `/projects/${encodeURIComponent(projectId)}/knowledge/evaluation/jobs/${encodeURIComponent(jobId)}`,
  );
}

export async function getStataRunnerStatus(): Promise<RunnerStatus> {
  return request<RunnerStatus>("/runners/stata");
}

export async function uploadDataAsset(projectId: string, file: File): Promise<DataAsset> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(
    `${API_ROOT}/projects/${encodeURIComponent(projectId)}/assets/data`,
    { method: "POST", body, cache: "no-store" },
  );
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload;
    throw new ApiError(
      payload.error?.message || `数据上传失败（${response.status}）`,
      response.status,
      payload.error?.code,
    );
  }
  return response.json() as Promise<DataAsset>;
}

export function preflightAnalysisRun(projectId: string, inputAssetId: string): Promise<AnalysisPreflight> {
  return request<AnalysisPreflight>(`/projects/${encodeURIComponent(projectId)}/stages/analysis/preflight`, {
    method: "POST",
    body: JSON.stringify({ input_asset_id: inputAssetId }),
  });
}

export function submitAnalysisRun(
  projectId: string,
  inputAssetId: string,
  timeoutSeconds: number,
): Promise<AnalysisJob> {
  return request<AnalysisJob>(`/projects/${encodeURIComponent(projectId)}/stages/analysis/runs`, {
    method: "POST",
    body: JSON.stringify({
      input_asset_id: inputAssetId,
      timeout_seconds: timeoutSeconds,
    }),
  });
}

export async function listAnalysisJobs(projectId: string): Promise<AnalysisJob[]> {
  const response = await request<{ items: AnalysisJob[] }>(
    `/projects/${encodeURIComponent(projectId)}/stages/analysis/runs`,
  );
  return response.items;
}

export function getAnalysisJob(projectId: string, runId: string): Promise<AnalysisJob> {
  return request<AnalysisJob>(
    `/projects/${encodeURIComponent(projectId)}/stages/analysis/runs/${encodeURIComponent(runId)}`,
  );
}

export function getAnalysisRunResult(projectId: string, runId: string): Promise<AnalysisRun> {
  return request<AnalysisRun>(
    `/projects/${encodeURIComponent(projectId)}/stages/analysis/runs/${encodeURIComponent(runId)}/result`,
  );
}

export function analysisRunArtifactUrl(
  projectId: string,
  runId: string,
  artifactPath: string,
): string {
  const encodedPath = artifactPath
    .split("/")
    .filter(Boolean)
    .map(encodeURIComponent)
    .join("/");
  return `${API_ROOT}/projects/${encodeURIComponent(projectId)}/stages/analysis/runs/${encodeURIComponent(runId)}/artifacts/${encodedPath}`;
}

export function cancelAnalysisRun(projectId: string, runId: string): Promise<AnalysisJob> {
  return request<AnalysisJob>(
    `/projects/${encodeURIComponent(projectId)}/stages/analysis/runs/${encodeURIComponent(runId)}/cancel`,
    { method: "POST", body: JSON.stringify({}) },
  );
}

export function rerunAnalysis(
  projectId: string,
  runId: string,
  timeoutSeconds: number,
): Promise<AnalysisJob> {
  return request<AnalysisJob>(
    `/projects/${encodeURIComponent(projectId)}/stages/analysis/runs/${encodeURIComponent(runId)}/rerun`,
    {
      method: "POST",
      body: JSON.stringify({ timeout_seconds: timeoutSeconds }),
    },
  );
}

export function exportDelivery(projectId: string): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(projectId)}/stages/delivery/export`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function deliveryArtifactUrl(
  projectId: string,
  exportId: string,
  kind: "report" | "word" | "pdf" | "stata" | "package" | "manifest",
): string {
  return `${API_ROOT}/projects/${encodeURIComponent(projectId)}/exports/${encodeURIComponent(exportId)}/${kind}`;
}

export function decideStage(
  projectId: string,
  stageKey: string,
  decision: ApprovalDecision,
  reason: string,
): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}/decisions`, {
    method: "POST",
    body: JSON.stringify({ decision, reason, actor_type: "human" }),
  });
}
