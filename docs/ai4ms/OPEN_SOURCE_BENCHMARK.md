# GitHub 开源项目能力对照

调研日期：2026-07-21

## 1. 调研目的与口径

本轮不是按 Star 数机械拼装项目，也不复制第三方界面。选择标准是：项目是否提供可验证的科研工作流、文献证据链、因果方法、统计/优化建模或长程智能体能力；是否能转化为 AI4MS 的稳定产品对象和调用规则。

调研覆盖管理科学常见的实证研究、运营研究、系统综述、科学写作和 AI 科研编排。采用的是“接口与工作流模式”，不直接复制未核验结论、数据或受许可证限制的代码。

## 2. 核心项目与吸收能力

| 项目 | 相关能力 | 对 AI4MS 的启发 | 本轮落地 |
|---|---|---|---|
| [SakanaAI/AI-Scientist](https://github.com/SakanaAI/AI-Scientist) | 想法、实验、论文、评审的循环；文献检索；危险代码警告 | 科研产物必须有阶段循环、审查和隔离运行，不能把自动化等同于可信 | S0–S9 阶段资产、人工门禁、Stata/Python Runner 隔离规则 |
| [Future-House/paper-qa](https://github.com/Future-House/paper-qa) | PDF 全文索引、证据检索、带引用回答、撤稿与元数据检查 | 文献回答应以证据片段和来源为基础，并保留检索/引用质量 | 证据库、论文卡、来源等级、主张—证据连接 |
| [stanford-oval/storm](https://github.com/stanford-oval/storm) | 检索后先形成大纲，再生成带引用长文；多视角提问；人机协作知识整理 | 长文交付需要“研究—结构—正文”分离，允许用户持续注入判断 | S1 检索协议、S9 结构化写作、对话同步正文 |
| [asreview/asreview](https://github.com/asreview/asreview) | 主动学习辅助系统综述筛选；透明、交互式纳入排除 | 文献筛选必须记录人工标签与理由，AI 只能排序和建议 | 纳入/排除决定、待全文状态、筛选审计的后端要求 |
| [py-why/dowhy](https://github.com/py-why/dowhy) | `model → identify → estimate → refute` 因果工作流；图模型和反驳 API | 方法库应围绕 estimand、识别、估计和反驳组织，而不是只列回归命令 | 方法卡的估计目标、假设、诊断、失败规则 |
| [py-why/EconML](https://github.com/py-why/EconML) | 双重机器学习、异质处理效应、因果森林 | 高维与 CATE 方法需要交叉拟合、重叠、校准和样本外验证 | DML/因果森林方法卡与公式卡 |
| [uber/causalml](https://github.com/uber/causalml) | uplift、CATE、树模型与策略评估 | 异质性发现不能自动变成政策分群，必须保留探索性标签 | S8 异质性审计与诊断规则 |
| [statsmodels/statsmodels](https://github.com/statsmodels/statsmodels) | 回归、GEE、离散模型、GMM、时间序列和统计诊断 | 方法注册表需要统一模型规格、结果和诊断接口 | 统计与面板方法家族、跨引擎实现字段 |
| [bashtage/linearmodels](https://github.com/bashtage/linearmodels) | PanelOLS、IV、系统回归、公式接口 | 公式可作为方法与代码之间的稳定中间表达 | 面板 FE、2SLS 公式、Python/Stata 双实现 |
| [Pyomo/pyomo](https://github.com/Pyomo/pyomo) | 集合、参数、变量、目标、约束、求解器的符号优化建模 | 管理科学不能只做计量；方法库应容纳优化模型和求解资产 | LP/MILP、鲁棒优化、随机规划、DEA 方法卡 |
| [google/or-tools](https://github.com/google/or-tools) | CP-SAT、LP/MIP、路由、调度、网络流 | 运营研究需要问题类型、求解器能力、可行性和 gap 诊断 | 网络流/路由/调度方法卡与求解器任务要求 |
| [coin-or/pulp](https://github.com/coin-or/pulp) | 轻量 LP/MILP 建模及多求解器适配 | 通用模型对象和具体 Solver 应解耦 | 后端 Solver Adapter 与模型 manifest 设计 |
| [J535D165/pyalex](https://github.com/J535D165/pyalex) | OpenAlex 检索、过滤、相似论文和开放全文接口 | 文献连接器需要规范化查询、游标、速率限制和来源快照 | S0/S1 OpenAlex Connector 与查询快照要求 |
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | 长程有状态工作流、持久执行、人工中断和恢复 | 每个阶段智能体应是可暂停、可恢复、可人工修改状态的执行图 | Agent Run/Checkpoint/Interrupt 与审批状态模型 |

## 3. 统一研究范式

这些项目虽然服务不同任务，但可以收敛为一个适合管理科学的通用闭环：

1. 定义问题与决策边界：明确研究对象、贡献主张、不可回答范围和停止条件。
2. 检索与筛选证据：保存查询、来源、去重、纳入/排除、全文状态和证据片段。
3. 构建理论与可证伪命题：显式记录机制、竞争解释和因果图。
4. 定义 estimand 或决策目标：先确定要估计/优化什么，再选择方法。
5. 建立方法与公式：连接数据形态、符号、假设、诊断、实现和失败规则。
6. 冻结数据与分析计划：变量字典、许可、样本、代码任务和资源限制形成 revision。
7. 受控执行：只运行已审批的代码/模型，保存输入签名、环境、日志、输出和 hash。
8. 反驳与稳健性：保留失败、负结果、安慰剂、敏感性和替代解释。
9. 主张—证据审阅：每条主张连接文献、运行产物、反证和适用边界。
10. 人机协作交付：智能体生成候选正文，用户修改、同步、审批并导出可复现研究包。

## 4. 不直接采用的做法

- 不采用“智能体自动批准自己的实验或论文”的全自动闭环。
- 不把 GitHub 项目中的示例结果当作管理科学证据。
- 不让方法推荐分数替代识别假设、可行性或专家审核。
- 不自动执行模型生成的 shell、网络访问、动态包安装或未知 Stata ado。
- 不把摘要级文献、搜索片段或未核验引用写成核心结论。
- 不在没有合法 Stata 许可和受控数据环境时宣称已完成正式分析。

## 5. 对后端的直接要求

- 建立 `MethodDefinition`、`FormulaDefinition`、`DiagnosticRule` 三个版本化注册表。
- 文献检索保存 `SearchRun`、`QueryVariant`、`SourceRecord`、`ScreeningDecision` 和 locator。
- 智能体执行保存 `AgentRun`、`ToolCall`、`Checkpoint`、`HumanInterrupt` 和 `SyncOperation`。
- 优化求解与统计运行统一使用 `ExecutionRun`，但各自保留 Solver/Stata/Python 专属 manifest。
- 每个 Agent 工具必须声明读写范围、审批前置、网络权限、最大成本、超时和可重试错误。
