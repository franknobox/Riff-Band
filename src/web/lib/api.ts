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

interface ApiErrorPayload {
  error?: { code?: string; message?: string };
  detail?: string | Array<{ msg?: string }>;
}

const API_ROOT = (process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1").replace(/\/$/, "");

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
      : payload.detail;
    throw new ApiError(
      payload.error?.message || validationMessage || `API 请求失败（${response.status}）`,
      response.status,
      payload.error?.code,
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
): Promise<StageChatTurn> {
  return request<StageChatTurn>(
    `/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}/chat`,
    {
      method: "POST",
      body: JSON.stringify({ message }),
    },
  );
}

export function searchLiterature(projectId: string, queries: string[] = []): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(projectId)}/stages/literature/search`, {
    method: "POST",
    body: JSON.stringify({ queries }),
  });
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
  kind: "report" | "package" | "manifest",
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
