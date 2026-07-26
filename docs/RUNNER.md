# Stata Local Runner 与 Result Bundle

## 1. 产品边界

AI4MS Docker 镜像不分发 Stata。研究者在同一台机器启动 `ai4ms-stata-runner`，由它调用合法安装并有权使用的 Stata。

Local Runner 不是公网服务。它要求：

- Docker 工作台和 Runner 使用相同 `AI4MS_STATA_RUNNER_TOKEN`；
- `AI4MS_STATA_EXECUTABLE` 指向本机 Stata；
- `AI4MS_STATA_LICENSE_CONFIRMED=true`；
- 防火墙禁止外部网络访问 Runner 端口。

Windows 可从仓库根目录进入 `scripts/stata-runner/`，依次运行
`SETUP_STATA_RUNNER.bat`、`START_STATA_RUNNER.bat` 和
`CHECK_STATA_RUNNER.bat`。配置保存在 Git 忽略的
`.env.stata-runner.local`，工作台与 Runner 会自动读取同一配对令牌。

## 2. 数据资产

上传 `.dta` 后，平台登记：

- `asset_id`、原文件名、项目内不可变路径和上传时间；
- 文件大小与 SHA-256；
- Stata 格式版本、数据标签、时间戳、行列数；
- 变量名、标签、存储类型、显示格式和值标签。

Preflight 只接受 `input_asset_id`，不接受浏览器提供宿主机任意路径。运行前重新计算 SHA-256，并检查 S5 所需变量。

## 3. Preflight

正式提交前必须同时满足：

- S5/G3 已由人批准；
- S6 绑定的计划 revision/hash 未过期；
- 执行引擎为 Stata；
- do-file 结构和策略通过；
- 数据资产存在、hash 一致且变量完整；
- Local Runner 可连接且许可已确认。

策略默认阻塞 shell、外部进程、动态安装、网络 URL、Python/Java、父目录穿越、绝对路径、删除输入和提前退出。

## 4. Run Bundle 1.0

工作台发送：

```text
run_request.json
analysis.do
entrypoint.do
result_contract.do
input.dta
```

`run_request.json` 固定记录 `run_id`、项目、S5 revision/hash、do-file SHA-256、数据 SHA-256、seed、参数和超时，并使用配对令牌生成 HMAC-SHA256 签名。

Local Runner 解包时复核签名、路径、文件数量、体积、hash 和代码策略。`analysis.do` 是 G3 已批准内容；服务端通过受控 `entrypoint.do` 调用它，并执行固定结果契约。

## 5. Result Bundle 1.0

Runner 只返回允许的聚合产物：

```text
result_bundle.json
structured_results.csv
data_signature.txt
analysis.log
runner.stdout.log
runner.stderr.log
*.csv / *.xlsx / *.tex
*.png / *.svg / *.pdf / *.gph
```

`.dta` 不进入返回包。结构化结果字段包括：

```text
result_id, kind, specification_id, term, label,
estimate, std_error, statistic, p_value,
ci_lower, ci_upper, sample_size, status, unit
```

工作台复核 Result Bundle 签名、run ID、数据 hash、do-file hash 和每个 artifact hash。退出码为 0 但缺少结构化结果时，状态仍为 `failed:missing_structured_results`。

## 6. 后台任务 API

提交立即返回 `202 Accepted`。FastAPI 使用轻量进程内任务执行，并把状态 JSON 写入项目 `artifacts/jobs/`。

```text
GET  /api/v1/projects/{project_id}/stages/analysis/runs
POST /api/v1/projects/{project_id}/stages/analysis/runs
GET  /api/v1/projects/{project_id}/stages/analysis/runs/{run_id}
GET  /api/v1/projects/{project_id}/stages/analysis/runs/{run_id}/result
GET  /api/v1/projects/{project_id}/stages/analysis/runs/{run_id}/artifacts/{path}
POST /api/v1/projects/{project_id}/stages/analysis/runs/{run_id}/cancel
POST /api/v1/projects/{project_id}/stages/analysis/runs/{run_id}/rerun
```

状态为：

```text
queued / running / canceling / succeeded / failed / canceled / interrupted
```

- `timeout_seconds` 范围为 1-7200 秒，并传递到本机执行进程；
- 取消从工作台继续传到 Local Runner 和活动 Stata 进程；
- 重跑复用原请求、记录 `parent_run_id`，但重新执行 Preflight；
- 失败和取消也生成最小 manifest，Result API 始终具有明确终态；
- 日志和图表只能通过 manifest 已声明的 artifact 路径读取；下载前再次核对文件大小与 SHA-256；
- 后端重启后未完成任务标记为 `interrupted:backend_restarted`。
- `AI4MS_ANALYSIS_MAX_CONCURRENCY` 控制真正的执行槽；超过槽位的任务保持
  `queued`，不会提前伪装成 `running`。

当前任务实现面向比赛单实例，不支持多进程协调或重启续跑。

## 7. S6-S8 证据约束

- S6 保存 Run、Result Bundle、数据签名、结构化结果和 artifact hash；
- S7 只能引用成功且具有结构化结果的 Run 形成数值判断；
- S8 只有成功 Run 可以作为估计、检验或诊断证据；
- blocked、failed、canceled 或无结构化结果的 Run 只能作为限制和审计说明。

## 8. 安全边界

Local Runner 使用独立临时目录并在完成后删除输入副本，但仍以研究者本机账户启动 Stata，不等同于操作系统级沙箱。受限数据应在机构管理的专用账户、计算节点和防火墙策略下运行。
