# Paper-Agent 与 skill-thesis-writer 适配说明

日期：2026-07-26
AI4MS Prompt Policy Registry：`2.1.0`

## 1. 目的

本次改造把两个开源项目中的可复用工作流转成 AI4MS 的可审计科研资产，而不是复制一个自动写论文流程：

- [Tswoen/Paper-Agent](https://github.com/Tswoen/Paper-Agent)（审阅基线 commit `37e9c2376445182dbe6c8daf3241c5ab48fdc4d1`，MIT）；
- [yanlin-cheng/skill-thesis-writer](https://github.com/yanlin-cheng/skill-thesis-writer)（审阅基线 commit `0d35ef18ec4f6a1a7cb0389b75f652e54c4a3f8e`，Mulan PSL v2）。

采用原则是“研究协议 + 证据 + 可复现性 + 人工责任”。AI 负责检索规划、结构化提取、比较、起草和检查；研究者负责选题、纳排、解释、修改、审批和发布。

## 2. 采用与拒绝

| 参考模式 | AI4MS 采用方式 | 明确不采用 |
|---|---|---|
| Paper-Agent 的 Search → Read → Analyze → Write → Report | 转成有 revision、ID、provenance 和人工门禁的 S0/S1/S9 资产链 | 不复制示例中的硬编码搜索结果 |
| 查询生成后人工确认 | 模型 query plan 绑定确定性 fingerprint；未获人工批准不得自动执行 | 不让检索智能体自行批准检索范围 |
| 每篇论文并行阅读与结构化抽取 | `paper_evidence_cards` 记录问题、理论、设计、样本、数据、方法、发现、限制、贡献和 locator | 不把摘要当全文，不用“行业常识”填补原文缺失 |
| 聚类、流派内分析和全局综合 | `research_streams`、`method_comparisons`、`contradictions` 和跨流派 `syntheses` | 不把聚类标签当作客观学科分类 |
| Outline → 分节写作 → Review → Assembly | `outline` 与 `manuscript_sections` 一一对应，逐节绑定 paper/claim/evidence ID，再由服务端确定性装配 | 不允许写作智能体新增论文、数据、数值或发布状态 |
| thesis-writer 的管理学写作结构 | 作为按研究范式适用的写作检查，而非固定模板 | 不默认所有管理研究都要问卷、SEM、中介/调节或 Harman 检验 |
| 结构、逻辑、变量/数据、引用、风格、格式检查 | 形成 `author_self_review`，并由独立确定性 `AcademicOutputQualityService` 再检查 | 不采用机械总分，不以“降低 AI 检测率”为目标 |
| GB/T 7714、APA 等格式 | `document_profile.citation_style` 驱动服务端书目装配；缺失字段必须回到 S1 核验 | 不让模型猜测作者、年份、卷期页或 DOI |

## 3. 新工作流

### 3.1 S0 问题识别

1. 区分管理现象、管理决策问题、科学问题和候选贡献。
2. 生成至少两个 materially distinct 的 `question_candidates`。
3. 每个候选说明问题类型、管理决策、分析单位、数据需求、可行性和 falsifier。
4. 生成 `problem_diagnostics`，覆盖清晰度、管理/理论相关性、创新候选、数据、伦理和层级匹配。
5. 研究者调用问题选择接口，选择 `question_id` 并写理由。
6. 选择记录绑定候选集 SHA-256；候选语义变化后旧选择自动失效。
7. G0 只能批准由人选择且与当前候选集一致的版本。

### 3.2 S1 文献检索与综述

1. 智能体生成经典、近期、相邻、反向和争议查询族。
2. 研究者批准 query plan；批准记录绑定 plan fingerprint。
3. 多源检索保存查询、来源、时间、返回量、失败和快照。
4. DOI、规范化题名和作者年份确定性去重。
5. 智能体返回的论文先写入 `evidence_candidates`，状态为 `pending`，不能直接进入综述或参考文献。
6. 研究者打开原始来源，修改并批准、拒绝或退回候选，同时声明证据等级和理由。
7. 人工批准后生成带 revision、内容哈希和审计轨迹的 `EVLIB_*` 权威记录。
8. 每篇 active 权威论文生成一张 `paper_evidence_card`；卡片必须与输入权威论文一一对应。
9. 先做研究流派内比较，再做跨流派综合；显式保留相反结果、可能解释和解决性检索。
10. `review_outline` 按概念、理论、方法、证据、争议、空白和研究切入点组织，禁止逐篇罗列。
11. 服务端生成 `coverage_audit`，只统计可观察覆盖，不推断科研结论。

证据等级规则：

- `metadata`：只能使用题名、作者、年份、来源等书目信息；
- `abstract`：可以提取摘要明确陈述，并标记摘要推断；
- `full_text`：只有阶段资产中确实存在可供模型读取的全文文本或摘录时可使用；仅填写“已读全文”或保存文件路径不能升级证据等级；
- 每个发现都必须带 `evidence_basis` 和 `locator`；
- 未报告内容写入 `unknowns`，不得补造。

### 3.3 S9 学术输出

1. `document_profile` 先声明文档类型、研究范式、受众、语言、引用规范和 CMB 适用性。
2. 生成摘要、关键词和大纲。
3. `manuscript_sections` 与大纲 section ID 一一对应，正文可人工逐节编辑和同步。
4. 正文使用以下显式来源标记：
   - `[paper:paper_id]`
   - `[claim:claim_id]`
   - `[evidence:evidence_id]`
5. 每节以 `citation_evidence_ids` 声明权威来源；每个 paper ID 必须映射到 active 的 `EVLIB_*`，数据研究直接使用 `EVLIB_*`，不伪造 paper ID。
6. 服务端校验正文标记、章节声明、参考文献与权威证据库一致，pending / rejected / archived 候选不能进入正文。
7. `logic_closure` 连接研究问题、方法/设计、获批主张和结论，并保留 partial/blocked 环节。
8. `author_self_review` 区分 `must_fix`、`should_improve` 和 `note`。
9. 服务端独立检查引用双向对应、重复书目、必要字段、逻辑闭环、适用性规则和绝对化措辞。
10. `must_fix` 未清零时禁止正式导出；通过后生成 HTML、质量 JSON、manifest 和研究 ZIP。
11. G5 仍需研究者确认当前 revision、披露和发布范围。

## 4. 新增 API

| 方法 | 路径 | 作用 |
|---|---|---|
| `POST` | `/api/v1/projects/{project_id}/stages/problem/question-selection` | 人工选择候选研究问题并绑定候选集指纹 |
| `POST` | `/api/v1/projects/{project_id}/stages/literature/plan-review` | 人工批准或退回模型检索计划 |
| `PATCH` | `/api/v1/projects/{project_id}/stages/literature/papers/{paper_id}/screening` | 保存逐篇纳排、理由和证据等级 |
| `GET` | `/api/v1/projects/{project_id}/stages/delivery/quality` | 获取当前 S9 的确定性质量报告 |
| `POST` | `/api/v1/projects/{project_id}/stages/delivery/export` | 质量门通过后生成 research package v2 |

如果研究者在检索请求中显式提交 `queries`，该动作本身作为本次人工查询范围；若请求使用模型生成的已保存 query plan，则必须先完成 plan review。

## 5. 确定性质量规则

`AcademicOutputQualityService` 不给论文打机械总分，只返回具体问题、位置和修复动作：

- 大纲与正文 section ID 一致；
- inline marker、章节声明和上游 ID 注册表一致；
- 每节 evidence ID 必须属于该节 claim ID；
- 正文论文引用与参考文献双向对应；
- 已引用论文的题名、作者和年份完整；
- DOI/规范化题名重复检查；
- 每个核心结论进入逻辑闭环；
- CMB 只在 profile 声明适用时检查；
- “证明了、首次、完全空白、无人研究”等表述进入人工复核；
- 模型自检标记的 `must_fix` 会进入服务端阻塞项。

质量报告写入研究包的 `quality/output_quality.json`，manifest 使用 `ai4ms.research-package.v2` 并记录规则版本、状态和问题计数。

## 6. 向后兼容

- 新结构字段对历史人工 revision 保留默认值；
- Prompt `2.1.0` 的模型生成强制产出新结构；
- 旧 S9 草稿仍可打开和导出，但会收到“补全文档 profile、正文和逻辑闭环”的建议优化项；
- 空默认字段与缺失字段在交付 fingerprint 中等价，避免模板升级导致已导出 revision 被错误判定为内容变化；
- 一旦使用新结构，ID 唯一性、证据等级、来源标记和逻辑映射立即进入硬校验。

## 7. 验收重点

- 模型不能把摘要升级成全文证据；
- 被人工排除的论文不能进入综合上下文；
- 检索计划变化后旧批准失效；
- 候选问题变化后旧人工选择失效；
- 正文不能引用未知 paper/claim/evidence ID；
- `must_fix` 未清零不能导出或批准 G5；
- 研究包必须包含质量报告及其 hash；
- 所有增强仍服从 G0–G5 人工审批和 revision/patch 语义。
