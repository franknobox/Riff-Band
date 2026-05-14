# AOrchestra v1 PLAN — Research Mode

> 方案构想文档 | 2026-05-06

## 一、核心定位

AOrchestra 是一个**可被外部 Agent 调用的 Research Skills + 编排引擎**。

定位三角：**文献检索 · 观点生成与辩论 · 结构化输出**

```
┌──────────────────────────────────────────────┐
│  AOrchestra Research Mode                     │
│                                               │
│  ① 文献检索 + 知识综合                        │
│     真实引用，证据链，不编造                    │
│                                               │
│  ② 多 Agent 观点生成 + 辩论（★ 核心亮点）      │
│     3-5 个独立视角 SubAgent 并行，跨模型协作    │
│                                               │
│  ③ 结构化研究报告输出                          │
│     科研 → LaTeX 文献综述                      │
│     行业 → HTML 调研报告                        │
│                                               │
│  ④ 不绑定模型，有成本优势                     │
│     (MiniMax/DeepSeek/Gemini 自由组合)        │
└──────────────────────────────────────────────┘
```

### 为什么不做实验和论文全文

不同学科的实验环境差异巨大（CV 要 GPU + PyTorch，NLP 要 TPU，系统要 Linux 内核），做一套通用实验框架的工程量远超 Agent 编排本身。一项能稳定产出结构化文献综述 + 研究空白/未来方向 + 多视角辩论记录的系统，比赛展示效果强于"理论上能发论文但各种报错"的系统。

AO 的边界清晰：**聚焦信息收集、推理与结构化输出**。实验留给外部 Agent，论文排版留给 Overleaf。

### 竞争力分析

| | Codex + Research Skills | AOrchestra Research Mode |
|---|---|---|
| Skills 形式 | 纯 MD 模板，靠 LLM 自由发挥 | 硬流程 + 每步闸门校验，执行结果可预期 |
| 多 Agent | 弱（fork session，同模型） | 强（SubAgent 独立配置 I,C,T,M，跨模型并行） |
| 模型选择 | 绑定 GPT-5 系 | 任意组合（MiniMax 执行 + Gemini 审稿 + DeepSeek 写初稿） |
| 单次研究成本 | ~$15-50 | **~$1-3**（10-50 倍差距） |
| 稳定性 | 依赖 prompt 质量 | 程序化 pipeline + 闸门保证 |
| 角色分工 | 模糊 | 结构化多视角（Innovator/Pragmatist/Theorist/...） |

### 为什么不吃 Agent 性能

AOrchestra 不替代外部 Agent——作为 MCP tool 被调用。外部 Agent 越强，组合越强。**我们不做最优 Agent，我们让任何 Agent 都能做复杂研究**。

### 参考项目对比

| 项目 | Stars | 定位 | 核心方法 | Agent 内核 | 我们借鉴什么 |
|------|-------|------|---------|-----------|-------------|
| [**STORM**](https://github.com/stanford-oval/storm) (Stanford) | ⭐28.2k | 知识策展系统 | 多视角提问 + 模拟对话 | 无 | 视角引导提问 ← 多 Agent 辩论 |
| [**GPT Researcher**](https://github.com/assafelovic/gpt-researcher) | ⭐26.9k | Deep Research Agent | Planner + 执行 Agent 并行 | 无 | 同类架构，已有 MCP |
| [**Open Deep Research**](https://github.com/dzhng/deep-research) | ⭐18.9k | 极简递归搜索 | 广度×深度递归，<500 行 | 无 | 极简设计理念 |
| [**AI Scientist v2**](https://github.com/SakanaAI/AI-Scientist-v2) (SakanaAI) | ⭐6.1k | 学术鼻祖 | BFTS 树搜索 | 无 | 多路径并行探索 |
| [**AutoResearchClaw**](https://github.com/aiming-lab/AutoResearchClaw) | ⭐11.9k | 全自动 pipeline | 23 阶段线性流程 | 无 | 工作流步骤设计 |
| [**ARIS**](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) | ⭐8.1k | 科研 skills 工具箱 | 交叉模型 review | 无 | Skills 接入机制 |
| [**awesome-ai-research-writing**](https://github.com/Leey21/awesome-ai-research-writing) | ⭐21.8k | Prompt 资源合集 | 论文写作模板 | 无 | 写作 prompt 参考 |
| [**Sibyl**](https://github.com/Sibyl-Research-Team/sibyl-research-system) | ⭐238 | 全自主 AI 科学家 | 双循环自进化 | Claude Code | 自进化系统 |
| [**Dr. Claw**](https://github.com/OpenLAIR/dr-claw) | ⭐925 | 研究工作站 GUI | 多 Agent 调度器 | 无 | 产品化 UI 参考 |
| [**ResearchArena**](https://github.com/YouAreSpecialToMe/ResearchArena) | ⭐32 | 科研能力评测 | Benchmark | 无 | 输出质量评分 |
| **AOrchestra** | — | **通用 Agent 编排引擎** | **动态 SubAgent 合成 × MCP** | **有** | — |

STORM 的"多视角提问"和 AO 的多 Agent 辩论在理念上同源——都是让不同视角互相挑战。AO 的差异在于**每个视角可用不同模型 (I,C,T,M)**，而 STORM 受限于同模型。

## 二、Research Mode 工作流

**4 个阶段、9 个步骤**。聚焦文献检索、轻量论文阅读、观点生成与结构化输出。

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: 文献检索 (Literature Search)                       │
│                                                             │
│  Step 1  课题拆解        decompose_topic                    │
│  Step 2  多源顺序检索    literature_search  检索式驱动批量记录 │
│  Step 2.5 论文轻量阅读   paper_enrichment  摘要/网页/PDF抽取 │
│  Step 3  多视角知识综合  knowledge_synthesis ★ 跨角度交叉对比 │
│                                                             │
│ Phase 2: 观点生成与辩论 (Claim Formation)                   │
│                                                             │
│  Step 4  观点生成       claim_generation  核心亮点            │
│  Step 5  观点辩论       claim_debate     ★ 多视角评审        │
│                                                             │
│ Phase 3: 结构化写作 (Structured Writing)                    │
│                                                             │
│  Step 6  大纲构建        outline_build                      │
│  Step 7  章节撰写        section_draft                      │
│                                                             │
│ Phase 4: 质量审查 + 输出 (Review & Export)                  │
│                                                             │
│  Step 8  多 Agent 审稿   multi_agent_review ★ 多视角评审     │
│                                                             │
│  产出:   科研任务 → paper.tex (LaTeX 文献综述)               │
│          行业任务 → report.html (HTML 调研报告)              │
│          papers.jsonl / paper_notes.jsonl / findings.jsonl   │
│          debate_log.md                                      │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 关键创新：全流程多 Agent 并行（★）

区别于 AutoResearchClaw 的固定 6 角色——AO 的**每个步骤的 SubAgent 角色是根据该步骤的实际内容动态合成的**，从 Phase 1 到 Phase 4 全流程都有多 Agent 参与：

- **Step 2 (文献检索)**：MainAgent 优先解析 Step 1 在 scratchpad 中生成的 `检索式`，将其组合成学术 query，并启动单个检索任务。该任务先调用 `batch_literature_search`，按工具顺序串行兜底（Semantic Scholar → arXiv → Crossref → DBLP），检索到论文立即写入 `papers.jsonl`，避免 SubAgent 逐篇记录导致步数耗尽；随后补充 `findings.jsonl` 和检索覆盖说明。
- **Step 2.5 (论文轻量阅读)**：不做完整向量库，先基于摘要、论文网页或本地 PDF 对高相关论文抽取 problem、method、scenario、main_findings、limitations、relevance_to_topic 和 evidence_source，写入 `paper_notes.jsonl`
- **Step 3 (知识综合)**：多 Agent 从不同分析角度（方法论、实验结果、理论框架、应用场景）交叉对比检索结果，相互印证和质疑，识别研究空白和矛盾点
- **Step 4 (观点生成)**：MainAgent 同时创建 3-5 个 SubAgent，每个持一种独立综述视角（方法论、应用场景、证据强度、争议点、跨学科），不同视角可用不同模型，独立生成研究空白、未来方向、可检验研究问题和综述观点后汇总
- **Step 5 (观点辩论)**：将各视角的观点发送给其他视角 Agent 进行批判性评审，重点检查证据覆盖、创新性、相关性、方法局限和优先级。**交叉模型 + 交叉视角 = 打破单一模型的综述盲区**
- **Step 8 (审稿)**：多审稿 Agent 从方法正确性、逻辑完整性、表达清晰度独立评审

### 2.2 输出格式：按任务类型区分

| 任务类型 | 输出格式 | 场景 |
|---------|---------|------|
| 科研任务（MCP 研究状态） | **LaTeX** 文献综述 (paper.tex + references.bib) | 会议/期刊投稿前的 survey 工作 |
| 行业调研（普通任务状态） | **HTML** 结构化调研报告 | 产业分析、商业决策 |

## 三、Prompt 工程

从 awesome-ai-research-writing 中吸收经过验证的 prompt 作为**可选风格化预设**，不做完整的模板库。核心复用几类：

- 学术润色（中/英）、去 AI 味
- 审稿视角审视
- 逻辑一致性检查

SubAgent 在生成内容时自动匹配对应风格的 prompt 作为 Context 的一部分。不过度包装——就是"好的 prompt 模板直接拿来用"。

## 四、Skills 机制

吸收 ARIS 的 skill 理念，但只集成我们能运行的部分。

### 4.1 集成策略

从 ARIS 60+ skills 中筛选 AO 能直接用的（文献搜索、观点生成、写作润色），对于需要特殊环境的能力（实验执行、GPU 调度、Docker 沙箱），不强行移植，在 Skill 文件中显式标注 `requires: external`，由调用方 Agent 决定是否执行。

### 4.2 Skill 文件结构

纯 Markdown，零依赖。AO 内置约 8 个核心 skills：

```
skills/
├── literature-search.md      # 多源文献检索
├── knowledge-synthesis.md    # 知识综合与空白识别
├── claim-generation.md       # 研究空白、未来方向与可检验问题生成
├── claim-debate.md           # 多视角观点辩论与优先级评估
├── outline-build.md          # 结构化大纲
├── section-draft.md          # 章节撰写
├── multi-agent-review.md     # 多 Agent 审稿
└── polish/                   # 可选风格化预设
    ├── academic-polish.md    # 学术润色
    └── de-ai.md              # 去 AI 味
```

外部 Agent 通过 MCP 调用时，自动加载匹配的 skill。

## 五、两种运行形态

一个内核，两种状态。当前 CLI Agent 已能完成信息收集、多 Agent 并行、报告输出等研究任务，research mode 在此基础上增加固定流程和闸门校验。

### 普通任务状态

单/多 Agent 模式，MainAgent 自由编排。当前 CLI 的默认形态：

- 报告输出、代码撰写、信息搜集
- 对话式增量研究
- 灵活、短程、无固定流程

### 研究任务状态

走固定长程流程（Phase 1-4），每步有闸门校验。**CLI 和 MCP 均可触发**：

```
CLI 触发:   Riff Band [auto] > /research 研究 XX 问题
MCP 触发:   外部 Agent 调用 aorchestra.research("研究 XX 问题")
```

| | 普通任务状态 | 研究任务状态 |
|---|---|---|
| 触发方式 | 直接对话 | `/research` 命令 或 MCP 调用 |
| 流程控制 | MainAgent 自由编排 | 固定 Phase 序列 + 闸门 |
| 稳定性 | 依赖 LLM 决策质量 | 程序化 pipeline 保证 |
| 适用任务 | 日常问答、写代码、搜信息 | 文献综述、观点辩论、结构化报告 |

## 六、7 天实施路线图

当前已完成：CLI 交互、流式消息、会话持久化、ContentPart 流式文本、Crash 中断、配置/工作区、首次引导。

### Day 1-2: 研究流程内核 + Skills

**状态**: CLI 已稳定，直接进入开发

- [ ] 创建 `src/research/` 模块，实现固定流程状态机
  - Phase 状态枚举 + 步骤调度器
  - 每步闸门：输出物存在 + 非空 + 格式校验
  - 超时 + 失败重试机制
- [ ] 编写 8 个核心 skill MD 文件
  - `skills/literature-search.md` — 多源文献检索
  - `skills/knowledge-synthesis.md` — 知识综合
  - `skills/claim-generation.md` — 研究空白、未来方向与可检验问题生成
  - `skills/claim-debate.md` — 多视角观点辩论与优先级评估
  - `skills/outline-build.md` — 大纲构建
  - `skills/section-draft.md` — 章节撰写
  - `skills/multi-agent-review.md` — 多 Agent 审稿
  - `skills/polish/` — 润色风格预设
- [ ] `/research` slash 命令集成到 shell

### Day 3-4: 多 Agent 并行 + 输出格式

- [ ] Step 4 多 Agent 并行观点生成
  - 复用现有 `delegate_tasks` 机制
  - 每个视角一个 SubAgent，不同 (I,C,T,M)
  - 汇总 + 去重逻辑
- [ ] Step 5 多视角观点辩论
  - 方法论视角生成的观点 → 证据强度视角审稿
  - 应用场景视角生成的观点 → 争议点视角审稿
- [ ] LaTeX 输出模板（NeurIPS 格式）
- [ ] HTML 报告模板（响应式单页）

### Day 5-6: MCP 集成

- [x] 实现最小 MCP Server 入口 (`python mcp_server.py --config aorchestra.yaml`)
- [x] 研究流程封装为 MCP `research` tool
  - 暴露 `research`、`literature_search`、`claim_generation` 等 tool
  - 流式进度推送
- [ ] 与外部 Agent 对接测试（Claude Code / Codex）
- [ ] 生命周期管理：启动 → 执行 → 返回结果 → 清理

### Day 7: 收尾

- [ ] 端到端验证：输入课题 → 文献综述 → 观点辩论 → LaTeX/HTML 输出
- [ ] 多 Agent 并行步骤验证（Step 4-5）
- [ ] README + 文档更新
- [ ] 示例 demo
- [ ] commit & push

## 七、风险与待解决问题

1. **长程稳定性**：12 步、多 Agent 并行 → 容易在某步卡死或超时。需要每步独立超时 + 断点恢复。
2. **成本控制**：多 Agent × 多步 = 大量 LLM 调用。需要 per-step token 预算。
3. **引用真实性**：LLM 编造参考文献是自动科研的痼疾。Step 2 必须用真实 API（Semantic Scholar / arXiv），引用校验必不可少。
4. **实验可复现性**：LLM 生成的实验代码质量不稳定。需要沙箱隔离 + 自动修 bug 机制。
