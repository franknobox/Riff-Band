# {{报告标题}}

报告版本：{{report_version}}  
检索快照：{{searched_at}}  
TopicBrief：{{topic_brief_id}} / v{{topic_brief_version}}  
状态：{{draft | needs_revision | approved | rejected}}

> 本报告说明“在已记录的数据库、检索式、日期和筛选范围内找到了什么”。它不证明某项研究绝对不存在，也不自动证明选题原创。

## 1. 决策摘要

### 课题一句话说明

{{研究对象、核心关系/决策、时间和情境}}

### 为什么重要

{{理论、管理或政策意义；每项事实绑定 synthesis/evidence ID}}

### 已有研究版图

- 经典基础：{{stream IDs + 代表论文}}
- 近年进展：{{stream IDs + 代表论文}}
- 稳定共识：{{supported synthesis IDs}}
- 主要争议：{{contested synthesis IDs}}
- 仍然未知：{{limited/not_found/inference synthesis IDs}}

### 候选研究空白

{{每项列 gap ID、类型、状态、支持/反向证据、覆盖限制。只有 supported_gap 可进入正式选题理由。}}

### 建议

{{continue | narrow | reframe | merge | pause}}：{{依据}}

## 2. 检索范围与可复现信息

| 字段 | 内容 |
|---|---|
| 数据库 | {{OpenAlex / Crossref / Semantic Scholar / arXiv / institution sources}} |
| 检索日期 | {{ISO datetime}} |
| 年份/语言/文献类型 | {{filters}} |
| 核心概念块 | {{concept blocks}} |
| 完整检索式 | {{query strings or search protocol link}} |
| 命中数 | {{各库原始计数与合计}} |
| 去重后 | {{count}} |
| 已筛选/纳入 | {{counts}} |
| 前向/后向扩展 | {{sources and counts}} |
| 空白反向查询 | {{counter-search protocol IDs}} |
| 未覆盖范围 | {{数据库、语言、全文、时间与许可限制}} |

## 3. 研究脉络与主要流派

### {{流派 1 名称}}

定义：{{stream description}}  
代表论文：{{paper IDs + citation}}  
主要问题/理论：{{summary}}  
常用数据/方法：{{summary}}  
主要发现与边界：{{synthesis IDs}}

{{按流派重复；流派名称必须有 naming_evidence 和 review_status。}}

## 4. 代表研究证据表

| 论文 | 研究问题/理论 | 数据/样本 | 方法 | 核心发现 | 稳健性/局限 | 证据等级与定位 |
|---|---|---|---|---|---|---|
| {{paper ID + short citation}} | {{...}} | {{...}} | {{...}} | {{...}} | {{...}} | {{metadata/abstract/fulltext/human_verified + locator}} |

规则：缺失写 `unknown`；摘要信息不得标为全文；不得用自动补全制造看似完整的单元格。

## 5. 共识、争议与未知

### 相对稳定的共识

- [{{synthesis ID}}] {{statement}} — 支持证据：{{IDs}}；限定：{{qualifiers}}

### 存在争议

- [{{synthesis ID}}] {{statement}} — 支持：{{IDs}}；反向：{{IDs}}；可能来源：{{情境/测量/方法/样本}}

### 证据有限或本次未检索到

- [{{synthesis ID}}] {{statement}} — 状态：{{limited | not_found | inference}}；覆盖限制：{{limitations}}

## 6. 研究空白地图

| Gap ID | 类型 | 候选表述 | 支持证据 | 最近似/反向证据 | 反向查询 | 覆盖限制 | 置信 | 人工状态 |
|---|---|---|---|---|---|---|---|---|
| {{...}} | {{theory/context/data/method/time/practice}} | {{...}} | {{IDs}} | {{IDs}} | {{protocol IDs}} | {{...}} | {{0—1}} | {{candidate/supported_gap/rejected/needs_review}} |

禁止把 `candidate` 写成确定贡献；禁止“首个、无人研究、完全空白”等无覆盖依据的绝对表述。

## 7. 数据与方法可行性

### 可用数据

- {{data source ID}}：单位、时间、地域、关键变量、访问、成本、许可、PII、测量风险。

### 首选与备选方法

- {{method ID}}：适用理由、最小数据、关键假设、诊断、不能解决的问题、备选方法。

### 阻塞项

- {{数据不可得、许可未清、处理/结果不可观测、关键识别假设不成立、计算不可行等}}

## 8. 候选课题卡

### {{candidate ID}} — {{研究问题}}

- 已知与未知：{{...}}
- 可能贡献：{{...}}
- 最近似研究：{{paper IDs}}
- 最小可行数据：{{...}}
- 首选/备选方法：{{method IDs}}
- 关键假设：{{...}}
- 风险与停止条件：{{...}}
- 新颖性/重要性/可行性/可证伪性：{{1—5 分 + 文字依据}}
- 建议：{{continue | narrow | reframe | merge | pause}}

{{重复 2—3 张。}}

## 9. 建议的下一步

1. {{必须精读/人工核查的论文}}
2. {{必须验证的数据}}
3. {{需要导师/领域/方法专家确认的问题}}
4. {{若 G0 通过，映射到 Research Protocol 的字段}}

## 10. 风险与报告限制

- {{数据库覆盖、检索式、语言、付费墙、版本、引用网络、抽取准确性、时间快照等限制}}
- {{任何状态为 inference 的内容}}
- {{厂商/第三方数据的独立核验状态}}

## 11. 参考文献

{{仅从已核验 paper records 输出；包含 DOI/URL、文献版本和来源库。}}

## 12. 审计附录

- SearchProtocol IDs：{{...}}
- 原始快照 artifact IDs / hashes：{{...}}
- 纳入/排除决定及理由：{{...}}
- 模型、提示和抽取版本：{{...}}
- 人工修改：{{...}}
- DOI/数字/引用/绝对新颖性审计结果：{{...}}
- G0 决定：{{approver / time / selected_candidate / reason}}

