# AI4MS / RiffBand

面向管理科学（MS）的垂直 AI 科研工作台：从研究想法、文献和设计，到分析、证据、HTML 可视化报告与成果交付。

> 当前工程已经提供可运行的 S0-S9 十阶段浏览器工作台、FastAPI、SQLite 项目状态、不可变 revision、人工门禁、领域画像、Stata BYOL Runner、Claim-Evidence 审核、HTML/ZIP 交付和 Docker 基础文件。现有 CLI、MCP、Agent Runtime 与研究流水线继续作为工程基础。

[文档索引](docs/README.md) | [产品定义](docs/PRODUCT.md) | [当前架构](docs/ARCHITECTURE.md) | [开发指南](docs/DEVELOPMENT.md)

## 产品定位

AI4MS 不是自动论文生成器。它更像一名严谨的科研项目经理和研究助理，帮助研究者从一个不成熟的想法出发，完成已有研究检索、选题判断、研究设计、数据与方法规划、分析管理、证据核查、可视化报告和复现交付。

产品形态可以理解为“MS 领域的轻量玻尔”：把文献、研究过程、方法数据、科研计算和成果组织在同一个工作台中，并针对管理科学强化研究设计、Stata、证据边界和人工决定。AI4MS 与玻尔不存在隶属关系，也不复制其未公开能力。

核心工作流：

```text
研究想法
  -> S0. 问题识别
  -> S1. 文献综述
  -> S2. 理论构建
  -> S3. 研究设计
  -> S4. 数据与变量
  -> S5. 识别与检验
  -> S6. 结果分析
  -> S7. 稳健性检验
  -> S8. 机制与异质性
  -> S9. 结论与政策含义
```

## 当前实现

S0-S9 十阶段已经进入同一个项目工作台，当前基础能力包括：

- 创建、读取和切换科研项目；
- 查看十阶段状态并逐步解锁；
- 编辑和保存结构化阶段资产；
- 为每次修改生成不可变 revision 和 SHA-256 hash；
- 人工执行批准、退回修改和阻塞决定；
- 上游修改后自动使下游状态失效，同时保留历史审批；
- 通过 SQLite 在重启后恢复项目；
- 通过浏览器 GUI 使用完整产品；FastAPI 作为前后端内部服务层。

当前 S0-S9 均支持真实模型生成。S0-S1 与 S7-S8 已接入基于论文 **AOrchestra: Automating Sub-Agent Creation for Agentic Orchestration** 的动态 SubAgent 编排：S0-S1 并行执行边界澄清、检索侦察、反向检索和综述，S7-S8 并行执行稳健性、负结果、Claim-Evidence 与过度主张审查。S7-S8 的 SubAgent 只有既有项目资产只读权限，不能联网或启动 Runner；AO 报告还必须经过阶段 Pydantic 契约和 ID 白名单，才能保存为 `needs_review` 的 agent revision。

S1 可执行多源检索、去重与快照，S2 构建理论，S3-S5 从方法、数据源和公式库形成研究设计、数据合同与分析计划；S6 支持 `.dta` 上传、资产登记、SHA-256、元信息读取，并通过 HMAC 签名 Run Bundle 连接研究者本机 Stata Local Runner，回收结构化结果、数据签名、日志和表图；S7 生成受 Run 证据约束的稳健性矩阵；S8 形成主张、证据、假设、机制、异质性和反证图谱；S9 只从 G4 已批准主张生成结论，并确定性导出 HTML 报告、manifest 和 ZIP 研究包。十个阶段批准前都执行结构契约校验，S1 还必须具有真实检索快照和论文记录。

保留的研究引擎已经支持多来源文献检索、结构化研究产物和独立 HTML 可视化报告。Stata Runner 已接入本地/机构 BYOL 批处理边界；Claim-Evidence 审核和成果导出已进入同一项目、revision 与 Gate 状态机。

## 人机协作

AI 只能创建草稿、patch、问题和建议，不能批准自己的输出。G0-G5 人工门禁必须由 `human` 身份执行。

所有可编辑研究资产都会产生不可变 revision；审批绑定具体 revision 和 hash。上游选题、设计、数据或分析计划发生变化时，受影响的下游审批自动失效，但历史决定不会被删除。

## 多学科泛用性

AI4MS 首先服务管理科学，但不会把某个课题或单一方法写死在通用流程里。统一 `DomainProfile` 支持以下研究泳道：

- 实证与因果研究；
- 解析建模与优化；
- 预测与计算研究；
- 行为、实验与定性研究；
- 系统综述与设计科学。

领域差异通过 profile、方法卡、数据卡和 Gate Registry 注入，通用 Agent Runtime、资产版本、审批和证据模型保持稳定，为后续扩展到其他科研学科保留接口。

## HTML 可视化报告

RiffBand 已支持独立 HTML 研究报告、响应式排版、目录、表格和 ECharts 图表。AI4MS 保留并升级这项能力，用于展示检索范围、研究流派、共识争议、候选空白、数据方法可行性、人工决定和审计记录。

HTML 报告是成果交付阶段的一等产物，不属于需要清理的旧工程内容。

## 工程基础

RiffBand 基于论文 [AOrchestra: Automating Sub-Agent Creation for Agentic Orchestration](https://arxiv.org/abs/2602.03786) 的动态子智能体思想开发。原论文将动态创建的智能体抽象为：

```text
<Instruction, Context, Tools, Model>
```

RiffBand 在此基础上增加了固定研究流水线、工具权限、并发委派、CLI/MCP 接口、结构化产物和 HTML 报告。AI4MS 继续复用这些底层能力，并把原有课题硬编码替换为领域画像和研究协议驱动的服务。

## 安装与运行

安装项目：

```powershell
pip install -e .
```

创建本地配置：

```powershell
Copy-Item .env.example .env
Copy-Item aorchestra.yaml.example aorchestra.yaml
```

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

打开以下地址：

- Next.js 工作台：`http://localhost:3000/`
- 后端接口（仅开发调试）：`http://localhost:8000/api/v1`
- OpenAPI（仅开发调试）：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/healthz`

Next.js 默认把同源 `/api/v1` 和 `/healthz` 代理到 `http://127.0.0.1:8000`。需要连接其他 FastAPI 地址时，在 `src/web/.env.local` 设置 `AI4MS_API_INTERNAL_URL`。

兼容 CLI 和 MCP 入口：

```powershell
riffband
riffband-mcp --config aorchestra.yaml
```

兼容研究命令：

```text
/research 企业采用生成式AI对创新绩效的影响 --depth=deep
/research 低碳物流与供应链优化 --mode=visual --depth=deep --format=html
```

## Docker 交付

比赛版本以带浏览器 GUI 的 Docker Web 产品交付：

```powershell
docker compose up --build
```

SQLite、`.dta` 项目资产和 HTML 报告通过 Docker volume 持久化。模型与检索 Key 在运行时注入；Stata 不进入镜像，Docker 工作台通过配对令牌连接研究者本机的自有许可 Local Runner。

项目没有公网网站。比赛只提交带 GUI 的 Docker 部署包，评委在本机启动后访问 `http://localhost:8000/`。详细说明见 [Docker 部署说明](docs/DEPLOYMENT.md)。

## 文档

- [文档索引与版本口径](docs/README.md)
- [AI4MS 产品定义](docs/PRODUCT.md)
- [当前工程架构](docs/ARCHITECTURE.md)
- [开发、测试与协作](docs/DEVELOPMENT.md)
- [Docker 部署](docs/DEPLOYMENT.md)
- [提示词工程](docs/PROMPT_ENGINEERING.md)
- [Stata Local Runner](docs/RUNNER.md)
- [原始产品介绍](docs/reference/AI4MS_非技术产品介绍书.md)

## 产品边界

- 不承诺自动发现绝对原创课题；
- 不伪造论文、DOI、数据、统计量、实验或审稿记录；
- 不绕过付费数据库、版权、数据许可、隐私控制和软件许可；
- 不把相关性、显著性或模型复杂度自动等同于因果和贡献；
- 不让 AI 越过选题、设计、数据、分析、结论和发布审批；
- 不允许写作层隐藏失败诊断、负结果和反证。

## 许可证与引用

本项目保留原始 Apache 2.0 `LICENSE`。使用底层编排思想时，请引用原论文：

```bibtex
@misc{ruan2026aorchestra,
  title={AOrchestra: Automating Sub-Agent Creation for Agentic Orchestration},
  author={Jianhao Ruan and Zhihao Xu and Yiran Peng and Fashen Ren and
          Zhaoyang Yu and Xinbing Liang and Jinyu Xiang and Yongru Chen and
          Bang Liu and Chenglin Wu and Yuyu Luo and Jiayi Zhang},
  year={2026},
  eprint={2602.03786},
  archivePrefix={arXiv},
  primaryClass={cs.AI},
  url={https://arxiv.org/abs/2602.03786}
}
```
