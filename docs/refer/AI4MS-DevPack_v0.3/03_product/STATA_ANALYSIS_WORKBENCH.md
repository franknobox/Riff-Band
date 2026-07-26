# Stata 可复现分析工作台

版本：0.3  
日期：2026-07-16

## 1. 产品定位

Stata Workbench 是 AI4MS 的受控统计分析入口。它把已经批准的研究设计、数据协议和分析计划转换为**可人工编辑、可审批、可批量运行、可追溯的 do-file 与结果包**。

它不是“让 AI 随意写几行 Stata 代码并解释显著性”。主分析只有在 G3 分析计划与代码冻结通过后才能运行；任何代码修改都会形成新版本，必要时重新触发审批。

## 2. 用户看到的产品形态

| 区域 | 用户看到什么 | 用户可以做什么 |
|---|---|---|
| Analysis Plan | estimand/目标、样本、变量、固定效应、标准误、权重、缺失处理、主次结果、稳健性 | 逐字段编辑、比较方案、提交 G3 |
| Do-file Studio | 由批准计划生成的 `.do` 文件、AI 建议差异、方法卡与公式卡 | 接受/拒绝单个 patch、直接编辑、回滚、评论 |
| Preflight | 数据变量、唯一键、面板/时序声明、命令可用性、Stata 版本、许可和资源 | 修正映射、安装已批准 ado、选择 Runner |
| Run Console | 运行参数、队列、日志、退出码、耗时和资源 | 启动、取消、重跑、从批准版本分叉 |
| Results Review | 表格、图、诊断、稳健性矩阵和失败项 | 标注解释、要求补跑、提交 G4；不能手改原始数值 |
| Repro Package | do-file、日志、数据签名、版本/包清单、表图和哈希 | 下载、交接、在本地/机构 Runner 重放 |

## 3. 标准人机流程

1. Analysis Plan Agent 从 G1/G2 已批准的设计和数据合同生成分析计划草案。
2. 用户修改 estimand、样本、变量、标准误、主要结果和稳健性要求。
3. Stata Analyst Agent 生成 do-file patch，并解释每一段代码对应哪项计划和假设。
4. 用户逐段接受、修改或拒绝；平台执行静态策略检查和变量预检。
5. 方法审核者批准 G3。批准对象是明确的 `analysis_plan_revision + do_file_sha256 + input_data_contract_version`。
6. Stata Runner 在无网络、受限文件系统中批处理执行，保存日志、退出码和全部输出。
7. Robustness Agent 读取运行产物，提出诊断和追加检验；用户决定是否创建新运行分支。
8. 人工在 G4 批准结果解释和 Claim。AI 不能把 p 值自动转换成最终研究结论。

## 4. 首批 Stata 模板

| 模板组 | 主要命令/任务 | 必须检查 |
|---|---|---|
| 数据审计 | `describe`, `codebook`, `misstable`, `duplicates`, `isid`, `datasignature` | 单位、缺失、重复、异常、数据签名 |
| 描述与 Table 1 | `summarize`, `tabulate`, `dtable`, `collect` | 分母、权重、样本口径、缺失处理 |
| OLS/GLM | `regress`, `logit/probit/poisson` | 效应量、区间、异方差、共线性、聚类层级 |
| 面板 FE/RE | `xtset`, `xtreg` | 组内变异、序列相关、时间/个体效应、聚类误差 |
| DiD/事件研究 | 官方 treatment-effects/面板命令或已批准 ado | 平行趋势、分期处理、提前反应、溢出、事件窗 |
| IV/2SLS | `ivregress 2sls` | 一阶段、弱工具、排除限制、LATE 边界 |
| RDD | 官方命令或已批准 `rdrobust` | 带宽、密度、协变量平衡、donut/placebo cutoff |
| 生存分析 | `stset`, `sts`, `stcox/streg` | 起点、删失、比例风险、竞争风险 |
| SEM/测量 | `sem/gsem`, `estat gof` | 识别、信效度、拟合、竞争模型 |
| 调查/缺失 | `svyset`, `mi set/impute/estimate` | 权重、分层聚类、插补模型、合并规则 |
| 时序 | `tsset`, `arima/var` | 平稳、协整、滞后、残差、滚动回测 |
| 元分析 | `meta set/summarize/regress/bias` | 效应量口径、异质性、发表偏倚、敏感性 |

第三方 ado 不是默认依赖。每个项目必须锁定来源、版本、校验值和许可；未批准的 `ssc install/net install` 在运行环境中被阻塞。

## 5. Runner 方案

### MVP：批处理 Runner

- Linux/macOS 通过 Stata 官方支持的 batch do-file 模式运行；Windows Runner 使用对应的 batch/exit 参数。
- Orchestrator 只向 Runner 发送签名 Run Bundle，不把许可证密钥放进项目、日志或镜像。
- 优先支持两种部署：研究者本机 `local-runner`；学校/企业管理的机构 Runner。
- 使用用户或机构已有的 Stata 许可（BYOL）。平台不复制、出售或转发 Stata 安装包和许可证。
- 并发上限必须小于等于组织配置的许可席位，超额任务排队而不是额外启动实例。

### P1：PyStata Adapter

PyStata 可让 Python 调用 Stata并访问结果，适合把 Stata 嵌入 AI4MS Python Orchestrator 或 Jupyter。P1 才启用，原因是 MVP 的批处理 do-file 更容易做隔离、重放、日志和故障恢复。

### P2：交互式本地会话

用户可以在本机 Stata 中打开已批准的 Run Bundle，完成探索后把 do-file、日志和允许上传的结果重新导入。探索结果必须标为 exploratory，只有重新冻结并批处理重放后才能支撑核心 Claim。

## 6. Run Bundle 与产物

输入：

- `stata_run.json`：项目、协议、计划、Runner、Stata 版本/edition、参数、随机种子；
- `analysis.do`：人工批准的 do-file；
- Data Contract 与允许挂载的数据文件/只读路径；
- ado/package manifest；
- 预期输出清单和超时/资源限制。

必须输出：

- 原始 `.smcl` 与文本 `.log`；
- do-file、退出码、开始/结束时间；
- `about`、Stata 版本/edition、OS、locale、`adopath` 和关键 `which` 结果；
- 输入数据 `datasignature` 与文件 SHA-256；
- 表格（CSV/XLSX/DOCX）、图形（PNG/SVG/GPH）、结果数据（DTA）和 estimates（STER）清单；
- 每个输出的 SHA-256、生成命令、依赖 Run 和证据用途；
- 诊断结果与未通过项，但不自动生成最终结论。

## 7. 安全与许可边界

- Runner 默认无网络、非 root、只读输入、独立输出目录和资源上限。
- 静态策略默认阻塞 `shell/!`、外部进程、未批准 Python/Java、动态下载 ado、任意 URL 读取和越界文件路径。
- 需要 Python 或网络的 do-file 必须单独申请权限，并在隔离策略中显式列出目的、域名、包与数据范围。
- Restricted 数据优先在 local/institution runner 中执行；只上传许可允许的聚合结果、日志摘要和 manifest。
- 原始日志可能包含变量标签、路径或敏感值，上云前执行脱敏检查。
- 平台记录许可类型和并发上限，但不保存序列号、授权码或安装介质。

## 8. 复现规则

1. do-file 顶部固定 `version`、`set more off`、日志、随机种子和工作目录策略。
2. 原始输入只读，清洗后的 DTA 作为新 Artifact；不得覆盖原始数据。
3. 每个关键命令前后记录样本量、返回码和预期条件；失败立即进入 blocked/failed。
4. 数据签名不同、关键 ado 不同或 Stata 主版本不兼容时，不得把重跑标为 reproduced。
5. 表图必须由代码生成；用户只能修改展示配置，不能直接改数值单元格后冒充运行结果。
6. 结果解释与数值产物分离；解释修改不改变原始 Run，数值变化必须来自新 Run。

## 9. MVP 与后续边界

### MVP

- Local/Institution batch Runner；
- Data audit、OLS、FE、DiD 三类模板；
- do-file 编辑、patch 审阅、预检、G3 批准；
- 日志、数据签名、版本/ado manifest、表图输出；
- 结果与 Claim 的证据链接；
- 许可席位与安全策略检查。

### P1

- IV、RDD、生存、SEM、survey/MI、time series、meta-analysis；
- PyStata adapter、结果结构化解析、更多 collect/etable 导出；
- 机构 Runner 管理控制台。

### 暂不做

- 平台托管或转售 Stata 许可证；
- 允许 Agent 在未审批 do-file 上运行主分析；
- 自动安装任意社区 ado；
- 把显著性等同于贡献或因果；
- 用 LLM 重新计算或篡改 Stata 输出。

## 10. 验收映射

- A31：批准的 do-file 能批处理运行并完整捕获日志/退出码/产物；
- A32：固定输入、代码和环境的重放数值一致；
- A33：Stata/ado/数据签名/哈希 manifest 齐全；
- A34：危险命令、网络、路径和许可越界被阻塞；
- A35：表图和核心数值能回到 Run、命令、数据与 do-file revision。

## 11. 官方依据

- Stata Unix batch mode：https://www.stata.com/support/faqs/unix/batch-mode/
- Stata Windows batch mode：https://www.stata.com/support/faqs/windows/batch-mode/
- PyStata：https://www.stata.com/features/overview/pystata-python-integration/
- Reproducible reporting：https://www.stata.com/features/overview/truly-reproducible-reporting/
- `datasignature`：https://www.stata.com/manuals/ddatasignature.pdf
- License options：https://www.stata.com/order/license-options/

