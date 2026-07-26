# AI4MS 管理科学科研平台产品策划总文档

版本：0.3  
日期：2026-07-16  
技术基线：Riff-Band `dev` 分支

## 一、项目定义

AI4MS 是一个面向管理科学、运筹学、运营管理和信息系统研究的 AI for Science 平台。它先把模糊想法变成一份可追溯的“已有研究与选题建议报告”，再由 S0—S9 阶段智能体与用户合作，把研究问题、文献、理论、数据、方法、Stata/Python 运行、稳健性和论文主张连接起来。所有关键草案可人工修改，G0—G5 只能由人批准。

产品的核心不是“让 AI 自动写一篇论文”，而是：

> 用统一研究骨架管理不同方法分支，让每个阶段都有 AI 协作者、每个关键决定由人负责，并让每个结论回到证据、数据版本、模型假设和代码运行。

## 二、证据基础

本策划建立了 100 篇平衡型设计语料：10 本核心期刊各取 5 篇历史高引和 5 篇 2021—2025 近年高热论文。引用与元数据来自 OpenAlex，快照日期为 2026-07-12；100 篇均有 DOI 和摘要，已执行去重。

主要范式分布：规范/处方 28、实证解释 25、解析机制 10、证据综合 10、理论构建 8、因果 7、预测计算 7、探索/理论生成 4、设计构建 1。

这说明：管科不存在一条统一“模型流程”，但存在统一的**科研阶段、资产和门禁**。

## 三、统一研究范式

母流程：

`项目章程 → 问题/理论/可证伪 → 研究设计门 → 数据/模型协议 → 执行/诊断/稳健性 → Claim–Evidence → 复现包/写作/审稿`

研究设计门后分为五条泳道：

1. 实证/因果：DAG、estimand、识别、诊断、机制与外部效度；
2. 解析/优化：参与者/决策、目标/约束、均衡/求解、算例与敏感性；
3. 预测/计算：标签时点、切分、基线、训练、校准、外部测试与部署；
4. 行为/定性：实验/理论抽样、采集、估计/编码、负例与边界；
5. 综述/设计科学：检索/纳排/综合，或设计目标/构件/评估/设计原则。

所有泳道最终汇合到 Claim–Evidence–Assumption 层。

## 四、产品形态

### 1. Web Research Workbench

主产品，面向研究者和团队：

- 项目与协议；
- Literature Lab；
- Method/Data/Formula Studio；
- Runs 与 Robustness；
- Evidence 与 Writing；
- 审批、协作与治理。

### 2. CLI

保留 Riff-Band CLI，供高级用户、批处理和调试。CLI 后续调用统一服务层，不直接把工作区文件当数据库。

### 3. MCP/API

为 Codex、Claude Code、IDE、Zotero 和机构系统提供 Project、Protocol、Search、Run、Claim、Export 等工具/API。

### 4. Local Runner

受限和敏感数据留在用户本地/机构环境，云端只下发批准后的协议与代码，上传许可允许的聚合结果和 manifest。

Local Runner 同时承载用户/机构自带许可的 Stata batch 执行。平台只登记版本、edition、许可模式和并发席位，不保存授权码或分发安装包。

## 五、核心功能

### Topic Scout 与已有研究报告

用户用一句话输入研究想法，系统澄清概念和边界，执行地平线扫描、系统扩展和空白反向复核三层检索，形成经典基础、近年进展、研究流派、共识、争议和未知。研究空白按理论、情境、数据、方法、时间和实践六类展示，每个空白均带支持/反向证据、覆盖限制与人工批准。系统最终提交 2—3 张候选课题卡和一份“决策摘要 + 证据附录”报告；G0 通过后才进入 Research Protocol。

这一体验参考了玻尔（Bohrium）公开展示的“从自然语言问题出发—追溯文献证据—继续形成调研/综述/报告—沉淀知识资产”的工作流。AI4MS 不追求资源规模对标，而是在管科场景增加检索协议、理论—数据—方法编码、空白反向复核、数据/识别可行性、人工 Gate 和可复现性。详见 `03_product/BOHRIUM_BENCHMARK.md` 与 `03_product/TOPIC_SCOUT_AND_RELATED_RESEARCH_REPORT.md`。

### Project & Research Canvas

输入现象、目标、分析单位、时间、地域、理论和可证伪条件；比较主设计与至少一个备选设计；经人工 G1 批准后冻结协议版本。

### Literature Lab

OpenAlex、Crossref、Semantic Scholar、arXiv 多源并行检索；保存检索协议和每库快照；DOI/题名/作者/年份去重；纳排与冲突复核；论文卡字段带来源等级与页码/句子定位。

### Method Studio

本包已经整理 28 种方法、47 张公式卡。系统按目标、数据、假设和规模推荐，并必须说明适用理由、不可解决的问题、关键诊断和替代方法。

### Data Hub

本包已整理 40 个常用数据源。项目使用数据前必须有 Data Contract：来源、许可、版本、单位、时间、变量、连接键、PII、质量检查和存储策略。

### Experiment Lab

从方法卡生成可编辑代码/notebook；在受限容器中运行；记录 commit、lockfile、镜像、参数、随机种子、输入/输出 hash、日志和成本。

### Stata Analysis Workbench

从已批准分析计划生成 do-file patch，用户逐段接受、修改或拒绝；G3 绑定 Analysis Plan revision、do-file hash、Data Contract 和 Runner。Local/Institution Runner 使用自带许可批处理执行，保存 SMCL/text log、`datasignature`、Stata/ado 环境、表图与完整血缘。原始数值不可手改，解释由用户在 G4 前修改和批准。详见 `03_product/STATA_ANALYSIS_WORKBENCH.md`。

### Stage Agents 与人工审批

产品为选题、文献、理论、设计、数据、分析计划、Stata/计算、稳健性、证据和写作配置 S0—S9 主协作智能体。智能体只提交 `machine_draft` 和 patch；用户可直接编辑、评论、拒绝、回滚和分叉。G0—G5 绑定明确 revision/hash，上游语义变化自动失效下游批准。详见 `03_product/STAGE_AGENT_COLLABORATION.md` 与 `03_product/HUMAN_APPROVAL_AND_EDITING.md`。

### Robustness Center

按泳道生成并执行专属检查：因果预趋势/弱工具，优化可行性/gap/压力，ML 泄漏/外部测试，实验功效/流失，定性负例/一致性。失败必须影响 claim 置信。

### Evidence Graph

核心对象为 Claim、Evidence、Assumption、Run 和 Artifact。MVP 先用表格和双向链接，不急于做复杂图数据库/可视化。

### Writing & Review

只从已批准 claims、图表和参考文献生成大纲/正文；执行 DOI、引文蕴含、数值—表图一致性检查；支持方法、复现、数据伦理审稿；导出 Markdown、LaTeX、DOCX/BibTeX 与研究包。

## 六、Riff-Band 如何复用

直接复用：Agent runtime、委派/并行、Pipeline 控制流、Artifact 思路、工具系统、CLI、MCP、学术 API adapter。

优先重构：

- 去除 RIS/ISAC/beamforming 等通信课题硬编码；
- BatchLiteratureSearch 从 first-success 改为多源并集；
- PaperCard 从摘要句子启发式升级为 schema + locator + confidence + review；
- Gate 从文件/章节/数量升级为 common + lane + method；
- ResearchRequest 升级为 ResearchProtocol；
- JSONL Artifact 增 ID、schema、hash、lineage、run 和 protocol version。

新增：FastAPI、PostgreSQL、对象存储、队列、Web、Auth/RBAC、Compute Sandbox、Data Governance 和评测集。

## 七、实现技术

- Web：Next.js/TypeScript/Tailwind/shadcn；
- API：FastAPI/Pydantic v2；
- Orchestrator：Riff-Band async pipeline；高可靠跨日任务成熟后再考虑 Temporal；
- Queue：Redis + Dramatiq/RQ；
- DB：PostgreSQL，向量用 pgvector；不先上 Neo4j；
- 文件：S3/MinIO；
- 数据：DuckDB + Polars；
- PDF：pypdf/PyMuPDF + GROBID；
- 统计/因果：statsmodels、linearmodels、DoubleML/EconML；
- Stata：BYOL local/institution batch Runner；P1 PyStata；
- 优化：Pyomo、OR-Tools、HiGHS，商业求解器插件；
- ML：scikit-learn、XGBoost/LightGBM、PyTorch；
- 复现：uv lock、Git SHA、OCI image、SHA-256 manifest；
- 观测：OpenTelemetry；
- 安全：OIDC/RBAC、Secret Manager、无网络非 root 沙箱。

## 八、MVP

8—10 周的 MVP 闭环：

`Research Idea → S0 Topic Agent → G0 → Literature/Theory/Design Agents → G1 → Data Agent → G2 → Analysis Plan + do-file → G3 → Python/Stata Run → Robustness/Evidence → G4 → Writing Agent → G5 → Repro Package`

暂不做：全功能 JupyterHub、通用数据湖、复杂知识图、全自治发文、付费全文抓取、Kubernetes/Spark/Neo4j。

## 九、24 周 Roadmap

- W1—2：测试基线、DomainProfile、去硬编码、ResearchProtocol；
- W3—6：Topic Scout/已有研究报告、API/DB、多源检索、PaperCard v2、最小 Web；
- W7—10：Revision/Approval、S0—S9 Stage Registry、方法/公式/数据源、Evidence 与 G0—G3；
- W11—14：Python 沙箱、Stata batch Runner、运行队列、连接器和模板；
- W15—18：稳健性、复现审计、G4/G5、写作与引用/数值审计；
- W19—22：Auth/RBAC、协作、治理、6 个真实课题试点；
- W23—24：安全/性能/恢复演练与 v0.1 发布。

## 十、你下一步应该做什么

第一天：在仓库记录 `dev` commit SHA，建立 `feature/management-science-protocol`。  
第一周：补 dev 依赖/CI、3 个管科 fixtures、DomainProfile、去全部通信主题硬编码。  
第二周：实现 ResearchProtocol、legacy adapter、多源检索并集、PaperCard v2、Artifact Manifest 和 Gate Registry。  
第 14 天：用因果、优化、平台供应链三个课题跑端到端 CLI/MCP 演示；随后按 Sprint 1 做“一句话想法 → 已有研究报告 → G0 → Protocol 草案”，再按 Sprint 2 做“人工修改/审批 → Stata do-file → G3 → batch run → G4”的第三个竖切。

详细逐日任务见 `05_roadmap/SPRINT_0_14_DAYS.md`、`SPRINT_1_TOPIC_SCOUT_14_DAYS.md` 和 `SPRINT_2_STATA_HITL_14_DAYS.md`，接口/Schema/示例见 `06_developer_starter/`。
