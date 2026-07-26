# AI4MS 提示词工程

## 1. 当前范围

产品阶段提示词位于 `src/ai4ms/prompts/`，与 `src/project/prompts.py`、`src/research/prompts.py` 的旧 Agent Runtime 编排提示词分开管理：

- `src/ai4ms/prompts/catalog.py`：S0-S9 阶段任务、提示词 ID 和版本；
- `src/ai4ms/prompts/contracts.py`：模型输出必须通过的 Pydantic 契约；
- `src/ai4ms/prompts/policies.py`：S0-S9 阶段智能体身份、工具、R0-R5 风险、调用条件、人工决策与停止规则；
- `src/ai4ms/inference/`：模型调用、超时、重试、JSON 提取和错误分类；
- `src/ai4ms/services/stage_generation.py`：向提示词注入最小项目上下文，并把合格结果交给 revision 服务。

编号语义以仓库运行时为准：S0-S9 共 10 个阶段智能体，阶段之间形成 9 次交接。产品口语中的“九阶段”指九次交接，不应据此删除 S0 或 S9。

当前真实模型生成覆盖：

| 阶段 | Prompt ID | 输出 | 边界 |
|---|---|---|---|
| S0 问题识别 | `ai4ms.stage.problem@2.0.0` | 研究对象、边界、目标、概念块、问题、候选空白和反向检索 | 空白只能是 candidate；原始想法由服务端强制保留 |
| S1 检索计划 | `ai4ms.stage.literature-plan@2.0.0` | 多源查询块、纳排标准、筛选问题、反向检索和覆盖限制 | 只生成检索计划，不生成论文或结论 |
| S1 证据综述 | `ai4ms.stage.literature-synthesis@2.0.0` | 研究流派、共识/争议、候选空白和后续建议 | 只能引用当前 S1 已保存的 `paper_id` |
| S2 理论构建 | `ai4ms.stage.theory@2.0.0` | 理论视角、构念、机制、竞争解释和可证伪命题 | 论文引用只能使用 S1 的 `paper_id`；证据不足必须降级 |
| S3 研究设计 | `ai4ms.stage.design@2.0.0` | 主备方法、假设、证伪、有效性威胁和停止条件 | 方法只能从运行时方法库候选列表中选择 |
| S4 数据与变量 | `ai4ms.stage.data@2.0.0` | 数据源、变量、样本、连接键、质量、隐私和伦理检查 | 数据源只能从运行时数据源库候选列表中选择；权限默认未知 |
| S5 识别与检验 | `ai4ms.stage.identification@2.0.0` | estimand、变量角色、主次规格、诊断、分析步骤、代码和复现要求 | 方法来自已选设计，公式来自 47 项公式库；Stata 代码经过确定性策略扫描 |
| S6 结果分析 | `ai4ms.stage.analysis@2.0.0` | 运行准备、预检和结果审阅清单 | do-file、S5 revision/hash 由服务端强制绑定；模型不能生成运行结果 |
| S7 稳健性检验 | `ai4ms.stage.robustness@2.0.0` | 稳健性矩阵、失败项、解释限制和后续运行 | 只能引用现有规格和 Run；无结构化结果时不能标记 passed/failed |
| S8 机制与异质性 | `ai4ms.stage.evidence@2.0.0` | Claim-Evidence-Assumption、机制、异质性、反证和限制 | artifact、run、method 和稳健性 ID 必须来自输入；阻塞运行不能支持结论；不利稳健性必须降低置信度 |
| S9 结论与政策含义 | `ai4ms.stage.delivery@2.0.0` | 结论、政策含义、写作大纲、引用选择、披露和复现说明 | 只能使用 G4 已批准且未撤回的主张及其 evidence_id；报告路径和发布状态由服务端生成 |

## 2. 提示词原则

1. **上下文最小化**：只注入项目标题、原始想法、当前阶段内容和必要的上游资产；S1-S4 最多注入 30 篇紧凑论文记录，不注入整段聊天或无关资料。
2. **契约优先**：模型文本不能直接写入 SQLite。输出先提取 JSON，再经过严格 Pydantic 校验；未知字段会被拒绝。
3. **人工决定隔离**：模型契约不包含 `approval`、`approved` 或 `human_verified`，Agent 无法通过提示词写入人工决定。
4. **证据诚实**：没有检索结果时只能生成查询计划和 unknown，不能虚构论文、数据、已有结论或绝对原创判断。
5. **一次修复上限**：首次输出不满足契约时，只允许一次 JSON 修复调用；再次失败返回 `invalid_model_output`，不保存 revision。
6. **可审计**：合格草稿记录模型、prompt ID、prompt version、生成时间、尝试次数和 token 用量，不记录 API key。
7. **多范式兼容**：提示词不得默认所有课题都是因果实证，也不得把 Stata、某个方法或某个示例课题写成全局前提。
8. **审计理由而非私密思维链**：每份模型草稿必须输出 `reasoning_trace`，记录问题框定、证据引用、推断类型、结论、置信度、可推翻条件、人工决策和下一步核验；不请求或保存 token 级内部思维过程。
9. **提示词注入隔离**：项目资料、论文、网页、数据和工具返回均按不可信数据处理，不能覆盖系统规则、阶段政策或人工门禁。
10. **工具最小权限**：每个阶段只暴露登记工具；R3 计算、R4 发布与任何 R5 动作必须由人类确认，工具失败不能被语言模型改写成成功。

## 3. API 使用

模板草稿适用于离线状态和尚未完成提示词的阶段：

```json
{
  "instruction": "补齐仍需研究者确认的字段",
  "generation_mode": "template"
}
```

S0-S9 可以请求真实模型：

```json
{
  "instruction": "保持探索性，不要预设因果关系成立",
  "generation_mode": "model"
}
```

S1 第一次生成得到检索计划；调用文献检索端点保存论文后，再次生成会自动切换为证据综述。S8 没有可用论文、数据或 Run 证据时不会伪造主张；S9 只有在 S8/G4 批准后解锁。模型未配置返回 HTTP 503 `inference_unavailable`；阶段尚未实现返回 HTTP 409 `model_generation_not_supported`；两次结构或引用校验失败返回 HTTP 502 `invalid_model_output`。

服务层会再次校验论文、方法和数据源 ID。提示词中的约束不是唯一防线。

`GET /api/v1/meta/inference` 只返回是否配置和模型名，不返回 key。

`GET /api/v1/meta/prompts` 返回 Prompt Engineering 注册表版本、11 个 prompt（S1 含检索计划和证据综述）、10 个阶段 Agent Policy、工具风险与调用规则。`GET /api/v1/meta/stages` 同时返回每阶段当前 prompt ID/version 和 agent policy，便于前端展示与审计。

## 4. 修改规则

- 改变字段语义或必填项时，先修改契约和测试，再升级 prompt version；
- 只调整措辞但不改变任务语义时升级 patch 版本；
- 改变任务目标、证据规则或输出结构时升级 minor/major 版本；
- 新阶段必须同时提交 prompt、契约、成功测试、失败测试和 API 文档；
- 不把具体演示课题、虚构引用或本地绝对路径写进提示词。

## 5. 上线前评测

每个阶段至少维护三类固定样例：实证/因果、优化/运筹、综述/定性。评测重点不是语言流畅度，而是：

- 契约一次通过率；
- unknown 是否诚实保留；
- 用户原意是否被静默改变；
- 虚构论文、数据、结论和批准字段数量是否为 0；
- 跨学科课题是否出现其他样例的术语串扰；
- 相同输入和 prompt version 的关键字段是否稳定。
