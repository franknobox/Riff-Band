# AI4MS 工程基线

记录日期：2026-07-18  
目标分支：`ai4ms`
基线 commit：`ed2e255`  
对照分支：`dev` / `origin/dev`

## 1. 基线范围

本记录描述 AI4MS 代码改造开始前的 RiffBand 状态。AI4MS DevPack v0.3 已放入 `docs/refer/AI4MS-DevPack_v0.3/`，但尚未将其中的目标 API、数据库和服务代码合入运行时。

## 2. 已有能力

- MainAgent/SubAgent 与动态 `<Instruction, Context, Tools, Model>` 组合；
- 通用 Agent 执行循环、流式事件、超时和取消；
- 工具权限、并发委派、子任务隔离和结果合并；
- CLI、MCP 和会话文件持久化；
- 固定研究流水线、步骤技能和规则型 Gate；
- OpenAlex、Crossref、Semantic Scholar、arXiv、DBLP 等检索工具；
- JSONL 论文、发现、Claim、笔记和 synthesis 产物；
- Markdown、LaTeX、BibTeX、普通 HTML 和可视化 HTML 导出；
- 响应式 HTML、目录、表格和 ECharts 图表标记。

## 3. 已确认技术债

- 查询扩展、相关性评分、材料就绪检查和聚类存在 RIS/ISAC/beamforming 硬编码；
- Batch Literature Search 对每个 query 使用 first-success backend，而不是多源并集；
- PaperCard 主要由摘要句子和关键词启发式生成，缺少字段级 locator；
- Gate 主要检查文件、章节和数量，不能代表研究有效性；
- manifest 缺少 artifact ID、schema version、SHA-256 和 lineage；
- 会话和 MCP job 主要保存在本地文件或进程内存；
- 没有 Web/API、PostgreSQL、统一 Revision/Approval、RBAC、任务队列和对象存储；
- 没有受控 Python/Stata Runner。

## 4. 测试基线

命令：

```powershell
pytest -q -p no:cacheprovider --basetemp <writable-workspace-temp>
```

结果：`114 passed, 2 failed`。

失败项：

| 测试 | 原因 |
|---|---|
| `test_mcp_research_tool_returns_before_long_job_finishes` | 测试导入 `src/mcp_server.py`，但按根兼容模块的 `_module` 属性进行 monkeypatch |
| `test_mcp_cancel_research_sets_cancel_event` | 同一 MCP 模块边界问题 |

两项均属于需要修复的测试/模块边界问题。Windows 下若 pytest 默认临时目录不可写，应通过 `--basetemp` 指定仓库内可写的隔离目录。十阶段工作台接入现有 Runtime 前，应先使基线测试转绿或明确隔离兼容层失败。

## 5. 示例运行状态

现有研究命令能够建立固定步骤和 scaffold。当模型配置不可用时，流水线仍会生成部分产物并明确返回 `partial`，但不会执行真实检索和智能体步骤。完整演示必须同时验证：

- 模型配置可被 `LLMsConfig` 识别；
- 至少一个真实检索后端可用；
- 报告包含真实来源链接；
- findings、papers/sources 和 HTML 图表标记达到 Gate；
- partial 状态不能被当作完成结果。

## 6. 十阶段工作台接入条件

- 现有测试通过；
- 三个跨题型 fixture 无通信领域串扰；
- DomainProfile 可以注入当前 pipeline；
- TopicBrief、ResearchProtocol、ProjectState 和 legacy adapter round-trip 通过；
- 多源检索保留全部 backend provenance；
- Web、CLI/MCP 能调用同一 service 层；
- SQLite 项目状态和文件 artifact 在进程重启后可恢复；
- 十阶段状态机不能被 Agent 自批或静默跳过。
