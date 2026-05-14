# 多视角审稿

独立审查最终研究输出，重点判断它是否是一篇结构完整、证据可追溯的 LaTeX 文献综述。

## 阶段协议

步骤：`multi_agent_review`

目标：
- 审查 `paper.tex` 是否具备文献综述文章结构，而不是只审查过程报告。
- 审查 `references.bib`、`papers.jsonl`、`paper_notes.jsonl`、`findings.jsonl`、`claims.jsonl` 是否能支撑正文。
- 产出具体修复建议和最终建议：`accept`、`revise` 或 `blocked`。

推荐工具：
- `review_research_report`：主工具，检查核心综述章节、证据产物和 claims。
- `read_findings`、`read_papers`、`read_paper_notes`、`read_research_claims`、`read_scratchpad`：读取审查上下文。
- `novelty_check`：仅在某个观点明显过强或证据不足时使用。
- `write_report_section`：写入 `多视角审稿意见`。

执行步骤：
1. 检查最终 `paper.tex` 是否包含摘要、研究背景/目的与意义、研究现状、方法与主题综合、研究空白与未来方向、结论。
2. 检查 claims 是否有 evidence_basis 或 source_urls。
3. 检查 paper_notes 是否足以支撑正文；若只是摘要级证据，应明确标注证据深度限制。
4. 不要把“research_report.md 是否含 URL”作为核心失败条件；最终引用完整性应主要看 `paper.tex` 与 `references.bib`。
5. 使用 `review_research_report` 写入审查产物。
6. 写入报告章节：`多视角审稿意见`。

必须产出：
- 按严重程度分组的审查发现。
- 缺失核心论文结构章节的清单。
- 证据深度、claims 支撑和参考文献风险。
- 最终建议：`accept`、`revise` 或 `blocked`。

质量门：
- `accept` 要求没有阻塞性的结构、证据或引用问题。
- `revise` 必须包含具体修复项。
- `blocked` 必须解释阻塞原因和需要的外部输入。
