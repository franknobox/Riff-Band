# Agent 设计、工具边界与质量门禁

## 1. 设计原则

Riff-Band 已经采用“流水线掌握顺序，Agent 负责执行”的正确方向，应继续坚持。新增 Agent 不是为了堆角色，而是把任务限定在明确输入、工具、输出 schema 与评测集内。

产品层采用“每个科研阶段一个主协作智能体”。用户只面对当前阶段的主智能体；Librarian、Reader、Reviewer 等作为内部 helper。主智能体提交可编辑草案和 patch，用户拥有修改权，G0—G5 只能由人批准。

子 Agent 继续使用 `(Instruction, Context, Tools, Model)` 四元组，但增加：

- `InputSchema/OutputSchema`
- `AllowedArtifactTypes`
- `PermissionScope`
- `Budget/Deadline`
- `EvaluationPolicy`
- `HumanGateBefore/After`
- `EditableArtifactTypes/ImmutableArtifactTypes`
- `PatchAndApprovalImpactPolicy`

## 2. 用户可见的阶段主智能体

| 阶段 | 主智能体 | 关键协作对象 | 人工出口 |
|---|---|---|---|
| S0 | Topic Agent | TopicBrief、已有研究报告、候选课题 | G0 |
| S1 | Literature Agent | SearchProtocol、筛选、PaperCard | 覆盖/真实性检查 |
| S2 | Theory Agent | 构念、机制、问题、假设/命题 | G1 会签输入 |
| S3 | Design Agent | 主备设计、estimand/目标、Assumptions | G1 |
| S4 | Data Agent | Data Contract、变量、许可、伦理 | G2 |
| S5 | Analysis Plan Agent | 主次分析、样本、诊断、代码计划 | G3 输入 |
| S6 | Stata Analyst Agent | do-file patch、预检、batch run、manifest | G3 后执行 |
| S7 | Robustness Agent | 诊断、稳健性矩阵、复现 | G4 输入 |
| S8 | Evidence Agent | Claim、支持/反证、解释与边界 | G4 |
| S9 | Writing Agent | 成稿、审稿答复、引用与复现包 | G5 |

完整协作模型见 `STAGE_AGENT_COLLABORATION.md`。

## 3. 内部执行与评审 Agent

| Agent | 负责 | 不得做 | 主要工具 | 输出 |
|---|---|---|---|---|
| Orchestrator | 分阶段、依赖、重试、合并 | 改变已批准协议 | task/gate/artifact tools | task plan/events |
| Question Coach | 问题、目标、可证伪条件 | 直接选最终方法 | literature preview, canvas | RQ candidates |
| Topic Scout | 概念树、术语扩展、三层检索计划 | 宣称绝对原创 | query planner, search adapters | topic brief/search protocols |
| Librarian | 多源检索、去重、元数据核验 | 虚构或替换 DOI | OpenAlex/Crossref/S2/arXiv | search snapshot |
| Paper Reader | 结构化抽取与定位 | 把摘要推断标成全文事实 | GROBID/PDF, schema writer | paper cards |
| Evidence Synthesizer | 研究流派、共识、冲突与未知 | 用引用量替代证据质量 | paper cards, citation graph | streams/syntheses |
| Gap Analyst | 六类空白、反向查询、最近似研究 | 把未检索到改写成无人研究 | synthesis, query planner, catalogs | gap/topic candidates |
| Design Advisor | 比较研究设计与关键假设 | 越过 G1 | method/formula/data catalog | design memo |
| Data Steward | 数据可行性、许可、变量与质量 | 绕过授权或上传受限数据 | data connectors/contracts | data contracts |
| Method Engineer | 模型/代码骨架、诊断与测试 | 直接写核心结论 | compute sandbox, formula cards | code/run plan |
| Stata Analyst | 从批准计划生成 do-file patch、预检、受控 batch run 与结果 manifest | 自批 G3、手改结果、动态装任意 ado、绕过许可 | stata policy/preflight/runner, method cards | do-file revisions/stata runs |
| Repro Auditor | 复现、hash、环境、结果一致性 | 修改结果让测试通过 | manifest/test tools | audit report |
| Skeptical Reviewer | 替代解释、反证、主张强度 | 无证据地否定 | claim graph, robustness | review issues |
| Writer | 从批准 claims 组稿 | 新增未经批准数字/引文 | outline/citation/export | draft/export |

## 4. 每步统一返回协议

```json
{
  "status": "succeeded | partial | needs_input | blocked | failed",
  "summary": "一句话结果",
  "artifacts": [{"artifact_id": "...", "type": "...", "schema_version": "..."}],
  "claims_created_or_updated": ["C-..."],
  "assumptions_touched": ["A-..."],
  "gate_checks": [{"check": "...", "passed": true, "evidence": "artifact-id"}],
  "open_issues": [{"severity": "...", "owner": "human|agent|system", "next_action": "..."}],
  "draft_revision_id": "...",
  "patches": [{"target": "...", "reason": "...", "evidence_ids": [], "approval_impact": ["G3", "G4", "G5"]}],
  "decisions_needed": [{"role": "human", "question": "...", "due_before": "G3"}],
  "handoff_readiness": {"ready": false, "missing": []},
  "provenance": {"model": "...", "prompt_version": "...", "tool_calls": []}
}
```

## 5. 语义门禁与确定性门禁

| 阶段 | 确定性检查 | 语义/人工检查 |
|---|---|---|
| 课题侦察 | TopicBrief 版本、数据库/查询/日期、命中/去重/纳排数、反向查询、来源 ID | 概念边界、流派命名、空白是否成立、候选课题价值与 G0 批准 |
| 检索 | DOI 格式、重复、查询快照、结果数 | 主题覆盖、纳排理由 |
| 论文卡 | schema、locator、字段来源等级 | 方法/数据/结论抽取准确性 |
| 理论/问题 | 必填构念、竞争解释、可证伪条件、版本与 diff | 理论适配、贡献边界、假设合理性与 G1 |
| 设计 | 必填、备选≥1、假设清单 | 设计与问题/DGP匹配 |
| 数据 | license/PII、变量、版本、质量检查 | 代理变量合理性、可得性 |
| 分析计划/Stata | G2/G3、do-file hash、变量、危险命令、许可席位、版本/ado manifest | 模型设定、样本、标准误、主次分析 |
| 运行 | 测试、退出码、hash、环境、随机种子、数据签名 | 模型设定与业务机制 |
| 结果 | 指标/表一致、诊断阈值、不可变 Run | 替代解释、外部效度与 G4 |
| 写作 | DOI/引用、数值、图表、证据覆盖 | 贡献强度、论证、边界与 G5 |

## 6. 评测体系

### 离线基准

- 100 篇论文中的 30 篇人工全文金标：问题、理论、数据、方法、公式、稳健性、结果、局限；
- 10 个真实管科研究想法的课题侦察金标：种子论文、同义词、最近似研究、结论冲突、错误空白和可行候选题；
- 30 个研究问题的设计推荐金标：正确泳道、关键假设、危险替代方案；
- 20 个 Data Contract：许可、PII、变量和质量缺陷；
- 20 个统计/优化 notebook：可复现、故意注入错误、预期门禁；
- 20 个 Stata do-file/Runner fixture：正确版本、危险命令、缺变量、过期审批、许可并发和数值漂移；
- 50 个 claim：支持、反证、过度表述和正确边界。

### 指标

- 检索：recall@k、精确率、去重准确率、DOI准确率；
- 课题侦察：种子论文 Recall@50、流派覆盖、冲突证据召回、错误空白判断率、报告结论可追溯率；
- 抽取：字段级 precision/recall/F1、locator 准确率、置信校准；
- 设计：关键假设召回率、错误方法推荐率、阻塞判断率；
- 代码：测试通过、数值一致、sandbox policy violation；
- Stata：batch 成功率、日志/manifest 完整率、危险命令阻塞、重放一致性；
- 写作：claim-evidence coverage、citation entailment、数值一致性；
- 人机：patch 接受/修改/拒绝率、审批完整率、错误失效率、越权尝试、完成时间和返工率。

## 7. 防止“多 Agent 看起来很忙但没有增益”

- 只有当子任务可独立、工具/模型不同或需要对抗审查时才委派。
- 默认单 Agent + 确定性工具；并行用于多数据库检索、独立论文抽取和多视角审稿。
- 每个委派必须有增益指标：时间、召回、错误发现或质量提升。
- 同一输入的重复角色辩论不计为证据；最终结论由 artifact 和 gate 支撑。
- 设置调用预算、最大深度和停止条件；失败不无限创建新 Agent。
- 用户可见的主智能体不因内部 helper 数量变化而变化；所有建议最终落到可编辑 revision、证据或 issue。
- Agent 不能提交或批准 Gate；只有用户能把草案送审，Approval Service 只接受 human actor。
