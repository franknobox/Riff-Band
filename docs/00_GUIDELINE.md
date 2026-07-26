# AI4MS 开发与运行指南

## 1. 当前状态

`ai4ms` 分支处于 AI4MS 工作台改造期。当前代码可以运行 Next.js S0-S9 十阶段浏览器工作台、FastAPI、SQLite revision/审批状态机、S0-S9 阶段模型能力、Stata BYOL Runner、Claim-Evidence 审核和 HTML/ZIP 交付，以及 RiffBand CLI/MCP 与既有研究流水线。

工程基线见 [ai4ms/BASELINE.md](ai4ms/BASELINE.md)。

## 2. 环境

- Python 3.10+
- pip
- Node.js 20.9+
- 可用的 OpenAI-compatible 或 Gemini 模型接口
- 可选的联网检索 key
- SQLite 使用 Python 标准库，作为六天产品的本地事实存储
- FastAPI/Uvicorn 已写入 `pyproject.toml`，作为 Web 工作台的内部后端服务
- Stata 采用用户自有许可的可选 Runner；未发现可执行文件时必须显示 blocked
- PostgreSQL、Redis 和 MinIO 不属于六天单用户产品的依赖

安装当前项目：

```powershell
pip install -e .
```

本地配置：

```powershell
Copy-Item .env.example .env
Copy-Item aorchestra.yaml.example aorchestra.yaml
```

密钥只能写入本地 `.env` 或受管 secret manager，不得提交到 Git、文档、日志、测试 fixture 或 prompt 示例。

## 3. 当前兼容入口

终端 1 启动 FastAPI：

```powershell
ai4ms-web
```

终端 2 启动 Next.js 十阶段工作台：

```powershell
cd src/web
npm ci
npm run dev
```

打开 `http://localhost:3000/`；OpenAPI 位于 `http://localhost:8000/docs`，健康检查既可访问 FastAPI 的 `http://localhost:8000/healthz`，也可通过 Next.js 代理访问 `http://localhost:3000/healthz`。

启动 CLI：

```powershell
riffband
```

示例：

```text
/research 企业生成式AI采用与创新绩效 --depth=deep
/research 低碳物流与供应链优化 --mode=visual --depth=deep --format=html
```

启动 MCP：

```powershell
riffband-mcp --config aorchestra.yaml
```

当前命令和参数在迁移期保持兼容。新的产品对象和 API 必须通过 legacy adapter 接入，不能直接破坏现有 `/research` 和 MCP 调用。

目标产品入口是十阶段 Web 工作台。首屏直接进入项目，不建设营销页面；新的阶段能力必须接入 `ProjectService` 和 revision 状态机。CLI/MCP 的研究能力将在后续 adapter 中复用该项目上下文，不能长期维护平行状态。

## 4. AI4MS 实现原则

### 研究协议优先

研究步骤读取版本化 ResearchProtocol，不从历史聊天中猜测关键研究选择。未知字段保留为 `needs_input`，不得自动补全为用户决定。

### 证据优先

重要陈述必须绑定 paper、data、run、artifact 或人工审查证据。向量检索和 LLM 输出只能产生候选，不能成为事实来源。

### 人工审批

Agent 只能创建草稿、revision patch 和 issue。G0-G5 由独立 Approval Service 执行，批准绑定具体 revision 与 hash。

### 不可变 revision

研究资产通过新 revision 修改。论文元数据快照、原始数据、原始日志和运行数值不可直接编辑，只能更正来源、添加 annotation 或创建新 Run。

### 确定性控制

DOI、权限、hash、schema、状态机、统计计算、许可证和代码策略使用确定性程序。LLM 只做需要语义判断的候选生成与解释。

### 可复现性

Run 必须记录 protocol version、代码 commit、环境、参数、seed、输入输出 hash 和 lineage。固定输入、代码与环境的重放结果必须在约定容差内一致。

### 多学科领域画像

课题词、查询扩展、抽取字段、方法假设和 Gate 必须来自 DomainProfile 或 Registry。禁止在通用 pipeline 中加入某个具体课题的关键词加分和固定聚类。

### 将可视化报告作为产品视图

HTML 报告只能渲染结构化、版本化对象。图表和表格不得重新计算或覆盖底层数值，关键元素必须能回到 evidence、artifact、revision 和 approval。

### 十阶段完整性

S0-S9 共享同一个 `ProjectState`。每个阶段都必须实现读取当前资产、生成 AI 草稿、人工编辑、批准/退回、保存状态和进入下一步；不能用十张互不相连的静态页面冒充工作台。

### 本地优先产品

六天版本使用 FastAPI、SQLite 和本地 artifact 目录交付完整单用户产品。服务接口必须保留迁移到 PostgreSQL、对象存储和队列的边界，但不得为未来基础设施推迟当前十阶段闭环。

## 5. Schema 与数据契约

第一批契约来自：

- `research_protocol.schema.json`
- `related_research_report.schema.json`
- `approval_record.schema.json`
- `artifact_manifest.schema.json`
- `claim_evidence.schema.json`
- `stata_run.schema.json`

位置：[02_knowledge_bases/schemas](refer/AI4MS-DevPack_v0.3/02_knowledge_bases/schemas)。

实现前必须先统一以下问题：

- ResearchProtocol 草案不能强制 `human_approved=true`；
- 统一 TopicBrief、Protocol 和 Report 的研究目标枚举；
- 只保留一个权威 Approval Service，避免 inline approval 绕过；
- Schema、Pydantic、OpenAPI、SQL 和示例对象使用同一状态与 ID 语义。

## 6. 测试

当前基线命令：

```powershell
pytest -q -p no:cacheprovider
```

AI4MS 新增测试至少覆盖：

- 项目重启后十阶段状态、资产和审批能够恢复；
- 未批准关键上游步骤时不能进入下一正式状态；
- 三个跨题型 benchmark 无领域串扰；
- 任一检索后端失败时其他后端仍返回并保存 provenance；
- DOI、题名、作者、年份去重和版本关系；
- PaperCard 字段证据等级、locator 和 unknown；
- Agent 自批、过期 hash、缺少会签和越权工具被拒绝；
- 上游语义修改准确失效下游审批；
- 无 G3、危险 Stata 命令、越界路径和许可超额被阻塞；
- HTML 报告中的核心结论、图表和数字可以回溯。

验收编号和阈值见 [ACCEPTANCE_TESTS.md](refer/AI4MS-DevPack_v0.3/05_roadmap/ACCEPTANCE_TESTS.md)。

## 7. 生产增强边界

- 不先移动或重写整个 runtime；
- 不把更多 Agent 数量当作质量提升；
- 不上 Kubernetes、Neo4j、Spark 或 JupyterHub；
- 不接入未明确许可的付费数据库和全文；
- 不在正式 Run 中动态安装任意包或 ado；
- 不把摘要抽取描述为全文证据。
- 不在六天版本实现组织级登录、多租户、实时协作、四眼会签和云端 Stata 托管。

这些边界只延期生产级规模和治理能力，不得删除九个用户步骤中的 Web 交互、持久化、人工决定、Runner 状态、证据关联或导出功能。

## 8. Docker 交付约定

最终部署包必须包含：

- `Dockerfile`：构建 FastAPI、静态 Web 和运行时依赖；
- `.dockerignore`：排除 `.env`、`.git`、缓存、`workspace` 和本地受限文件；
- `docker-compose.yml`：声明端口、健康检查、环境变量和持久化卷；
- `docs/DEPLOYMENT.md`：镜像构建、启动、升级、数据目录和故障排查；
- 容器 smoke test：检查 `/healthz`、`/` 和 GUI 最小项目流程。

目标调用方式：

```powershell
docker build -t ai4ms-workbench:competition .
docker run --rm -p 127.0.0.1:8000:8000 --env-file .env -v ai4ms-data:/app/data ai4ms-workbench:competition
```

浏览器访问 `http://localhost:8000` 使用 GUI。`/api/v1` 只服务同一产品的前端和开发调试。容器进程内部监听 `0.0.0.0` 以适配 Docker 网络，宿主机端口只绑定 `127.0.0.1`，项目不提供公网网站。

API Key、Stata 许可证和受限数据不得写入 Docker layer、Compose 文件、示例或镜像内置数据库。Stata Runner 地址与认证只能在运行时配置。
