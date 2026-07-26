# Riff-Band → AI4MS 迁移映射

## 1. 目标目录建议

```text
src/
  runtime/                 # 从 core/agents/orchestration_tools 收敛
  protocols/               # ResearchProtocol、版本、审批、状态
  pipelines/               # 通用 stage engine + management-science pipeline
  domains/
    base.py
    management_science/
      profile.yaml
      extraction_schema.py
      design_router.py
      gates/
      skills/
  connectors/
    literature/
    data/
    models/
  knowledge/
    methods.py
    formulas.py
    data_sources.py
    claims.py
  artifacts/
    registry.py
    manifests.py
    storage.py
  compute/
    sandbox.py
    runners/
  services/
    api/
    tasks/
  ui/                      # 现有 CLI；Web 独立 apps/web
apps/
  web/
tests/
  unit/
  integration/
  benchmarks/management_science/
```

不必在第一天大规模移动文件。先用新包封装旧模块，测试稳定后分 PR 迁移。

## 2. 文件级映射

| 现有 | 目标 | 变化 |
|---|---|---|
| `research/schema.py::ResearchRequest` | `protocols/models.py::ResearchProtocol` | 增 question/design/data/analysis/gates，保留 legacy adapter |
| `research/steps.py` | `pipelines/management_science.py` | 统一阶段 + 五泳道分支，不再只面向综述 |
| `research/pipeline.py` | `pipelines/engine.py` | 状态/依赖/幂等/暂停/人工门 |
| `research/artifacts.py` | `artifacts/registry.py` | ID、schema、hash、lineage、对象存储 |
| `research/gates.py` | `domains/.../gates/registry.py` | common + lane + method 动态门禁 |
| `literature_tools.py` | `connectors/literature/*.py` | 每后端独立 adapter 与统一 record |
| `BatchLiteratureSearchTool` | `services/literature/search_pipeline.py` | 所有后端并发、快照、合并、去重、筛选 |
| `_paper_note/card_from_record` | `domains/.../extraction_schema.py` | 全文 locator、字段置信、人工验证 |
| `_paper_relevance_score` | `domains/.../screening.py` | 配置化、可训练、无主题硬编码 |
| `_cluster_name_for_card` | `knowledge/synthesis.py` | embedding + taxonomy +人工可改标签 |
| `finding_tools.py` | `knowledge/claims.py` | Claim/Evidence/Assumption 正规对象 |
| `citation_audit` | `gates/citation.py` | 加 DOI、entailment、数值与表图一致性 |
| `mcp_server.py` | `services/mcp.py` | research + project/protocol/search/run/evidence tools |
| `ui/shell.py` | 保留 | 调用 service API，而非直接写工作区 |

## 3. 兼容策略

- 保留 `/research topic --mode=academic`，内部转换为 `goal=synthesize` 的 legacy protocol。
- 旧 JSONL 文件可读；写出新 schema v2，并提供一次性 migrator。
- 旧 `research` MCP tool 不删除，新增 `protocol_version` 和 `project_id` 可选字段。
- 输出目录保留 `paper.tex/references.bib`，但 manifest 记录新 artifact IDs。

## 4. PR 序列（按顺序）

| PR | 内容 | 退出条件 |
|---|---|---|
| 1 | dev 依赖、CI、锁文件、基线测试 | 当前测试在 CI 通过 |
| 2 | domain profile 接口 + 去 RIS/ISAC 硬编码 | 3 个管科 fixtures 无串扰 |
| 3 | ResearchProtocol schema + legacy adapter | 旧 CLI/MCP 测试通过 |
| 4 | multi-source literature union + provenance | 后端故障仍有结果；跨源去重测试通过 |
| 5 | PaperCard v2 + locator/confidence | 金标字段 F1 达到初始阈值 |
| 6 | Artifact manifest/hash/lineage | 重跑可验证输入输出 hash |
| 7 | Gate registry + 五泳道 gates | 每泳道至少 3 个故障 fixture 被拦截 |
| 8 | Method/Data/Formula registry | CLI/MCP 可查询、版本化 |
| 9 | Compute sandbox POC | 无网络/资源限制/manifest 测试通过 |
| 10 | FastAPI Project/Protocol/Search API | OpenAPI 合同测试通过 |

## 5. 不建议做的迁移

- 不先把全部代码重命名/移动；这会制造无功能价值的大 diff。
- 不把每种方法做成独立“人格 Agent”；用 method card + gate registry 更稳定。
- 不先建 Neo4j；先验证 Evidence Graph 的真实查询和协作价值。
- 不让 Web 前端直接依赖工作区文件路径；只依赖 API/Artifact ID。
- 不以 LLM judge 作为唯一质量门；确定性检查和人工批准优先。

