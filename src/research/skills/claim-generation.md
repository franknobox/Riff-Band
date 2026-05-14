# 综述观点与研究空白生成

将知识综合结果转为文献综述可使用的研究空白、未来方向、局限性和综述观点。本阶段不设计实验，不提出未经证据支撑的实现方案。

## 阶段协议

步骤：`claim_generation`

目标：
- 基于 `paper_notes.jsonl` 和 `findings.jsonl` 生成 4-8 个候选综述观点。
- 每个观点必须说明证据依据、不确定性和优先级。
- 将结构化结果写入 `claims.jsonl`。

推荐工具：
- `batch_claim_generation`：主工具，基于论文笔记和发现批量生成 claims。
- `read_research_claims`：检查生成结果。
- `write_scratchpad_note`：记录观点优先级和交接说明。
- `write_report_section`：写入 `研究空白、未来方向与可检验问题`。

执行要求：
1. 第一动作优先调用 `batch_claim_generation`。
2. 不要调用 `read_sources` 读取 output 目录里的研究产物。
3. 不要输出 `Invalid` action；只使用当前允许的工具。
4. 没有证据依据或明确不确定性的观点不得升级为 high priority。
5. 本阶段输出的是综述观点和研究空白，不是最终正文。

必须产出：
- `claims.jsonl` 中 4-8 条候选综述观点、方向或问题。
- 每条 claim 的 evidence_basis、source_urls、priority 和 uncertainty。
- 报告章节：`## 研究空白、未来方向与可检验问题`。
