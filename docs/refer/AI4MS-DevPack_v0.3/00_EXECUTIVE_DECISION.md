# 执行决策：AI4MS 应该怎么做

## Go，但按“研究操作系统”而不是“论文生成器”立项

建议立项。Riff-Band 已具备约 40% 的内核能力：Agent 编排、研究流水线、学术检索、论文卡/claims、Artifact、质量门禁、CLI/MCP。剩余工作主要是把原型变成**协议驱动、可执行、可审计、可协作**的平台。

## 产品核心

AI4MS 的核心对象不是 Chat，而是：

`TopicBrief → RelatedResearchReport → ResearchAsset/Revision/Approval → ResearchProtocol → Paper/Data/Method → Python/Stata Run/Artifact → Claim/Evidence/Assumption → Reproducible Package`

用户仍可聊天，但聊天只是操纵这些对象的一种入口。

## MVP 必须有

1. Topic Scout：从一句想法生成可追溯的已有研究报告、六类候选空白和 2—3 个候选课题；
2. S0—S9 每个阶段一个主协作智能体，所有输出可由用户修改、拒绝、回滚或分叉；
3. G0 选题、G1 设计、G2 数据/伦理、G3 分析代码、G4 结果/Claim、G5 发布六个人工门，Agent 不能审批；
4. 多源文献检索、去重、筛选、PaperCard v2；
5. 方法、数据源和公式库；
6. BYOL Stata batch/local Runner：可编辑 do-file、G3 冻结、日志/数据签名/版本/ado manifest；
7. Claim–Evidence–Assumption 表；
8. Artifact Manifest 与基础复现；
9. 从已批准 claims 导出 Markdown/LaTeX/BibTeX；
10. Web + CLI + MCP 共用后端。

## MVP 不做

- 完全自治批准选题/发文；
- 未经授权抓取付费全文；
- 大而全数据湖；
- 复杂知识图可视化；
- Kubernetes/Neo4j/Spark 的提前投入；
- 让 LLM 直接计算统计量或决定门禁。
- 托管/转售 Stata 许可证、动态安装任意 ado，或让 Agent 在未审批代码上运行主分析。

## 第一优先级技术债

Riff-Band 当前的通用研究代码含通信主题硬编码，文献批检索是 first-success，论文卡以摘要关键词抽取，质量门禁主要检查文件/章节/数量。若不先解决这些问题，直接做 GUI 会把错误抽象固化。

## 资源与时间

- 2—3 人：先做 14 天 Sprint 0；完整试点版约 9 个月。
- 5 人左右：按 24 周 Roadmap，可交付 6 个真实课题试点。
- 建议先投入一个月，Go/No-Go 以领域去硬编码、100 篇检索去重、Protocol/Gate 竖切和用户访谈结果决定。

## 30 天里程碑

第 30 天必须展示：

1. 在同一 Riff-Band 内核上跑因果、优化、平台供应链三个课题；
2. 没有 RIS/ISAC 串扰；
3. 多源检索保存 provenance；
4. PaperCard 字段带证据等级与定位；
5. 未批准设计无法进入分析；
6. 每个输出有 manifest/hash；
7. 一个简单 Web 或 CLI 演示能展示项目状态和失败原因。
8. 从一句研究想法生成一份有真实来源、研究流派、争议、候选空白和 2—3 个候选题的报告，并能由 G0 人工批准。
9. 展示一次 AI patch → 用户修改 → 四眼批准 → 上游修改自动失效下游 Gate 的演示。
10. 展示 Stata Runner preflight、do-file hash/G3 校验、batch 日志和数据签名；许可由用户/机构自带。

若 30 天后仍只能“检索并写长报告”，却不能展示检索审计、证据状态、空白反向复核和 Protocol 转化，应暂停平台投入，先修研究设计与结构化资产。
