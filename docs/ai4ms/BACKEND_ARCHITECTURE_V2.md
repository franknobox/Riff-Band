# AI4MS 后端结构方案 v2

更新日期：2026-07-21  
对应前端：S0–S9 工作台、证据库、方法与公式库、Stata 工作台、审批中心、智能体对话与正文同步。

## 1. 结论

保留仓库现有 `FastAPI + Pydantic + SQLite + RiffBand Agent Runtime + 文件资产目录 + Stata BYOL Runner` 作为第一阶段骨架，不在当前阶段替换成重型微服务。新增能力应按清晰的领域模块进入同一 Python 应用：方法/公式注册表、智能体运行与工具策略、正文同步、证据图、后台任务和审计事件。

现有 `KnowledgeRegistry` 的 28 个方法、47 个公式和 40 个数据源是迁移基线与权威目录。前端高频深度卡提供了更丰富的 estimand、诊断、失败规则和实现模板，后端应按既有 ID 增量扩展 schema；禁止用较小的前端演示集合覆盖现有种子。

生产化时把 SQLite、进程内任务和本地文件分别替换为 PostgreSQL、Redis/任务队列和 S3 兼容对象存储；API 和领域对象保持不变。

## 2. 总体结构

```text
Next.js Web
  └─ /api/v1
      ├─ FastAPI routes / auth / validation
      ├─ Application services
      │   ├─ Project & Workflow
      │   ├─ Artifact & Revision
      │   ├─ Agent Session & Sync
      │   ├─ Literature & Evidence
      │   ├─ Method / Formula / Diagnostic Registry
      │   ├─ Analysis & Solver Runs
      │   ├─ Approval & Invalidation
      │   └─ Delivery & Export
      ├─ RiffBand Agent Runtime + Tool Policy Engine
      ├─ Connectors / Stata / Python / Solver adapters
      └─ Persistence
          ├─ SQLite → PostgreSQL
          ├─ Local files → Object storage
          └─ In-process jobs → Redis queue
```

## 3. 建议目录

在现有 `src/ai4ms/` 基础上扩展，不破坏已存在的 `api/ services/ db/ domains/ inference/ literature/ knowledge/ prompts/ runners/ delivery/`：

```text
src/ai4ms/
  api/
    app.py                    # 应用装配；逐步把路由拆到 routers/
    dependencies.py          # 当前用户、服务、幂等键、请求上下文
    routers/
      projects.py
      stages.py
      agents.py
      sync.py
      literature.py
      evidence.py
      knowledge.py
      runs.py
      approvals.py
      delivery.py
  services/
    project_service.py
    workflow_service.py
    artifact_service.py
    revision_service.py
    agent_session_service.py
    sync_service.py
    evidence_service.py
    knowledge_service.py
    approval_service.py
    execution_service.py
    delivery_service.py
  domain/
    project.py
    workflow.py
    artifact.py
    evidence.py
    knowledge.py
    agent.py
    execution.py
    approval.py
    events.py
  agents/
    registry.py               # S0–S9 AgentDefinition
    runtime_adapter.py        # 复用 RiffBand Runtime
    context_builder.py
    checkpoint.py
    guardrails.py
  tools/
    registry.py
    policy.py
    literature/
    evidence/
    statistics/
    optimization/
    stata/
    delivery/
  knowledge/
    methods.py
    formulas.py
    diagnostics.py
    data_sources.py
    data/*.json
  literature/
    connectors/
      openalex.py
      crossref.py
      semantic_scholar.py
    normalize.py
    deduplicate.py
    screening.py
    locators.py
  runners/
    base.py
    stata.py
    python.py
    solver.py
    preflight.py
    manifests.py
  repositories/
    project_repository.py
    artifact_repository.py
    agent_repository.py
    evidence_repository.py
    run_repository.py
  db/
    schema.py
    migrations/
    sqlite.py
  jobs/
    dispatcher.py
    tasks.py
    events.py
  observability/
    audit.py
    metrics.py
    tracing.py
  delivery/
  inference/
  prompts/
```

## 4. 通用基础骨架

### 4.1 API 层

职责：HTTP 验证、认证、错误映射、分页、幂等键和服务装配。不得在路由中直接修改阶段状态或拼接科研资产。

统一约定：

- Base path：`/api/v1`。
- 写接口接受 `Idempotency-Key`；同键同请求返回同一结果。
- 修改 revision 时使用 `If-Match: <content_hash>` 或请求体 `base_revision_id`，冲突返回 `409 revision_conflict`。
- 长任务返回 `202` 和 `job_id`；前端通过事件流或轮询读取进度。
- 错误统一为 `{ "error": { "code", "message", "details", "trace_id" } }`。
- 列表统一支持 `cursor`、`limit`、`q`、`status`。

### 4.2 应用服务层

一个用户动作对应一个用例。例如“智能体回答同步正文”由 `SyncService` 完成：检查目标 revision、生成 patch、创建新 revision、记录来源消息、写审计事件；前端不应分多次写数据库来模拟事务。

### 4.3 领域层

领域对象负责科研工作流不变量：

- AI 不能创建 `approved` 决定。
- 阶段资产保存后形成不可变 revision。
- 审批绑定 revision 和 content hash。
- 上游语义变化使受影响的下游审批失效，但不删除历史。
- 正式运行只能引用有效 G3 revision。
- S9 正式结论只能引用有效 G4 主张。
- 同步智能体内容必须保存来源 session/message 与人工确认者。

### 4.4 Repository 层

领域服务只依赖 Repository Protocol。当前实现用 SQLite + 文件；未来可替换为 PostgreSQL + 对象存储。大文本和二进制资产保存在对象存储，数据库保留 URI、hash、大小和媒体类型。

### 4.5 任务层

以下任务不得占用普通 HTTP 请求：多源文献检索、全文解析、嵌入索引、长模型调用、Stata/Python/Solver 运行、HTML/ZIP 导出。

当前可先使用 SQLite job 表和单进程 worker；生产环境改为 Redis + Dramatiq/Celery/RQ。每个任务必须支持：幂等、取消、超时、重试分类、心跳、检查点和资源上限。

## 5. 具体功能服务

| 服务 | 对应前端功能 | 关键职责 |
|---|---|---|
| `ProjectService` | 项目列表、新建项目、项目中心 | 项目 CRUD、成员/角色、领域画像、当前阶段 |
| `WorkflowService` | S0–S9 导航、阶段解锁、一致性检查 | 状态迁移、依赖、退出条件、下游失效 |
| `ArtifactService` | 当前草稿、交付正文、证据说明、决定记录 | 结构化资产读写、字段级 patch、内容校验 |
| `RevisionService` | 保存草稿、保存新版本、版本历史 | 不可变 revision、diff、hash、恢复为新草稿 |
| `AgentSessionService` | 与 10 个阶段智能体聊天 | session、message、上下文快照、流式输出、checkpoint |
| `SyncService` | 对话同步交付正文 | preview、append/replace/section insert、人工确认、provenance |
| `LiteratureService` | 新建检索、论文卡、筛选 | 多源查询、去重、快照、全文级别、纳入/排除 |
| `EvidenceService` | 证据库、主张连接、反证 | Claim、Evidence、Locator、边界、图谱查询 |
| `KnowledgeService` | 方法库、公式库、诊断规则 | 版本化方法/公式/规则、搜索、比较、加入设计 |
| `ExecutionService` | Stata 工作台、Python/Solver | preflight、提交、取消、日志、manifest、产物回收 |
| `ApprovalService` | G0–G5 审批中心 | 提交、会签、退回、拒绝、冻结、失效与审计 |
| `DeliveryService` | 论文草稿、HTML、ZIP、manifest | 只从获批对象导出、引用/数字核验、包清单 |

## 6. 核心数据模型

### 6.1 项目与工作流

`projects`

- `id`, `title`, `code`, `domain_profile_id`, `owner_id`
- `status`, `current_stage`, `created_at`, `updated_at`

`project_members`

- `project_id`, `user_id`, `role`：`researcher/pi/method_reviewer/data_steward/author/viewer`

`stage_instances`

- `project_id`, `stage_key`, `status`, `active_revision_id`
- `blocked_reason`, `entered_at`, `approved_at`, `updated_at`

`stage_dependencies`

- `upstream_stage`, `downstream_stage`, `dependency_type`, `invalidation_policy`

### 6.2 资产与版本

`artifacts`

- `id`, `project_id`, `stage_key`, `artifact_type`, `logical_name`
- `active_revision_id`, `created_by`, `created_at`

`artifact_revisions`

- `id`, `artifact_id`, `revision_no`, `schema_version`
- `content_json` 或 `object_uri`, `content_hash`, `base_revision_id`
- `author_type`, `author_id`, `change_reason`, `created_at`

`artifact_edges`

- `source_revision_id`, `target_revision_id`, `edge_type`
- 例如 `derived_from / cites / generated_by / invalidates / synced_from`

### 6.3 智能体与同步

`agent_definitions`

- `id`, `stage_key`, `version`, `instruction_ref`, `output_schema_ref`
- `allowed_tool_ids`, `model_policy`, `approval_policy`, `active`

`agent_sessions`

- `id`, `project_id`, `stage_key`, `agent_definition_id`
- `context_revision_ids`, `status`, `created_by`, `created_at`, `closed_at`

`agent_messages`

- `id`, `session_id`, `role`, `content`, `content_hash`
- `model`, `token_usage`, `created_at`

`agent_runs`

- `id`, `session_id`, `trigger_message_id`, `status`
- `checkpoint_uri`, `started_at`, `finished_at`, `error_code`

`tool_calls`

- `id`, `agent_run_id`, `tool_id`, `policy_version`, `input_redacted`
- `status`, `approval_required`, `approved_by`, `output_ref`, `cost`, `latency_ms`

`sync_operations`

- `id`, `project_id`, `stage_key`, `source_message_id`
- `target_artifact_id`, `base_revision_id`, `result_revision_id`
- `target_field`, `mode`：`append/replace/insert_section`
- `preview_hash`, `confirmed_by`, `confirmed_at`, `status`

### 6.4 方法、公式和诊断

`method_definitions`

- `id`, `version`, `name`, `family`, `goal`, `data_shape`
- `estimand_or_objective`, `assumptions_json`, `failure_rule`
- `implementation_refs`, `source_refs`, `review_status`, `valid_from`

`formula_definitions`

- `id`, `version`, `method_id`, `title`, `expression_latex`, `expression_text`
- `symbols_json`, `assumptions_json`, `diagnostic_rule_ids`
- `stata_template`, `python_template`, `solver_template`, `source_refs`

`diagnostic_rules`

- `id`, `version`, `name`, `applies_to`, `severity`
- `required_inputs`, `evaluation_type`, `pass_condition`, `failure_action`

`project_method_selections`

- `project_id`, `stage_key`, `method_version_id`, `role`：`primary/alternative/robustness/exploratory`
- `rationale`, `rejected_reason`, `selected_by`, `revision_id`

`variable_bindings`

- `project_id`, `formula_version_id`, `symbol`, `variable_id`, `transform`, `unit`, `binding_revision_id`

### 6.5 文献与证据

`search_runs`, `query_variants`, `source_records`, `source_snapshots`, `screening_decisions`, `evidence_locators`, `claims`, `claim_evidence_edges`。

必须区分：元数据已核验、摘要级、全文已核验、撤稿/更正、无法访问全文。Locator 至少保存页码/章节/表图/字符范围之一。

### 6.6 执行与审批

`execution_runs`

- `id`, `project_id`, `run_type`：`stata/python/solver/simulation`
- `analysis_plan_revision_id`, `code_revision_id`, `input_manifest_hash`
- `runner_id`, `environment_hash`, `status`, `exit_code`
- `started_by`, `approved_gate_revision_id`, `started_at`, `finished_at`

`run_artifacts`

- `run_id`, `kind`, `uri`, `sha256`, `size_bytes`, `media_type`, `created_at`

`approval_requests`, `approval_decisions`, `approval_signatures`, `approval_invalidations`。

所有批准者必须是 human identity；模型和 service account 只能准备摘要。

## 7. 关键 API

在现有接口基础上新增或细化：

### 7.1 方法与公式

```http
GET  /knowledge/methods?q=&family=&data_shape=&limit=
GET  /knowledge/methods/{method_id}/versions/{version}
POST /projects/{project_id}/method-selections
PATCH /projects/{project_id}/method-selections/{selection_id}

GET  /knowledge/formulas?q=&method_id=&family=
GET  /knowledge/formulas/{formula_id}/versions/{version}
POST /projects/{project_id}/formula-bindings/validate
PUT  /projects/{project_id}/formula-bindings/{binding_id}

GET  /knowledge/diagnostics?method_id=&severity=
POST /projects/{project_id}/analysis-plan/diagnostics
```

### 7.2 智能体对话

```http
POST /projects/{project_id}/agent-sessions
GET  /projects/{project_id}/agent-sessions/{session_id}
POST /projects/{project_id}/agent-sessions/{session_id}/messages
GET  /projects/{project_id}/agent-runs/{run_id}/events
POST /projects/{project_id}/agent-runs/{run_id}/cancel
POST /projects/{project_id}/agent-runs/{run_id}/interrupts/{interrupt_id}/resolve
```

`messages` 返回 `202 run_id`；事件流包含 `message.delta`、`tool.requested`、`tool.completed`、`human.input_required`、`run.completed`。

### 7.3 对话同步正文

```http
POST /projects/{project_id}/sync-operations/preview
POST /projects/{project_id}/sync-operations/{sync_id}/confirm
POST /projects/{project_id}/sync-operations/{sync_id}/cancel
GET  /projects/{project_id}/sync-operations?stage_key=S9
```

Preview 请求示例：

```json
{
  "source_message_id": "msg_123",
  "target_artifact_id": "artifact_delivery",
  "base_revision_id": "rev_18",
  "target_field": "content",
  "mode": "append"
}
```

Confirm 必须携带 `preview_hash` 和 human identity。若 base revision 已变化，返回 `409` 并生成重新预览，不静默覆盖人工编辑。

### 7.4 一致性检查

```http
POST /projects/{project_id}/stages/{stage_key}/checks
GET  /projects/{project_id}/checks/{check_run_id}
POST /projects/{project_id}/checks/{check_run_id}/issues/{issue_id}/resolve
```

每项 issue 连接字段、规则版本、当前值 hash、建议 patch、人工处理方式和下游影响。

## 8. 状态机

### 8.1 阶段状态

```text
not_started → in_progress → needs_review → approved
                    ↘ blocked ↗
approved --上游失效--> needs_review
```

- 智能体可把 `in_progress` 推到 `needs_review`，不能推到 `approved`。
- `blocked` 需要结构化原因：缺证据、缺许可、方法假设失败、无 Runner、审批失效等。
- 阶段解锁和审批门分离；能编辑下游草稿不等于能正式运行或发布。

### 8.2 Agent Run 状态

`queued → running → waiting_for_human → running → completed`，另有 `failed/cancelled/timed_out/blocked_by_policy`。

等待人工期间持久化 checkpoint；重启后可恢复到同一 tool call 之前，不重复外部写操作。

### 8.3 Sync 状态

`draft_preview → awaiting_confirmation → applied`，另有 `cancelled/conflict/expired`。只有 `applied` 会创建目标资产 revision。

## 9. 工具策略引擎

每个工具注册以下元数据：

- `tool_id`, `version`, `description`, `input_schema`, `output_schema`
- `read_scopes`, `write_scopes`, `network_domains`
- `risk_level`：`read_only / reversible_write / controlled_execution / external_side_effect`
- `requires_human_approval`, `required_gate`, `timeout`, `max_retries`, `max_cost`
- `redaction_policy`, `artifact_policy`, `audit_policy`

调用顺序固定为：Agent 请求 → Policy 校验 → 必要时人工中断 → 执行 → 输出校验 → provenance 入库 → Agent 继续。任何工具返回的文本不得绕过结构化输出校验直接写阶段正式资产。

## 10. Stata、Python 与优化 Solver

采用统一 `RunnerAdapter`：

```python
class RunnerAdapter(Protocol):
    def status(self) -> RunnerStatus: ...
    def preflight(self, request: RunRequest) -> PreflightResult: ...
    async def submit(self, request: RunRequest) -> RunHandle: ...
    async def cancel(self, run_id: str) -> None: ...
    def collect(self, run_id: str) -> RunManifest: ...
```

共同要求：

- 只读输入挂载、独立输出目录、CPU/内存/时间限制。
- 锁定环境/软件/ado/包/solver 版本。
- 禁止 shell、任意网络、动态安装和未授权路径。
- 输入、代码、环境、日志、输出全部 hash。
- 正式运行必须绑定 G3；重跑形成新 run，不覆盖旧产物。

Stata 额外记录许可位置但不保存许可密钥；Solver 额外记录求解器、最优性 gap、bound、终止原因和可行性；Python 额外记录 lockfile 与随机种子。

## 11. 权限与安全

本地单用户版本也应保留 actor 类型，为未来多人协作留接口。

- `researcher`：编辑草稿、确认同步、提交审批、启动已批准运行。
- `pi`：G0/G1/G4，确认价值、设计和主张。
- `method_reviewer`：G1/G3/G4，审核方法、代码、诊断和解释。
- `data_steward`：G2，审核许可、隐私和数据位置。
- `corresponding_author`：G5，批准发布。
- `agent/service`：生成建议、执行已授权工具，不拥有批准权限。

敏感字段不进入模型上下文；Tool Call 日志保存脱敏输入。连接器密钥放环境或 secret store。输出日志禁止包含密钥、受限数据原文和 Stata 许可信息。

## 12. 可观测性与审计

每个请求、Agent Run、Tool Call、Sync、Approval、Execution Run 使用同一个 `trace_id`。最低指标：请求错误率、模型失败率、工具拒绝率、每阶段耗时、人工等待时长、文献去重率、来源核验率、sync 冲突率、run 成功率、审批失效率、单项目成本。

审计事件为追加写：`project.created`、`revision.created`、`agent.tool_requested`、`sync.applied`、`approval.signed`、`approval.invalidated`、`run.started`、`run.completed`、`delivery.exported`。

## 13. 非功能要求

- 本地读取项目 P95 < 300 ms；方法/公式检索 P95 < 500 ms。
- 长任务 2 秒内返回 job/run ID，并持续报告进度。
- 保存 revision、确认同步和审批签名必须事务化。
- Agent/Runner 失败不影响打开已保存项目和历史报告。
- 所有正式资产可由 hash 验证；导出包包含 manifest。
- 数据库迁移可回滚；对象资产不因迁移丢失。
- 核心状态机、审批、失效、同步冲突和 Runner policy 需要单元/集成测试。

## 14. 与当前仓库的迁移顺序

1. 不改现有 `ProjectService` 对外返回，先加 Repository Protocol 和数据库迁移。
2. 把 `app.py` 中方法/公式路由迁到 `knowledge` router，并扩充 schema。
3. 新增 Agent Session/Message/Run/ToolCall 表和只读对话 API。
4. 新增 Sync preview/confirm 事务，接通前端“同步到交付正文”。
5. 把方法/公式 JSON 种子导入版本化 Registry；加项目级 selection/binding。
6. 抽象统一 Runner，保留现有 Stata Adapter，再增加 Python/Solver Adapter。
7. 引入 job worker、事件流和 checkpoint。
8. 最后再把 SQLite/本地文件替换为 PostgreSQL/对象存储，避免过早分布式化。
