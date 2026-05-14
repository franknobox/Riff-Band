# 观点辩论与优先级评估

## 阶段协议

阶段：`claim_debate`

目标：
- 对 `claims.jsonl` 中的候选综述观点、研究空白、未来方向和可检验问题做证据压力测试。
- 判断每个重要观点应当保留、修订、降级还是移除。
- 生成 `debate_log.md`，并稳定写入报告章节 `观点辩论与优先级评估`。

输入：
- `claims.jsonl`
- `findings.jsonl`
- 前序知识综合和论文阅读摘要

推荐工具：
- `batch_claim_debate`：首选工具。批量读取 claims/findings，生成辩论记录，并写入报告章节。
- `read_claim_debate_log`：检查已经生成的辩论记录。
- `read_research_claims`：必要时读取候选观点。
- `write_report_section`：仅在需要人工补充或修正章节时使用。

执行步骤：
1. 首先调用 `batch_claim_debate`，不要逐条反复调用 `record_claim_debate`。
2. 检查 `debate_log.md` 是否包含 keep/revise/downgrade/remove 或等价决策。
3. 确认 `research_report.md` 中存在 `## 观点辩论与优先级评估`。
4. 如果观点证据不足，在章节中明确标注证据层级和使用边界。

必须产出：
- `debate_log.md`
- 报告章节：`## 观点辩论与优先级评估`
- 用于最终文献综述正文的观点优先级列表

质量要求：
- 保留的观点必须能追溯到前序 claims/findings 或 paper notes。
- 修订或降级的观点必须说明证据风险。
- 不要把摘要级或元数据级证据写成完整实验结论。

说明：
- 当前项目中的“辩论”主要是批量证据压力测试，不是严格的多角色正反方辩论。
- 如果后续要实现真正多 agent 辩论，可以在本阶段拆分为支持者、质疑者和裁决者三个角色，再由裁决者写入 `debate_log.md`。
