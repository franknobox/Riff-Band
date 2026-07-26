# AI4MS 当前架构

## 1. 总体结构

```text
Browser
  -> Next.js static workbench
  -> FastAPI /api/v1
       -> ProjectService
       -> StageGenerationService
       -> LiteratureSearchService
       -> AnalysisJobService / AnalysisRunnerService
       -> DeliveryExportService
       -> SQLite + project artifact directory
       -> retained RiffBand Agent Runtime

Docker workbench
  -> signed HTTP bundle
  -> host ai4ms-stata-runner
  -> licensed local Stata batch process
  -> signed Result Bundle
```

Docker 交付时，Next.js 静态导出和 FastAPI 使用同一个 `8000` 端口。开发时通常使用 Next.js `3000` 和 FastAPI `8000`。

## 2. 代码目录

| 目录 | 职责 |
|---|---|
| `src/ai4ms/api` | FastAPI 路由、错误映射和静态前端挂载 |
| `src/ai4ms/services` | 项目、阶段、审批、生成和应用用例 |
| `src/ai4ms/db` | SQLite schema、项目状态、revision 和审批持久化 |
| `src/ai4ms/orchestration` | S0-S1、S7-S8 的 AOrchestra 阶段编排 |
| `src/ai4ms/inference` | 模型配置、调用、超时、重试和 JSON 提取 |
| `src/ai4ms/literature` | 多源检索、规范化、去重和快照 |
| `src/ai4ms/knowledge` | 方法、公式和数据源注册表 |
| `src/ai4ms/prompts` | S0-S9 提示词目录与 Pydantic 输出契约 |
| `src/ai4ms/assets` | `.dta` 上传、SHA-256 和元信息 |
| `src/ai4ms/runners` | Stata 策略检查、后台任务、Local Runner 和 Result Bundle |
| `src/ai4ms/delivery` | HTML 报告、manifest 和 ZIP 研究包 |
| `src/web` | Next.js/React/TypeScript 工作台 |
| `src/base`、`src/agents`、`src/orchestration_tools` | 保留的通用 Agent Runtime |
| `src/project`、`src/research` | 文献工具、研究流水线和 HTML 导出兼容能力 |

AI4MS 仍显式复用旧 Runtime 的四类能力：模型传输、文献适配器、AOrchestra Agent 构建和 HTML 报告导出。因此这些目录当前不能作为“旧代码”直接删除。

## 3. 项目状态

`ProjectStore` 是项目结构化事实的权威来源。核心对象包括：

- project：标题、初始问题、当前阶段和状态；
- stage state：阶段状态和当前 revision；
- stage revision：内容、hash、作者类型、变更理由和时间；
- approval event：人工决定、理由和所批准 revision/hash；
- data asset：文件元信息、SHA-256 和项目内路径。

阶段内容更新只追加 revision。批准只绑定确定 revision 和 hash；上游语义变化时，下游阶段和批准按规则失效。

前端长文本工作区保存在阶段 `content._workspace`，不得用通用编辑器覆盖阶段规范字段。

## 4. 阶段生成

```text
POST stage draft
  -> 检查阶段是否解锁
  -> 收集最小上游上下文
  -> 选择普通生成或 AOrchestra
  -> 模型返回 JSON
  -> Pydantic 契约校验
  -> 论文、Run、Claim 等 ID 白名单校验
  -> 保存 agent revision
  -> 标记 needs_review
```

服务端负责状态、hash、revision、审批和确定性产物。模型不能生成这些事实，也不能声明检索、运行或发布已经成功。

## 5. AOrchestra

`AOrchestraStageService` 复用现有 MainAgent/SubAgent Runtime，为指定阶段动态构建并行研究任务。

- S0-S1 可以使用受控检索能力；
- S7-S8 只能读取项目内论文、计划和成功 Run，不能联网或启动 Runner；
- 最大尝试、子任务步数、并发和超时由 `AI4MS_AO_*` 环境变量控制；
- 编排报告作为生成元数据保存，不替代阶段规范内容；
- 编排失败返回明确错误，不保存未经校验的半成品。

## 6. Stata 执行

S6 分为工作台任务和宿主机执行两层：

1. `AnalysisJobService` 创建 `queued/running/...` 任务并持久化 JSON；
2. `AnalysisRunnerService` 绑定获批计划、do-file hash、数据资产和 Runner Profile；
3. Docker 通过 `RemoteStataAdapter` 发送 HMAC 签名 ZIP；
4. Local Runner 复核令牌、许可、hash、变量和命令策略；
5. Stata batch 只读输入，在独立目录输出；
6. Result Bundle 校验后写入 S6，并作为 S7-S8 的唯一数值证据。

详细契约见 [RUNNER.md](RUNNER.md)。

## 7. 主要 API

```text
GET/POST/PATCH  /api/v1/projects...
GET/PUT/PATCH   /api/v1/projects/{id}/stages...
POST            /api/v1/projects/{id}/stages/{stage}/draft
POST            /api/v1/projects/{id}/stages/{stage}/decisions
POST            /api/v1/projects/{id}/stages/literature/search
GET/POST         /api/v1/projects/{id}/assets/data
POST             /api/v1/projects/{id}/stages/analysis/preflight
GET/POST         /api/v1/projects/{id}/stages/analysis/runs
GET/POST         /api/v1/projects/{id}/stages/analysis/runs/{run_id}/...
POST             /api/v1/projects/{id}/stages/delivery/export
GET              /api/v1/projects/{id}/exports/{export_id}/...
```

OpenAPI 以运行中的 `/docs` 和 `/openapi.json` 为准。

## 8. 持久化

```text
AI4MS_DATA_DIR/
  ai4ms.db
  projects/<project_id>/
    artifacts/
      data/
      jobs/
      runs/
      literature/
    exports/
```

SQLite 保存索引和状态，项目目录保存不可变文件产物。Docker 使用 `/app/data` volume。

## 9. 当前部署边界

- 单用户、单 FastAPI 进程、SQLite 和本地文件系统；
- 任务进程重启后标记为 `interrupted`，不自动恢复；
- 没有组织级 OIDC/RBAC、多租户、对象存储或分布式任务队列；
- Local Runner 是受令牌保护的宿主机连接器，不等同于操作系统级沙箱；
- 生产级隔离和多实例调度属于后续增强，不应污染当前比赛实现。
