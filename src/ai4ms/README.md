# AI4MS 后端包

本目录是比赛产品的 Python 命名空间。

| 目录 | 职责 |
|---|---|
| `api/` | FastAPI 路由与服务装配 |
| `services/` | 项目、阶段、审批和生成用例 |
| `db/` | SQLite、revision 和审批持久化 |
| `orchestration/` | AOrchestra 阶段编排 |
| `inference/` | 模型网关与结构化输出 |
| `literature/` | 文献检索和快照 |
| `knowledge/` | 方法、公式和数据源注册表 |
| `prompts/` | S0-S9 提示词和输出契约 |
| `assets/` | 数据资产登记和元信息 |
| `runners/` | Stata Runner、后台任务和 Result Bundle |
| `delivery/` | HTML 报告和研究包 |

边界规则：

- HTTP 逻辑留在 `api/`，业务状态变化进入 `services/`；
- `db/` 不调用 API、模型或前端；
- 前端只通过 `/api/v1` 使用产品能力；
- 复用旧 Runtime 时显式导入，不复制实现。

完整架构见 [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md)。
