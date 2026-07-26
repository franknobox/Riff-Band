# AI4MS ROADMAP

## 1. 交付目标

截止时间：2026-07-26。

团队在最后 6 个开发日内，把 RiffBand 改造成一个可运行、可操作、可演示的 **管理科学（Management Science, MS）垂直 AI 科研工作台**。产品形态借鉴玻尔将检索、阅读、研究和计算放在同一工作区的思路，但聚焦管理科学的研究设计、数据方法、Stata、证据审查和人工决策。

本轮不再只交付文献报告，也不按 24/36 周阶段路线拆目标。介绍书中的用户任务按前端 S0-S9 十阶段落地，每个阶段都必须在同一个产品中有入口、状态、结构化产物和人工动作。

## 2. S0-S9 十阶段产品闭环

| 阶段 | 用户看到的工作区 | 必须产出的对象 | 人工动作 |
|---|---|---|---|
| S0 问题识别 | 项目创建、科学问题、研究边界与候选空白 | `TopicBrief` | G0 确认边界或退回 |
| S1 文献综述 | 查询规划、多源状态、论文卡、流派与覆盖限制 | `SearchRun`、`PaperCard`、`RelatedResearchReport` | 纳入、排除或标记不确定 |
| S2 理论构建 | 理论机制、研究问题、竞争解释与可证伪命题 | `TheoryModel` | 确认理论和贡献边界 |
| S3 研究设计 | 分析单位、主备设计、关键假设和停止条件 | `ResearchProtocol` | G1 确认设计 |
| S4 数据与变量 | 数据源、变量、许可、隐私、伦理与口径 | `DataContract` | G2 确认数据与合规 |
| S5 识别与检验 | estimand、模型式、诊断、分析步骤和代码计划 | `AnalysisPlan` | G3 冻结计划和代码 |
| S6 结果分析 | Runner、日志、表图、结果和复现信息 | `RunArtifact` | 批准运行和选择重跑 |
| S7 稳健性检验 | 替代口径、模型、样本、安慰剂与失败检查 | `RobustnessReport` | 追加检验或接受影响 |
| S8 机制与异质性 | Claim-Evidence、机制、异质性、反证和限制 | `ClaimEvidence` | G4 确认解释边界 |
| S9 结论与政策含义 | 大纲、结论、政策含义、HTML 报告和研究包 | `ResearchPackage` | G5 确认发布与导出 |

每一步必须支持“生成草稿、人工编辑、批准/退回、查看依据、进入下一步”。AI 不能替用户批准自己的输出。

## 3. 六天产品架构

### Web 科研工作台

- 首屏直接进入项目工作台，不建设营销落地页；
- 左侧固定 S0-S9 十阶段导航，显示 `not_started/in_progress/needs_review/approved/blocked`；
- 中间显示当前步骤的结构化编辑区、AI 建议和运行结果；
- 右侧或抽屉显示来源、差异、Gate 问题和下一步；
- HTML 可视化报告作为步骤 2、8、9 的统一审阅与交付视图。

### API 与服务层

- 使用 FastAPI 提供本地 API 和静态 Web 工作台；
- `ProjectService` 管理项目、阶段状态和当前资产；
- `ResearchService` 复用现有 RiffBand Agent Runtime 和 research pipeline；
- `LiteratureService` 执行多源并集检索、规范化、去重和 provenance；
- `KnowledgeService` 加载 DevPack 的方法、公式和数据源 Registry；
- `ApprovalService` 实现本地单人 G0-G5 决定与审计；
- `RunnerService` 提供 Stata BYOL preflight/submit/collect 和明确 blocked 状态；
- `ExportService` 生成 HTML、Markdown、JSON 和研究包。

### 数据与资产

- SQLite 保存项目、阶段、资产 revision、审批和运行索引；
- `workspace/projects/<project_id>/` 保存检索快照、报告、代码、日志和导出包；
- 每个资产至少包含 ID、类型、版本、作者类型、时间和内容 hash；
- 原始论文元数据、运行日志和结果只追加，不静默覆盖；
- 六天版本为单用户本地产品，不实现组织级登录与多租户。

### Docker 交付边界

- 最终交付单镜像 `ai4ms-workbench:<version>`，用户通过 Web GUI 使用产品；
- 容器进程监听 `0.0.0.0:8000`，宿主机只映射 `127.0.0.1:8000`；`/` 为十阶段工作台，`/api/v1` 为 GUI 内部应用接口，`/docs` 仅供开发调试，`/healthz` 为健康检查；
- SQLite、项目资产和导出报告写入 `/app/data`，通过 Docker volume 持久化；
- 模型和检索 Key 通过 `--env-file` 或运行时环境变量注入，禁止写入镜像；
- 容器允许访问已配置的模型和开放检索服务；断网时仍能打开已保存项目和静态报告；
- Stata 安装、许可证和受限数据不进入镜像，容器通过 `RunnerService` 连接用户或机构提供的外部 Runner；
- 同时提供 `Dockerfile`、`.dockerignore`、`docker-compose.yml`、部署说明和 GUI smoke test。

### Stata 外部依赖

当前开发机未检测到 Stata 可执行文件。D1 必须确认一台具有合法 Stata 许可的演示 Runner；若没有，产品仍需完整实现 BYOL Runner 发现、do-file 编辑、策略预检和 `blocked:no_runner` 状态，但不得宣称已经完成真实 Stata 执行。

## 4. 双人分工

| 负责人 | 产品角色 | 主责 | 主要代码边界 |
|---|---|---|---|
| 工程负责人 | Tech Lead / Integrator | 架构、API、SQLite、十阶段状态机、检索、Runner、测试、发布 | `src/ai4ms/`、`src/research/`、核心测试和工程配置 |
| 产品设计负责人 | Product & Research Lead | 十阶段交互、MS 规则、Prompt、方法数据内容、报告与演示 | `src/web/`、`src/research/skills/`、`src/ai4ms/domains/`、`src/ai4ms/prompts/`、fixtures 和产品文档 |

产品设计负责人可以 Vibecoding，但公共 Schema、状态迁移、Runner、权限和持久化由工程负责人审核。两人不得同时修改同一个核心文件；接口和示例先冻结，再并行实现。

## 5. 每日 DDL

| 日期 | 工程负责人 | 产品设计负责人 | 当日完成标准 |
|---|---|---|---|
| 7 月 21 日 D1 | 建立 FastAPI/Web 壳、SQLite ProjectStore、十阶段状态机和公共 Schema；验证豆包；移除通信硬编码 | 完成十阶段线框、字段、按钮、空/错/加载状态；冻结三个主演示课题和验收样例 | 能创建项目、切换十阶段、保存编辑和审批；模型真实可调用 |
| 7 月 22 日 D2 | 打通 S0-S1：TopicBrief、多源并集检索、去重、PaperCard、Gap 和最小 G0 | 完成问题识别、检索、论文和流派界面及 Prompt，人工核查种子论文 | 从一句想法生成真实来源报告，并完成问题边界审批 |
| 7 月 23 日 D3 | 打通 S2-S4：理论、Protocol、设计方案、方法/公式/数据 Registry、G1/G2 | 完成理论、设计、数据、方法、许可和风险编辑界面 | 课题形成可编辑、可审批的理论、数据方法与研究设计 |
| 7 月 24 日 D4 | 打通 S5-S7：AnalysisPlan、do-file revision、Stata preflight/Runner、结果、稳健性和复现元数据 | 完成代码 diff、运行状态、结果表图和稳健性工作区 | 有 Runner 时真实运行；无 Runner 时准确阻塞且完整展示准备结果 |
| 7 月 25 日 D5 | 打通 S8-S9；完成 Dockerfile/Compose、健康检查、volume 和容器端到端 smoke | 完成机制与异质性、证据中心、HTML 报告、演示稿和容器内置示例项目 | Docker 启动后十阶段 GUI 完整走通两次，功能冻结 |
| 7 月 26 日 D6 | 构建固定 tag 镜像，复核部署说明、数据迁移、测试和提交包，禁止临时开发 | 复核视频、截图、介绍、答辩和提交表单 | 中午前形成镜像与部署包，至少预留 4 小时上传和纠错 |

## 6. 产品验收

### 十阶段完整性

- 一个项目可以从 S0 走到 S9，并在重启后恢复；
- 每个阶段均有可编辑资产、AI 草稿、人工决定、状态和下一步；
- 未批准上一步时，下一关键步骤不能静默进入正式状态；
- 所有失败显示为 `blocked/partial/failed`，不能伪装为完成。

### 科研可信度

- 三个主演示课题不出现 RIS/ISAC/beamforming 串扰；
- 报告论文和外部链接真实，演示集中虚构引用为 0；
- 核心综合结论、Gap 和 Claim 均能回到论文、数据或 Run；
- “本次未检索到”与“证明不存在”严格区分；
- 摘要级证据不标记为全文证据；
- 数据或方法不可行时允许返回缩小、改题或暂停。

### 产品体验

- 首屏是实际工作台，十阶段状态清晰；
- 用户能在 10 分钟内找到当前任务、证据、风险和下一步；
- HTML 报告包含目录、真实来源、论文表、至少一个图表和决策摘要；
- 断网、模型失败或无 Stata Runner 时仍可打开已保存项目和报告。

### Docker 交付

- `docker compose up` 或一条 `docker run` 命令可以启动产品；
- 浏览器访问 `/` 能使用完整 GUI，不依赖宿主机 Python 环境；
- `/healthz` 返回健康状态，GUI 可以完成创建项目、执行阶段、保存编辑、审批和导出报告；
- 重启容器后，挂载卷中的项目、审批和报告仍然存在；
- 镜像历史和日志不包含 API Key、Stata 许可证或用户受限数据。

## 7. 六天范围边界

十个产品阶段不能删除，但每个阶段采用最小实现。以下生产级能力不在本轮建设：组织级 OIDC/RBAC、多租户、四眼/多人会签、复杂审批失效矩阵、付费数据库连接器、受限全文抓取、云端 Stata 托管、复杂知识图谱、实时协同编辑、Kubernetes、Neo4j 和大规模任务队列。

这不是用静态页面代替功能：检索、AI 生成、编辑、审批、持久化、Runner 状态、证据关联和导出都必须有真实代码路径。

## 8. 协作规则

- `ai4ms` 是集成分支，个人分支使用 `feat/core-workbench-*` 和 `feat/product-workbench-*`；
- 每天至少两次合流，D4 起每天跑完整十阶段 smoke；
- 每个 Vibecoding PR 必须人工通读并带测试或固定样例；
- 引用虚构、状态丢失、AI 自批、运行结果可编辑、失败误报成功均为发布阻塞问题；
- D5 下午停止增加功能；D6 只处理提交阻塞问题。

详细调研、Schema 和原始规划仍保留在 [AI4MS DevPack v0.3](refer/AI4MS-DevPack_v0.3/README.md)，但不再作为当前六天交付节奏。
