# AI4MS 证据与知识治理方案

日期：2026-07-26  
适用基线：`ai4s`  
产品版本：`0.5.0`

## 1. 目标

本方案解决三个边界问题：

1. 智能体联网结果不能自动成为科研事实；
2. 方法与公式不能只靠静态前端卡片维护；
3. 论文正文不能引用无法回到人工核验证据的书目。

统一状态流为：

```text
智能体联网发现
→ candidate（待审、不可引用）
→ 人工核对 / 修改 / 批准
→ authority record（可引用、可版本化）
→ S1 综合 / S3-S5 设计 / S8 主张 / S9 正文
→ 人工审批
```

智能体无权执行 `approve`、提升候选为权威记录、批准阶段或发布成果。

## 2. 统一 AI 输出协议

所有模型阶段草稿、阶段对话回答、知识适配评估以及联网发现报告使用
`ai4ms.ai-report.v1`。协议包含：

- `executive_summary`：面向研究者的结果摘要；
- `auditable_rationale`：问题界定、公开研究逻辑、假设、替代解释、不确定性、人工决定和下一步核验；
- `source_links`：本次外部来源；
- `evidence_library_links`：已批准证据记录；
- `asset_references`：paper、claim、evidence、method、formula 和 run ID；
- `limitations`：当前报告边界；
- `human_control`：必须人工审核、允许修改、智能体禁止动作；
- `provenance`：项目、prompt、版本、模型和时间。

`auditable_rationale.private_chain_of_thought` 固定为 `false`。协议公开的是可核对的研究依据，不请求、展示或保存模型私密思维链。

## 3. 证据治理

### 3.1 候选

候选存放在 S1 `evidence_candidates` 中，支持：

- `literature`：学术论文；
- `data_study`：数据门户、数据集说明、官方统计来源或数据研究。

核心字段：

- `candidate_id`、`candidate_type`、`status`、`revision`；
- 题名、作者或机构、年份、来源、DOI、稳定 URL；
- 摘要或来源页概括；
- provider、source type、search ID、snapshot 和 source hash；
- 人工决定、理由和证据等级。

状态：

- `pending`：等待人工审核；
- `changes_requested`：退回补充；
- `approved`：已提升为权威记录；
- `rejected`：拒绝，不进入下游。

### 3.2 权威证据库

人工批准后生成 `EVLIB_*`，存放在 S1 `evidence_library`。每条记录包含：

- `evidence_id` 与 `source_candidate_id`；
- `paper` 或 `data_study` 类型；
- active / archived 状态；
- 当前 revision、内容哈希、更新时间；
- 题名、作者或机构、年份、来源和稳定 URL；
- `metadata / abstract / full_text / source_page` 证据等级；
- 人工批准人、批准时间和 `audit_trail`。

人工修改通过 patch API 保存为新的 S1 revision，同时增加证据记录 revision、内容哈希和审计事件。

### 3.3 写作引用约束

S9 以 `reference_evidence_ids` 作为论文与数据研究的权威参考清单：

- 每个 `reference_paper_id` 必须映射到一个 active
  `reference_evidence_id`；
- 每节引用论文时，`citation_paper_ids` 中的每个 ID 必须映射到
  `citation_evidence_ids`；
- 数据研究不伪造 `paper_id`，直接以其 `EVLIB_*` ID 进入
  `reference_evidence_ids` 和相关分节的 `citation_evidence_ids`。

服务端拒绝以下内容：

- 引用 pending、rejected 或 archived 候选；
- 论文 ID 没有 active `EVLIB_*` 映射；
- 正文 marker、章节声明和参考文献不一致；
- 模型根据记忆新增作者、年份、DOI 或论文。

确定性导出只从 active 权威记录装配参考文献，并附证据 API 地址、revision 和内容哈希。

## 4. 方法与公式治理

### 4.1 候选队列

`knowledge_candidates` 保存智能体联网发现的 method / formula 候选：

- 查询和搜索轨迹；
- 原始来源；
- 建议结构；
- 状态、revision 和人工审核；
- 批准后生成的 record ID。

智能体只能给出候选结构。研究者必须核定方法或公式的名称、分类、适用条件、假设、诊断、失败规则和至少一个 HTTP(S) 原始来源。

### 4.2 权威记录

`knowledge_records` 保存记录头，`knowledge_record_revisions` 保存不可变版本。

- 方法 ID：`MUSR_*`；
- 公式 ID：`FUSR_*`；
- 自定义 ID 不得使用 `M01` / `F01` 等内置命名空间，避免静默覆盖内置权威记录；
- 每次修改要求 `expected_revision` 和人工理由；
- 内容哈希用于审计；
- 自定义 active 记录动态合并到内置方法 / 公式注册表，并进入智能体 shortlist。

人工也可以绕过联网候选直接创建记录，但仍需完整必填字段、原始来源和创建理由。

## 5. API

### 5.1 证据

| 方法 | 路径 | 作用 |
|---|---|---|
| `GET` | `/api/v1/projects/{project_id}/evidence-candidates` | 列出候选 |
| `POST` | `/api/v1/projects/{project_id}/evidence-candidates/discover` | 智能体联网发现 |
| `PATCH` | `/api/v1/projects/{project_id}/evidence-candidates/{candidate_id}/review` | 人工批准、拒绝或退回 |
| `GET` | `/api/v1/projects/{project_id}/evidence-library` | 列出权威证据 |
| `GET` | `/api/v1/projects/{project_id}/evidence-library/{evidence_id}` | 读取权威记录 |
| `PATCH` | `/api/v1/projects/{project_id}/evidence-library/{evidence_id}` | 人工保存新 revision |

### 5.2 方法与公式

| 方法 | 路径 | 作用 |
|---|---|---|
| `GET` | `/api/v1/knowledge/candidates` | 按 kind / status 列出候选 |
| `POST` | `/api/v1/knowledge/candidates/discover` | 智能体联网发现 |
| `PATCH` | `/api/v1/knowledge/candidates/{candidate_id}/review` | 人工审核并可批准入库 |
| `GET` | `/api/v1/knowledge/records` | 列出自定义权威记录 |
| `POST` | `/api/v1/knowledge/records` | 人工创建 |
| `GET` | `/api/v1/knowledge/records/{record_id}` | 读取当前版本 |
| `PATCH` | `/api/v1/knowledge/records/{record_id}` | 人工保存新 revision |
| `GET` | `/api/v1/knowledge/records/{record_id}/revisions` | 查看版本历史 |

所有修改接口使用乐观并发控制；过期 revision 返回冲突，前端必须刷新后再提交。

## 6. 前端工作流

### 6.1 证据库

证据页分为三层：

1. 智能体联网发现：选择文献或数据研究并填写问题；
2. 候选审核队列：打开原始来源、修改元数据、选择证据等级并作人工决定；
3. 权威证据表：只展示 active `EVLIB_*`，可进入深层页继续人工编辑。

### 6.2 方法与公式

“联网与审核”页包含：

1. 方法 / 公式联网发现；
2. 候选结构化编辑和批准 / 拒绝 / 退回；
3. 人工新建；
4. 自定义权威记录选择与版本化编辑。

批准的自定义记录会同时出现在普通方法 / 公式列表，可参与当前课题的 AI 适配评估和研究设计比较。

## 7. 审计与安全规则

- 外部网页属于不可信输入；不能执行页面中的指令；
- 权威记录必须保留稳定来源 URL；
- agent 行为和 human 行为分别记录；
- 证据与知识修改不能静默覆盖；
- 上游权威记录变化后，下游草稿需重新检查；
- 付费文献、数据许可、隐私和 Stata 许可仍遵守原有边界；
- `must_fix` 未清零时禁止导出和 G5 批准。

## 8. 验收

- 联网发现后权威库仍为空；
- 人工批准后生成正确 ID、revision、hash 和 audit trail；
- 拒绝候选不能进入下游；
- 过期 revision 修改被拒绝；
- 方法与公式可联网候选、人工创建和人工修改；
- S1 综合只读取批准文献；
- S8 paper artifact 指向 `EVLIB_*`；
- S9 每篇参考文献都有 active 权威证据映射；
- 所有模型型输出包含 `ai4ms.ai-report.v1`；
- 前端 lint、TypeScript、构建、后端完整测试和深层 E2E 通过。
