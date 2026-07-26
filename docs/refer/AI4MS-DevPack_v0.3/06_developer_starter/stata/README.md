# AI4MS Stata Runner Starter

本目录定义 Stata 分析能力的最小开发契约，不包含 Stata 安装包、许可证或第三方 ado。

## MVP 运行方式

1. 用户/机构在本机或受管服务器安装并许可 Stata；
2. AI4MS 注册 Runner Profile，只保存版本、edition、可用席位和健康状态，不保存授权码；
3. G2、G3 通过后，平台生成包含 do-file、Data Contract、输入清单和资源限制的签名 Run Bundle；
4. Runner 做静态策略、变量、许可和席位预检；
5. 使用 Stata batch mode 执行；
6. 上传允许的日志、表图、结果数据和 manifest；
7. 数值产物保持不可变，解释进入人工可编辑的 Claim/Interpretation revision。

## 文件

- `analysis_template.do`：带版本、日志、数据签名、变量预检和基准回归的 do-file 骨架；
- `../examples/stata_run_request.example.json`：运行请求与结果清单；
- `../../02_knowledge_bases/schemas/stata_run.schema.json`：结构化契约；
- `../../03_product/STATA_ANALYSIS_WORKBENCH.md`：完整产品与安全规格。

## 实现接口

```python
class StataRunner:
    async def preflight(self, bundle) -> PreflightReport: ...
    async def submit(self, bundle) -> RunnerJob: ...
    async def cancel(self, job_id: str) -> None: ...
    async def events(self, job_id: str): ...
    async def collect(self, job_id: str) -> StataRunManifest: ...
```

Runner 必须把程序路径、操作系统差异和 batch 参数封装在 adapter 内，API 不接受用户提交任意可执行文件路径。

## 默认阻塞规则

- `shell`、`!`、`winexec` 和外部进程；
- `ssc install`、`net install`、`update all` 等动态安装；
- 未批准的 `python`、`java`、插件或 DLL；
- 任意网络 URL、越界绝对路径和父目录穿越；
- 覆盖原始输入、删除项目外文件；
- G3 未通过、审批 revision/hash 不匹配或许可席位不足。

允许例外时必须使用项目级策略、明确审批人和一次性运行授权，不能仅靠提示词放行。

