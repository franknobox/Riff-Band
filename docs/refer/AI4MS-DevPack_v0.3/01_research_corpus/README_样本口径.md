# 管科顶刊 100 篇设计语料：口径与使用说明

## 1. 这份“100篇”是什么

这不是声称“全球绝对排名前100”的榜单，而是一份为 AI for Science 产品设计服务的**平衡型研究语料**。单纯按总引用量排序会被早期信息系统经典论文和少数方法论文占满，无法代表今天管科研究的完整工作流；单纯看近年论文又无法识别已经被反复验证的经典范式。

因此，本语料采用：

- 10 本管科核心期刊；
- 每本 5 篇历史高引用论文；
- 每本 5 篇 2021—2025 年的近年高热论文；
- 共 100 篇；论文类型限定为 `article`，排除勘误、撤稿、编辑说明等；
- 引用与元数据快照日期：**2026-07-12**。

核心期刊中的 8 本来自 [UTD Top 100 的期刊清单](https://jsom.utdallas.edu/the-utd-top-100-business-school-research-rankings/list-of-journals)，另加入 Transportation Science 与 Decision Sciences，补足交通物流和综合决策科学方法。期刊构成如下：

1. Management Science
2. Operations Research
3. Manufacturing & Service Operations Management
4. Production and Operations Management
5. Journal of Operations Management
6. Information Systems Research
7. MIS Quarterly
8. INFORMS Journal on Computing
9. Transportation Science
10. Decision Sciences

## 2. 指标与算法

元数据与引用量来自 [OpenAlex Works API](https://developers.openalex.org/api-reference/works)。

- 经典高引：每本期刊按 `cited_by_count` 降序筛选前 5 篇合格论文。
- 近年高热：先取 2021—2025 年高引用候选，再按下式排序：

$$
H=\frac{C_{2024:2026}+1}{\sqrt{2026-y+1}}+0.15\frac{C_{all}}{2026-y+1}
$$

其中 $y$ 为发表年份，$C_{2024:2026}$ 为 2024—2026 年引用流，$C_{all}$ 为总引用量。2026 年只有截至 7 月的部分数据，所以总引用年均值只作为次要修正项。

所有记录执行 DOI/规范化题名去重。本次结果为：

- 100 条记录；
- 10 本期刊各 10 条；
- 50 条经典高引，50 条近年高热；
- DOI 覆盖 100%；
- OpenAlex 摘要覆盖 100%；
- 无重复题名。

## 3. 结构化抽取字段

`papers_100.csv` 与 `papers_100.json` 包含：

- 书目信息：题名、作者、期刊、年份、DOI、OpenAlex ID；
- 动态指标：总引用、2024—2026 引用、热点分数、快照日期；
- 研究设计信息：主主题、研究范式、方法族、数据类型；
- 产品训练信息：推断研究流程、框架摘要、抽取证据等级；
- 审核状态：当前均标注“待逐篇全文复核”。

研究设计字段由题名、主题与摘要规则辅助归类，**不是全文人工编码结果**。它适合形成产品信息架构、方法分支和初版评测集，不应直接用于发表级别的逐篇内容主张。

## 4. 使用边界

- 引用量随数据库覆盖和时间变化，必须同时保留快照日期。
- 高引用不等于高质量，也不等于适合当前研究问题。
- 近年热点受发表时间、开放获取、主题热度和数据库覆盖影响。
- 摘要不能充分识别变量构造、数据许可、识别假设、公式细节和稳健性检验。
- 进入正式训练/评测前，应进行双人全文编码，并记录一致性（例如 Cohen's κ）。
- 本文件夹只保存书目元数据、摘要级短摘和推断标签，不批量分发受版权保护的论文全文。

## 5. 文件说明

| 文件 | 用途 |
|---|---|
| `papers_100.csv` | 适合 Excel、筛选与人工补录 |
| `papers_100.json` | 适合程序、检索与评测 |
| `corpus_provenance.json` | 查询口径、期刊 Source ID 与 API 元信息 |
| `corpus_summary.json` | 基础计数与覆盖率 |
| `analysis_summary.json` | 引用、范式、方法和数据类型统计 |
| `paradigm_by_journal.csv` | 期刊×研究范式交叉表 |
| `UNIFIED_RESEARCH_PARADIGM.md` | 由样本归纳的统一科研骨架 |

## 6. 下一轮人工编码建议

先对每种范式抽 3 篇、共约 27 篇进行双人全文编码，字段包括：研究问题、理论、数据源、样本期、识别/求解、核心公式、主结果、稳健性、局限、可复现资产。若一致性低于 0.75，先改编码手册，再扩到 100 篇，不要直接把自动标签当训练真值。

