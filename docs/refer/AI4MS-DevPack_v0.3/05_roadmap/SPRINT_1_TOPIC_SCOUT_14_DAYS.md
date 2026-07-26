# Sprint 1：14 天做出“课题侦察与已有研究报告”竖切

前置条件：完成 `SPRINT_0_14_DAYS.md` 中的 DomainProfile、ResearchProtocol、多源检索并集、PaperCard v2、Artifact Manifest 和 Gate Registry 基础。  
目标：用户输入一句研究想法，系统能输出一份有真实文献、检索快照、研究流派、共识/争议、候选空白和 2—3 个候选课题的 Markdown 报告，并由人批准后生成 Research Protocol 草案。

## Day 1：冻结用例和金标

- 选 10 个真实管科研究想法，覆盖因果/实证、优化、预测、行为/定性和综述；
- 每题由领域人员提供 5—10 篇种子论文、相邻术语、至少一个容易误判的“伪空白”；
- 固定评价：Recall@50、DOI 准确率、错误空白、结论可追溯、人工修改时间。

完成标准：`topic_scout_benchmark_v1` 可离线运行，模型更新不能更改金标。

## Day 2：TopicBrief schema 与澄清接口

- 实现 idea、objective、units、geography、time、concept blocks、seed papers、approved；
- Question Coach 只提出最少必要问题；未知允许为空，不替用户虚构；
- 增加 `POST /projects/{id}/topic-briefs`。

完成标准：TopicBrief 未批准不得启动完整课题侦察。

## Day 3：Query Planner

- 生成概念块、同义词、排除词和中英文变体；
- 输出可读布尔查询，同时保留模型/提示版本；
- 支持用户逐块修改和重新生成。

完成标准：10 个基准课题的关键种子术语召回达标；查询可重放。

## Day 4：Topic Scout 状态机

- 状态：queued/running/needs_input/blocked/failed/succeeded/cancelled；
- 固定三个阶段：horizon、systematic_expand、gap_counter_search；
- task key 包含 TopicBrief 版本、数据库、查询和输入 hash。

完成标准：任一阶段失败可恢复，不重复写入已成功快照。

## Day 5：多源搜索快照与去重

- 并行 OpenAlex/Crossref/S2/arXiv；
- 保存每后端查询、时间、原始计数、错误、限流和原始 artifact；
- DOI/题名/作者/年份去重，保留版本关系。

完成标准：A03/A04/A05 通过，任一后端失败不丢失其他结果。

## Day 6：筛选工作台与排序

- 使用可解释特征做相关性排序：概念命中、题名/摘要语义、种子引文邻近、年份；
- 用户可 include/exclude/unsure，排除理由必填；
- 排序不自动替代纳排决定。

完成标准：专家种子论文 Recall@50 ≥0.90；纳排历史可审计。

## Day 7：PaperCard v2 抽取

- 抽取问题、理论、数据、样本、变量、方法、结论、稳健性、局限；
- 每个字段标记 metadata/abstract/fulltext/human_verified、locator 和 confidence；
- 本 Sprint 可先完成摘要级，绝不能标为全文。

完成标准：低置信和冲突字段进入人工队列，缺失用 unknown。

## Day 8：研究流派与时间脉络

- 用嵌入/引文/结构字段产生候选簇；
- Evidence Synthesizer 为每簇提供名称、定义、代表论文和命名依据；
- UI/CLI 支持合并、拆分、改名并记录人工编辑。

完成标准：每个流派至少有 2 篇论文或明确标为 singleton；代表论文真实存在。

## Day 9：共识、争议与未知

- 综合对象状态限定为 supported/contested/limited/not_found/inference/human_verified；
- 每条陈述绑定支持和反向 evidence ID；
- 引用量只用于候选发现，不计算“真理分”。

完成标准：没有 evidence ID 的陈述不能进入报告核心结论。

## Day 10：Gap Analyst 与反向查询

- 六类 gap：theory/context/data/method/time/practice；
- 为每个候选自动生成反向查询和最近似论文列表；
- 机器只能保存 `candidate`，人工批准后才可为 `supported_gap`；
- 禁止“首个、无人研究、完全空白”等绝对词。

完成标准：每个 supported_gap 有反向查询、覆盖限制和批准记录。

## Day 11：候选课题卡与可行性

- 生成 2—3 个研究问题；
- 连接方法、公式和数据源库；
- 展示新颖性、重要性、可行性、可证伪性及文字依据；
- 列出最近似研究、关键假设、阻塞和建议动作。

完成标准：数据不可得或关键假设不成立时能返回 narrow/reframe/pause。

## Day 12：报告生成与审计

- 按固定模板生成决策摘要、研究版图、代表研究、空白、数据/方法、候选题、风险、参考文献和检索附录；
- 只从数据库对象组稿；
- 运行 DOI、引用、数字、状态和绝对原创表述审计；
- 导出 Markdown/JSON，DOCX 放在下一个前端任务也可。

完成标准：虚构文献 0；核心结论 100% 可追溯；快照计数一致。

## Day 13：G0 与 Protocol 转化

- 用户逐条接受/修改/驳回流派、综合结论、空白和候选课题；
- G0 记录批准人、时间、理由和报告版本；
- 批准的候选卡映射到 Research Protocol 草案，缺失字段变为 needs_input。

完成标准：Agent 不能自批；报告修改后旧批准失效或触发重新确认。

## Day 14：真实演示和 Go/No-Go

- 跑 3 个完整真实课题；
- 与人工/传统搜索比较耗时、漏检、错误引用、空白误判和报告可读性；
- 评审 10 个基准任务，记录错误分类；
- Go：达到 A21—A25，且没有严重来源/许可错误；否则只修检索与证据，不扩更多 Agent/UI。

## Sprint 演示脚本

1. 输入一句话课题；
2. 确认 TopicBrief；
3. 展示三层查询和四库实时状态；
4. 展示去重后的文献、流派和争议；
5. 点开任一结论查看来源；
6. 查看候选空白的反向查询和限制；
7. 选择一张候选课题卡；
8. 批准 G0；
9. 导出相关研究报告和 Research Protocol 草案。

## Sprint 内不做

- 不承诺全学科/全中文数据库覆盖；
- 不自动抓取受限全文；
- 不做复杂知识图动画；
- 不用一个总分替代证据和人工判断；
- 不自动批准研究空白和选题；
- 不把摘要级抽取写成全文结论。

