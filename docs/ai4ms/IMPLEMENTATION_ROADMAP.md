# AI4MS 下一步开发 Roadmap

本 Roadmap 从当前可交互前端和仓库已有 FastAPI/SQLite/RiffBand/Stata 基础出发，按依赖关系开发。不要同时大改 UI、状态机和持久化协议。

## P0｜先冻结契约（2–3 天）

1. 把前端 `MethodRecord`、`FormulaRecord`、`StageDraft.syncHistory` 转成 Pydantic schema。
2. 冻结 `ArtifactRevision`、`AgentSession`、`AgentMessage`、`SyncOperation`、`ToolCall` API。
3. 为写接口加 `base_revision_id`、幂等键和 `409 revision_conflict`。
4. 给方法/公式/诊断种子建立版本号与来源字段。

完成标准：OpenAPI 能表达当前页面全部读写，不需要前端继续使用演示数据补逻辑。

## P1｜方法、公式和诊断真实化（4–6 天）

1. 保留现有 28 个方法、47 个公式、40 个数据源作为权威种子，扩展 `KnowledgeRegistry` 为 method/formula/diagnostic 三个版本化注册表。
2. 实现搜索、家族筛选、方法详情、公式详情和来源查询。
3. 新增项目级 `method-selection` 与 `formula-binding`。
4. 实现符号—变量绑定校验和单位/角色冲突检查。
5. 把“加入研究设计”接到 S3/S5 revision。

完成标准：刷新页面后，方法选择、公式绑定和诊断清单仍存在；主/备/稳健/探索角色明确。

## P2｜智能体对话与正文同步（5–7 天）

1. 建立 AgentSession/Message/Run/Checkpoint 表。
2. 将 RiffBand Runtime 包装为阶段 Agent Runtime Adapter。
3. 实现消息流式事件和取消。
4. 实现 sync preview/confirm/cancel，包含 diff、来源消息和人工确认。
5. 处理并发 revision 冲突，绝不静默覆盖人工内容。
6. 在阶段版本历史中展示 sync provenance。

完成标准：S9 智能体回答可同步正文、生成新 revision、刷新可恢复；同一正文被人工修改后旧 preview 必须冲突。

## P3｜工具策略与 S0–S9 接通（7–10 天）

1. 建立 Tool Registry 和 Policy Engine。
2. 把 OpenAlex/Crossref/检索、方法、公式、证据、Stata 工具注册为有 schema 的工具。
3. 为每个 Agent 加 allowed tools、审批点、超时、成本和停止规则。
4. 实现 HumanInterrupt 和重启恢复。
5. 补齐每阶段正常/失败/权限/取消测试。

完成标准：任何 Agent 不能调用未授权工具，不能自批，等待人工后可从 checkpoint 恢复。

## P4｜运行与证据闭环（7–10 天）

1. 抽象统一 RunnerAdapter，保留 Stata，增加 Python/Solver。
2. 完成 G3、code hash、data signature、environment hash preflight。
3. 运行结果生成 immutable manifest 和 artifact hash。
4. 让 S7 只读取正式 Run，并保留全部失败项。
5. 让 S8 的 Claim 强制连接 source/run locator。

完成标准：修改获批代码或数据后无法正式运行；每个数字可以追溯到 run artifact。

## P5｜交付与生产化（5–8 天）

1. S9 只读取 G4 有效主张，完成引用/数字/表图一致性检查。
2. G5 后导出 HTML、manifest、ZIP；受限数据默认排除。
3. 增加审计事件、trace id、指标和错误分类。
4. 完成 Docker volume、断网恢复、备份恢复和升级迁移测试。
5. 数据量或多人需求出现后，再迁 PostgreSQL/Redis/对象存储。

完成标准：从创建项目到导出发布包可走通；重启后项目、审批、会话、run 和报告均可恢复。

## 现在立即做的 8 件事

1. 在后端新增 `sync_operations` 表和两个接口：preview、confirm。
2. 给 `artifact_revisions` 增加 `base_revision_id` 和 `content_hash` 冲突检查。
3. 不覆盖现有 28/47/40 注册表；把本轮 16 张方法深度卡和 12 张公式深度卡中的 `estimand`、代码模板、失败规则、符号映射等增强字段，按既有 ID 对齐后增量合并。
4. 扩展 `/knowledge/methods` 和 `/knowledge/formulas` 的详情/筛选 API。
5. 新增 `AgentSession`、`AgentMessage` 最小持久化，不急着先做复杂多智能体调度。
6. 将前端聊天 mock 替换为 session/message API，再接 RiffBand Runtime。
7. 写 4 个关键测试：AI 不能批准、旧 revision 不能覆盖、G3 失效不能运行、sync 必须有人确认。
8. 完成上述后再开发 Python/Solver Runner，避免同时扩张执行面。
