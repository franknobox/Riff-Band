# 视觉设计

## 阶段协议

步骤：visual_design

目标：对HTML报告进行视觉设计，生成图表和美观排版。

输入：report.md、outline.md、findings.jsonl、insights.jsonl。

推荐工具：read_research_report、write_report_section

执行步骤：1.读取报告正文 2.识别可图表化数据 3.生成chart/table标记 4.写入visual HTML

必须产出：report_visual.html、图表标记、响应式排版

质量门：HTML必须包含至少一个data-chart或data-table标记。