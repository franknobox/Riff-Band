# 论文轻量阅读与结构化抽取

把 `papers.jsonl` 中的高相关论文转换成可写作的结构化阅读笔记。本阶段是轻量实现，主要基于摘要和元数据，不声称完成全文阅读。

## 阶段协议

步骤：`paper_enrichment`

目标：
- 从 `papers.jsonl` 中选择前 N 篇高相关论文。
- 优先选择摘要可用、RIS/ISAC 主题词匹配、年份较新、URL/DOI 完整的论文。
- 为每篇论文生成一条 `paper_notes.jsonl`，字段包括 problem、method、scenario、main_findings、limitations、relevance_to_topic、evidence_source。

推荐工具：
- `batch_paper_enrichment`：主工具。直接读取 `papers.jsonl`，排序并批量写入 `paper_notes.jsonl`。
- `read_paper_notes`：检查生成结果。
- `write_scratchpad_note`：记录证据深度和仍需全文阅读的缺口。
- `write_report_section`：写入 `论文阅读笔记与结构化抽取`。

执行要求：
1. 第一动作优先调用 `batch_paper_enrichment`。
2. 不要反复用 `read_papers` 读取过窄 query；如需要检查结果，使用 `read_paper_notes`。
3. 如果某篇论文只有摘要，`evidence_source` 必须标为 `abstract`；如果只有元数据，标为 `metadata`。
4. 不得根据标题编造方法、实验或结论。
5. 本阶段不做跨论文综合，只为 Step 3 准备每篇论文的结构化材料。

必须产出：
- `paper_notes.jsonl`：每篇论文一条结构化阅读摘要。
- 报告章节：`## 论文阅读笔记与结构化抽取`。
