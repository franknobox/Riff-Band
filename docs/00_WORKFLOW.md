# AI4MS 协作与提交规范

## 1. 分支职责

- `ai4ms`：AI4MS 产品改造集成分支；
- `dev`：RiffBand 现有能力的对照基线；
- `feat/*`：独立功能开发；
- `fix/*`：缺陷修复；
- `docs/*`：文档和 Schema 整理；
- `experiment/*`：不保证进入产品的验证代码。

不要直接把未完成的大型重构长期堆在 `ai4ms`。从 `ai4ms` 创建短生命周期分支，通过小型 PR 回收。

## 2. 六天并行开发

当前目标是完整十阶段工作台，不能按长期基础设施路线串行开发。两条工作流从同一 Schema 和示例出发并行推进：

| 工作流 | 分支前缀 | 主要内容 |
|---|---|---|
| Core Workbench | `feat/core-workbench-*` | FastAPI、SQLite、ProjectState、stage transition、检索、审批、Runner、导出与测试 |
| Product Workbench | `feat/product-workbench-*` | S0-S9 十阶段 Web 界面、MS Profile、Prompt、方法数据内容、HTML 报告、fixtures 与演示 |

建议 PR 边界：

1. 公共 Schema、API 示例和十阶段状态机；
2. Web shell、项目创建和通用 stage workspace；
3. S0-S1 的问题识别、检索和综述；
4. S2-S4 的理论、设计、方法、数据和合规；
5. S5-S7 的识别、代码、Runner、结果和稳健性；
6. S8-S9 的机制、异质性、证据、写作、HTML 和研究包；
7. Docker、健康检查、API 示例、端到端测试、演示数据和发布。

两人每天至少两次合流。公共 Schema 变更先合入 `ai4ms`，前后端不得通过复制字段或临时 JSON 绕过契约。

## 3. 目录边界

目标结构遵守以下职责：

- `src/base`、`src/core`、`src/agents`：通用 Agent Runtime；
- `src/orchestration_tools`：委派、权限、任务和并发；
- `src/ai4ms`：比赛产品后端的统一 Python 命名空间；
- `src/ai4ms/domains`：DomainProfile 与学科规则；
- `src/protocols`：ResearchProtocol 和 legacy adapter；
- `src/artifacts_v2`：manifest、hash 和 lineage；
- `src/research`：阶段流水线与兼容入口；
- `src/ai4ms/api`：FastAPI 路由、请求响应模型和静态工作台入口；
- `src/ai4ms/services`：十阶段用例、检索、审批、Runner 和导出服务；
- `src/ai4ms/db`：SQLite repository 与迁移；
- `src/ai4ms/inference`、`knowledge`、`literature`、`prompts`：模型网关、知识库、文献能力和阶段提示词；
- `src/web`：Next.js 十阶段工作台，不承载科研事实计算；
- `docs/refer/AI4MS-DevPack_v0.3`：只作为调研和规格参考，不由运行时写入。

新增产品后端代码应先归入 `src/ai4ms` 的现有边界；通用 Runtime 与兼容研究引擎仍留在原目录。只有职责已经稳定时才创建新顶层包。

## 4. 提交规范

一个 commit 只完成一种可解释的变化。标题使用英文：

```text
type: short summary
```

常用类型：

- `feat`：新能力；
- `fix`：缺陷修复；
- `refactor`：不改变外部行为的结构调整；
- `docs`：文档或契约更新；
- `test`：测试与 fixture；
- `chore`：依赖、CI 和维护。

示例：

```text
refactor: add management science domain profile
feat: union literature results across providers
feat: add immutable research asset revisions
test: add cross-domain protocol fixtures
docs: establish AI4MS documentation baseline
```

## 5. PR 描述

PR 至少说明：

- 背景和目标；
- 修改的对象、接口和行为；
- 对旧 CLI/MCP 的兼容影响；
- 对 Gate、审批和数据治理的影响；
- 执行的测试与验收 ID；
- 已知限制和回滚方式。

Schema 变更必须同时列出迁移策略和旧数据读取方式。

## 6. 评审重点

- 是否把某个课题关键词重新写进通用层；
- LLM 是否被用于本应确定性执行的权限、hash、统计或状态判断；
- Agent 是否可能绕过人工审批或修改不可变产物；
- 上游 revision 变化是否正确影响下游 Gate；
- 检索结果是否保存来源、查询、日期、错误和快照；
- 摘要证据是否被错误提升为全文结论；
- HTML 报告是否与底层结构对象和证据一致；
- Licensed/Sensitive/Restricted 数据是否进入不允许的模型或日志；
- 新功能是否有失败、取消、重试和审计路径。
- 十阶段是否共享同一 ProjectState，而不是形成互不连通的页面；
- 页面上的批准动作是否真的改变服务端状态并约束后续步骤；

## 7. 仓库卫生

提交前检查：

```powershell
git status --short
git diff --check
pytest -q -p no:cacheprovider
```

禁止提交：

- `.env`、API key、许可证序列号和授权码；
- 含密钥、许可证或用户数据的 Docker layer、镜像导出和 Compose 配置；
- `workspace/`、运行日志、缓存和临时输出；
- 受限论文全文和无权再分发的数据；
- Stata 安装包、许可证和未经批准的第三方 ado；
- 从本机生成的绝对路径和用户标识。

## 8. 文档同步

以下变化不能只改代码：

- 产品范围变化：更新 `00_PRODUCT.md`；
- 十阶段范围、分工和 DDL 变化：更新 `00_ROADMAP.md`；
- API/Schema/SQL 变化：同步 DevPack 契约或其正式迁移版本；
- 命令与配置变化：更新根 README 和 `00_GUIDELINE.md`；
- 新风险或许可边界：更新风险登记和治理文档。

仓库中只保留一套当前产品定位。历史方案通过 Git 追溯，不再以平行文档长期保留。
