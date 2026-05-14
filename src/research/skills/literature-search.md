# 文献检索

收集真实、可验证、可引用的论文候选，并为后续轻量阅读、知识综合和最终 `paper.tex` / `references.bib` 建立干净的论文池。本阶段只负责检索、筛选和去重，不做跨论文知识综合，也不写 `findings.jsonl`。

## 阶段协议

步骤：`literature_search`

目标：

- 根据 Step 1 的研究主题、研究线索和“检索式”构造组合学术 query。
- 优先使用具体检索式，不要只用单个宽泛关键词。
- 建立至少 30 篇合格论文的候选池，写入 `candidates.jsonl`、`shortlist.jsonl` 和 `papers.jsonl`。
- 对候选论文进行相关性筛选和去重，保证后续 Step 2.5 可以直接读取高相关论文生成 `paper_cards.jsonl`。
- 不在本阶段生成跨论文结论、研究空白或宏观发现。

推荐工具：

- `batch_literature_search`：主工具。按 query 批量检索，内部负责多源检索、筛选、去重，并将合格论文写入 `papers.jsonl`。
- `read_papers`：只用于检查论文池数量、相关性和覆盖情况，不要反复读取完整论文列表。
- `write_scratchpad_note`：记录检索覆盖、失败工具、替代 query、明显缺口和下一步建议。
- `write_report_section`：写入 `## 文献检索与证据表`，只总结检索策略、论文池规模、主题覆盖和不足。

执行要求：

1. 第一动作优先调用 `batch_literature_search`。
2. `queries` 使用 Step 1 的“检索式”和组合学术 query，例如“RIS-assisted ISAC vehicular networks”“reconfigurable intelligent surface integrated sensing communication beamforming”，不要只传入 “RIS” 或 “ISAC” 这种单词级关键词。
3. `record_findings` 必须保持为 `false`。Step 2 不写 `findings.jsonl`，跨论文 findings 由 Step 3 的知识综合阶段生成。
4. 达到论文数量目标后停止继续检索，转为总结检索覆盖情况和缺口。
5. 如果同一工具连续失败，不要原样重试；缩小 query、切换检索源，或记录 open issue。
6. 输出内容必须避免把原始检索列表当成综述结论。

必须产出：

- `candidates.jsonl`：原始候选论文。
- `shortlist.jsonl`：筛选后的候选论文。
- `papers.jsonl`：去重后的合格论文池。
- 报告章节：`## 文献检索与证据表`。

不得产出：

- 不在 Step 2 写 `findings.jsonl`。
- 不在 Step 2 生成研究空白、跨论文主题、争议或假设。
- 不调用 `record_finding` 记录摘要级 finding。
