# S0–S9 智能体工具与调用规则

更新日期：2026-07-21

## 1. 统一定义

每个阶段智能体由以下对象版本化定义：

```text
AgentDefinition = Instruction + ContextPolicy + ToolPolicy + ModelPolicy + OutputSchema + ApprovalPolicy
```

智能体是阶段协作者，不是阶段所有者。它可以读取获准上下文、提出候选方案、调用允许的工具、生成结构化草稿和等待用户输入；不能批准、代签、接受风险或静默修改正式资产。

## 2. 通用调用协议

每次工具调用必须按以下顺序执行：

1. 说明当前任务和所需输出。
2. 检查阶段、项目、数据权限和有效上游 revision。
3. 选择最小权限工具；优先只读工具。
4. 生成结构化参数并通过 schema 校验。
5. Policy Engine 检查网络域、读写范围、审批门、成本和超时。
6. 高风险调用创建 `HumanInterrupt`，等待人工确认。
7. 执行并保存原始结果、hash、时间、版本和来源。
8. 对输出进行事实、引用、数据或代码校验。
9. 生成候选 patch，不直接覆盖用户正文。
10. 用户确认后创建 revision 或 sync operation。

## 3. 通用工具等级

| 等级 | 类型 | 例子 | 默认规则 |
|---|---|---|---|
| R0 | 纯推理，不访问外部系统 | 比较候选理论、解释公式 | 可直接调用；输出仍是建议 |
| R1 | 只读项目工具 | 读取阶段资产、方法卡、历史 revision | 可调用；最小上下文与字段脱敏 |
| R2 | 只读外部检索 | OpenAlex、Crossref、开放网页 | 允许已配置域名；保存查询和来源快照 |
| R3 | 可逆写入 | 建立草稿、筛选标签、同步 preview | 需用户可见；正式写入前人工确认 |
| R4 | 受控执行 | Stata、Python、Solver、全文解析 | 需有效审批、隔离环境、资源限制和 manifest |
| R5 | 外部副作用 | 发布、发送、付费下载、写第三方系统 | 默认禁止；另行授权和人工确认 |

## 4. 阶段智能体

### S0 Topic Agent｜问题识别

目标：把初始想法收敛为可检索、可证伪、可执行的候选问题，并报告已有研究，而不是宣称“绝对空白”。

| 工具 | 作用 | 调用规则 |
|---|---|---|
| `query_expand` | 生成中英文同义词、概念、结果变量和反向问题 | R0；每个概念保留来源或用户定义 |
| `openalex_search` | 搜索论文、主题、作者、期刊和引用网络 | R2；保存 query、filter、cursor、时间和 work ID |
| `crossref_lookup` | 核验 DOI、题名、作者、年份 | R2；只做元数据核验，不推断全文结论 |
| `similar_work_search` | 以摘要/问题寻找相似研究 | R2；结果标记为候选，不自动纳入 |
| `novelty_matrix` | 比较对象、机制、情境、方法、数据和结果维度 | R0/R1；没有覆盖证据时输出“未检索到”，不输出“不存在” |
| `feasibility_score` | 评估数据、方法、伦理、时间和资源 | R1；评分必须展示依据和不确定性 |

允许输出：`TopicBriefDraft`、候选问题、已有研究报告、检索限制、停止建议。  
人工点：修改问题、确认边界、接受/拒绝候选空白、G0。  
停止规则：关键概念无法操作化、核心数据不可获得、已有研究已充分回答且无可信增量时，建议缩小/改题/暂停。

### S1 Literature Agent｜文献综述

目标：形成可复核检索协议、论文卡、研究流派、分歧和证据缺口。

| 工具 | 作用 | 调用规则 |
|---|---|---|
| `search_plan_builder` | 生成数据库、检索式、时间窗和纳排标准 | R0；检索前形成版本化 protocol |
| `multi_source_search` | 并集检索 OpenAlex/Crossref/S2/arXiv 等 | R2；不能使用 first-success 丢弃其他来源 |
| `deduplicate_sources` | DOI、题名、作者、年份多键去重 | R1；保留合并来源与冲突字段 |
| `active_screening_ranker` | 按人工标签排序待筛论文 | R1；只排序，纳入/排除由人决定 |
| `fulltext_parser` | 解析用户有权访问的 PDF/TEI | R4；不得绕过付费墙或版权限制 |
| `evidence_locator` | 提取页码、章节、表图和片段定位 | R1/R4；片段与人工概括分开保存 |
| `citation_verifier` | 核验引用、撤稿、更正和元数据 | R2；异常必须阻塞核心引用 |

允许输出：`SearchRun`、`PaperCardDraft`、`RelatedResearchReportDraft`、覆盖限制。  
人工点：纳入/排除/不确定、全文核验、流派命名、综述定稿。  
停止规则：检索源不可用时明确 partial；核心来源未全文核验时不能结束 S1 核心证据检查。

### S2 Theory Agent｜理论构建

目标：把证据流派转为理论机制、竞争解释和可证伪命题。

| 工具 | 作用 | 调用规则 |
|---|---|---|
| `concept_extractor` | 从已核验证据抽取构念与关系 | R1；每个概念连接来源和定义 |
| `causal_graph_editor` | 建议 DAG、混杂、中介、碰撞点 | R3 preview；用户确认后写 TheoryModel revision |
| `theory_compare` | 比较解释力、边界与可检验性 | R0；不以引用量自动决定理论优劣 |
| `competing_explanation_generator` | 主动生成替代机制和反向因果 | R0；至少保留一个可信竞争解释 |
| `hypothesis_linter` | 检查方向、可证伪性、单位和边界 | R1；不能把相关表述改写成因果而不提示 |

允许输出：`TheoryModelDraft`、DAG patch、假设表、竞争解释。  
人工点：选择理论、编辑构念、确认贡献边界、G1 前置。  
停止规则：命题不可证伪、概念定义循环或理论链条没有可观测结果时退回修改。

### S3 Design Agent｜研究设计

目标：把研究问题转成分析单位、estimand/决策目标、主备设计、关键假设和停止条件。

| 工具 | 作用 | 调用规则 |
|---|---|---|
| `method_search` | 按目标、数据形态和约束检索方法卡 | R1；方法复杂度不进入适配分主权重 |
| `estimand_builder` | 定义处理、结果、总体、时间和对比 | R0/R3；写入前用户确认 |
| `design_comparator` | 比较 FE/DID/IV/RDD/实验/优化等 | R0/R1；展示假设、失败条件和未采用理由 |
| `identification_audit` | 检查混杂、溢出、操纵、选择与反向因果 | R1；发现阻塞项不得自动换模型 |
| `optimization_model_scaffold` | 生成集合、参数、变量、目标、约束骨架 | R3 preview；业务硬约束需用户确认 |

允许输出：`ResearchProtocolDraft`、候选方法 selection、设计风险。  
人工点：主备设计、估计/决策目标、停止条件、G1。  
停止规则：estimand 不清楚、识别假设无法论证、优化目标/约束缺失时不得进入正式 S4。

### S4 Data Agent｜数据与变量

目标：形成数据合同、变量字典、许可、隐私、质量和运行位置计划。

| 工具 | 作用 | 调用规则 |
|---|---|---|
| `data_source_registry` | 检索官方、商业、开放和自建数据源 | R1；标记许可、更新频率和字段覆盖 |
| `schema_profiler` | 检查字段类型、缺失、唯一键和时间范围 | R4；数据留在授权环境，只返回必要统计 |
| `variable_dictionary_builder` | 连接构念、变量、转换、单位与公式符号 | R3；每个关键变量由人确认口径 |
| `license_privacy_scanner` | 检查合同、PII、敏感字段和数据出境 | R1/R4；任何不确定项进入 G2 |
| `data_quality_rules` | 生成完整性、范围、重复和一致性规则 | R3；规则版本化，修复不覆盖原始数据 |

允许输出：`DataContractDraft`、变量字典、数据质量报告。  
人工点：许可、代理变量、数据位置、PII 处理、G2。  
停止规则：无合法访问、关键口径不可构造或隐私风险未处理时阻塞。

### S5 Analysis Plan Agent｜识别与检验

目标：把获批设计和数据转成公式、符号绑定、主次分析、诊断、稳健性和代码任务。

| 工具 | 作用 | 调用规则 |
|---|---|---|
| `formula_search` | 检索与方法版本匹配的公式卡 | R1；返回公式版本和来源 |
| `symbol_binding_validator` | 公式符号连接变量字典 | R1/R3；缺失、单位冲突或处理后变量直接报错 |
| `diagnostic_rule_loader` | 加载必须诊断与失败动作 | R1；主方法不能删除强制规则 |
| `power_sample_size` | 功效、样本量或仿真设计 | R4；保存假设、随机种子和不确定性 |
| `analysis_plan_compiler` | 生成可审阅 AnalysisPlan 与代码任务 | R3；主/稳健/探索分层且可人工修改 |
| `stata_template_generator` | 生成 do-file 草稿 | R3；只写草稿，不执行，不动态安装 ado |
| `solver_template_generator` | 生成模型/solver 草稿 | R3；参数、约束和 gap 需显式定义 |

允许输出：`AnalysisPlanDraft`、FormulaBinding、CodePlan、DiagnosticPlan。  
人工点：冻结变量、公式、主次分析、代码 revision、G3。  
停止规则：公式符号未绑定、诊断缺失、探索性分析混入主分析或代码与计划不一致时阻塞。

### S6 Stata Analyst｜结果分析

目标：协作编写、审查和解释代码；只在批准后通过机构 Runner 正式执行。

| 工具 | 作用 | 调用规则 |
|---|---|---|
| `stata_code_review` | 静态检查语法、路径、聚类和危险命令 | R1；禁止 shell、网络、动态安装和未知路径 |
| `stata_preflight` | 验证 G3、代码 hash、数据签名、许可与环境 | R4 前置；全部通过才允许 submit |
| `stata_run_submit` | 在 BYOL Runner 批处理执行 | R4；必须由人点击启动，Agent 无权调用到执行态 |
| `run_event_stream` | 读取进度和结构化日志 | R1；敏感行脱敏，不改原始日志 |
| `run_artifact_collector` | 回收表、图、日志和 manifest | R4；逐项 hash，只追加 |
| `result_interpreter` | 根据获批 estimand 生成解释草稿 | R1/R0；不得只以 p 值或显著性判断贡献 |

允许输出：do-file patch、preflight、`RunArtifact`、结果解释草稿。  
人工点：代码编辑、启动、取消、重跑分支、结果解释。  
停止规则：G3 失效、hash 不一致、无合法 Runner、数据签名变化或 policy 违规时硬阻塞。

### S7 Robustness Agent｜稳健性检验

目标：执行已预注册稳健性矩阵并主动暴露失败、负结果和结论边界。

| 工具 | 作用 | 调用规则 |
|---|---|---|
| `robustness_matrix` | 从方法卡和诊断规则生成检验矩阵 | R1/R3；区分预注册与新增探索性检验 |
| `placebo_generator` | 生成时点、组别、结果或随机化安慰剂 | R3/R4；运行仍走 G3/重跑审批策略 |
| `sensitivity_analysis` | 未观测混杂、带宽、样本、参数敏感性 | R4；完整保存通过与失败 |
| `run_comparator` | 比较主运行和稳健性运行 | R1；按 estimand、样本和代码差异对齐 |
| `failure_impact_assessor` | 评估失败对具体主张的影响 | R0/R1；只能建议降级，不能替人接受风险 |

允许输出：`RobustnessReportDraft`、失败影响 patch。  
人工点：追加检验、是否降级主张、是否重做设计。  
停止规则：关键失败项未解释、结果被选择性隐藏或新增检验未标探索性时不得进入 S8。

### S8 Evidence Agent｜机制与异质性

目标：把每条主张连接到文献、运行结果、机制、异质性、反证和边界。

| 工具 | 作用 | 调用规则 |
|---|---|---|
| `claim_builder` | 从获批结果生成最小可审查主张 | R3 preview；不超过结果支持强度 |
| `claim_evidence_linker` | 建立支持/冲突/限制/反证边 | R1/R3；每条边连接 locator 或 run artifact |
| `mechanism_audit` | 检查机制证据和替代顺序 | R1；机制探索与因果验证分开 |
| `heterogeneity_audit` | 检查 CATE、分组、多重比较和样本外验证 | R1；未验证分组不能写确定性政策 |
| `counterevidence_search` | 主动检索反证与边界研究 | R2；保存查询，不将未检索到当作不存在 |
| `claim_strength_linter` | 检查相关、因果、机制和外推措辞 | R1；越界主张创建阻塞 issue |

允许输出：`ClaimEvidenceDraft`、机制/异质性备忘录。  
人工点：降级、改写、撤回主张、G4。  
停止规则：主张没有 run/source locator、忽略冲突或外推越界时阻塞。

### S9 Writing Agent｜结论与政策含义

目标：协作生成论文、答复信、HTML 报告与发布包，同时保证数字、引用、限制和复现一致。

| 工具 | 作用 | 调用规则 |
|---|---|---|
| `outline_builder` | 从 G4 主张生成论文结构 | R1/R3；只读取有效批准主张 |
| `section_drafter` | 生成段落候选 | R0/R1；输出只进入对话或 sync preview |
| `sync_preview` | 将回答映射到正文/摘要/证据/决定字段 | R3；显示目标、模式、diff 和来源消息 |
| `sync_confirm` | 生成目标资产新 revision | R3；必须由 human identity 明确确认 |
| `citation_number_checker` | 核对引用、数字、表图和 run artifact | R1；任何不一致创建阻塞 issue |
| `repro_package_builder` | 生成 HTML、manifest、ZIP | R4；排除受限数据和密钥，保存 hash |
| `delivery_export` | 导出获批发布包 | R5；仅 G5 有效且由通讯作者触发 |

允许输出：正文候选、sync preview、`ResearchPackageDraft`。  
人工点：逐段修改、确认同步、披露限制、G5、导出发布。  
停止规则：引用/数字不一致、失败诊断被隐藏、受限资产进入包或 G5 未通过时禁止正式导出。

## 5. 智能体之间的交接

智能体不能直接调用另一个阶段智能体来绕过用户或审批。阶段交接通过已版本化资产：

| 上游 | 下游读取对象 | 不允许读取 |
|---|---|---|
| S0 → S1 | G0 有效 TopicBrief、查询词表 | 被拒绝问题的未说明结论 |
| S1 → S2 | PaperCards、RelatedResearchReport、证据 locator | 未核验摘要作为核心证据 |
| S2 → S3 | TheoryModel、竞争解释、假设 | 隐藏的单一路径假设 |
| S3 → S4 | ResearchProtocol、estimand、数据需求 | 未确认备选设计当作主设计 |
| S4 → S5 | G2 DataContract、变量字典 | 未授权字段与敏感原文 |
| S5 → S6 | G3 AnalysisPlan、代码 revision/hash | 聊天中的临时代码 |
| S6 → S7 | Run manifest、全部结果与日志 | 人工改写的“结果数值” |
| S7 → S8 | RobustnessReport、失败影响 | 被隐藏或删除的失败 run |
| S8 → S9 | G4 ClaimEvidence、限制与反证 | 未批准的强结论 |

## 6. 重试、停止与升级规则

- 网络超时、429、临时 5xx：指数退避，最多 3 次；保留每次尝试。
- schema 不合格：允许模型自修复 1 次；再次失败转人工，不保存为阶段 revision。
- 权限、许可、审批、hash、隐私和 policy 错误：不重试，立即阻塞。
- 数据/方法假设失败：不自动切换方法；创建 design decision 供用户处理。
- Stata/Solver 非零退出：保存日志和 partial artifacts；不得标记成功。
- 用户取消：停止后续调用，保存 checkpoint 和已生成的可审阅内容。
- 成本/时间超限：暂停为 `waiting_for_human`，由用户决定继续、缩小或停止。

## 7. 最低验收测试

每个智能体至少包含：

- 正常输出 schema 测试。
- 无来源/无数据/无 Runner 的阻塞测试。
- 工具权限拒绝测试。
- 人工 interrupt 和恢复测试。
- 上游 revision 变化后的失效测试。
- 取消、超时、重复请求和幂等测试。
- AI 无法创建 approval 的安全测试。
- 敏感字段和密钥不进入日志/模型上下文的测试。
