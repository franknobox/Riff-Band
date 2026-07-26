# 信息检索

## 阶段协议

步骤：information_search

目标：建立足够大的信息源池，覆盖核心主题和相邻主题。

输入：scratchpad中的研究线索、关键词、纳入/排除标准。

推荐工具：web_search、web_fetch、read_url、record_finding、write_scratchpad_note

执行步骤：1.生成查询组 2.调用检索工具 3.记录findings 4.说明缺口

必须产出：sources.jsonl记录、多条有来源支撑的findings、工具失败说明

质量门：不得编造来源，若无法达到数量目标返回partial。