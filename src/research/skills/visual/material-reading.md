# 材料阅读

## 阶段协议

步骤：material_reading

目标：从检索到的资料中抽取结构化阅读笔记。

输入：sources.jsonl、findings.jsonl、研究计划。

推荐工具：read_url、web_fetch、record_paper_note、record_finding

执行步骤：1.选择优先处理材料 2.补充网页/PDF内容 3.记录结构化笔记 4.追加findings

必须产出：material_notes.jsonl中的结构化阅读笔记、证据来源标记

质量门：不得根据标题编造内容，无摘要/网页/PDF支撑时只能记录为uncertain。