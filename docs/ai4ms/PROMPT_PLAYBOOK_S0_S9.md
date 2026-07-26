# AI4MS S0-S9 阶段智能体 Prompt Playbook

版本：2.0.0
对象：产品、科研、提示词、后端、前端与测试人员

## 1. 如何阅读

这是实施手册，不是另一套权威提示词。运行时以以下代码为准：

- `src/ai4ms/prompts/policies.py`：Agent 与工具规则；
- `src/ai4ms/prompts/catalog.py`：阶段任务和 prompt version；
- `src/ai4ms/prompts/contracts.py`：结构化输出；
- `src/ai4ms/services/stage_generation.py`：确定性校验。

S0-S9 是 10 个阶段和 9 次交接。每个阶段都由“阶段智能体 + 研究者”共同完成：智能体检索、比较、起草和检查；研究者修改、接受取舍、批准运行与承担发布责任。

## 2. 通用运行协议

### 2.1 输入顺序

每次调用只注入：

1. 当前项目和阶段 ID；
2. 当前阶段草稿；
3. 回答本阶段所必需的上游 approved revision/hash；
4. 经过压缩的论文、数据、运行或证据记录；
5. 权威方法/公式/数据源/诊断 shortlist；
6. 本轮研究者指令。

不注入其他项目聊天、无关附件、密钥、原始敏感记录或无限历史。

### 2.2 固定输出

模型必须只输出一个 JSON 对象，由本阶段科研资产字段和以下审计理由组成：

```json
{
  "reasoning_trace": {
    "problem_framing": "当前阶段要判断的问题",
    "logic_chain": [
      {
        "step_id": "L01",
        "question": "可审查子问题",
        "evidence_refs": ["paper_123", "M06", "run_abc"],
        "inference_type": "synthesis",
        "conclusion": "受证据边界约束的结论",
        "confidence": "medium",
        "falsifier": "会推翻该步的观察"
      }
    ],
    "assumptions": [],
    "alternatives": [],
    "uncertainties": [],
    "human_decisions": ["必须由研究者决定的事项"],
    "next_verifications": ["下一步核验"]
  }
}
```

这是审计型研究理由，不是模型私密思维链。

### 2.3 工具调用状态机

1. 说明当前缺口和为何需要工具；
2. 检查工具是否属于本阶段、风险等级和前置条件；
3. R3/R4/R5 或政策指定动作等待人工确认；
4. 使用最小参数调用一次；
5. 保存输入版本、查询/动作、时间、结果或错误；
6. 校验返回 ID、provenance、hash 和作用域；
7. 只把真实返回写入草稿；
8. 失败时执行登记的 failure action，不用语言补造结果。

### 2.4 修复与保存

- 第一次结构、理由或引用校验失败：允许一次受约束修复；
- 第二次失败：返回 `invalid_model_output`，不保存；
- 合格结果：作为 AI draft 保存，保留 prompt/model/time/usage；
- 智能体对话同步：研究者选择章节和追加/替换，预览 diff 后写 revision/patch API；
- 人工审批：只能由审批 API 和人工 actor 完成。

## 3. 阶段卡

| 阶段 | 主智能体 | 核心交付 | 主要工具 | 人工决定 | 关键停止条件 |
|---|---|---|---|---|---|
| S0 | 选题侦察 | 问题、边界、目标、概念、候选空白、反向检索 | 项目资产读取、文献侦察、revision patch | 题目、边界、G0 | 概念不可检索；单位/目标矛盾 |
| S1 | 文献证据 | 检索计划、论文记录、流派、争议、空白候选、覆盖限制 | OpenAlex、Crossref、Semantic Scholar、arXiv、去重筛选 | 核心论文、纳排、G1 | 来源失败；证据不足；全文不可得 |
| S2 | 理论建模 | 理论视角、构念、机制、竞争解释、可证伪命题 | 证据图、方法只读查询、revision patch | 理论视角、构念、贡献边界 | 无证据连接；层级冲突；不可证伪 |
| S3 | 研究设计 | 泳道、estimand/目标、主备方法、假设、证伪和停止规则 | 方法库、公式库、设计完整性检查 | 主方法、效度风险、G2 | 无可行方法；假设不可接受；资源不可得 |
| S4 | 数据契约 | 数据源、变量、样本、连接、质量、许可、隐私和伦理 | 数据源库、资产 profile、治理检查 | 权限、口径、伦理 | 无合法访问；伦理未决；关键变量不可操作化 |
| S5 | 分析计划 | 主次规格、公式、诊断、步骤、稳健性、Stata/其他代码 | 公式库、36 条诊断、Stata policy scan | 冻结计划、G3 | 变量映射缺失；扫描不通过；上游冲突 |
| S6 | 分析执行 | 预检、排队、取消、日志、结果与产物 hash 审阅 | runner preflight/submit/status/cancel | 运行、取消、重跑 | hash 不匹配；超时；契约/产物不可验证 |
| S7 | 稳健性 | 稳健性矩阵、失败项、限制和新增运行请求 | 诊断库、结果读取、rerun request | 接受降级、批准重跑 | 缺少结构化结果；不利结果未传递 |
| S8 | 证据裁决 | Claim-Evidence-Assumption、机制、异质性、反证和范围 | artifact verify、证据图 patch、结果读取 | 主张状态、G4 | 无真实证据；强度越界；遗漏反证 |
| S9 | 写作交付 | 可编辑正文、引用、披露、HTML/manifest/研究包 | revision patch、引用校验、export/publish | 作者责任、G5、发布范围 | 未批准主张；引用失败；hash/权限失败 |

## 4. 每阶段审查问题

### S0 问题识别

- 这是管理现象、决策问题还是科学问题？
- 分析单位、决策单位和数据单位是否一致？
- “空白”是否仍是待反向检索的 candidate？
- 是否并列考虑解释、因果、预测、优化、综合和理论构建？

### S1 相关研究

- 查询是否覆盖核心、相邻、经典、近期、反向和争议？
- 每篇论文的 paper_id、DOI/URL、来源和检索时间是否可追踪？
- 是否区分元数据、摘要和全文证据？
- 不利/无效研究是否获得对称检索机会？

### S2 理论

- 每个理论陈述来自哪篇论文，哪些只是本项目推断？
- 构念、测量和层级是否清楚？
- 机制链是否包含主体、行动、约束与可观察后果？
- 哪个观察能区分竞争解释？

### S3 设计

- 设计回答的是同一个研究问题吗？
- 主备方法的关键假设、失败动作和数据要求是什么？
- 是否因工具可用或模型复杂而偏选？
- 经验、优化、预测、定性和综合泳道是否使用各自标准？

### S4 数据

- 每个变量如何从构念映射到原始字段和派生规则？
- 时间顺序、样本选择、连接键和测量误差如何处理？
- access/license/ethics 状态是否有真实依据？
- 敏感数据是否遵循最小化、隔离和用途限制？

### S5 分析计划

- estimand/目标与 S3 是否一致？
- method_id、formula_id、诊断和变量是否真实存在且互相兼容？
- 每个诊断的 pass condition 和 failure action 是否明确？
- Stata do-file 是否只读输入、只写输出、无 shell/网络/安装/路径穿越？

### S6 执行

- approved revision/hash、代码 hash 和输入 hash 是否完全匹配？
- 预检通过是否有日志证据？
- 超时、取消、退出码和产物 hash 是否保存？
- “运行成功”是否被错误等同于“科学主张成立”？

### S7 稳健性

- 检查是预先计划还是结果后追加？
- passed/failed 是否有结构化 run 结果？
- 不利检查是否进入解释限制与 S8 置信度？
- 新运行是否等待人工批准？

### S8 主张与证据

- 主张类型是否超过研究设计能力？
- 每个 evidence_id 是否连接真实 artifact_id 和 locator？
- 支持、反证、限定、假设和作用域是否共同保留？
- blocked/failed Run 是否仅作 reviewer note，而未支持结论？

### S9 正文与交付

- 每个核心结论是否连接 approved claim/evidence？
- 正文是否新增了未批准数值、论文或因果强度？
- 管理/政策含义是否写明适用对象、条件和风险？
- 当前 revision、导出 hash、披露和发布目标是否一致？

## 5. Prompt 版本规则

- 修正错字、格式和不改变行为的措辞：patch；
- 改变阶段任务、工具规则、证据要求或字段语义：minor；
- 改变阶段体系、审批边界或不向后兼容的输出：major；
- 每次升级同时更新：
  - `PromptCatalog`；
  - `PROMPT_POLICY_REGISTRY_VERSION`；
  - 成功、失败、注入和 ID 越界测试；
  - 本手册与 `docs/PROMPT_ENGINEERING.md`；
  - API manifest 与前端版本展示。

## 6. 开发验收

一个阶段只有在以下条件全部满足时才算实现：

1. 有 Agent Policy、任务 prompt 和 Pydantic contract；
2. 有真实上下文最小化和上游 revision/hash 绑定；
3. 所有工具有风险、调用条件、前置条件、禁止项和失败动作；
4. 有服务端结构、理由、ID 和领域规则校验；
5. 有人工编辑、patch/revision 和批准入口；
6. 有至少五种管理科学泳道的固定评测；
7. 有注入、幻觉、越权、工具失败和并发 revision 冲突测试；
8. API 能返回当前 prompt/policy version，运行记录能保存该版本。
