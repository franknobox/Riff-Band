CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE organizations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  external_subject text NOT NULL UNIQUE,
  email text NOT NULL,
  display_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE organization_members (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('owner','admin','researcher','reviewer','viewer')),
  PRIMARY KEY (organization_id, user_id)
);

CREATE TABLE projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id),
  slug text NOT NULL,
  title text NOT NULL,
  owner_id uuid NOT NULL REFERENCES users(id),
  status text NOT NULL CHECK (status IN ('draft','active','paused','frozen','archived')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, slug)
);

CREATE TABLE project_members (
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('owner','editor','method_reviewer','data_steward','viewer')),
  PRIMARY KEY (project_id, user_id)
);

CREATE TABLE topic_briefs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  version integer NOT NULL,
  schema_version text NOT NULL,
  body jsonb NOT NULL,
  body_sha256 text NOT NULL,
  approved boolean NOT NULL DEFAULT false,
  approved_by uuid REFERENCES users(id),
  approved_at timestamptz,
  created_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, version),
  UNIQUE (project_id, body_sha256),
  CHECK ((approved = false) OR (approved_by IS NOT NULL AND approved_at IS NOT NULL))
);

CREATE TABLE search_protocols (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  topic_brief_id uuid REFERENCES topic_briefs(id),
  purpose text NOT NULL CHECK (purpose IN ('horizon','systematic_expand','gap_counter_search','protocol_literature','watch_update')),
  body jsonb NOT NULL,
  body_sha256 text NOT NULL,
  created_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, body_sha256)
);

CREATE TABLE topic_scout_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  topic_brief_id uuid NOT NULL REFERENCES topic_briefs(id),
  status text NOT NULL CHECK (status IN ('queued','running','needs_input','blocked','failed','succeeded','cancelled')),
  stage text NOT NULL CHECK (stage IN ('horizon','systematic_expand','gap_counter_search','synthesis','report')),
  task_key text NOT NULL UNIQUE,
  requested_by uuid NOT NULL REFERENCES users(id),
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE protocols (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  version integer NOT NULL,
  schema_version text NOT NULL,
  body jsonb NOT NULL,
  body_sha256 text NOT NULL,
  created_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, version),
  UNIQUE (project_id, body_sha256)
);

CREATE TABLE gate_decisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  protocol_id uuid NOT NULL REFERENCES protocols(id) ON DELETE CASCADE,
  gate_id text NOT NULL,
  decision text NOT NULL CHECK (decision IN ('passed','failed','waived')),
  checks jsonb NOT NULL DEFAULT '[]'::jsonb,
  reason text NOT NULL DEFAULT '',
  decided_by uuid NOT NULL REFERENCES users(id),
  decided_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (protocol_id, gate_id, decided_at)
);

CREATE TABLE search_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  protocol_id uuid REFERENCES protocols(id),
  search_protocol_id uuid REFERENCES search_protocols(id),
  topic_scout_run_id uuid REFERENCES topic_scout_runs(id),
  query_protocol jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('queued','running','needs_input','blocked','failed','succeeded','cancelled')),
  requested_by uuid NOT NULL REFERENCES users(id),
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE papers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_doi text,
  openalex_id text,
  normalized_title text NOT NULL,
  title text NOT NULL,
  publication_year integer,
  venue text,
  current_metadata jsonb NOT NULL,
  metadata_snapshot_date date NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE search_results (
  search_run_id uuid NOT NULL REFERENCES search_runs(id) ON DELETE CASCADE,
  paper_id uuid NOT NULL REFERENCES papers(id),
  backend text NOT NULL,
  query_key text NOT NULL,
  rank integer,
  raw_record jsonb NOT NULL,
  included boolean,
  exclusion_reason text,
  PRIMARY KEY (search_run_id, paper_id, backend, query_key)
);

CREATE TABLE paper_cards (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  paper_id uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  schema_version text NOT NULL,
  fields jsonb NOT NULL,
  extraction_provenance jsonb NOT NULL,
  review_status text NOT NULL CHECK (review_status IN ('unreviewed','accepted','corrected','rejected')),
  created_by_type text NOT NULL CHECK (created_by_type IN ('agent','human','import')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE citation_edges (
  citing_paper_id uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  cited_paper_id uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  source text NOT NULL,
  snapshot_date date NOT NULL,
  PRIMARY KEY (citing_paper_id, cited_paper_id, source),
  CHECK (citing_paper_id <> cited_paper_id)
);

CREATE TABLE related_research_reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  topic_brief_id uuid NOT NULL REFERENCES topic_briefs(id),
  topic_scout_run_id uuid NOT NULL REFERENCES topic_scout_runs(id),
  version integer NOT NULL,
  schema_version text NOT NULL,
  status text NOT NULL CHECK (status IN ('draft','needs_revision','approved','rejected')),
  body jsonb NOT NULL,
  body_sha256 text NOT NULL,
  created_by_type text NOT NULL CHECK (created_by_type IN ('agent','human','import')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, version),
  UNIQUE (project_id, body_sha256)
);

CREATE TABLE research_streams (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id uuid NOT NULL REFERENCES related_research_reports(id) ON DELETE CASCADE,
  name text NOT NULL,
  description text NOT NULL,
  naming_evidence text NOT NULL,
  review_status text NOT NULL CHECK (review_status IN ('machine_draft','human_edited','human_verified')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE research_stream_papers (
  research_stream_id uuid NOT NULL REFERENCES research_streams(id) ON DELETE CASCADE,
  paper_id uuid NOT NULL REFERENCES papers(id),
  membership_basis jsonb NOT NULL,
  PRIMARY KEY (research_stream_id, paper_id)
);

CREATE TABLE evidence_syntheses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id uuid NOT NULL REFERENCES related_research_reports(id) ON DELETE CASCADE,
  statement text NOT NULL,
  status text NOT NULL CHECK (status IN ('supported','contested','limited','not_found','inference','human_verified')),
  supporting_evidence_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  opposing_evidence_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  qualifiers jsonb NOT NULL DEFAULT '[]'::jsonb,
  confidence numeric(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE gap_candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id uuid NOT NULL REFERENCES related_research_reports(id) ON DELETE CASCADE,
  gap_type text NOT NULL CHECK (gap_type IN ('theory','context','data','method','time','practice')),
  statement text NOT NULL,
  status text NOT NULL CHECK (status IN ('candidate','supported_gap','rejected','needs_review')),
  supporting_evidence_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  opposing_evidence_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  counter_search_protocol_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  coverage_limitations jsonb NOT NULL DEFAULT '[]'::jsonb,
  confidence numeric(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  human_approved boolean NOT NULL DEFAULT false,
  approved_by uuid REFERENCES users(id),
  approved_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK ((status <> 'supported_gap') OR (human_approved = true AND approved_by IS NOT NULL AND approved_at IS NOT NULL))
);

CREATE TABLE topic_candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id uuid NOT NULL REFERENCES related_research_reports(id) ON DELETE CASCADE,
  external_key text NOT NULL,
  research_question text NOT NULL,
  contribution text NOT NULL,
  body jsonb NOT NULL,
  recommendation text NOT NULL CHECK (recommendation IN ('continue','narrow','reframe','merge','pause')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (report_id, external_key)
);

CREATE TABLE report_decisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id uuid NOT NULL REFERENCES related_research_reports(id) ON DELETE CASCADE,
  decision text NOT NULL CHECK (decision IN ('approved','needs_revision','rejected')),
  selected_topic_candidate_id uuid REFERENCES topic_candidates(id),
  reason text NOT NULL,
  decided_by uuid NOT NULL REFERENCES users(id),
  decided_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE watchlists (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  search_protocol_id uuid NOT NULL REFERENCES search_protocols(id),
  cadence text NOT NULL CHECK (cadence IN ('daily','weekly','monthly')),
  status text NOT NULL CHECK (status IN ('active','paused','archived')),
  body jsonb NOT NULL,
  created_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE methods (
  method_id text NOT NULL,
  version text NOT NULL,
  body jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('draft','active','deprecated')),
  PRIMARY KEY (method_id, version)
);

CREATE TABLE formulas (
  formula_id text NOT NULL,
  version text NOT NULL,
  body jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('draft','active','deprecated')),
  PRIMARY KEY (formula_id, version)
);

CREATE TABLE data_sources (
  source_id text NOT NULL,
  version text NOT NULL,
  body jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('draft','active','deprecated')),
  PRIMARY KEY (source_id, version)
);

CREATE TABLE data_contracts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  protocol_id uuid NOT NULL REFERENCES protocols(id),
  data_id text NOT NULL,
  body jsonb NOT NULL,
  body_sha256 text NOT NULL,
  created_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (protocol_id, data_id)
);

CREATE TABLE assumptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  protocol_id uuid NOT NULL REFERENCES protocols(id),
  external_key text NOT NULL,
  category text NOT NULL,
  statement text NOT NULL,
  status text NOT NULL CHECK (status IN ('open','supported','violated','waived')),
  body jsonb NOT NULL,
  UNIQUE (protocol_id, external_key)
);

CREATE TABLE runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  protocol_id uuid NOT NULL REFERENCES protocols(id),
  parent_run_id uuid REFERENCES runs(id),
  status text NOT NULL CHECK (status IN ('queued','running','needs_input','blocked','failed','succeeded','cancelled')),
  task_key text NOT NULL UNIQUE,
  manifest jsonb,
  requested_by uuid NOT NULL REFERENCES users(id),
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE artifacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  run_id uuid REFERENCES runs(id),
  artifact_type text NOT NULL,
  schema_version text,
  uri text NOT NULL,
  media_type text NOT NULL,
  sha256 text NOT NULL,
  size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
  pii_class text NOT NULL CHECK (pii_class IN ('none','low','sensitive','restricted')),
  license text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, sha256, artifact_type)
);

CREATE TABLE artifact_lineage (
  parent_artifact_id uuid NOT NULL REFERENCES artifacts(id),
  child_artifact_id uuid NOT NULL REFERENCES artifacts(id),
  relation text NOT NULL CHECK (relation IN ('derived_from','uses','supersedes','validates')),
  PRIMARY KEY (parent_artifact_id, child_artifact_id, relation),
  CHECK (parent_artifact_id <> child_artifact_id)
);

CREATE TABLE claims (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  protocol_id uuid NOT NULL REFERENCES protocols(id),
  external_key text NOT NULL,
  claim_text text NOT NULL,
  claim_type text NOT NULL,
  status text NOT NULL CHECK (status IN ('candidate','supported','mixed','refuted','withdrawn')),
  confidence text CHECK (confidence IN ('low','medium','high')),
  scope jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (protocol_id, external_key)
);

CREATE TABLE evidence_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  artifact_id uuid NOT NULL REFERENCES artifacts(id),
  evidence_type text NOT NULL,
  locator text NOT NULL,
  method_id text,
  run_id uuid REFERENCES runs(id),
  source_url text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE claim_evidence_edges (
  claim_id uuid NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
  evidence_id uuid NOT NULL REFERENCES evidence_items(id) ON DELETE CASCADE,
  direction text NOT NULL CHECK (direction IN ('supports','contradicts','qualifies')),
  strength text NOT NULL CHECK (strength IN ('weak','moderate','strong')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (claim_id, evidence_id)
);

CREATE TABLE research_assets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  asset_type text NOT NULL CHECK (asset_type IN (
    'topic_brief','related_research_report','search_protocol','theory_map',
    'research_protocol','data_contract','analysis_plan','do_file','robustness_matrix',
    'interpretation_memo','claim_set','manuscript','release_package'
  )),
  external_key text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, asset_type, external_key)
);

CREATE TABLE asset_revisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id uuid NOT NULL REFERENCES research_assets(id) ON DELETE CASCADE,
  revision_number integer NOT NULL CHECK (revision_number > 0),
  parent_revision_id uuid REFERENCES asset_revisions(id),
  body jsonb NOT NULL,
  body_sha256 text NOT NULL,
  author_type text NOT NULL CHECK (author_type IN ('human','agent','import')),
  created_by_user_id uuid REFERENCES users(id),
  created_by_agent text,
  change_reason text NOT NULL,
  semantic_scope text NOT NULL CHECK (semantic_scope IN (
    'topic','design','data','analysis','result','claim','writing','format_only'
  )),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (asset_id, revision_number),
  UNIQUE (asset_id, body_sha256),
  CHECK (
    (author_type = 'human' AND created_by_user_id IS NOT NULL AND created_by_agent IS NULL)
    OR (author_type = 'agent' AND created_by_user_id IS NULL AND created_by_agent IS NOT NULL)
    OR (author_type = 'import')
  )
);

CREATE TABLE revision_patches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  base_revision_id uuid NOT NULL REFERENCES asset_revisions(id),
  proposed_revision_id uuid REFERENCES asset_revisions(id),
  patch_type text NOT NULL CHECK (patch_type IN ('json_patch','text_diff','code_diff')),
  patch jsonb NOT NULL,
  rationale text NOT NULL,
  evidence_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  approval_impact jsonb NOT NULL DEFAULT '[]'::jsonb,
  status text NOT NULL CHECK (status IN ('proposed','accepted','modified','rejected','withdrawn')),
  proposed_by_agent text NOT NULL,
  decided_by uuid REFERENCES users(id),
  decided_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK ((status = 'proposed') OR (decided_by IS NOT NULL AND decided_at IS NOT NULL))
);

CREATE TABLE approval_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  stage_key text NOT NULL CHECK (stage_key IN (
    'S0_topic','S1_literature','S2_theory','S3_design','S4_data',
    'S5_analysis_plan','S6_execution','S7_robustness','S8_evidence','S9_writing'
  )),
  gate_id text NOT NULL CHECK (gate_id IN ('G0','G1','G2','G3','G4','G5')),
  target_revision_id uuid NOT NULL REFERENCES asset_revisions(id),
  target_sha256 text NOT NULL,
  policy text NOT NULL CHECK (policy IN ('single_reviewer','four_eyes','multi_signoff')),
  required_roles jsonb NOT NULL DEFAULT '[]'::jsonb,
  checklist jsonb NOT NULL DEFAULT '[]'::jsonb,
  status text NOT NULL CHECK (status IN (
    'draft','in_review','changes_requested','approved','rejected','withdrawn','invalidated','superseded'
  )),
  requested_by uuid NOT NULL REFERENCES users(id),
  requested_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz,
  UNIQUE (gate_id, target_revision_id, policy)
);

CREATE TABLE approval_decisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  approval_request_id uuid NOT NULL REFERENCES approval_requests(id) ON DELETE CASCADE,
  decision text NOT NULL CHECK (decision IN ('approved','changes_requested','rejected','withdrawn')),
  decided_by uuid NOT NULL REFERENCES users(id),
  role_snapshot text NOT NULL,
  checklist_result jsonb NOT NULL DEFAULT '[]'::jsonb,
  comment text NOT NULL,
  conflict_disclosure text NOT NULL DEFAULT '',
  decided_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE approval_invalidations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  approval_request_id uuid NOT NULL REFERENCES approval_requests(id),
  trigger_revision_id uuid NOT NULL REFERENCES asset_revisions(id),
  rule_key text NOT NULL,
  reason text NOT NULL,
  invalidated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (approval_request_id, trigger_revision_id, rule_key)
);

CREATE TABLE stage_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  stage_key text NOT NULL CHECK (stage_key IN (
    'S0_topic','S1_literature','S2_theory','S3_design','S4_data',
    'S5_analysis_plan','S6_execution','S7_robustness','S8_evidence','S9_writing'
  )),
  principal_agent text NOT NULL,
  status text NOT NULL CHECK (status IN (
    'drafting','awaiting_user','in_review','changes_requested','approved','blocked','completed'
  )),
  input_revision_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  output_revision_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  decisions_needed jsonb NOT NULL DEFAULT '[]'::jsonb,
  handoff_readiness jsonb NOT NULL DEFAULT '{}'::jsonb,
  started_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE agent_suggestions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  stage_session_id uuid NOT NULL REFERENCES stage_sessions(id) ON DELETE CASCADE,
  revision_patch_id uuid NOT NULL REFERENCES revision_patches(id),
  status text NOT NULL CHECK (status IN ('proposed','accepted','modified','rejected','withdrawn')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE stata_runner_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  runner_type text NOT NULL CHECK (runner_type IN ('local','institution','compute_server')),
  stata_version text NOT NULL,
  stata_edition text NOT NULL CHECK (stata_edition IN ('BE','SE','MP','StataNow','unknown')),
  license_mode text NOT NULL CHECK (license_mode IN ('user_byol','institution_network','institution_compute_server')),
  concurrency_limit integer NOT NULL CHECK (concurrency_limit > 0),
  status text NOT NULL CHECK (status IN ('active','paused','offline','revoked')),
  config jsonb NOT NULL DEFAULT '{}'::jsonb,
  last_seen_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, name)
);

CREATE TABLE stata_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL UNIQUE REFERENCES runs(id) ON DELETE CASCADE,
  runner_profile_id uuid NOT NULL REFERENCES stata_runner_profiles(id),
  analysis_plan_revision_id uuid NOT NULL REFERENCES asset_revisions(id),
  do_file_artifact_id uuid NOT NULL REFERENCES artifacts(id),
  do_file_sha256 text NOT NULL,
  g3_approval_request_id uuid NOT NULL REFERENCES approval_requests(id),
  engine_snapshot jsonb NOT NULL,
  package_manifest jsonb NOT NULL DEFAULT '[]'::jsonb,
  input_data_signatures jsonb NOT NULL DEFAULT '{}'::jsonb,
  preflight_report jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('queued','running','needs_input','blocked','failed','succeeded','cancelled')),
  exit_code integer,
  log_artifact_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  output_artifact_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  result_manifest jsonb,
  requested_by uuid NOT NULL REFERENCES users(id),
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE audit_events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations(id),
  project_id uuid REFERENCES projects(id),
  actor_id uuid REFERENCES users(id),
  action text NOT NULL,
  object_type text NOT NULL,
  object_id text NOT NULL,
  detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_protocols_project_version ON protocols(project_id, version DESC);
CREATE INDEX idx_topic_briefs_project_version ON topic_briefs(project_id, version DESC);
CREATE INDEX idx_search_protocols_project_created ON search_protocols(project_id, created_at DESC);
CREATE INDEX idx_topic_scout_runs_project_created ON topic_scout_runs(project_id, created_at DESC);
CREATE INDEX idx_search_runs_project_created ON search_runs(project_id, created_at DESC);
CREATE UNIQUE INDEX uq_papers_doi_not_null ON papers(canonical_doi) WHERE canonical_doi IS NOT NULL;
CREATE UNIQUE INDEX uq_papers_openalex_not_null ON papers(openalex_id) WHERE openalex_id IS NOT NULL;
CREATE INDEX idx_papers_title ON papers USING gin (to_tsvector('simple', title));
CREATE INDEX idx_cards_paper_created ON paper_cards(paper_id, created_at DESC);
CREATE INDEX idx_related_reports_project_version ON related_research_reports(project_id, version DESC);
CREATE INDEX idx_gap_candidates_report_status ON gap_candidates(report_id, status);
CREATE INDEX idx_topic_candidates_report ON topic_candidates(report_id);
CREATE INDEX idx_watchlists_project_status ON watchlists(project_id, status);
CREATE INDEX idx_runs_project_created ON runs(project_id, created_at DESC);
CREATE INDEX idx_artifacts_run ON artifacts(run_id);
CREATE INDEX idx_claims_project_status ON claims(project_id, status);
CREATE INDEX idx_assets_project_type ON research_assets(project_id, asset_type);
CREATE INDEX idx_asset_revisions_asset_version ON asset_revisions(asset_id, revision_number DESC);
CREATE INDEX idx_approval_requests_project_status ON approval_requests(project_id, status, gate_id);
CREATE INDEX idx_approval_decisions_request ON approval_decisions(approval_request_id, decided_at);
CREATE INDEX idx_stage_sessions_project_stage ON stage_sessions(project_id, stage_key, updated_at DESC);
CREATE INDEX idx_stata_runner_org_status ON stata_runner_profiles(organization_id, status);
CREATE INDEX idx_stata_runs_runner_status ON stata_runs(runner_profile_id, status);
CREATE INDEX idx_audit_project_created ON audit_events(project_id, created_at DESC);
