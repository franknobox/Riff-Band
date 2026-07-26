# AI4MS 开发指南

## 1. 环境

- Python 3.10 及以上，推荐 3.12；
- Node.js 20.9 及以上；
- npm；
- Docker 仅在构建提交镜像时需要；
- Stata 仅在验证真实 S6 执行时需要，且必须由用户或机构合法提供。

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

默认使用 DeepSeek V4 Pro，并在请求失败时回退到 V4 Flash：

```text
AI4MS_MODEL=deepseek-v4-pro
AI4MS_FALLBACK_MODELS=deepseek-v4-flash
AUTOENV_OPENAI_API_KEY=...
AUTOENV_OPENAI_BASE_URL=https://api.deepseek.com
AUTOENV_OPENAI_MODELS=deepseek-v4-pro,deepseek-v4-flash
```

不要提交 `.env`、API Key、许可证、用户数据或本地 `aorchestra.yaml`。

## 2. 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

前端：

```powershell
Set-Location src/web
npm ci
```

## 3. 本地启动

终端一：

```powershell
ai4ms-web
```

FastAPI 地址为 `http://127.0.0.1:8000`。

终端二：

```powershell
Set-Location src/web
npm run dev
```

浏览器打开 `http://127.0.0.1:3000`。Next.js 默认把 `/api/v1` 和 `/healthz` 转发到 `8000`。需要修改地址时复制 `src/web/.env.local.example` 并设置 `AI4MS_API_INTERNAL_URL`。

## 4. 常用检查

后端：

```powershell
python -m pytest -q
```

前端：

```powershell
Set-Location src/web
npm run lint
npm run build
```

Docker 静态导出：

```powershell
$env:AI4MS_STATIC_EXPORT="1"
npm run build
```

提交前至少检查：

```powershell
git diff --check
git status --short
```

## 5. 目录职责

- 产品后端新增代码优先放入 `src/ai4ms` 的现有子域；
- 前端页面、交互和类型化 API 客户端位于 `src/web`；
- 通用 Agent Runtime 留在 `src/base`、`src/agents` 和 `src/orchestration_tools`；
- 兼容研究工具留在 `src/project` 和 `src/research`；
- 不为单一函数创建新顶层目录；
- API 路由只处理 HTTP，业务规则进入 service；
- SQLite 层不调用 API、模型或前端。

## 6. 数据契约

- 后端 Pydantic 模型和 OpenAPI 是前后端契约来源；
- 前端 `src/web/lib/api.ts` 必须同步状态和响应类型；
- 阶段规范内容不能被 `_workspace` 编辑器覆盖；
- Run、论文、Claim 和 Evidence 的引用必须使用项目内真实 ID；
- 正式数值只来自校验后的 Result Bundle；
- 修改阶段结构时必须增加或调整契约测试。

## 7. 协作

- `ai4s` 是当前集成分支，`ai4ms` 用于队友并行开发时需先同步；
- 功能分支保持单一主题，合并前先更新目标分支；
- 前端设计者尽量只修改 `src/web`，工程负责人维护公共 API、状态机、Runner 和持久化；
- 两人同时修改 `page.tsx` 或 `globals.css` 前先划分组件区域；
- 不覆盖与当前任务无关的工作区改动；
- 重大 Schema、Runner 和 Gate 修改必须有人审阅。

建议提交格式：

```text
feat(scope): ...
fix(scope): ...
docs(scope): ...
test(scope): ...
chore(scope): ...
```

## 8. 仓库卫生

禁止提交：

- `.env`、密钥、许可证和本地配置；
- `workspace/`、用户 `.dta`、运行日志和导出结果；
- `.venv/`、`node_modules/`、`.next/`、`out/`、`build/`；
- `__pycache__/`、`.pytest-*` 和临时测试目录；
- 重复格式的同一文档和一次性审计报告。

需要保留的决策进入正式文档；临时排查过程进入 Issue、PR 或提交信息。

## 9. 当前工程重点

后续重构优先级：

1. 把证据库和智能体建议中的展示数据替换为真实项目资产；
2. 将 `src/web/app/page.tsx` 拆成独立工作区组件；
3. 合并 `globals.css` 中重复的历史样式层；
4. 在装有 Docker 和合法 Stata 的机器完成最终端到端演示；
5. 比赛结束后再评估任务队列、多用户和生产隔离。
