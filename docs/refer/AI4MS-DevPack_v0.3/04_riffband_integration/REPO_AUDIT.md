# Riff-Band `dev` 分支技术审计

审计对象：[franknobox/Riff-Band `dev`](https://github.com/franknobox/Riff-Band/tree/dev)  
快照读取日期：2026-07-12  
声明：本审计基于当日下载的 `dev` 分支快照；未取得 Git commit SHA，因此落地开发前应在仓库内补记 commit。

## 1. 已有能力

| 能力 | 代码位置 | 状态 | AI4MS 用法 |
|---|---|---|---|
| 动态多 Agent `(I,C,T,M)` | `src/agents/`, `src/orchestration_tools/` | 可复用 | 作为任务执行单元与并行抽取器 |
| single/multi/auto 模式 | `src/modes/router.py` | 可复用 | 依据任务复杂度/预算路由 |
| 固定 academic/visual 流水线 | `src/research/pipeline.py`, `steps.py` | 核心可复用、步骤需重构 | 升级为 Protocol 驱动的管科流程 |
| Artifact 管理 | `src/research/artifacts.py` | 可复用 | 扩展 schema、版本、hash、lineage |
| 规则型质量门禁 | `src/research/gates.py` | 框架可复用 | 扩展设计专属与语义/人工门禁 |
| 学术搜索 | `literature_tools.py` | 可复用连接器 | OpenAlex/S2/arXiv/Crossref/DBLP |
| 批量检索、筛选、论文卡 | `research_phase_tools.py` | 可复用骨架 | 改多源合并、通用抽取、全文定位 |
| BibTeX/PDF/引用审计 | `literature_tools.py` | 可复用 | 作为确定性引用链 |
| findings/claims/debate/outline | `research_phase_tools.py` | 部分可复用 | 改为 Claim–Evidence–Assumption 对象 |
| CLI + Rich TUI | `src/ui/` | 可保留 | 高级用户入口 |
| MCP research tool | `src/mcp_server.py` | 可保留并扩展 | 外部 Agent/IDE 集成 |
| 测试文件 | `tests/` | 基础存在 | 建立 CI 与新增领域 benchmark |

当前包版本 `0.2.0`，Python `>=3.10`；主要依赖有 `aiohttp`、`openai`、`google-genai`、`pydantic`、`pypdf`、`PyYAML`、`rich`。

## 2. 最重要的发现

### 2.1 “通用研究模式”仍带通信领域硬编码

`src/project/tools/literature_tools.py` 的 query expansion 和相关性逻辑含 RIS/ISAC、智能反射面、波束赋形等硬编码。`research_phase_tools.py` 的 `_paper_relevance_score` 和 `_cluster_name_for_card` 也将 beamforming、channel estimation、RIS architecture 等作为默认主题簇。

这会导致管理科学课题被错误打分或聚类，是第一优先级缺陷。必须把领域词表、方法抽取和聚类策略移到可配置 domain profile，默认实现不得含具体研究主题。

### 2.2 批量检索是 first-success，不是真正多源融合

`BatchLiteratureSearchTool._search_one_query` 依次调用后端，一旦某后端返回记录就结束该 query。这样能容错，但无法获得多数据库召回、跨源核验和每库命中统计。

AI4MS 应把检索拆成 `search all → normalize → merge/dedupe → screen`，并保存每个后端的原始快照和错误。

### 2.3 论文卡主要是摘要句子启发式抽取

`_paper_note_from_record` 通过查找 “propose/method/algorithm...” 等词选择方法句，找不到时写入通用缺失说明。它适合原型，不足以可靠抽取管科的数据源、变量、识别策略、公式和稳健性。

需要：领域无关 schema、GROBID/页码定位、字段级置信、人工审核队列、全文/摘要/元数据证据等级。

### 2.4 门禁偏“文件存在与数量”，缺少研究有效性

`ResearchGatekeeper` 检查章节、论文数、findings 数、URL、LaTeX/BibTeX 存在等。这些是必要但不充分条件。它不会判断：

- DiD 是否检查平行趋势；
- IV 是否有弱工具与排除限制论证；
- ML 是否泄漏、是否冻结测试集；
- MIP 是否可行、gap 是否可接受；
- claim 是否超过证据强度；
- 数据许可是否允许当前执行方式。

应保留 Gate 接口，但让门禁由 `protocol.lane + method_id` 动态装配。

### 2.5 Artifact 很有价值，但缺版本与血缘合同

现有 JSONL/Markdown/manifest 便于原型迭代，是最值得保留的资产。产品化需要：

- schema version；
- artifact ID、SHA-256、media type、size；
- input/output lineage；
- protocol version、run ID、code/environment；
- 不可变版本与权限。

### 2.6 暂无平台层

当前正式形态是 CLI + 单个 MCP research tool，且产品文档明确“不做 GUI”。用户现在要做平台，因此需要新增 Web、API、持久化、组织/项目权限、异步任务与协作。这是产品方向变化，不应硬塞进 TUI。

## 3. 代码质量与验证基线

- `python -m compileall -q src`：通过。
- `python -m pytest -q`：未执行，当前运行环境缺少 `pytest`。
- `pyproject.toml` 没有开发/测试依赖组，尽管仓库包含 pytest 测试。
- 建议第一批 PR 增加 `[project.optional-dependencies].dev`、锁文件和 CI，再以测试保护领域去硬编码。

## 4. 可复用/重构/新增判定

| 组件 | 判定 | 原因 |
|---|---|---|
| BaseAgent/Runner/Session/Trace | 直接复用 | 已形成轻量 Agent runtime |
| delegate/worker isolation | 直接复用并压测 | 适合并行检索与论文抽取 |
| ResearchPipeline | 重构 | 固定顺序值得保留，步骤和状态需 Protocol 化 |
| ResearchRequest | 替换/兼容 | 只有 topic/mode/depth，不足以表达研究设计 |
| Artifacts | 扩展 | 文件结构好，缺 ID/版本/血缘/对象存储 |
| Gates | 重构 | 接口好，规则过浅 |
| Literature connectors | 复用 adapter | 需要多源融合、速率和快照 |
| Relevance/cluster heuristics | 删除默认硬编码 | 通信领域残留会污染全部课题 |
| Paper cards | 重写 schema，保留工具接口 | 抽取过浅且无 locator |
| Claim debate | 降级为 reviewer 辅助 | Agent 辩论不能替代证据 |
| CLI/MCP | 保留 | 作为高级入口和集成面 |
| Web/API/Auth/DB/Queue | 新增 | 平台化必需 |
| Compute sandbox | 新增 | 现有系统不执行完整科研分析 |
| Data governance | 新增 | 许可、PII、IRB、外部模型边界缺失 |

## 5. 推荐的第一批修改

1. 建立 `feature/management-science-protocol` 分支并冻结基线。
2. 增加 dev 依赖、CI、ruff/mypy（可渐进）和 benchmark fixtures。
3. 新增 `src/domains/base.py` 与 `src/domains/management_science/`。
4. 删除/迁移 RIS/ISAC 硬编码；添加三个管科测试课题确保无领域串扰。
5. 将 `ResearchRequest` 包装为向后兼容的 `ResearchProtocol`。
6. 将论文卡升级为 schema v2，增加 `evidence_level` 与 `locators`。
7. 将 BatchLiteratureSearch 改为 multi-source union + provenance。
8. 将 `Gatekeeper` 改为 registry：common gates + lane/method gates。
9. 暂不做 Web；先让 CLI/MCP 跑通新的端到端协议。
10. 通过 benchmark 后再接 FastAPI/前端，避免 UI 固化错误模型。

