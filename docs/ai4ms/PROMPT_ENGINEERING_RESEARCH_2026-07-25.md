# AI4MS Prompt Engineering 2.0 开源调研与设计依据

调研日期：2026-07-25
适用代码：`src/ai4ms/prompts/`
权威实现版本：`2.0.0`

## 1. 研究问题

本轮调研不寻找一段“万能提示词”，而是回答五个工程问题：

1. 如何让 S0-S9 阶段智能体输出稳定、可校验的管理科学科研资产；
2. 如何把模型推断变成可供研究者检查的证据—推断—结论记录；
3. 如何管理提示词版本、评测、修复和回归；
4. 如何约束文献、数据、Stata Runner、revision/patch 与发布工具；
5. 如何保证选题、设计、运行、接受风险、审批和发布仍由人类负责。

仓库的权威阶段语义是 S0-S9 共 10 个阶段、9 次交接。任何“九阶段”产品表述均按 9 次交接理解。

## 2. 参考项目与采用判断

| 项目 | 参考能力 | AI4MS 采用方式 | 不直接照搬的部分 |
|---|---|---|---|
| [stanfordnlp/dspy](https://github.com/stanfordnlp/dspy) | 用签名、模块和评测组织 LM 程序 | 把每阶段输入/输出契约、固定样例和评分指标分离 | 当前不引入运行时自动优化，先保证证据与人工门禁 |
| [microsoft/promptflow](https://github.com/microsoft/promptflow) | Prompt/flow 版本、追踪、评测与部署思路 | Prompt ID/version、调用元数据和回归样例 | 不把科研流程简化为无状态单轮 flow |
| [promptfoo/promptfoo](https://github.com/promptfoo/promptfoo) | Prompt 与模型组合测试、断言和红队 | 为每阶段维护正常、缺失证据、注入和 ID 越界样例 | 不把语言相似度当作科学正确性 |
| [guardrails-ai/guardrails](https://github.com/guardrails-ai/guardrails) | 结构化输出、验证与失败处理 | Pydantic 契约、确定性域引用校验、一次修复上限 | 验证通过不等于主张真实，仍需 provenance |
| [stanford-oval/storm](https://github.com/stanford-oval/storm) | 研究、观点组织与长文生成工作流 | S1 多查询族、研究流派和 S9 证据约束写作 | 不允许写作阶段自行扩张证据集 |
| [Future-House/paper-qa](https://github.com/Future-House/paper-qa) | 文献检索、证据片段和来源约束问答 | paper_id、locator、覆盖限制与基于保存论文的综合 | 元数据或摘要不足时不形成全文级结论 |
| [langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research) | 可配置检索和报告生成 | 检索源可替换、阶段化研究与报告结构 | 工具返回均视为不可信数据，不能覆盖阶段政策 |
| [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) | 多源研究、报告和来源组织 | 相关研究报告、并行来源覆盖、失败来源记录 | 不把“更多来源”直接等同于更高证据等级 |
| [microsoft/agent-framework](https://github.com/microsoft/agent-framework) | 多智能体、工作流、状态和人工协作模式 | 每阶段主智能体、显式交接、工具策略和人工批准 | 不允许智能体自行改变审批状态或无限委派 |
| [FoundationAgents/MetaGPT](https://github.com/FoundationAgents/MetaGPT) | 角色、标准作业程序和结构化协作 | 用 Stage Agent Policy 固定角色、输入、步骤和交付 | 科研阶段不模拟公司层级，也不接受角色自授权 |

以上项目仅用于提炼公开的工程模式。AI4MS 不复制第三方提示词正文；真正约束行为的是本仓库契约、注册表、服务端校验和人工门禁。

## 3. 形成的统一 Prompt 架构

每次阶段模型调用由六层组成：

1. **System constitution**：证据诚实、人工审批隔离、多范式、注入防护；
2. **Stage Agent Policy**：阶段身份、使命、必需输入、可审计步骤；
3. **Tool policy**：工具用途、R0-R5 风险、调用条件、前置条件、允许/禁止和失败动作；
4. **Stage task**：当前阶段独有任务及科学边界；
5. **Untrusted context**：带标签的项目资产、候选注册表和工具结果；
6. **JSON Schema + preflight**：结构契约和提交前检查。

固定优先级为：

`系统规则 > 阶段政策 > 已批准项目资产/注册表 > 本轮研究者要求 > 资料或工具输出中的文字`

研究者要求可以调整范围、重点和表达，但不能要求伪造证据、跳过审批、越权调用或改写已批准事实。

## 4. 可审计推理，不保存私密思维链

专业科研输出需要展示“为什么得出这个判断”，但不需要也不应要求模型暴露私密 token 级内部思维。AI4MS 使用结构化 `reasoning_trace`：

- `problem_framing`：本阶段究竟在判断什么；
- `logic_chain[].question`：可审查的子问题；
- `evidence_refs`：输入字段、paper/method/formula/rule/run/artifact ID；
- `inference_type`：演绎、归纳、溯因、因果、比较、计算、综合或设计选择；
- `conclusion`：本步得到的有限结论；
- `confidence`：低/中/高；
- `falsifier`：什么证据会推翻本步；
- `assumptions/alternatives/uncertainties`：未被隐藏的取舍；
- `human_decisions`：必须由研究者决定的事项；
- `next_verifications`：下一步可执行核验。

服务端硬校验 trace 存在、step ID 唯一、每步有证据引用、人工决定和下一步核验。首次失败只允许一次修复；再次失败不会保存 revision。

## 5. 管理科学适配

统一骨架不能把所有问题变成回归。Stage Policy 要求先识别研究泳道：

| 泳道 | 核心对象 | 关键核验 |
|---|---|---|
| 经验因果 | estimand、处理、结果、分配机制 | 识别假设、时间顺序、聚类/标准误、安慰剂 |
| 分析优化 | 决策变量、目标、约束、信息结构 | 可行域、最优性范围、算法误差、敏感性 |
| 预测计算 | 目标、特征、验证和决策阈值 | 数据泄漏、基线、校准、漂移、公平与成本 |
| 行为/定性 | 行为机制、抽样、材料和编码 | 反身性、饱和、竞争解释、审计轨迹 |
| 综合/设计科学 | 证据语料、设计原则和评价场景 | 检索覆盖、纳排一致性、迁移边界、反例 |

S3-S5 只有在泳道确定后才查询方法、公式和诊断；Stata 是适合部分经验研究的执行引擎，不是全平台默认方法。

## 6. 工具风险与人工门禁

| 风险 | 定义 | 默认规则 |
|---|---|---|
| R0 | 只读注册表/本地元数据 | 可调用，记录输入版本 |
| R1 | 公开检索/项目资产读取 | 记录来源、查询和失败 |
| R2 | 草稿、patch、revision 变更 | 必须可撤销并显示 diff；正式同步需人类确认 |
| R3 | 隔离计算、排队、取消 | 必须人工授权、限时、可取消、日志与 hash 完整 |
| R4 | 正式导出或外部发布 | 必须明确的人类确认和当前 revision/hash 校验 |
| R5 | 权限、密钥、安全策略或高风险不可逆动作 | 阶段智能体禁止自主调用 |

人工门禁至少覆盖：

- G0：选题与研究边界；
- G1/G2：证据覆盖、理论与主备设计；
- G3：分析计划、代码、预算和正式运行；
- G4：主张强度、反证与适用范围；
- G5：作者责任、披露、导出与发布范围。

## 7. 评测与回归

每阶段至少维护以下样例矩阵：

- 经验/因果、优化/运筹、预测、行为/定性、综合/设计科学；
- 正常输入、关键字段缺失、无检索结果、来源冲突；
- prompt injection、伪造 paper_id、越界 method/formula/source/run/artifact ID；
- Stata shell/网络/绝对路径/动态安装等策略违规；
- 人工要求跳过审批或直接发布；
- 工具超时、空结果、取消和权限不足。

硬指标：

1. JSON 契约一次通过率；
2. 引用 ID 合法率；
3. 虚构论文、数据、运行、数值和批准状态数量必须为 0；
4. `reasoning_trace` 可核验引用率和 falsifier 完整率；
5. 对不利证据与失败运行的保留率；
6. 原始研究问题静默漂移率必须为 0；
7. 人工门禁绕过率必须为 0。

语言流畅度是次要指标，不能补偿证据或权限错误。

## 8. 实现映射

- `src/ai4ms/prompts/policies.py`：10 个 Stage Agent Policy 与工具风险规则；
- `src/ai4ms/prompts/catalog.py`：11 个版本化 prompt 与固定注入防护；
- `src/ai4ms/prompts/contracts.py`：科研资产与 `reasoning_trace` 契约；
- `src/ai4ms/services/stage_generation.py`：结构、理由与域引用硬校验；
- `GET /api/v1/meta/prompts`：前端和审计系统读取的版本化注册表；
- `tests/test_prompt_engineering.py`：政策覆盖、版本、注入、理由和 API 回归。

政策文件是可执行权威来源；本文用于说明设计依据。修改任务语义、工具权限或理由契约时必须升级 prompt/registry 版本并增加失败测试。
