# Sprint 2：Stata、人工审批与阶段智能体（14 天）

目标：跑通“已批准研究设计 → 用户与智能体共同修改分析计划/do-file → G3 人工审批 → Stata batch run → 诊断/结果 → G4 人工审批”的竖切，并让所有关键资产支持 revision、diff 和审批失效。

## Day 1：Revision 对象

- 实现 `research_assets/asset_revisions`；
- 支持 human/agent/import 三类作者；
- 内容 hash、parent revision、变更原因和 semantic scope；
- 原始 Run Artifact 不可编辑。

## Day 2：Approval 对象

- 实现 G0—G5 通用 ApprovalRequest/Decision；
- 单人、四眼和多人会签策略；
- Agent 身份在数据库/API 层永远不能批准。

## Day 3：失效引擎

- 编码选题→设计→数据→分析→Claim→发布依赖；
- 上游语义修改自动追加 invalidation event；
- 旧决定保留，新运行必须绑定有效批准 hash。

## Day 4：Stage Agent Registry

- 注册 S0—S9 主智能体、输入/可编辑/不可变对象、工具和 Gate；
- Orchestrator 在 tool call 前检查 stage/gate/permission；
- 完成 StageSession 状态机。

## Day 5：Stage Workspace API

- 当前阶段、完成条件、待决定问题、patch 和 handoff readiness；
- 创建/比较 revision；
- 提交审批、changes requested、批准/拒绝。

## Day 6：Stata Runner 接口

- `preflight/submit/cancel/events/collect` adapter；
- Local Runner Profile 与心跳；
- 版本、edition、许可模式和席位上限。

## Day 7：Do-file 策略与预检

- 危险命令、网络、路径、Python/Java 和动态 ado 安装规则；
- 变量、唯一键、`xtset/tsset`、命令可用性预检；
- 策略例外必须绑定人工审批。

## Day 8：Batch 执行

- 生成签名 Run Bundle；
- Linux/macOS 与 Windows adapter；
- 无网络、只读输入、独立输出、超时/内存/大小限制；
- 取消、退出码和日志流。

## Day 9：Manifest 与输出

- Stata/OS/locale/adopath/which、数据签名、代码/输入/输出 hash；
- SMCL/text log、XLSX/CSV/DOCX、PNG/SVG/GPH、DTA/STER；
- 表图与 Run/命令/代码 revision 血缘。

## Day 10：首批模板

- 数据审计、OLS、FE 和 DiD；
- 每张模板绑定 MethodCard、必需诊断和失败影响；
- 正确 fixture 与注入错误 fixture。

## Day 11：AI Patch 协作

- Stata Analyst 只能提交 diff/patch；
- 用户接受、修改、拒绝、要求证据；
- 接受前显示 Gate 失效影响。

## Day 12：审批界面

- Stage Workspace 编辑器与版本比较；
- Approval Inbox、检查清单、评论和会签；
- 过期 revision、无权限角色和 Agent 自批拒绝演示。

## Day 13：结果与 Claim

- Robustness Agent 读取不可变 Run Artifact；
- 失败诊断降低/阻塞 Claim；
- 结果解释人工修改，原始数值不可修改；
- G4 通过后才能进入正式写作。

## Day 14：端到端演示与决策

- 用一个面板/DiD 课题从 G1/G2 跑到 G4；
- 刻意修改主结果变量，验证 G2—G5 自动失效；
- 在干净 Runner 重放并比较数值；
- 依据 A31—A40 做 Go/No-Go。

## 验收

- Stata 批处理日志/退出码/产物完整；
- 危险命令、越界路径、无许可席位和无 G3 被拒绝；
- 固定输入/代码/环境重跑结果一致；
- AI patch 与人工编辑均可回滚；
- Agent 不能批准，过期 hash 不能运行；
- 上游变化按矩阵失效下游 Gate；
- 用户能解释每阶段 AI 做了什么、自己改了什么、批准了什么。

