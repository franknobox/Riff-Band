# AI4MS / RiffBand

面向管理科学（MS）的垂直 AI 科研工作台：从研究想法、文献和设计，到分析、证据、可交互报告与复现交付。

> 当前工程已经提供可运行的 S0-S9 十阶段浏览器工作台、FastAPI、SQLite 项目状态、不可变 revision、人工门禁、领域画像、Stata BYOL Runner、Claim-Evidence 审核、HTML/Word/PDF/Stata 复现包交付和 Docker 基础文件。现有 CLI、MCP、Agent Runtime 与研究流水线继续作为工程基础。

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

S0 会并列生成可比较的问题候选与诊断，由研究者选择并绑定候选集指纹；S1 的模型检索计划需人工批准后才能自动执行。智能体找到的文献和数据研究先进入候选队列，研究者核对、修改并批准后生成 `EVLIB_*` 权威证据；综述、主张与参考文献只读取 active 权威记录。S2 构建理论，S3-S5 从方法、数据源和公式库形成研究设计、数据合同与分析计划；方法与公式也支持联网候选、人工审核、人工新建和版本化修改。S6 支持 `.dta` 上传、资产登记、SHA-256、元信息读取，并通过 HMAC 签名 Run Bundle 连接研究者本机 Stata Local Runner，回收结构化结果、数据签名、日志和表图；S7 生成受 Run 证据约束的稳健性矩阵；S8 形成主张、证据、假设、机制、异质性和反证图谱；S9 只从 G4 已批准主张与 active 权威论文、数据研究生成可编辑分节正文，每篇 `paper_id` 必须绑定 `EVLIB_*`，数据研究直接使用 `EVLIB_*`，通过引用双向对应和逻辑闭环质量门后，确定性导出可交互 HTML、质量报告、manifest、可编辑 DOCX、固定版 PDF、图表、Mermaid 源码、独立 Stata 复现包和 ZIP 研究包 v2。十个阶段批准前都执行结构契约校验，S1 还必须具有真实检索快照和论文记录。

所有模型阶段草稿、智能体回答、知识适配评估和联网发现报告都使用 `ai4ms.ai-report.v1`，包含执行摘要、公开可审计研究依据、来源、资产 ID、限制、人工决定与生成来源；不请求或保存模型私密思维链。

阶段智能体对话支持“自动 / 联网 / 关闭”三种搜索模式。联网时会并行调用 Serper、DuckDuckGo 与开放学术检索源，读取和去重高排名页面，再把编号来源、检索轨迹和快照随回答保存；涉及官方统计指标时可额外调用只读的 Google Data Commons MCP。MCP 未配置或单个检索源失败时，回答会降级并保留失败记录，不会把未取得的材料伪装成来源。

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

## 多格式研究交付

S9 导出中心以同一份结构化研究资产生成可交互 HTML、DOCX、PDF 和完整研究包。HTML 内嵌图表筛选、Claim-Evidence 关系图和 Mermaid 源码，不依赖外部 CDN；Word 用于继续编辑，PDF 用于固定版本与归档。

独立 Stata 复现包包含获批 do-file、运行契约、结构化结果、日志、图表、数据签名、Runner 环境和 manifest。原始 `.dta`、Stata 软件与许可证不进入交付包。

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

开发环境中的浏览器默认直连 `http://127.0.0.1:8000/api/v1`，避免长模型请求经过 Next.js 开发代理。需要连接其他 FastAPI 地址时，在 `src/web/.env.local` 设置 `NEXT_PUBLIC_API_BASE_URL`。Docker 静态前端继续使用同源 `/api/v1`。

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

比赛版本以带浏览器 GUI 的 Docker Web 产品交付。提交方生成私下交付目录：

```powershell
.\scripts\deployment\BUILD_COMPETITION_PACKAGE.ps1 -ValidateOnly
.\scripts\deployment\BUILD_COMPETITION_PACKAGE.ps1
```

评委在交付目录双击 `START_AI4MS.bat`，脚本会加载镜像、启动服务、执行真实 LLM 连通性探针并打开 `http://localhost:8000/`。

SQLite、`.dta` 项目资产和 HTML 报告通过 Docker volume 持久化。比赛专用模型 Key 只放在私下交付目录的 `.env.competition`，不进入 Git 或镜像层；Stata 不进入镜像，Docker 工作台通过配对令牌连接研究者本机的自有许可 Local Runner。

项目没有公网网站。比赛只提交带 GUI 的 Docker 部署包，评委在本机启动后访问 `http://localhost:8000/`。详细说明见 [Docker 部署说明](docs/DEPLOYMENT.md)。

## 文档

- [文档索引与版本口径](docs/README.md)
- [AI4MS 产品定义](docs/PRODUCT.md)
- [当前工程架构](docs/ARCHITECTURE.md)
- [开发、测试与协作](docs/DEVELOPMENT.md)
- [Docker 部署](docs/DEPLOYMENT.md)
- [提示词工程](docs/PROMPT_ENGINEERING.md)
- [Paper-Agent 与 thesis-writer 适配说明](docs/ai4ms/PAPER_AGENT_THESIS_WRITER_ADAPTATION_2026-07-26.md)
- [证据与知识治理方案](docs/ai4ms/EVIDENCE_KNOWLEDGE_GOVERNANCE_V1.md)
- [Stata Local Runner](docs/RUNNER.md)
- [智能体应用设计文档（评委版 HTML）](docs/competition/AI4MS_AGENT_APPLICATION_DESIGN.html)

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
