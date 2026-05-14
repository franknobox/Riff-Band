# 多视角知识综合

将 `paper_cards.jsonl`、`paper_notes.jsonl` 和 `findings.jsonl` 转换为跨论文的主题、研究脉络、争议、空白和综述结构。本阶段才负责真正的跨论文综合。

## 阶段协议

步骤：`knowledge_synthesis`

目标：
- 优先基于 `paper_cards.jsonl` 聚类研究问题、方法路线、应用场景、关键结果和局限。
- 在 `paper_cards.jsonl` 不足时，再用 `paper_notes.jsonl` 补充摘要级阅读信息。
- 基于 `findings.jsonl` 回溯证据来源，避免无来源的宏观判断。
- 输出可服务于后续观点生成、大纲构建和 LaTeX 文献综述写作的综合材料。

推荐工具：
- `batch_knowledge_synthesis`：主工具，读取论文卡片，生成 `synthesis_digest.json`，并写入跨论文研究空白 findings。
- `read_paper_cards`：第一优先级，读取每篇论文的结构化知识卡片。
- `read_paper_notes`：第二优先级，只在需要补充摘要级细节时读取。
- `read_findings`：读取单篇或少量论文级证据点，作为跨论文综合的证据索引。
- `read_papers`：只在需要补充 URL、年份、venue 或摘要元数据时使用。
- `read_scratchpad`：读取 Step 1/2/2.5 的研究计划和覆盖缺口。
- `synthesize_findings`：固化主题、共识、争议、空白和证据质量说明。
- `write_scratchpad_note`：记录可复用的综合笔记。
- `write_report_section`：写入 `知识综合与研究空白`。

执行要求：
1. 第一动作优先调用 `batch_knowledge_synthesis`。
2. 如需人工补充，再调用 `read_paper_cards`，限制返回数量，优先读取高相关卡片。
3. 如果 card 数量不足或字段缺失，再调用 `read_paper_notes`。
4. 把 findings 当作综合后的证据索引，不要把原始检索列表简单拼接成综述。
5. 明确区分共识、争议、方法限制、应用场景差异和证据不足。
6. 每个研究空白都要回指到 paper_cards/findings，或明确说明证据不足。
7. 本阶段输出跨论文综合结论，但不直接生成最终 LaTeX 正文。

必须产出：
- 3-6 个跨论文综合主题。
- 共识与争议对照。
- 带证据依据的研究空白分析。
- 证据质量说明。
- `synthesis_digest.json`。
- 报告章节：`## 知识综合与研究空白`。
