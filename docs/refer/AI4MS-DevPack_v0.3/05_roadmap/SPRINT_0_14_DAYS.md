# 接下来 14 天：可以直接照做的开发清单

目标：不做大平台，先证明 Riff-Band 能稳定承载一个通用管科 Research Protocol。

## Day 1：冻结基线与建立分支

```bash
git fetch origin
git switch dev
git pull --ff-only
git rev-parse HEAD
git switch -c feature/management-science-protocol
```

把 commit SHA 写入 `docs/ai4ms/BASELINE.md`。运行现有启动命令与测试，保存结果。不要把本交付包直接覆盖进仓库；先挑选 Sprint 0 文件。

完成标准：基线 commit、环境、测试失败项、一个示例运行都有记录。

## Day 2：开发依赖与 CI

- 在 `pyproject.toml` 增加 `dev` 依赖：pytest、pytest-asyncio、coverage、ruff；
- 生成锁文件；
- CI 运行 compile、unit tests 和最小 CLI smoke；
- 修复测试文件名 `test_ standard.py` 等可疑命名。

完成标准：干净环境一条命令运行测试。

## Day 3：建立三个 benchmark fixtures

创建：

1. `AI adoption → firm performance`（面板/因果）；
2. `low-carbon vehicle routing`（优化）；
3. `platform information sharing`（解析/供应链）。

每个 fixture 给出期望泳道、必须提到的关键假设、禁止出现的 RIS/ISAC 词和最小产物。

完成标准：当前系统至少暴露出领域硬编码问题，测试先红。

## Day 4：DomainProfile 接口

- 新建 `src/domains/base.py`；
- 定义 `expand_queries/screen/extract_schema/gates_for`；
- 新建 `management_science` profile；
- 旧逻辑通过 legacy profile 适配。

完成标准：现有 pipeline 可注入 profile，不改变外部命令。

## Day 5：去课题硬编码

- 移除 `_research_query_candidates` 中 RIS/ISAC 中文替换；
- 移除 `_paper_relevance_score` 的通信专属加分；
- 移除 `_cluster_name_for_card` 的 beamforming/channel/RIS 主题；
- 课题关键词由 Protocol 传入，学科 taxonomy 由 profile 配置。

完成标准：Day 3 三个 fixtures 通过“无串扰”。

## Day 6：ResearchProtocol v0.1

- 采用本包 `research_protocol.schema.json`；
- 建 Pydantic 模型；
- 必填 question goal/unit/time/geography/falsification；
- design 包含 lane、主/备选方法和人工批准。

完成标准：未批准设计不能进入分析；schema round-trip 测试通过。

## Day 7：Legacy Adapter

把旧 `ResearchRequest(topic, mode, depth...)` 转为 protocol：

- `academic → goal=synthesize`；
- 标注 `legacy=true`；
- 缺字段设为 `needs_input`，不伪造用户选择。

完成标准：旧 CLI/MCP 测试继续通过。

## Day 8：多源检索并集

- 每个 query 并发调用全部启用后端；
- 不再 first-success return；
- 保存 backend、query、timestamp、raw count、error、rate limit；
- 统一 record schema。

完成标准：任一后端故障不影响其他结果；所有来源均有 provenance。

## Day 9：去重与筛选

- DOI 规范化优先；
- 无 DOI 时用题名+作者+年份模糊候选；
- 预印本/最终版建立 relation，不简单删除；
- inclusion/exclusion reason 必填。

完成标准：用本包 100 篇语料注入重复/版本，去重准确率 ≥98%。

## Day 10：PaperCard v2

字段：问题、理论、数据源、样本、变量、方法、公式、结果、稳健性、局限；每字段带 `value/evidence_level/locator/confidence/review_status`。

完成标准：摘要字段不能标为 fulltext；缺失必须为空/unknown，不生成“看似完整”的句子。

## Day 11：Artifact Manifest

- 引入 artifact ID、schema version、SHA-256、input/output lineage；
- run 记录 protocol version、code commit、环境、参数、随机种子；
- 旧路径仍可读。

完成标准：同一输入输出可验 hash；改输入产生新 artifact。

## Day 12：Gate Registry

- common gates：schema、来源、引用、许可、manifest；
- 三个 benchmark 泳道的最小 gates；
- `human` gate 由权限层批准，Agent 不能自批。

完成标准：故意缺平行趋势/可行性/时间切分时分别被拦截。

## Day 13：端到端 CLI/MCP 演示

用三个 fixtures 跑：Protocol → Search → PaperCard → Design Memo → Gate Report → Manifest。暂不写 Web。

完成标准：每个步骤可恢复；产物可读；失败原因可操作。

## Day 14：评审与下一 Sprint 决策

- 对照本包 `ACCEPTANCE_TESTS.md`；
- 记录性能、成本、错误与人工修改；
- 只选择一个后续主线：`Literature MVP` 或 `Protocol/Method UI`；
- 合并前拆分 PR，避免把重构、功能和文档揉成一个提交。

完成标准：有可演示闭环、已知问题列表、下一 Sprint 目标和 Go/No-Go 决定。

## Sprint 0 绝对不要做

- 不上 Kubernetes；
- 不做复杂知识图可视化；
- 不接付费数据库；
- 不一次迁移全部目录；
- 不做“全自动写论文”；
- 不用更多 Agent 掩盖 schema、数据或测试问题。

