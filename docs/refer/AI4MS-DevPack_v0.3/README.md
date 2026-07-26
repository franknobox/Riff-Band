# AI4MS 管理科学 AI for Science 产品与开发包

版本：0.3  
日期：2026-07-16  
基于：Riff-Band `dev` 分支当日快照 + 10 本核心期刊的 100 篇平衡型论文设计语料

## 最重要的判断

1. **能做，而且 Riff-Band 值得保留。** 它已经有 Agent runtime、固定研究流水线、学术搜索、结构化 artifact、质量门禁、CLI 和 MCP。
2. **不要把产品做成“自动写论文”。** 更有价值的核心是 Research Protocol、Method/Data/Formula Library、Claim–Evidence Graph、Compute/Reproducibility。
3. **统一的是研究骨架，不是研究方法。** 产品应实现“统一阶段 + 五条方法泳道 + 统一证据/门禁”。
4. **第一步是去硬编码和协议化。** 当前通用研究代码仍含 RIS/ISAC/beamforming 等通信课题硬编码，且文献检索是 first-success，不是真正多源融合。
5. **先跑通 CLI/MCP 竖切，再做平台 UI。** 14 天内可完成 Protocol、领域去硬编码、多源检索、PaperCard v2、Manifest 和 Gate Registry 原型。
6. **选题前必须先完成已有研究报告。** 新增 Topic Scout：从一句想法形成研究版图、共识/争议、六类候选空白和 2—3 张候选课题卡，经 G0 人工确认后才进入 Research Protocol。
7. **每阶段 AI 协作、关键决定人负责。** S0—S9 各有主智能体；所有草案可人工修改，G0—G5 由人审批；Stata 使用自带许可的受控 Runner，原始数值不可手改。

## 目录

| 目录 | 内容 |
|---|---|
| `01_research_corpus/` | 100 篇论文 CSV/JSON、口径、来源、统计与统一范式 |
| `02_knowledge_bases/` | 28 种方法、40 个数据源、47 张公式卡及 JSON Schema |
| `03_product/` | PRD、Stata Workbench、人工审批/编辑、阶段 Agent、用户/技术架构与治理 |
| `04_riffband_integration/` | 仓库审计、复用/重构判断、文件级迁移图 |
| `05_roadmap/` | 24 周 Roadmap、三轮 14 天 Sprint、验收矩阵、风险登记 |
| `06_developer_starter/` | OpenAPI、PostgreSQL schema、Stata starter、profile、示例、backlog |
| `07_workbook/` | 可筛选工作簿（Topic Scout、S0—S9、G0—G5、Stata、论文/方法/数据/公式、80 项 Backlog、Risk） |
| `08_nontechnical_intro/` | 非技术产品介绍书（Markdown、Word、PDF） |
| `scripts/` | 语料、分析与知识库的可复现生成脚本 |
| `sources/` | 主要外部来源与官方链接 |

## 你现在应该先打开的 10 个文件

1. `00_EXECUTIVE_DECISION.md`：产品边界与立项决定；
2. `04_riffband_integration/REPO_AUDIT.md`：现有技术和关键缺口；
3. `01_research_corpus/UNIFIED_RESEARCH_PARADIGM.md`：统一范式；
4. `03_product/PRD.md`：完整产品功能；
5. `03_product/TOPIC_SCOUT_AND_RELATED_RESEARCH_REPORT.md`：课题检索、空白判断和报告规格；
6. `03_product/STAGE_AGENT_COLLABORATION.md`：S0—S9 每阶段智能体与用户分工；
7. `03_product/HUMAN_APPROVAL_AND_EDITING.md`：G0—G5、人工修改和审批失效规则；
8. `03_product/STATA_ANALYSIS_WORKBENCH.md`：Stata 功能、Runner、许可与复现规格；
9. `08_nontechnical_intro/AI4MS_非技术产品介绍书.docx`：给导师、管理者、合作方和非技术成员的产品介绍；
10. `05_roadmap/SPRINT_0_14_DAYS.md`、`SPRINT_1_TOPIC_SCOUT_14_DAYS.md` 与 `SPRINT_2_STATA_HITL_14_DAYS.md`：三轮逐日开发。

## 使用方式

- 产品讨论：以 `PRD.md` 和工作流为准；
- 技术立项：以 `TECH_ARCHITECTURE.md`、`MIGRATION_MAP.md` 和 ADR 为准；
- 开发排期：把 `backlog.csv` 导入 Jira/Linear/GitHub Projects；
- Stata 开发：先读 `06_developer_starter/stata/README.md`；只在自带许可的本地/机构 Runner 上执行；
- 科研内容：在工作簿中筛选论文、方法、数据源和公式；
- 训练/评测：先对 30 篇论文做双人全文金标，不直接把自动标签作为真值；
- 仓库改造：从新分支挑选 Developer Starter 内容，不整体覆盖原仓库。

## 当前证据等级

- 论文题名、DOI、期刊、年份、引用：OpenAlex 元数据快照；
- 论文方法/流程：摘要级规则辅助归类，全部待全文复核；
- Riff-Band 能力：代码快照审计；
- 产品/架构/Roadmap：基于上述证据的设计建议；
- 数据源许可：连接器规划提示，正式接入前必须重新核验。

## 复现

语料和知识库脚本保留在 `scripts/`。引用数据是动态的；重跑语料会得到新的引用量和可能不同的近年热点。所有研究使用都应保留快照日期与 `corpus_provenance.json`。
