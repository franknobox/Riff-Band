# LaTeX 文献综述正文撰写

基于已验证的中间产物撰写可转换为 `paper.tex` 的文献综述正文，并保持引用真实、可追溯。

## 阶段协议

步骤：`section_draft`

目标：
- 根据 `outline.md`、`findings.jsonl`、`papers.jsonl`、`claims.jsonl`、辩论记录和 scratchpad 撰写连续的论文式综述正文。
- 正文应面向最终 LaTeX 论文，而不是过程报告。
- 为 `references.bib` 和 `paper.tex` 保留来源 URL 或 citation key。

输入：
- `outline.md`
- `findings.jsonl`
- `papers.jsonl`
- `claims.jsonl`
- `debate_log.md`
- `scratchpad/shared.md`

推荐工具：
- `read_research_outline`、`read_findings`、`read_papers`、`read_research_claims`、`read_claim_debate_log`、`read_scratchpad`：撰写前读取材料。
- `crossref_lookup`、`dblp_lookup`、`bibtex_export`：核验参考文献并导出 `references.bib`。
- `citation_audit`：撰写后检查引用覆盖。
- `write_report_section`：写入本步骤报告章节。

执行步骤：
1. 读取大纲、findings、papers、claims、辩论记录和综合笔记。
2. 组织论文式结构：Abstract、Introduction、Background、Related Work、Literature Synthesis、Research Gaps、Future Directions、Conclusion。
3. 只基于已验证材料撰写，不足之处明确标注为 limitation 或 open issue。
4. 在关键论断附近保留来源 URL；最终导出会把可匹配 URL 转成 `\cite{...}`。
5. 调用 `bibtex_export` 生成 `references.bib`，确保 papers.jsonl 中的文献能进入参考文献。
6. 尽可能运行 `citation_audit`，若失败则修正文中引用或返回 `partial`。
7. 写入报告章节：`LaTeX文献综述正文`。

必须产出：
- 连续、可阅读的文献综述正文。
- 明确的局限性和未来方向。
- 有来源支撑的主要论断。
- `references.bib`，以及可导出为 `paper.tex` 的 markdown 中间稿。

质量门：
- 不得编造参考文献元数据。
- 无支撑观点必须删除或标注为不确定。
- 如果引用审计失败，返回 `partial` 并列出修复项。
