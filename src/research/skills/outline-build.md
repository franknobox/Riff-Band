# 结构化论文大纲构建

将已筛选的论文卡片、候选观点、辩论结论和证据索引转换为面向 LaTeX 文献综述的论文大纲。

## 阶段协议

步骤：`outline_build`

目标：
- 生成一篇文献综述论文的大纲，而不是普通任务报告大纲。
- 将主要章节映射到论文卡片、claims、findings 和计划引用。
- 控制上下文规模：优先使用 prompt 中的压缩材料摘要，不读取完整 candidates/shortlist。

输入：
- `synthesis_digest.json` 中的主题簇、research gaps、证据质量和代表论文。
- `claims.jsonl` 中已生成的研究空白、未来方向和综述观点。
- `debate_log.md` 中的观点保留/修订建议。
- 少量代表性 `paper_cards.jsonl`，只用于补充章节引用和论文例子。

推荐工具：
- `read_synthesis_digest`：第一优先级，读取 Step 3 生成的综合摘要。
- `read_research_claims`：读取候选观点和研究空白。
- `read_claim_debate_log`：读取观点优先级和风险。
- `read_paper_cards`：需要更多代表论文时小批量读取。
- `build_research_outline`：写入结构化大纲和观点-证据映射到 `outline.md`。
- `write_report_section`：写入本步骤报告章节。

执行步骤：
1. 先读取 `synthesis_digest.json`，以主题簇和 research gaps 确定核心综述结构。
2. 必须包含论文式章节：Abstract、Introduction、Background、Related Work、Literature Synthesis、Research Gaps、Future Directions、Conclusion。
3. 为每个章节列出要使用的 synthesis clusters、claims、debate decisions 和代表性 paper cards。
4. 为主要论断附上 source_url 或计划 citation key。
5. 列出会影响最终 `paper.tex` 质量的缺失材料。
6. 调用 `build_research_outline` 写入 `outline.md`。
7. 调用 `write_report_section` 写入 `## 结构化论文大纲`。

质量门：
- 大纲必须能支撑一篇标准文献综述 `.tex`。
- 主要章节都应有证据或计划引用支撑。
- 本步骤不撰写最终正文。
