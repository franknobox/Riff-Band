"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Download,
  ExternalLink,
  FileText,
  FileType2,
  Globe2,
  PackageCheck,
  RefreshCw,
  Search,
  SendHorizontal,
} from "lucide-react";
import {
  ApiError,
  analysisRunArtifactUrl,
  cancelAnalysisRun,
  createKnowledgeRecord as createApiKnowledgeRecord,
  createStageDraft as createApiStageDraft,
  createProject as createApiProject,
  decideStageSuggestion as decideApiStageSuggestion,
  decideStage as decideApiStage,
  discoverEvidenceCandidates as discoverApiEvidenceCandidates,
  discoverKnowledgeCandidates as discoverApiKnowledgeCandidates,
  deliveryArtifactUrl,
  exportDelivery as exportApiDelivery,
  getAnalysisJob,
  getAnalysisRunResult,
  getDeliveryQuality as getApiDeliveryQuality,
  getDiagnosticRegistry as getApiDiagnosticRegistry,
  getKnowledgeEvaluation as getApiKnowledgeEvaluation,
  getKnowledgeEvaluationJob as getApiKnowledgeEvaluationJob,
  getStageDefinitions as getApiStageDefinitions,
  getStageSuggestions as getApiStageSuggestions,
  getStataRunnerStatus,
  getProject as getApiProject,
  getUserProfile as getApiUserProfile,
  listKnowledgeGovernanceCandidates as listApiKnowledgeGovernanceCandidates,
  listKnowledgeGovernanceRecords as listApiKnowledgeGovernanceRecords,
  listProjects as listApiProjects,
  listAnalysisJobs,
  listStageChat as listApiStageChat,
  listStageRevisions as listApiStageRevisions,
  generateStageSuggestions as generateApiStageSuggestions,
  invokeStageTool as invokeApiStageTool,
  preflightAnalysisRun,
  patchStageAssetSection as patchApiStageAssetSection,
  patchEvidenceRecord as patchApiEvidenceRecord,
  patchKnowledgeRecord as patchApiKnowledgeRecord,
  rerunAnalysis,
  reviewLiteraturePlan as reviewApiLiteraturePlan,
  reviewEvidenceCandidate as reviewApiEvidenceCandidate,
  reviewKnowledgeCandidate as reviewApiKnowledgeCandidate,
  restoreStageRevision as restoreApiStageRevision,
  saveStage as saveApiStage,
  saveStageWorkspace as saveApiStageWorkspace,
  searchLiterature as searchApiLiterature,
  selectProblemQuestion as selectApiProblemQuestion,
  sendStageChat as sendApiStageChat,
  submitAnalysisRun,
  submitKnowledgeEvaluation as submitApiKnowledgeEvaluation,
  uploadDataAsset,
  updateProject as updateApiProject,
  updateUserProfile as updateApiUserProfile,
  type AnalysisPreflight,
  type AnalysisJob,
  type AnalysisRun,
  type ChatSearchMode,
  type EvidenceCandidate,
  type EvidenceLevel,
  type KnowledgeEvaluation,
  type KnowledgeAssetKind,
  type KnowledgeGovernanceCandidate,
  type KnowledgeGovernanceRecord,
  type DiagnosticRule,
  type DeliveryExportRecord,
  type InterfaceTheme,
  type Project as ApiProject,
  type ProjectStage as ApiProjectStage,
  type ProjectSummary as ApiProjectSummary,
  type RunnerStatus,
  type SearchCitation,
  type SearchTrace,
  type StageRevision,
  type StageDefinition as ApiStageDefinition,
  type StageSuggestionSet,
  type StageToolPolicy,
  type SuggestionDecision,
  type StageChatMessage as ApiStageChatMessage,
  type StageWorkspacePayload,
} from "@/lib/api";
import {
  ApprovalGatePage,
  AssetVersionPage,
  ConsistencyCheckWorkspace,
  createCheckIssues,
  createStageDraft as createLocalStageDraft,
  EvidenceRecordPage,
  FormulaRecordPage,
  IssueRemediationPage,
  MethodRecordWorkspace,
  ProjectOverviewPage,
  ProjectWizard,
  StageDecisionsWorkspace,
  StageDraftWorkspace,
  type AssetVersionSnapshot,
  type DeepRoute,
  type EvidenceRecord,
  type FormulaRecord,
  type MethodRecord,
  type ResearchProject,
  type StageDraft,
} from "./deep-workspaces";

type ViewKey = "journey" | "evidence" | "methods" | "runs" | "approvals";
type DetailPanel = {
  eyebrow: string;
  title: string;
  description: string;
  rows?: { label: string; value: string }[];
  bullets?: string[];
  code?: string;
};
type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  time: string;
  model?: string;
  totalTokens?: number;
  citations?: SearchCitation[];
  search?: SearchTrace | null;
  error?: boolean;
};
type ChatSyncTarget = "content" | "summary" | "evidenceNote" | "decision";
type ChatSyncMode = "append" | "replace";

const stages = [
  { key: "problem", id: "S0", name: "问题识别", agent: "Topic Agent", gate: "G0", status: "done", output: "课题简报与已有研究报告", decision: "确认边界、改写问题或暂停课题", check: "候选空白完成反向检索" },
  { key: "literature", id: "S1", name: "文献综述", agent: "Literature Agent", gate: "覆盖检查", status: "done", output: "检索协议、论文卡与证据流派", decision: "修改检索式并决定纳入/排除", check: "核心结论全部可回溯" },
  { key: "theory", id: "S2", name: "理论构建", agent: "Theory Agent", gate: "G1 前置", status: "done", output: "理论图、研究问题与竞争解释", decision: "选择理论并确认贡献边界", check: "问题可证伪且存在竞争解释" },
  { key: "design", id: "S3", name: "研究设计", agent: "Design Agent", gate: "G1", status: "active", output: "研究协议、设计备忘录与假设表", decision: "选择主备设计、接受风险并送审", check: "estimand、识别假设和停止条件完整" },
  { key: "data", id: "S4", name: "数据与变量", agent: "Data Agent", gate: "G2", status: "todo", output: "数据合同、变量表与伦理清单", decision: "确认数据权限、代理变量和运行位置", check: "许可、隐私和关键口径通过" },
  { key: "identification", id: "S5", name: "识别与检验", agent: "Analysis Plan Agent", gate: "G3", status: "todo", output: "分析计划、模型卡与代码计划", decision: "逐项修改并冻结主次分析", check: "计划与代码逐项对应" },
  { key: "analysis", id: "S6", name: "结果分析", agent: "Stata Analyst", gate: "G3 后运行", status: "todo", output: "do-file、运行日志与结果产物", decision: "审代码、批准运行和选择重跑分支", check: "获批代码与数据签名一致" },
  { key: "robustness", id: "S7", name: "稳健性检验", agent: "Robustness Agent", gate: "G4 前置", status: "todo", output: "稳健性矩阵与复现报告", decision: "追加检验或接受失败影响", check: "关键失败项不可被隐藏" },
  { key: "evidence", id: "S8", name: "机制与异质性", agent: "Evidence Agent", gate: "G4", status: "todo", output: "主张、证据边与解释备忘录", decision: "改写、降级或撤回主张", check: "每条主张连接结果与反证" },
  { key: "delivery", id: "S9", name: "结论与政策含义", agent: "Writing Agent", gate: "G5", status: "todo", output: "论文草稿、答复信与发布包", decision: "重写、披露并批准发布", check: "引用、数字与复现包一致" },
] as const;

const agentProfiles = [
  { mission: "收敛研究边界、验证问题价值并形成可执行的选题简报。", skills: ["研究空白", "反向检索", "可行性"], starters: ["帮我缩小研究边界", "检查这个问题是否已有充分研究", "给出三个可证伪的问题版本"] },
  { mission: "构建可复核检索协议，整理文献流派、分歧与证据缺口。", skills: ["检索式", "论文卡", "研究流派"], starters: ["生成中英文检索式", "总结主要研究流派", "寻找可能推翻当前结论的文献"] },
  { mission: "连接理论机制、竞争解释与可检验假设。", skills: ["理论机制", "竞争解释", "假设"], starters: ["比较三个候选理论", "把机制写成可检验假设", "指出当前理论链条的薄弱点"] },
  { mission: "把研究问题转化为 estimand、识别策略和可执行研究协议。", skills: ["研究设计", "识别假设", "变量口径"], starters: ["比较固定效应与双重差分", "检查识别假设", "完善主设计与备选设计"] },
  { mission: "设计数据合同、变量字典、数据质量与伦理检查。", skills: ["数据源", "变量字典", "许可伦理"], starters: ["列出可用数据来源", "设计核心变量口径", "检查数据许可与隐私风险"] },
  { mission: "把研究设计冻结为分析计划、模型公式与代码任务。", skills: ["分析计划", "模型公式", "功效检验"], starters: ["生成分析计划目录", "检查模型与假设是否对应", "列出必须预注册的检验"] },
  { mission: "协作编写和审查 Stata do-file，解释日志与运行产物。", skills: ["Stata", "do-file", "结果诊断"], starters: ["生成基准回归 do-file", "解释这段 Stata 日志", "检查聚类标准误设置"] },
  { mission: "建立稳健性矩阵，主动暴露失败检验和结论边界。", skills: ["稳健性", "安慰剂", "敏感性"], starters: ["生成稳健性检验矩阵", "设计安慰剂检验", "如何解释失败的稳健性结果"] },
  { mission: "把主张连接到文献、模型结果、反证与适用边界。", skills: ["证据图谱", "机制检验", "异质性"], starters: ["检查每条主张的证据链", "规划机制检验", "识别需要降级的结论"] },
  { mission: "协作形成论文、审稿回复与可复现发布包。", skills: ["论文写作", "引用核查", "发布复现"], starters: ["生成论文结构", "改写贡献表述", "检查数字与引用一致性"] },
] as const;

const stageToolLabels: Record<string, string> = {
  "project.asset.read": "读取项目资产",
  "literature.scout": "选题文献侦察",
  "literature.openalex": "OpenAlex 检索",
  "literature.crossref": "Crossref 核验",
  "literature.semantic_scholar": "Semantic Scholar 检索",
  "literature.arxiv": "arXiv 检索",
  "literature.screen_and_dedupe": "筛选与去重审计",
  "evidence.graph.read": "读取证据图",
  "knowledge.method.lookup": "方法适配检索",
  "knowledge.formula.lookup": "公式库查询",
  "design.feasibility.check": "研究设计完整性检查",
  "knowledge.data_source.lookup": "数据源目录",
  "data.asset.profile": "数据资产画像",
  "data.governance.check": "许可与治理检查",
  "knowledge.diagnostic.lookup": "稳健性与诊断矩阵",
  "stata.policy.scan": "Stata 静态安全检查",
  "runner.preflight": "Runner 预检",
  "runner.submit": "提交正式运行",
  "runner.status_logs": "运行状态与日志",
  "runner.cancel": "取消运行",
  "runner.result.read": "读取与比较结果",
  "runner.rerun.request": "创建重跑请求",
  "evidence.artifact.verify": "证据产物核验",
  "evidence.graph.patch": "更新主张—证据图",
  "citation.validate": "数字与引用核验",
  "revision.patch": "写入阶段草稿",
  "delivery.export": "导出交付包",
  "delivery.publish": "发布交付成果",
};

const navItems: { key: ViewKey; label: string; short: string }[] = [
  { key: "journey", label: "Research Journey", short: "研究旅程" },
  { key: "evidence", label: "Evidence Library", short: "证据库" },
  { key: "methods", label: "Methods", short: "方法库" },
  { key: "runs", label: "Runs", short: "分析运行" },
  { key: "approvals", label: "Approvals", short: "审批" },
];

const methods: MethodRecord[] = [
  { id: "M01", name: "面板固定效应", family: "计量与面板", fit: null, goal: "估计同一研究对象随时间变化与结果之间的关系。", estimand: "组内变化的条件平均关联 / 处理效应", dataShape: "个体 × 时间面板", formula: "Y_it = βD_it + γX_it + α_i + λ_t + ε_it", assumptions: ["组内有效变异充分", "无随时间变化的遗漏混杂", "聚类层级与处理分配一致"], diagnostics: ["组内/组间变异分解", "序列相关与聚类层级", "高维固定效应吸收检查"], failureRule: "核心变量缺少组内变异或关键时变混杂无法处理时，停止因果表述。", engine: "Stata · xtreg / reghdfe", stata: "xtset firm_id year\nxtreg y treatment controls i.year, fe vce(cluster firm_id)", python: "PanelOLS.from_formula('y ~ treatment + controls + EntityEffects + TimeEffects', data)", tags: ["panel", "fixed effects", "cluster SE"], source: "statsmodels / linearmodels" },
  { id: "M02", name: "双重差分", family: "因果识别", fit: null, goal: "利用处理发生前后与对照组差异识别平均处理效应。", estimand: "ATT / group-time ATT", dataShape: "处理组与对照组的重复横截面或面板", formula: "Y_it = α_i + λ_t + β(Treat_i × Post_t) + γX_it + ε_it", assumptions: ["条件平行趋势", "无提前反应", "处理组间无干扰或溢出已建模"], diagnostics: ["处理前动态系数", "分期处理异质性", "安慰剂时点与组别"], failureRule: "平行趋势或处理时点有效性被实质性否定时，不报告主因果效应。", engine: "Stata · xtdidregress / csdid", stata: "xtdidregress (y controls) (treated), group(id) time(year) vce(cluster id)", python: "model.identify_effect(); model.estimate_effect(...); model.refute_estimate(...)", tags: ["ATT", "policy evaluation", "staggered adoption"], source: "DoWhy / linearmodels" },
  { id: "M03", name: "工具变量 / 2SLS", family: "因果识别", fit: null, goal: "借助外生工具变量处理选择偏差、反向因果或测量误差。", estimand: "LATE（在单调性条件下）", dataShape: "横截面、面板或时间序列", formula: "D = πZ + γX + u;   Y = βD̂ + γX + ε", assumptions: ["工具相关性", "排除限制", "工具独立性与单调性"], diagnostics: ["第一阶段强度", "弱工具稳健推断", "过度识别与排除限制论证"], failureRule: "弱工具或排除限制缺乏可信论证时，工具变量结果只能作为探索性证据。", engine: "Stata · ivregress / ivreghdfe", stata: "ivregress 2sls y controls (treatment = instrument), vce(cluster id)\nestat firststage", python: "IV2SLS.from_formula('y ~ 1 + controls + [treatment ~ instrument]', data).fit()", tags: ["endogeneity", "LATE", "weak IV"], source: "linearmodels / DoWhy" },
  { id: "M04", name: "事件研究", family: "动态效应", fit: null, goal: "展示事件发生前后的动态路径、提前反应与效应持续性。", estimand: "相对事件时间的动态效应 β_k", dataShape: "具有可信事件时点的面板", formula: "Y_it = α_i + λ_t + Σ_{k≠-1} β_k 1[t-T_i=k] + ε_it", assumptions: ["事件时点可靠", "基准期与窗口预先定义", "分期处理异质性得到处理"], diagnostics: ["处理前联合检验", "事件窗口敏感性", "队列加权与组成变化"], failureRule: "事件前出现系统性趋势且无法解释时，动态因果路径不得进入核心结论。", engine: "Stata · eventstudyinteract", stata: "eventstudyinteract y lead* lag*, absorb(id year) cohort(first_treat) control_cohort(never)", python: "# cohort-specific event-time effects with explicit reference period", tags: ["dynamic effect", "pre-trend", "cohort"], source: "DoWhy / causal inference practice" },
  { id: "M05", name: "断点回归 RDD", family: "准实验", fit: null, goal: "利用阈值附近的处理跳跃识别局部平均处理效应。", estimand: "阈值处 LATE", dataShape: "连续运行变量 + 明确阈值", formula: "τ = lim_{x↓c}E[Y|X=x] − lim_{x↑c}E[Y|X=x]", assumptions: ["阈值附近潜在结果连续", "运行变量不可精确操纵", "带宽与多项式阶数合理"], diagnostics: ["密度操纵检验", "协变量连续性", "带宽与核函数敏感性"], failureRule: "运行变量存在操纵或阈值同时触发其他制度变化时，停止局部因果解释。", engine: "Stata · rdrobust", stata: "rdrobust y running, c(cutoff) covs(controls)\nrddensity running, c(cutoff)", python: "# local polynomial fit on each side of cutoff", tags: ["threshold", "local effect", "bandwidth"], source: "DoWhy / rdrobust ecosystem" },
  { id: "M06", name: "倾向得分与加权", family: "选择校正", fit: null, goal: "在可观测混杂条件下构造可比样本或加权总体。", estimand: "ATE / ATT / ATC", dataShape: "处理、结果与处理前协变量", formula: "ATE = E[DY/e(X) − (1-D)Y/(1-e(X))]", assumptions: ["条件可忽略性", "正值性 / 重叠", "协变量均为处理前变量"], diagnostics: ["重叠与极端权重", "加权后平衡", "未观测混杂敏感性"], failureRule: "严重违反重叠或关键混杂不可观测时，不将匹配/加权解释为已消除选择偏差。", engine: "Stata · teffects", stata: "teffects ipwra (y controls) (treated controls), atet\ntebalance summarize", python: "CausalModel(...).identify_effect(); model.estimate_effect(...)", tags: ["propensity score", "IPW", "balance"], source: "DoWhy / CausalML" },
  { id: "M07", name: "合成控制", family: "政策评估", fit: null, goal: "以加权对照单元构造处理单元未受处理时的反事实路径。", estimand: "处理单元的时间路径效应", dataShape: "少量处理单元 + 长期面板 + donor pool", formula: "Y^N_{1t} ≈ Σ_{j=2}^{J+1} w_jY_{jt},  w_j≥0, Σw_j=1", assumptions: ["加权对照可逼近处理前路径", "无干扰与预期效应", "donor pool 未受同类冲击"], diagnostics: ["处理前 RMSPE", "空间与时间安慰剂", "剔除高权重单元"], failureRule: "处理前拟合质量不足或 donor pool 被污染时，停止反事实效应解释。", engine: "Stata · synth / sdid", stata: "synth y predictors, trunit(1) trperiod(2022) nested", python: "# optimize non-negative donor weights subject to sum(w)=1", tags: ["synthetic control", "policy", "counterfactual"], source: "optimization + causal inference practice" },
  { id: "M08", name: "动态面板 GMM", family: "计量与面板", fit: null, goal: "处理含滞后因变量的动态面板与潜在内生解释变量。", estimand: "动态短期与长期参数", dataShape: "大 N、小 T 面板", formula: "Y_it = ρY_{i,t-1} + βD_it + α_i + ε_it", assumptions: ["误差序列相关结构符合矩条件", "工具变量集合有效", "工具数量受控"], diagnostics: ["AR(1)/AR(2)", "Hansen/Sargan", "工具数量与折叠策略"], failureRule: "AR(2) 或工具有效性失败、工具膨胀时，不报告 GMM 作为主结果。", engine: "Stata · xtabond2", stata: "xtabond2 y L.y treatment controls i.year, gmm(L.y treatment, collapse) iv(controls i.year) twostep robust", python: "# dynamic panel GMM with explicitly bounded instrument set", tags: ["dynamic panel", "GMM", "instrument proliferation"], source: "linearmodels / econometrics practice" },
  { id: "M09", name: "中介、调节与 SEM", family: "机制模型", fit: null, goal: "检验理论机制、间接效应、边界条件与测量结构。", estimand: "直接效应、间接效应与条件效应", dataShape: "横截面、面板或潜变量测量数据", formula: "M = aX + e_M;   Y = c′X + bM + d(X×W) + e_Y", assumptions: ["因果顺序由理论与设计支持", "中介—结果混杂得到处理", "测量模型可接受"], diagnostics: ["Bootstrap 间接效应", "测量信效度与拟合", "替代因果顺序"], failureRule: "仅凭横截面相关或拟合指标不得宣称机制得到因果验证。", engine: "Stata · sem / gsem", stata: "sem (mediator <- treatment controls) (y <- mediator treatment controls), vce(robust)\nnlcom _b[mediator:treatment]*_b[y:mediator]", python: "# structural equations with bootstrap confidence intervals", tags: ["mediation", "moderation", "latent variable"], source: "statsmodels / SEM practice" },
  { id: "M10", name: "线性 / 混合整数规划", family: "优化与决策", fit: null, goal: "在资源、容量和逻辑约束下最小化成本或最大化收益。", estimand: "最优目标值与决策变量", dataShape: "集合、参数、决策变量、约束", formula: "min cᵀx  s.t. Ax ≥ b,  x_j∈ℝ/ℤ/{0,1}", assumptions: ["目标与约束可线性表达", "参数口径一致", "求解容差与最优性差距已定义"], diagnostics: ["可行性与冲突约束", "MIP gap / bound", "影子价格与情景敏感性"], failureRule: "模型不可行或关键约束缺失时，不得将求解器输出称为可执行最优方案。", engine: "Pyomo / PuLP / OR-Tools", stata: "* Stata 用于估计输入参数；优化由受控 solver job 执行", python: "model = ConcreteModel(); model.x = Var(...); model.obj = Objective(...); model.cons = Constraint(...)", tags: ["LP", "MILP", "resource allocation"], source: "Pyomo / PuLP / OR-Tools" },
  { id: "M11", name: "鲁棒优化", family: "优化与决策", fit: null, goal: "在参数处于不确定集合内时寻找最坏情形下仍可接受的方案。", estimand: "最坏情形目标与鲁棒决策", dataShape: "确定性骨架 + 不确定集合", formula: "min_x max_{u∈U} f(x,u)  s.t. g(x,u)≤0, ∀u∈U", assumptions: ["不确定集合有业务依据", "保守度参数可解释", "鲁棒对应可求解"], diagnostics: ["价格—稳健性曲线", "集合半径敏感性", "样本外压力测试"], failureRule: "不确定集合任意设定或保守成本未披露时，不输出政策建议。", engine: "Pyomo + robust counterpart", stata: "* 参数分布与区间可由 Stata 估计后冻结入模型", python: "# construct uncertainty set U and solve robust counterpart", tags: ["uncertainty set", "min-max", "stress test"], source: "Pyomo optimization ecosystem" },
  { id: "M12", name: "随机规划", family: "优化与决策", fit: null, goal: "在未来情景与概率不确定性下共同优化当前和递延决策。", estimand: "期望目标、CVaR 与情景决策", dataShape: "场景树或抽样情景", formula: "min cᵀx + E_ξ[Q(x,ξ)]", assumptions: ["情景生成覆盖关键风险", "概率或样本权重可信", "非预见性约束正确"], diagnostics: ["样本平均逼近稳定性", "EVPI / VSS", "尾部风险与场景删减"], failureRule: "场景覆盖不足或概率假设未审计时，最优方案只能作为情景演示。", engine: "Pyomo / mpi-sppy", stata: "* 用 Stata 估计情景概率与输入分布；求解在隔离 solver 运行", python: "# first-stage x, scenario recourse y[s], non-anticipativity constraints", tags: ["stochastic programming", "scenario", "CVaR"], source: "Pyomo / mpi-sppy" },
  { id: "M13", name: "网络流、路径与调度", family: "运营研究", fit: null, goal: "求解路由、分配、最短路、最大流、排程和容量决策。", estimand: "可行路径/排程及其成本、服务与碳排", dataShape: "节点、边、订单、资源与时间窗", formula: "min Σ_{(i,j)} c_{ij}x_{ij}  s.t. flow balance & capacity", assumptions: ["网络拓扑与成本可信", "时间窗/容量约束完整", "离散决策尺度可求解"], diagnostics: ["可行性与约束冲突", "最优性界与运行时", "扰动、需求与边成本敏感性"], failureRule: "遗漏业务硬约束或仅给出不可部署路线时，不进入实施建议。", engine: "OR-Tools · CP-SAT / Routing", stata: "* Stata 负责需求估计与结果统计检验", python: "routing = pywrapcp.RoutingModel(...); routing.AddDimension(...); solution = routing.SolveWithParameters(params)", tags: ["routing", "scheduling", "network flow"], source: "Google OR-Tools" },
  { id: "M14", name: "数据包络分析 DEA", family: "效率评价", fit: null, goal: "比较多个决策单元在多投入多产出条件下的相对效率。", estimand: "效率前沿距离与松弛变量", dataShape: "DMU × 投入/产出", formula: "max_u,v uᵀy_o / vᵀx_o  s.t. uᵀy_j/vᵀx_j≤1", assumptions: ["投入产出同质且方向合理", "样本量足以支撑维度", "异常值与环境变量已处理"], diagnostics: ["规模报酬设定", "Bootstrap 偏差", "异常值与超效率敏感性"], failureRule: "DMU 不可比或维度相对样本过高时，不发布效率排名。", engine: "DEA solver / linear programming", stata: "* dea / teradial（需在 ado manifest 中锁定）", python: "# solve one LP per DMU with Pyomo/PuLP", tags: ["efficiency", "frontier", "benchmarking"], source: "Pyomo / PuLP modeling pattern" },
  { id: "M15", name: "仿真与蒙特卡洛", family: "仿真与预测", fit: null, goal: "评估随机系统、策略情景和估计量在重复试验下的表现。", estimand: "输出分布、风险指标或策略差异", dataShape: "输入分布 + 状态转移/业务规则", formula: "θ̂_MC = (1/R)Σ_{r=1}^R h(X_r)", assumptions: ["输入分布与依赖结构有依据", "预热期与重复次数足够", "随机种子与版本可复现"], diagnostics: ["蒙特卡洛标准误", "收敛与方差缩减", "输入分布敏感性"], failureRule: "输入分布未经校准或仿真误差未量化时，不将场景差异解释为稳健政策效应。", engine: "Stata simulate / Python", stata: "simulate b=_b[treatment], reps(1000) seed(20260721): myprogram", python: "rng = np.random.default_rng(seed); results = [simulate(rng) for _ in range(R)]", tags: ["simulation", "Monte Carlo", "scenario"], source: "statsmodels / scientific simulation practice" },
  { id: "M16", name: "双重机器学习 / 因果森林", family: "因果机器学习", fit: null, goal: "在高维控制变量下估计平均或异质处理效应。", estimand: "ATE / CATE / policy value", dataShape: "大样本、高维特征、处理与结果", formula: "Y-ĝ(X) = θ(X)(T-m̂(X)) + ε", assumptions: ["可忽略性或有效工具变量", "交叉拟合与正则化条件", "重叠与样本量充分"], diagnostics: ["交叉拟合稳定性", "重叠与校准", "异质性多重比较与策略验证"], failureRule: "仅发现异质性模式而缺乏样本外验证时，不将 CATE 排名写成确定性分群结论。", engine: "EconML / CausalML", stata: "* Stata 输出经批准的分析样本；CATE 在锁定 Python 环境运行", python: "est = CausalForestDML(...); est.fit(Y, T, X=X, W=W); est.effect(X)", tags: ["DML", "CATE", "causal forest"], source: "EconML / CausalML" },
];

const formulas: FormulaRecord[] = [
  { id: "F01", title: "双向固定效应", family: "计量", methodId: "M01", formula: "Y_it = βD_it + γX_it + α_i + λ_t + ε_it", purpose: "吸收个体不变异质性与共同时间冲击。", symbols: [{ symbol: "Y_it", meaning: "个体 i 在 t 期的结果变量" }, { symbol: "D_it", meaning: "核心解释或处理变量" }, { symbol: "X_it", meaning: "预先定义的时变控制变量" }, { symbol: "α_i", meaning: "个体固定效应" }, { symbol: "λ_t", meaning: "时间固定效应" }], assumptions: ["严格外生或可辩护的条件外生", "组内变异充分"], diagnostics: ["组内变异", "聚类标准误", "残差结构"], stata: "xtreg y d controls i.year, fe vce(cluster id)", source: "linearmodels / statsmodels" },
  { id: "F02", title: "双重差分 ATT", family: "因果", methodId: "M02", formula: "Y_it = α_i + λ_t + β(Treat_i×Post_t) + ε_it", purpose: "比较处理与对照组在处理前后的变化差异。", symbols: [{ symbol: "Treat_i", meaning: "处理组指示变量" }, { symbol: "Post_t", meaning: "处理后时期指示变量" }, { symbol: "β", meaning: "目标 ATT 参数" }], assumptions: ["平行趋势", "无提前反应", "无干扰"], diagnostics: ["事件研究前趋势", "组时异质性", "安慰剂"], stata: "xtdidregress (y controls) (treated), group(id) time(year)", source: "DoWhy causal workflow" },
  { id: "F03", title: "事件时间动态系数", family: "因果", methodId: "M04", formula: "Y_it = α_i + λ_t + Σ_{k≠-1}β_k·1[t-T_i=k] + ε_it", purpose: "估计处理前后各相对时期的动态效应。", symbols: [{ symbol: "T_i", meaning: "个体首次处理时点" }, { symbol: "k", meaning: "相对事件时间" }, { symbol: "β_k", meaning: "相对基准期的动态效应" }], assumptions: ["处理时点可靠", "基准期固定", "队列异质性已处理"], diagnostics: ["处理前联合检验", "窗口敏感性", "队列权重"], stata: "eventstudyinteract y lead* lag*, absorb(id year) cohort(first_treat)", source: "event-study practice" },
  { id: "F04", title: "两阶段最小二乘", family: "因果", methodId: "M03", formula: "D=πZ+γX+u;  Y=βD̂+γX+ε", purpose: "用工具变量诱导的外生处理变异估计局部效应。", symbols: [{ symbol: "Z", meaning: "工具变量" }, { symbol: "D̂", meaning: "第一阶段预测处理" }, { symbol: "β", meaning: "局部平均处理效应" }], assumptions: ["相关性", "排除限制", "独立性与单调性"], diagnostics: ["第一阶段 F", "弱工具稳健区间", "过度识别"], stata: "ivregress 2sls y controls (d=z), vce(cluster id)", source: "linearmodels / DoWhy" },
  { id: "F05", title: "局部断点效应", family: "准实验", methodId: "M05", formula: "τ = lim_{x↓c}E[Y|X=x] − lim_{x↑c}E[Y|X=x]", purpose: "估计阈值两侧结果函数的局部跳跃。", symbols: [{ symbol: "X", meaning: "运行变量" }, { symbol: "c", meaning: "处理阈值" }, { symbol: "τ", meaning: "阈值处局部处理效应" }], assumptions: ["潜在结果连续", "不可精确操纵"], diagnostics: ["密度检验", "协变量连续", "带宽敏感性"], stata: "rdrobust y running, c(cutoff)", source: "RDD practice" },
  { id: "F06", title: "IPW 加权均值", family: "选择校正", methodId: "M06", formula: "ATE = E[DY/e(X) − (1-D)Y/(1-e(X))]", purpose: "以处理概率倒数重构目标总体。", symbols: [{ symbol: "e(X)", meaning: "倾向得分 P(D=1|X)" }, { symbol: "D", meaning: "处理状态" }, { symbol: "Y", meaning: "观测结果" }], assumptions: ["条件可忽略性", "正值性"], diagnostics: ["平衡", "极端权重", "有效样本量"], stata: "teffects ipwra (y controls) (d controls), ate", source: "DoWhy / CausalML" },
  { id: "F07", title: "中介间接效应", family: "机制", methodId: "M09", formula: "Indirect = a×b;  Total = c′ + a×b", purpose: "分解处理经中介路径传递的间接效应。", symbols: [{ symbol: "a", meaning: "处理对中介的效应" }, { symbol: "b", meaning: "控制处理后中介对结果的效应" }, { symbol: "c′", meaning: "直接效应" }], assumptions: ["因果顺序可信", "无中介—结果未测混杂"], diagnostics: ["Bootstrap 区间", "替代顺序", "测量误差"], stata: "sem (m <- x controls) (y <- m x controls)\nnlcom _b[m:x]*_b[y:m]", source: "SEM / mediation practice" },
  { id: "F08", title: "线性 / 混合整数规划", family: "优化", methodId: "M10", formula: "min cᵀx  s.t. Ax≥b, x_j∈ℝ/ℤ/{0,1}", purpose: "将资源配置、选择与逻辑约束表达为可求解模型。", symbols: [{ symbol: "x", meaning: "决策变量向量" }, { symbol: "c", meaning: "目标系数" }, { symbol: "A,b", meaning: "约束矩阵与边界" }], assumptions: ["线性表达充分", "参数与单位一致"], diagnostics: ["可行性", "最优性 gap", "敏感性"], stata: "* 估计参数后导出 solver manifest", source: "Pyomo / PuLP / OR-Tools" },
  { id: "F09", title: "鲁棒最坏情形", family: "优化", methodId: "M11", formula: "min_x max_{u∈U} f(x,u)", purpose: "在不确定集合内控制最坏情形损失。", symbols: [{ symbol: "x", meaning: "鲁棒决策" }, { symbol: "u", meaning: "不确定参数" }, { symbol: "U", meaning: "经审计的不确定集合" }], assumptions: ["不确定集合有经验依据", "鲁棒对应可求解"], diagnostics: ["保守成本", "集合半径", "压力测试"], stata: "* estimate uncertainty bounds; freeze into solver input", source: "Pyomo ecosystem" },
  { id: "F10", title: "两阶段随机规划", family: "优化", methodId: "M12", formula: "min cᵀx + E_ξ[Q(x,ξ)]", purpose: "平衡当前决策与未来情景中的补救成本。", symbols: [{ symbol: "x", meaning: "第一阶段决策" }, { symbol: "ξ", meaning: "随机情景" }, { symbol: "Q", meaning: "情景补救价值函数" }], assumptions: ["情景覆盖充分", "非预见性约束正确"], diagnostics: ["VSS/EVPI", "场景稳定性", "尾部风险"], stata: "* scenario probability estimation only", source: "Pyomo / mpi-sppy" },
  { id: "F11", title: "网络流平衡", family: "运营研究", methodId: "M13", formula: "Σ_j x_{ji} − Σ_j x_{ij} = b_i", purpose: "保证每个节点的流入、流出与供需守恒。", symbols: [{ symbol: "x_ij", meaning: "边 i→j 上的流量" }, { symbol: "b_i", meaning: "节点供给或需求" }], assumptions: ["拓扑完整", "容量与单位一致"], diagnostics: ["不可行约束", "容量瓶颈", "边成本扰动"], stata: "* validate demand and post-solution outcomes", source: "Google OR-Tools" },
  { id: "F12", title: "双重机器学习残差式", family: "因果机器学习", methodId: "M16", formula: "Y-ĝ(X) = θ(X)(T-m̂(X)) + ε", purpose: "用正交化与交叉拟合降低高维干扰估计偏差。", symbols: [{ symbol: "ĝ(X)", meaning: "结果条件均值模型" }, { symbol: "m̂(X)", meaning: "处理条件均值模型" }, { symbol: "θ(X)", meaning: "条件处理效应" }], assumptions: ["混杂可由 X 控制", "交叉拟合", "重叠"], diagnostics: ["校准", "样本外稳定性", "策略价值"], stata: "* export approved analytic sample to locked Python runner", source: "EconML / CausalML" },
];

const interfaceThemes: { id: InterfaceTheme; name: string; description: string; colors: string[]; note: string }[] = [
  { id: "graphite", name: "石墨极简", description: "黑白灰、低阴影、最克制的 Apple 工作台。", colors: ["#101114", "#f5f5f7", "#d2d2d7"], note: "适合长时间阅读与正式汇报" },
  { id: "blueprint", name: "冷蓝研究", description: "低饱和蓝灰、清晰状态色、轻量层次。", colors: ["#315f87", "#eef3f7", "#aebdca"], note: "适合证据、方法和运行监控" },
  { id: "paper", name: "论文纸张", description: "暖白纸色、深墨文字、学术编辑感。", colors: ["#2f2d29", "#f5f1e8", "#b8aa91"], note: "适合写作、评审和打印阅读" },
];

const gateCards = [
  { id: "G0", title: "选题与已有研究", owner: "研究者 + 导师", status: "approved", time: "07-17 16:42", asset: "TopicBrief v3 · 报告 v2" },
  { id: "G1", title: "理论与研究设计", owner: "导师 + 方法审核者", status: "draft", time: "等待提交", asset: "ResearchProtocol v4" },
  { id: "G2", title: "数据、伦理与许可", owner: "数据负责人", status: "blocked", time: "等待 G1", asset: "DataContract 草稿" },
  { id: "G3", title: "分析计划与代码", owner: "方法审核者", status: "locked", time: "等待 G2", asset: "AnalysisPlan · do-file" },
  { id: "G4", title: "结果与核心主张", owner: "PI + 方法审核者", status: "locked", time: "等待正式运行", asset: "Runs · Claims" },
  { id: "G5", title: "成稿与发布", owner: "通讯作者", status: "locked", time: "等待 G4", asset: "Manuscript · Repro package" },
];

function projectGateCards(project: ResearchProject, apiProject?: ApiProject) {
  const stage = project.stageIndex;
  const gateStages: Record<string, string> = {
    G0: "problem",
    G1: "design",
    G2: "data",
    G3: "identification",
    G4: "evidence",
    G5: "delivery",
  };
  return gateCards.map((gate) => {
    const stageKey = gateStages[gate.id];
    const remote = apiProject?.stages.find((item) => item.key === stageKey);
    const position = stages.findIndex((item) => item.key === stageKey);
    const history = (apiProject?.approvals ?? [])
      .filter((event) => event.stage_key === stageKey)
      .map((event) => ({
        revision: event.revision,
        decision: event.decision,
        reason: event.reason,
        createdAt: event.created_at,
      }));
    const status = remote?.status === "approved"
      ? "approved"
      : remote?.status === "blocked"
        ? "blocked"
        : remote?.status === "needs_review" && remote.readiness.can_submit
          ? "review"
        : apiProject?.current_stage === stageKey || stage === position
          ? "draft"
          : "locked";
    const time = remote?.approved_at
      ? `${new Date(remote.approved_at).toLocaleString("zh-CN")} 已批准`
      : status === "draft"
        ? remote?.revision
          ? `Revision ${remote.revision} 等待提交`
          : "尚未形成阶段资产"
        : `等待进入 S${position}`;
    return {
      ...gate,
      status,
      time,
      asset: remote
        ? `${remote.artifact_type} · Revision ${remote.revision}`
        : gate.asset,
      history,
    };
  });
}

const newProjectPlaceholder: ResearchProject = {
  id: "local-new-project",
  name: "新建研究项目",
  code: "NEW",
  icon: "研",
  discipline: "管理科学研究",
  question: "请通过项目向导创建第一个研究课题。",
  objective: "",
  boundary: "",
  sampleWindow: "",
  keywords: "",
  dataSources: [],
  owner: "当前研究者",
  reviewers: "导师 + 方法审核者",
  stageIndex: 0,
  status: "draft",
  createdAt: new Date().toLocaleDateString("zh-CN"),
};

function apiStageIndex(currentStage: string) {
  const index = stages.findIndex((stage) => stage.key === currentStage || stage.id === currentStage);
  return index >= 0 ? index : 0;
}

function designSelection(project?: ApiProject): string {
  const primary = project?.stages.find((stage) => stage.key === "design")?.content.primary_method_id;
  return methodSelection(primary);
}

function methodSelection(methodId: unknown): string {
  return methodId === "M02"
    ? "did"
    : methodId === "M01"
      ? "fe"
      : typeof methodId === "string" && methodId
        ? methodId
        : "fe";
}

function selectedMethodId(selection: string): string {
  return selection === "did"
    ? "M02"
    : selection === "fe"
      ? "M01"
      : selection;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : undefined;
}

function stageWorkspace(content: Record<string, unknown>): Record<string, unknown> {
  return asRecord(content._workspace) ?? content;
}

function assetVersionSnapshot(stage?: ApiProjectStage): AssetVersionSnapshot {
  const assetVersion = stage ? asRecord(stage.content._asset_version) : undefined;
  const rawSections = assetVersion ? asRecord(assetVersion.sections) : undefined;
  const sections = Object.fromEntries(
    Object.entries(rawSections ?? {}).flatMap(([key, value]) => {
      const section = asRecord(value);
      return section
        ? [[key, {
            title: typeof section.title === "string" ? section.title : undefined,
            content: typeof section.content === "string" ? section.content : undefined,
          }]]
        : [];
    }),
  );
  return {
    revision: stage?.revision ?? 0,
    contentHash: stage?.content_hash ?? null,
    sections,
  };
}

function projectEvidenceRecords(project?: ApiProject): EvidenceRecord[] {
  const literature = project?.stages.find((stage) => stage.key === "literature");
  const library = Array.isArray(literature?.content.evidence_library)
    ? literature.content.evidence_library
    : [];
  return library.flatMap((raw): EvidenceRecord[] => {
    const record = asRecord(raw);
    if (
      !record
      || record.status !== "active"
      || typeof record.evidence_id !== "string"
      || typeof record.title !== "string"
    ) return [];
    const authors = Array.isArray(record.authors)
      ? record.authors.filter((item): item is string => typeof item === "string").join(", ")
      : "";
    const evidenceLabels = {
      metadata: "元数据",
      abstract: "摘要级",
      full_text: "全文级",
      source_page: "来源页",
    } as const;
    const evidenceLevel = record.evidence_level === "abstract"
      || record.evidence_level === "full_text"
      || record.evidence_level === "source_page"
      ? record.evidence_level
      : "metadata";
    return [{
      id: record.evidence_id,
      evidenceType: record.evidence_type === "data_study" ? "data_study" : "paper",
      revision: typeof record.revision === "number" ? record.revision : 1,
      contentHash: typeof record.content_hash === "string" ? record.content_hash : undefined,
      title: record.title,
      authors,
      year: typeof record.year === "number" ? record.year : Number(record.year) || 0,
      stream: typeof record.venue === "string" && record.venue
        ? record.venue
        : record.evidence_type === "data_study"
          ? "数据研究"
          : "未归类",
      method: record.evidence_type === "data_study" ? "数据来源研究" : "待人工提取",
      status: evidenceLabels[evidenceLevel],
      abstract: typeof record.abstract === "string" ? record.abstract : undefined,
      summary: typeof record.summary === "string" ? record.summary : undefined,
      locator: typeof record.locator === "string" ? record.locator : undefined,
      accessNotes: typeof record.access_notes === "string" ? record.access_notes : undefined,
      venue: typeof record.venue === "string" ? record.venue : undefined,
      doi: typeof record.doi === "string" ? record.doi : undefined,
      sourceUrl: typeof record.url === "string" ? record.url : undefined,
      evidenceLevel,
      fullTextAvailable: evidenceLevel === "full_text",
      approvedAt: typeof record.approved_at === "string" ? record.approved_at : undefined,
    }];
  });
}

function projectEvidenceCandidates(project?: ApiProject): EvidenceCandidate[] {
  const literature = project?.stages.find((stage) => stage.key === "literature");
  const candidates = Array.isArray(literature?.content.evidence_candidates)
    ? literature.content.evidence_candidates
    : [];
  return candidates.flatMap((raw): EvidenceCandidate[] => {
    const candidate = asRecord(raw);
    if (
      !candidate
      || typeof candidate.candidate_id !== "string"
      || typeof candidate.title !== "string"
    ) return [];
    return [candidate as unknown as EvidenceCandidate];
  });
}

function textList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  if (typeof value !== "string") return [];
  return value.split(/\r?\n|；|;/).map((item) => item.trim()).filter(Boolean);
}

function knowledgeMethodRecord(record: KnowledgeGovernanceRecord): MethodRecord {
  const content = record.content;
  return {
    id: record.record_id,
    name: String(content.name || record.record_id),
    family: String(content.family || "人工方法"),
    fit: null,
    goal: String(content.goal || content.description || ""),
    estimand: String(content.estimand || content.goal || "待在研究设计中确认"),
    dataShape: String(content.data || content.data_shape || "待人工确认"),
    formula: String(content.formula || content.latex || "关联公式见公式库"),
    assumptions: textList(content.assumptions),
    diagnostics: textList(content.diagnostics),
    failureRule: String(content.failure || "未满足关键假设时退出主分析"),
    engine: String(content.packages || "人工配置"),
    stata: String(content.stata || ""),
    python: String(content.python || ""),
    tags: textList(content.tags),
    source: Array.isArray(content.source_urls)
      ? content.source_urls.map(String).join(" · ")
      : "",
  };
}

function knowledgeFormulaRecord(record: KnowledgeGovernanceRecord): FormulaRecord {
  const content = record.content;
  return {
    id: record.record_id,
    title: String(content.name || record.record_id),
    family: String(content.category || "人工公式"),
    methodId: String(content.method_id || ""),
    formula: String(content.latex || content.formula || ""),
    purpose: String(content.use_when || content.description || ""),
    symbols: [],
    assumptions: textList(content.assumptions),
    diagnostics: textList(content.diagnostics),
    stata: String(content.packages || content.stata || ""),
    source: Array.isArray(content.source_urls)
      ? content.source_urls.map(String).join(" · ")
      : "",
  };
}

function projectContext(project: ResearchProject): NonNullable<StageWorkspacePayload["project_context"]> {
  return {
    code: project.code,
    icon: project.icon,
    discipline: project.discipline,
    sample_window: project.sampleWindow,
    keywords: project.keywords,
    data_sources: project.dataSources,
    owner: project.owner,
    reviewers: project.reviewers,
  };
}

function draftWorkspace(
  draft: StageDraft,
  context?: StageWorkspacePayload["project_context"],
): StageWorkspacePayload {
  return {
    title: draft.title,
    summary: draft.summary,
    objective: draft.objective,
    content: draft.content,
    scope: draft.scope,
    evidence_note: draft.evidenceNote,
    decision: draft.decision,
    risk: draft.risk,
    handoff: draft.handoff,
    human_confirmed: draft.humanConfirmed,
    sync_history: draft.syncHistory,
    project_context: context,
  };
}

function mapApiProject(summary: ApiProjectSummary | ApiProject, existing?: ResearchProject): ResearchProject {
  const full = "stages" in summary ? summary : undefined;
  const designContent = full?.stages.find((stage) => stage.key === "design")?.content;
  const problemContent = full?.stages.find((stage) => stage.key === "problem")?.content;
  const problemWorkspace = problemContent ? stageWorkspace(problemContent) : undefined;
  const context = asRecord(problemWorkspace?.project_context);
  const question = typeof designContent?.research_question === "string" ? designContent.research_question : summary.initial_idea;
  const objective = typeof problemWorkspace?.objective === "string"
    ? problemWorkspace.objective
    : typeof designContent?.estimand_or_objective === "string"
      ? designContent.estimand_or_objective
      : existing?.objective ?? "围绕当前研究问题形成可复核、可审批、可复现的管理科学研究。";
  const contextText = (key: string, fallback: string) => typeof context?.[key] === "string" ? String(context[key]) : fallback;
  return {
    id: summary.project_id,
    name: summary.title,
    code: contextText("code", existing?.code ?? summary.project_id.slice(0, 12).toUpperCase()),
    icon: contextText("icon", existing?.icon ?? (summary.title.trim().slice(0, 1) || "研")),
    discipline: contextText("discipline", existing?.discipline ?? "管理科学研究"),
    question,
    objective,
    boundary: typeof problemWorkspace?.scope === "string" ? problemWorkspace.scope : existing?.boundary ?? "研究对象、地区、行业与排除范围待在 S0 由研究者确认。",
    sampleWindow: contextText("sample_window", existing?.sampleWindow ?? "待确认"),
    keywords: contextText("keywords", existing?.keywords ?? ""),
    dataSources: Array.isArray(context?.data_sources) ? context.data_sources.filter((item): item is string => typeof item === "string") : existing?.dataSources ?? [],
    owner: contextText("owner", existing?.owner ?? "当前研究者"),
    reviewers: contextText("reviewers", existing?.reviewers ?? "导师 + 方法审核者"),
    stageIndex: apiStageIndex(summary.current_stage),
    status: summary.status === "active" ? "active" : "paused",
    createdAt: new Date(summary.created_at).toLocaleDateString("zh-CN"),
  };
}

function mapApiDrafts(project: ApiProject, localProject: ResearchProject) {
  const mapped: Record<string, StageDraft> = {};
  project.stages.forEach((remoteStage) => {
    const index = stages.findIndex((stage) => stage.key === remoteStage.key);
    if (index < 0) return;
    const base = createLocalStageDraft(stages[index], localProject);
    const workspace = stageWorkspace(remoteStage.content);
    const text = (key: "title" | "summary" | "objective" | "content" | "scope" | "decision" | "risk" | "handoff") => typeof workspace[key] === "string" ? String(workspace[key]) : base[key];
    mapped[`${localProject.id}:${index}`] = {
      title: text("title"),
      summary: text("summary"),
      objective: text("objective"),
      content: text("content"),
      scope: text("scope"),
      evidenceNote: typeof workspace.evidence_note === "string"
        ? workspace.evidence_note
        : typeof workspace.evidenceNote === "string"
          ? workspace.evidenceNote
          : base.evidenceNote,
      decision: text("decision"),
      risk: text("risk"),
      handoff: text("handoff"),
      humanConfirmed: typeof workspace.human_confirmed === "boolean"
        ? workspace.human_confirmed
        : typeof workspace.humanConfirmed === "boolean"
          ? workspace.humanConfirmed
          : base.humanConfirmed,
      version: remoteStage.revision || base.version,
      savedAt: remoteStage.revision_created_at ? new Date(remoteStage.revision_created_at).toLocaleString("zh-CN") : base.savedAt,
      syncHistory: Array.isArray(workspace.sync_history)
        ? workspace.sync_history.filter((item): item is string => typeof item === "string")
        : Array.isArray(workspace.syncHistory)
          ? workspace.syncHistory.filter((item): item is string => typeof item === "string")
          : base.syncHistory,
    };
  });
  return mapped;
}

function StateBadge({ state }: { state: string }) {
  const labels: Record<string, string> = {
    supported: "已支持",
    pending: "待补证",
    review: "待审批",
    conflict: "有冲突",
    approved: "已批准",
    draft: "待提交",
    blocked: "前置阻塞",
    locked: "未解锁",
    succeeded: "运行成功",
    running: "正在运行",
  };
  return <span className={`state-badge state-${state}`}>{labels[state] ?? state}</span>;
}

function DetailModal({ detail, onClose }: { detail: DetailPanel | null; onClose: () => void }) {
  if (!detail) return null;
  return (
    <div className="modal-backdrop detail-backdrop" role="presentation" onMouseDown={(event) => event.currentTarget === event.target && onClose()}>
      <section className="detail-modal" role="dialog" aria-modal="true" aria-labelledby="detail-title">
        <header className="detail-modal-header">
          <div><p className="eyebrow">{detail.eyebrow}</p><h2 id="detail-title">{detail.title}</h2></div>
          <button className="modal-close" onClick={onClose} aria-label="关闭详情">×</button>
        </header>
        <p className="detail-lede">{detail.description}</p>
        {detail.rows && <dl className="detail-facts">{detail.rows.map((row) => <div key={row.label}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}</dl>}
        {detail.bullets && <ul className="detail-bullets">{detail.bullets.map((item) => <li key={item}>{item}</li>)}</ul>}
        {detail.code && <pre className="detail-code"><code>{detail.code}</code></pre>}
        <footer className="detail-modal-actions"><button className="primary-action" onClick={onClose}>完成查看</button></footer>
      </section>
    </div>
  );
}

function PreferencesModal({
  open,
  value,
  onSelect,
  onClose,
}: {
  open: boolean;
  value: InterfaceTheme;
  onSelect: (theme: InterfaceTheme) => void;
  onClose: () => void;
}) {
  if (!open) return null;
  const selectedTheme = interfaceThemes.find((theme) => theme.id === value) ?? interfaceThemes[0];
  return (
    <div className="modal-backdrop preferences-backdrop" role="presentation" onMouseDown={(event) => event.currentTarget === event.target && onClose()}>
      <section className="preferences-modal" role="dialog" aria-modal="true" aria-labelledby="preferences-title">
        <header className="detail-modal-header">
          <div><p className="eyebrow">Appearance preferences</p><h2 id="preferences-title">界面偏好</h2></div>
          <button className="modal-close" onClick={onClose} aria-label="关闭界面偏好">×</button>
        </header>
        <p className="detail-lede">选择最适合当前工作方式的颜色与排版。设置会先在本机即时恢复，再同步到用户 profile；不会改变研究内容。</p>
        <div className="theme-choice-grid" role="radiogroup" aria-label="界面风格">
          {interfaceThemes.map((theme) => (
            <button
              type="button"
              role="radio"
              aria-checked={theme.id === value}
              className={`theme-choice ${theme.id === value ? "is-selected" : ""}`}
              onClick={() => onSelect(theme.id)}
              key={theme.id}
            >
              <span className="theme-choice-check">{theme.id === value ? "✓" : ""}</span>
              <span className="theme-swatches" aria-hidden="true">{theme.colors.map((color) => <i style={{ background: color }} key={color} />)}</span>
              <strong>{theme.name}</strong>
              <small>{theme.description}</small>
              <em>{theme.note}</em>
            </button>
          ))}
        </div>
        <footer className="preferences-actions"><span>当前：{selectedTheme.name} · 本机保存并同步 profile</span><button className="primary-action" onClick={onClose}>完成</button></footer>
      </section>
    </div>
  );
}

function AgentChatDrawer({
  open,
  agentIndex,
  messages,
  loading,
  busy,
  tools,
  toolBusyId,
  onClose,
  onSelectAgent,
  onSend,
  onInvokeTool,
  onCapture,
}: {
  open: boolean;
  agentIndex: number;
  messages: ChatMessage[];
  loading: boolean;
  busy: boolean;
  tools: StageToolPolicy[];
  toolBusyId: string;
  onClose: () => void;
  onSelectAgent: (index: number) => void;
  onSend: (text: string, searchMode: ChatSearchMode) => void;
  onInvokeTool: (tool: StageToolPolicy) => void;
  onCapture: (text: string, target: ChatSyncTarget, mode: ChatSyncMode) => void;
}) {
  const [draft, setDraft] = useState("");
  const [syncCandidate, setSyncCandidate] = useState("");
  const [syncTarget, setSyncTarget] = useState<ChatSyncTarget>("content");
  const [syncMode, setSyncMode] = useState<ChatSyncMode>("append");
  const [syncConfirmed, setSyncConfirmed] = useState(false);
  const [searchMode, setSearchMode] = useState<ChatSearchMode>("auto");
  const unavailable = loading || busy;
  if (!open) return null;
  const stage = stages[agentIndex];
  const profile = agentProfiles[agentIndex];
  const submit = () => {
    const value = draft.trim();
    if (!value || unavailable) return;
    onSend(value, searchMode);
    setDraft("");
  };
  return (
    <div className="chat-backdrop" role="presentation" onMouseDown={(event) => event.currentTarget === event.target && onClose()}>
      <section className="agent-chat-shell" role="dialog" aria-modal="true" aria-labelledby="agent-chat-title">
        <header className="agent-chat-header">
          <div><p className="eyebrow">Research copilot workspace</p><h2 id="agent-chat-title">与科研智能体协作</h2></div>
          <div className="chat-human-badge"><span>人</span>关键决定仍由你审批</div>
          <button className="modal-close" onClick={onClose} aria-label="关闭智能体对话">×</button>
        </header>
        <div className="agent-chat-layout">
          <nav className="agent-directory" aria-label="选择科研智能体">
            <div className="agent-directory-label">10 个阶段智能体</div>
            {stages.map((item, index) => (
              <button className={index === agentIndex ? "is-active" : ""} onClick={() => { onSelectAgent(index); setSyncCandidate(""); setSyncConfirmed(false); }} key={item.id}>
                <span>{item.id}</span><div><strong>{item.agent}</strong><small>{item.name}</small></div>
              </button>
            ))}
          </nav>
          <section className="chat-conversation">
            <div className="chat-agent-summary">
              <div className="chat-agent-avatar">AI</div>
              <div><p className="eyebrow">{stage.id} · {stage.name}</p><h3>{stage.agent}</h3><p>{profile.mission}</p></div>
            </div>
            <div className="chat-skill-row">{profile.skills.map((skill) => <span key={skill}>{skill}</span>)}</div>
            <div className="chat-messages" aria-live="polite">
              <article className="chat-message is-assistant">
                <div className="message-role">{stage.agent}</div>
                <p className="message-content">连接模型后，我会读取当前阶段目标和交付要求。你可以让我解释、比较方案或形成一份可人工修改的草稿。</p>
              </article>
              {loading && <article className="chat-message is-assistant is-typing"><div className="message-role">{stage.agent}</div><p><span /><span /><span /> 正在读取历史记录</p></article>}
              {!loading && messages.map((message) => (
                <article className={`chat-message is-${message.role}${message.error ? " is-error" : ""}`} key={message.id}>
                  <div className="message-role">{message.role === "user" ? "你" : stage.agent}<time>{message.time}</time></div>
                  <p className={message.role === "assistant" ? "message-content" : undefined}>{message.text}</p>
                  {message.role === "assistant" && message.citations && message.citations.length > 0 && (
                    <section className="message-sources" aria-label="本轮联网来源">
                      <div className="message-source-summary">
                        <Search size={13} aria-hidden="true" />
                        <strong>已检索 {message.search?.queries.length ?? 1} 组查询</strong>
                        <span>{message.citations.length} 个来源</span>
                      </div>
                      <div className="message-source-list">
                        {message.citations.map((citation) => (
                          <a
                            href={citation.url}
                            target="_blank"
                            rel="noreferrer"
                            title={citation.snippet}
                            key={`${message.id}:${citation.citation_id}`}
                          >
                            <span className={`source-kind is-${citation.source_type}`}>
                              {citation.source_type === "official_data"
                                ? "官方数据"
                                : citation.source_type === "official"
                                  ? "官方"
                                  : citation.source_type === "academic"
                                    ? "学术"
                                    : citation.citation_id}
                            </span>
                            <span>
                              <strong>[{citation.citation_id}] {citation.title}</strong>
                              <small>{citation.domain || citation.provider}</small>
                            </span>
                            <ExternalLink size={13} aria-hidden="true" />
                          </a>
                        ))}
                      </div>
                    </section>
                  )}
                  {message.role === "assistant" && message.model && <small>{message.model}{message.totalTokens ? ` · ${message.totalTokens} tokens` : ""}</small>}
                  {message.role === "assistant" && !message.error && <button className="message-capture" onClick={() => { setSyncCandidate(message.text); setSyncTarget("content"); setSyncMode("append"); setSyncConfirmed(false); }}>同步到交付正文</button>}
                </article>
              ))}
              {busy && <article className="chat-message is-assistant is-typing"><div className="message-role">{stage.agent}</div><p><span /><span /><span /> {searchMode === "off" ? "正在整理回答" : "正在搜索、阅读并核对来源"}</p></article>}
            </div>
            <div className="chat-starters" aria-label="快捷提问">{profile.starters.map((prompt) => <button onClick={() => onSend(prompt, searchMode)} disabled={unavailable} key={prompt}>{prompt}</button>)}</div>
            <div className="chat-composer">
              <div className="chat-composer-field">
                <div className="search-mode-control" role="group" aria-label="联网搜索模式">
                  <Globe2 size={14} aria-hidden="true" />
                  {([
                    ["auto", "自动"],
                    ["on", "联网"],
                    ["off", "关闭"],
                  ] as const).map(([value, label]) => (
                    <button
                      type="button"
                      className={searchMode === value ? "is-active" : ""}
                      aria-pressed={searchMode === value}
                      onClick={() => setSearchMode(value)}
                      disabled={unavailable}
                      title={value === "auto" ? "由智能体判断是否需要联网" : value === "on" ? "本轮强制联网检索" : "本轮仅使用项目上下文"}
                      key={value}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <textarea
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      submit();
                    }
                  }}
                  placeholder={`向 ${stage.agent} 提问，Enter 发送，Shift+Enter 换行`}
                  aria-label="智能体聊天输入"
                />
              </div>
              <button
                className="primary-action chat-send"
                onClick={submit}
                disabled={!draft.trim() || unavailable}
                aria-label="发送消息"
                title="发送消息"
              >
                <SendHorizontal size={18} aria-hidden="true" />
              </button>
            </div>
          </section>
          <aside className="chat-context">
            <p className="eyebrow">Current context</p>
            <h3>本次对话上下文</h3>
            <dl>
              <div><dt>阶段</dt><dd>{stage.id} · {stage.name}</dd></div>
              <div><dt>审批门</dt><dd>{stage.gate}</dd></div>
              <div><dt>主要交付</dt><dd>{stage.output}</dd></div>
              <div><dt>需要人工决定</dt><dd>{stage.decision}</dd></div>
            </dl>
            <div className="context-notice"><strong>协作边界</strong><p>智能体可以提出建议和草稿，但不能替你接受风险、批准阶段或启动正式分析。</p></div>
            <div className="agent-tool-mini">
              <strong>本阶段可调用工具</strong>
              {tools.map((tool) => (
                <button
                  type="button"
                  disabled={unavailable || Boolean(toolBusyId)}
                  onClick={() => onInvokeTool(tool)}
                  title={`${tool.tool_id} · ${tool.purpose}`}
                  key={tool.tool_id}
                >
                  <span>{toolBusyId === tool.tool_id ? "调用中…" : stageToolLabels[tool.tool_id] ?? tool.tool_id}</span>
                  <small>{tool.risk_level}{tool.requires_human_confirmation ? " · 需人工确认" : ""}</small>
                </button>
              ))}
              {tools.length === 0 && <p>正在读取后端工具注册表。</p>}
              {tools.length > 0 && <p>每次调用都会校验阶段权限并保存工具运行记录；高风险动作只进入人工确认流程。</p>}
            </div>
            {syncCandidate && <div className="chat-sync-panel"><div className="chat-sync-title"><span>SYNC</span><strong>同步到阶段资产</strong></div><p>同步前可选择目标和写入方式；确认后仍可在草稿中人工修改。</p><label><span>目标位置</span><select value={syncTarget} onChange={(event) => setSyncTarget(event.target.value as ChatSyncTarget)}><option value="content">交付正文</option><option value="summary">阶段摘要</option><option value="evidenceNote">证据说明</option><option value="decision">决定记录草稿</option></select></label><label><span>写入方式</span><select value={syncMode} onChange={(event) => setSyncMode(event.target.value as ChatSyncMode)}><option value="append">追加并保留原文</option><option value="replace">替换目标内容</option></select></label><div className="sync-preview">{syncCandidate}</div><div className="chat-sync-actions"><button onClick={() => setSyncCandidate("")}>取消</button><button className="primary-action" disabled={syncConfirmed} onClick={() => { onCapture(syncCandidate, syncTarget, syncMode); setSyncConfirmed(true); }}>{syncConfirmed ? "已同步" : "人工确认并同步"}</button></div>{syncConfirmed && <small>已生成同步记录，可到“当前草稿”继续修改。</small>}</div>}
          </aside>
        </div>
      </section>
    </div>
  );
}

function ProgressNodes({
  activeIndex,
  remoteStages,
}: {
  activeIndex: number;
  remoteStages?: ApiProjectStage[];
}) {
  return (
    <div className="progress-nodes" aria-label={`研究进度，第 ${activeIndex + 1} 阶段，共 10 阶段`}>
      {stages.map((stage, index) => {
        const remote = remoteStages?.find((item) => item.key === stage.key);
        const done = remote ? remote.status === "approved" : index < activeIndex;
        return (
          <div className={`progress-node ${done ? "is-done" : ""} ${index === activeIndex ? "is-current" : ""}`} key={stage.id}>
            <span>{done ? "✓" : ""}</span>
            <small>{stage.id}</small>
          </div>
        );
      })}
    </div>
  );
}

function StageRail({
  activeIndex,
  remoteStages,
  onSelect,
}: {
  activeIndex: number;
  remoteStages?: ApiProjectStage[];
  onSelect: (index: number) => void;
}) {
  return (
    <aside className="stage-rail" aria-label="科研阶段导航">
      <div className="stage-rail-label">科研阶段</div>
      <div className="stage-list">
        {stages.map((stage, index) => {
          const remote = remoteStages?.find((item) => item.key === stage.key);
          const done = remote ? remote.status === "approved" : index < activeIndex;
          const locked = remote?.status === "not_started";
          return (
            <button
              className={`stage-item ${done ? "is-done" : ""} ${locked ? "is-locked" : ""} ${index === activeIndex ? "is-active" : ""}`}
              key={stage.id}
              onClick={() => onSelect(index)}
              aria-current={index === activeIndex ? "step" : undefined}
              title={locked ? "上游阶段批准后解锁" : remote?.status === "needs_review" ? "阶段资产待人工审阅" : undefined}
            >
              <span className="stage-dot">{done ? "✓" : stage.id.replace("S", "")}</span>
              <span className="stage-id">{stage.id}</span>
              <span className="stage-name">{stage.name}</span>
            </button>
          );
        })}
      </div>
      <div className="rail-footer">
        <span className="rail-lock">人</span>
        <div><strong>Human in control</strong><small>关键决定只能由人批准</small></div>
      </div>
    </aside>
  );
}

function AgentPanel({
  stageIndex,
  suggestions,
  suggestionBusy,
  onRefreshSuggestions,
  onDecision,
  onGenerate,
  onSubmit,
  onOpenChat,
  remoteStage,
  busy,
}: {
  stageIndex: number;
  suggestions?: StageSuggestionSet;
  suggestionBusy: boolean;
  onRefreshSuggestions: () => void;
  onDecision: (id: string, state: SuggestionDecision) => void;
  onGenerate: () => void;
  onSubmit: () => void;
  onOpenChat: () => void;
  remoteStage?: ApiProjectStage;
  busy: boolean;
}) {
  const stage = stages[stageIndex];
  const generation = asRecord(remoteStage?.content.generation);
  const orchestration = asRecord(generation?.orchestration);
  const orchestrationRuns = typeof orchestration?.subagent_runs === "number"
    ? orchestration.subagent_runs
    : 0;
  const usesAO = ["problem", "literature", "robustness", "evidence"].includes(stage.key);
  const canGenerate = Boolean(
    remoteStage
    && remoteStage.status !== "not_started"
    && remoteStage.status !== "approved"
    && !busy,
  );
  const workspace = remoteStage ? stageWorkspace(remoteStage.content) : undefined;
  const humanConfirmed = workspace?.human_confirmed === true;
  const canApprove = remoteStage?.readiness.can_submit === true;
  const literatureQueries = Array.isArray(remoteStage?.content.query_blocks)
    ? remoteStage.content.query_blocks
    : [];
  const literaturePapers = Array.isArray(remoteStage?.content.papers)
    ? remoteStage.content.papers
    : [];
  const literatureDecisions = Array.isArray(remoteStage?.content.screening_decisions)
    ? remoteStage.content.screening_decisions
    : [];
  const literatureReview = asRecord(remoteStage?.content.literature_plan_review);
  const generateLabel = stage.key === "literature"
    ? literatureQueries.length === 0
      ? "生成检索计划"
      : literatureReview?.status !== "approved"
        ? "等待人工批准计划"
        : literaturePapers.length === 0
          ? "执行文献检索"
          : literatureDecisions.length < literaturePapers.length
            ? "等待逐篇筛选"
            : "生成证据综述"
    : stage.key === "delivery"
      ? "生成报告与研究包"
      : usesAO
        ? "AO 生成阶段资产"
        : "生成阶段资产";
  const stageSuggestions = suggestions?.status === "current" ? suggestions.suggestions : [];
  const suggestionStatus = suggestions?.status === "current"
    ? `基于 Revision ${suggestions.stage_revision} · ${suggestions.model || "AI"}`
    : suggestions?.status === "stale"
      ? "阶段草稿已变化，请重新分析"
      : "尚未根据当前草稿生成 AI 建议";

  return (
    <aside className="agent-panel" aria-label={`${stage.agent} 协作建议`}>
      <button className="agent-profile-button" onClick={onOpenChat} aria-label={`打开与 ${stage.agent} 的对话`}>
        <div>
          <p className="eyebrow">本阶段协作智能体</p>
          <h2>{stage.agent}</h2>
          <span>点击进入完整对话工作区 →</span>
        </div>
        <span className="agent-avatar">AI</span>
      </button>
      <div className={`agent-live ${busy ? "is-busy" : ""}`}>
        <span />
        {busy
          ? usesAO ? "AOrchestra 正在编排 SubAgent" : "阶段智能体正在生成资产"
          : orchestration
            ? `AOrchestra · ${orchestrationRuns} 个 SubAgent · ${String(orchestration.status ?? "complete")}`
            : `${remoteStage ? `Revision ${remoteStage.revision} · ${remoteStage.status}` : "后端阶段未连接"} · 不会替你批准`}
      </div>

      <div className="suggestion-toolbar">
        <div><strong>AI 草稿建议</strong><span>{suggestionStatus}</span></div>
        <button
          type="button"
          disabled={
            !remoteStage
            || remoteStage.revision <= 0
            || remoteStage.status === "not_started"
            || suggestionBusy
          }
          onClick={onRefreshSuggestions}
        >
          {suggestionBusy ? "分析中…" : stageSuggestions.length ? "重新分析" : "AI 生成建议"}
        </button>
      </div>
      <div className="suggestion-list">
        {stageSuggestions.length === 0 && (
          <div className="suggestion-empty">
            <strong>等待分析当前草稿</strong>
            <p>保存阶段资产后，由模型读取当前 revision 和已批准的上游内容，再给出可审阅建议。</p>
          </div>
        )}
        {stageSuggestions.map((suggestion, index) => {
          const state = suggestion.state;
          return (
            <article className={`suggestion-card suggestion-${state}`} key={suggestion.suggestion_id}>
              <div className="suggestion-title"><span>{index + 1}</span><strong>{suggestion.title}</strong></div>
              <p>{suggestion.reason}</p>
              {suggestion.tool_id && <small className="suggestion-tool">建议工具 · {stageToolLabels[suggestion.tool_id] ?? suggestion.tool_id}</small>}
              <div className="diff-block">
                <div className="diff-before"><b>−</b>{suggestion.before}</div>
                <div className="diff-after"><b>+</b>{suggestion.after}</div>
              </div>
              {state === "pending" ? (
                <div className="suggestion-actions" aria-label="处理建议">
                  <button className="button-accept" onClick={() => onDecision(suggestion.suggestion_id, "accepted")}>接受</button>
                  <button onClick={() => onDecision(suggestion.suggestion_id, "modified")}>修改</button>
                  <button onClick={() => onDecision(suggestion.suggestion_id, "rejected")}>拒绝</button>
                </div>
              ) : (
                <div className={`decision-result result-${state}`}>
                  {state === "accepted" && "✓ 已接受，待写入阶段草稿"}
                  {state === "modified" && "✎ 已转为人工编辑候选"}
                  {state === "rejected" && "× 已拒绝，处理记录已保存"}
                  <button onClick={() => onDecision(suggestion.suggestion_id, "pending")}>撤销</button>
                </div>
              )}
            </article>
          );
        })}
      </div>
      <div className="agent-submit-wrap">
        <div className="submit-readiness">
          <span>{remoteStage?.revision ?? 0}</span>
          {remoteStage?.status !== "needs_review"
            ? " 先生成符合契约的阶段资产"
            : canApprove
              ? " 当前 Revision 已满足提交条件"
              : !remoteStage.readiness.checks.contract_valid
                ? " 阶段契约尚未通过，请打开草稿补齐"
                : humanConfirmed
                  ? " 当前 Revision 已保存人工确认"
                  : " 请先在阶段资产中保存人工确认"}
        </div>
        <div className="stage-flow-actions">
          <button className="generate-stage-action" disabled={!canGenerate} onClick={onGenerate}>{busy ? "处理中…" : generateLabel}</button>
          <button className="primary-action" disabled={!canApprove || busy} onClick={onSubmit}>提交 {stage.gate} 审批 <span>→</span></button>
        </div>
      </div>
    </aside>
  );
}

function DesignWorkspace({
  question,
  setQuestion,
  selectedDesign,
  setSelectedDesign,
  onCompareMethods,
  onSave,
  remoteStage,
  methodRecords,
  busy,
}: {
  question: string;
  setQuestion: (value: string) => void;
  selectedDesign: string;
  setSelectedDesign: (value: string) => void;
  onCompareMethods: () => void;
  onSave: () => void;
  remoteStage?: ApiProjectStage;
  methodRecords: MethodRecord[];
  busy: boolean;
}) {
  const methodOptions = (Array.isArray(remoteStage?.content.method_options)
    ? remoteStage.content.method_options
    : [])
    .map(asRecord)
    .filter((item): item is Record<string, unknown> => item !== undefined && typeof item.method_id === "string");
  const assumptions = (Array.isArray(remoteStage?.content.assumptions)
    ? remoteStage.content.assumptions
    : [])
    .map(asRecord)
    .filter((item): item is Record<string, unknown> => Boolean(item));
  const unknowns = Array.isArray(remoteStage?.content.unknowns)
    ? remoteStage.content.unknowns.filter((item): item is string => typeof item === "string")
    : [];

  return (
    <div className="design-workspace">
      <section className="content-card question-card">
        <div className="card-heading"><h2>研究问题</h2><div><span className="editable-mark">可人工编辑</span><button className="text-button" disabled={busy || !remoteStage || remoteStage.status === "approved"} onClick={onSave}>{busy ? "正在保存" : "保存到 Revision"}</button></div></div>
        <textarea aria-label="研究问题" value={question} onChange={(event) => setQuestion(event.target.value)} />
        <div className="field-meta"><span>{remoteStage ? `Revision ${remoteStage.revision} · ${remoteStage.author_type ?? "尚未生成"}` : "尚未连接后端阶段"}</span><span>保存后会重新计算契约与交接状态</span></div>
      </section>

      <section className="content-card">
        <div className="card-heading"><h2>设计选择</h2><button className="text-button" onClick={onCompareMethods}>比较方法卡</button></div>
        <div className="design-options" role="radiogroup" aria-label="研究设计选择">
          {methodOptions.map((option) => {
            const methodId = String(option.method_id);
            const selection = methodSelection(methodId);
            const selected = selectedDesign === selection;
            const method = methodRecords.find((item) => item.id === methodId);
            const fitConditions = Array.isArray(option.fit_conditions)
              ? option.fit_conditions.filter((item): item is string => typeof item === "string")
              : [];
            const risks = Array.isArray(option.risks)
              ? option.risks.filter((item): item is string => typeof item === "string")
              : [];
            return (
              <label className={`design-option ${selected ? "is-selected" : ""}`} key={methodId}>
                <input type="radio" name="design" value={selection} checked={selected} onChange={() => setSelectedDesign(selection)} />
                <span className="radio-ui" />
                <div className="design-copy">
                  <div><strong>{method?.name ?? methodId}</strong><span className={selected ? "recommend-mark" : "backup-mark"}>{selected ? "当前主设计" : option.role === "supporting" ? "支持方法" : "备选设计"}</span></div>
                  <p>
                    <span>{typeof option.rationale === "string" ? option.rationale : "尚未生成方法选择理由"}</span>
                    {fitConditions[0] && <span>条件：{fitConditions[0]}</span>}
                    {risks[0] && <span>风险：{risks[0]}</span>}
                  </p>
                </div>
                <span className="fit-score">{method?.fit == null ? "待 AI 评估" : `适配 ${method.fit}`}</span>
              </label>
            );
          })}
          {methodOptions.length === 0 && <div className="empty-state">尚无后端方法候选。请先生成 S3 阶段资产。</div>}
        </div>
      </section>

      <section className="content-card evidence-card">
        <div className="card-heading"><h2>关键假设与检查状态</h2><span className="evidence-count">{assumptions.length} 条假设 · {unknowns.length} 项未知</span></div>
        <div className="evidence-table-wrap">
          <table className="evidence-table">
            <thead><tr><th>编号</th><th>假设</th><th>计划检查</th><th>可检验性</th><th>类别</th></tr></thead>
            <tbody>
              {assumptions.map((assumption, index) => (
                <tr key={String(assumption.assumption_id ?? index)}>
                  <td>{String(assumption.assumption_id ?? `A${index + 1}`)}</td>
                  <td>{String(assumption.statement ?? "待补充")}</td>
                  <td>{String(assumption.planned_check ?? "待补充")}</td>
                  <td>{assumption.testability === "testable" ? "可检验" : assumption.testability === "partially_testable" ? "部分可检验" : "不可直接检验"}</td>
                  <td>{String(assumption.category ?? "未分类")}</td>
                </tr>
              ))}
              {assumptions.length === 0 && <tr><td colSpan={5}>尚无后端假设记录。请先生成 S3 阶段资产。</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function GenericStage({
  stageIndex,
  remoteStage,
  onOpenDraft,
  onOpenDecision,
  onRunCheck,
}: {
  stageIndex: number;
  remoteStage?: ApiProjectStage;
  onOpenDraft: () => void;
  onOpenDecision: () => void;
  onRunCheck: () => void;
}) {
  const stage = stages[stageIndex];
  const readiness = remoteStage?.readiness;
  const handoffTitle = !remoteStage
    ? "连接 FastAPI 后计算交接就绪度"
    : remoteStage.status === "approved"
      ? "当前阶段已批准，下一阶段已解锁"
      : remoteStage.status === "not_started"
        ? "等待前置阶段批准后解锁"
        : readiness?.can_submit
          ? "已满足提交条件，等待人工审批"
          : `进入下一阶段还缺 ${readiness?.missing.length ?? 0} 项`;
  const readinessPercent = readiness?.percent ?? 0;
  return (
    <div className="generic-stage">
      <section className="stage-hero-card">
        <div className="stage-hero-index">{stage.id}</div>
        <div><p className="eyebrow">本阶段目标</p><h2>{stage.name}</h2><p>与 {stage.agent} 协作形成一份可审阅资产，所有建议都先作为草稿，由研究者决定是否接受。</p></div>
      </section>
      <div className="stage-summary-grid">
        <article><span>01</span><p className="eyebrow">主要交付</p><h3>{stage.output}</h3><button onClick={onOpenDraft}>打开当前草稿 →</button></article>
        <article><span>02</span><p className="eyebrow">需要你决定</p><h3>{stage.decision}</h3><button onClick={onOpenDecision}>查看待决定项 →</button></article>
        <article><span>03</span><p className="eyebrow">退出检查</p><h3>{stage.check}</h3><button onClick={onRunCheck}>运行一致性检查 →</button></article>
      </div>
      <section className="stage-handoff-card">
        <div><p className="eyebrow">Handoff readiness</p><h3>{handoffTitle}</h3>{readiness && readiness.missing.length > 0 && <small>{readiness.missing.join(" · ")}</small>}</div>
        <div className="readiness-track"><span style={{ width: `${readinessPercent}%` }} /></div>
        <strong>{readinessPercent}%</strong>
      </section>
    </div>
  );
}

function ProblemQuestionControl({
  stage,
  busy,
  onSelect,
}: {
  stage?: ApiProjectStage;
  busy: boolean;
  onSelect: (questionId: string, rationale: string) => Promise<void>;
}) {
  const candidates = Array.isArray(stage?.content.question_candidates)
    ? stage.content.question_candidates.flatMap((raw) => {
        const item = asRecord(raw);
        return item && typeof item.question_id === "string" && typeof item.statement === "string"
          ? [{
              id: item.question_id,
              statement: item.statement,
              type: typeof item.question_type === "string" ? item.question_type : "待判断",
              decision: typeof item.management_decision === "string" ? item.management_decision : "待补充",
              feasibility: typeof item.feasibility_status === "string" ? item.feasibility_status : "unknown",
            }]
          : [];
      })
    : [];
  const selection = asRecord(stage?.content.question_selection);
  const savedQuestionId = typeof selection?.selected_question_id === "string"
    ? selection.selected_question_id
    : "";
  const [selectedId, setSelectedId] = useState(savedQuestionId || candidates[0]?.id || "");
  const [rationale, setRationale] = useState(
    typeof selection?.rationale === "string" ? selection.rationale : "",
  );
  if (!stage || candidates.length === 0) {
    return (
      <section className="research-control-card is-waiting">
        <header><div><p className="eyebrow">Human control · G0</p><h2>候选研究问题尚未生成</h2></div><span>等待 Topic Agent</span></header>
        <p>先生成 S0 正式资产；智能体会给出多个可证伪候选，但不会代替研究者选择。</p>
      </section>
    );
  }
  return (
    <section className="research-control-card">
      <header><div><p className="eyebrow">Human control · G0</p><h2>人工选择核心研究问题</h2></div><span>{savedQuestionId ? `已选择 ${savedQuestionId}` : "G0 前置"}</span></header>
      <div className="question-candidate-list">
        {candidates.map((candidate) => (
          <label className={selectedId === candidate.id ? "is-selected" : ""} key={candidate.id}>
            <input type="radio" name="research-question-candidate" checked={selectedId === candidate.id} onChange={() => setSelectedId(candidate.id)} />
            <span>{candidate.id}</span>
            <div><strong>{candidate.statement}</strong><small>{candidate.type} · {candidate.feasibility} · 管理决定：{candidate.decision}</small></div>
          </label>
        ))}
      </div>
      <div className="research-control-actions">
        <label><span>选择理由</span><textarea rows={3} value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="说明边界、理论价值、数据可行性与未采用候选的主要取舍。" /></label>
        <button className="primary-action" disabled={busy || !selectedId || rationale.trim().length < 3} onClick={() => void onSelect(selectedId, rationale.trim())}>{busy ? "正在保存…" : "保存人工选择到 revision"}</button>
      </div>
    </section>
  );
}

function LiteraturePlanControl({
  stage,
  busy,
  onReview,
}: {
  stage?: ApiProjectStage;
  busy: boolean;
  onReview: (decision: "approve" | "request_changes", reason: string) => Promise<void>;
}) {
  const queryBlocks = Array.isArray(stage?.content.query_blocks)
    ? stage.content.query_blocks.flatMap((raw) => {
        const item = asRecord(raw);
        const query = typeof item?.query_en === "string"
          ? item.query_en
          : typeof item?.query_zh === "string"
            ? item.query_zh
            : "";
        return query
          ? [{ label: typeof item?.label === "string" ? item.label : "查询块", query }]
          : [];
      })
    : [];
  const review = asRecord(stage?.content.literature_plan_review);
  const status = typeof review?.status === "string" ? review.status : "pending";
  const [reason, setReason] = useState(
    typeof review?.reason === "string"
      ? review.reason
      : "已核对检索主题、数据库、时间范围、纳排标准、反向检索与覆盖限制。",
  );
  return (
    <section className={`research-control-card literature-plan-control status-${status}`}>
      <header><div><p className="eyebrow">Human control · Search protocol</p><h2>检索计划人工审阅</h2></div><span>{status === "approved" ? "已批准当前计划" : status === "changes_requested" ? "已退回修改" : "检索前置"}</span></header>
      {queryBlocks.length ? (
        <>
          <div className="query-plan-preview">
            {queryBlocks.slice(0, 4).map((block, index) => <article key={`${block.label}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{block.label}</strong><code>{block.query}</code></div></article>)}
          </div>
          <div className="research-control-actions">
            <label><span>审阅理由 / 修改要求</span><textarea rows={3} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
            <div><button disabled={busy || reason.trim().length < 3} onClick={() => void onReview("request_changes", reason.trim())}>退回修改</button><button className="primary-action" disabled={busy || reason.trim().length < 3} onClick={() => void onReview("approve", reason.trim())}>{busy ? "正在保存…" : "批准当前检索计划"}</button></div>
          </div>
        </>
      ) : <p>先让 Literature Agent 生成经典、近期、相邻、反向和争议查询族；未获人工批准时平台不会自动执行模型检索计划。</p>}
    </section>
  );
}

function DeliveryCenter({
  projectId,
  remoteStage,
  busy,
  onExport,
}: {
  projectId: string;
  remoteStage?: ApiProjectStage;
  busy: boolean;
  onExport: () => void;
}) {
  const exports = Array.isArray(remoteStage?.content.exports)
    ? remoteStage.content.exports
        .map(asRecord)
        .filter((item): item is Record<string, unknown> => Boolean(item))
    : [];
  const latestRaw = exports.at(-1);
  const latest = latestRaw as unknown as DeliveryExportRecord | undefined;
  const complete = Boolean(
    latest?.export_id
    && latest.word_report_path
    && latest.pdf_report_path
    && latest.stata_package_path,
  );
  const reportUrl = latest?.export_id
    ? deliveryArtifactUrl(projectId, latest.export_id, "report")
    : "";

  return (
    <div className="delivery-center">
      <section className="delivery-heading">
        <div>
          <p className="eyebrow">Research delivery center</p>
          <h2>研究报告与复现交付</h2>
          <p>同一份获批研究资产生成可交互 HTML、可编辑 Word、固定版 PDF 和完整 Stata 复现包。</p>
        </div>
        <button
          className="delivery-refresh"
          type="button"
          disabled={busy || !remoteStage || remoteStage.revision < 1 || remoteStage.status === "not_started"}
          onClick={onExport}
        >
          <RefreshCw size={17} />
          {busy ? "正在生成" : latest ? "重新导出" : "生成交付物"}
        </button>
      </section>

      {!latest && (
        <section className="delivery-empty">
          <FileText size={30} />
          <div><h3>尚无正式导出</h3><p>先生成并保存 S9 草稿，再生成统一报告和 Stata 复现包。</p></div>
        </section>
      )}

      {latest && !complete && (
        <section className="delivery-empty delivery-upgrade">
          <RefreshCw size={28} />
          <div><h3>这是旧版交付记录</h3><p>重新导出后即可获得 Word、PDF、图表、Mermaid 和独立 Stata 复现包。</p></div>
        </section>
      )}

      {latest && complete && (
        <>
          <section className="delivery-actions" aria-label="报告下载">
            <a href={reportUrl} target="_blank" rel="noreferrer">
              <ExternalLink size={18} />
              <span><strong>打开 HTML</strong><small>交互图表与关系图</small></span>
            </a>
            <a href={deliveryArtifactUrl(projectId, latest.export_id, "word")} download>
              <FileType2 size={18} />
              <span><strong>下载 Word</strong><small>可继续编辑的 DOCX</small></span>
            </a>
            <a href={deliveryArtifactUrl(projectId, latest.export_id, "pdf")} download>
              <FileText size={18} />
              <span><strong>下载 PDF</strong><small>固定版本与归档</small></span>
            </a>
            <a href={deliveryArtifactUrl(projectId, latest.export_id, "stata")} download>
              <PackageCheck size={18} />
              <span><strong>Stata 复现包</strong><small>代码、结果、日志与签名</small></span>
            </a>
            <a href={deliveryArtifactUrl(projectId, latest.export_id, "package")} download>
              <Download size={18} />
              <span><strong>完整研究包</strong><small>全部报告与可视资产</small></span>
            </a>
          </section>

          <section className="delivery-preview">
            <header>
              <div><p className="eyebrow">Interactive HTML preview</p><h3>{String(remoteStage?.content.title || "AI4MS 研究报告")}</h3></div>
              <div><span>{latest.file_count} 个文件</span><code>{latest.package_sha256.slice(0, 12)}</code></div>
            </header>
            <iframe src={reportUrl} title="AI4MS 可交互研究报告预览" />
            <footer>
              <span>Export {latest.export_id}</span>
              <span>{new Date(latest.generated_at).toLocaleString("zh-CN")}</span>
              <span>Source S9 revision {latest.source_delivery_revision}</span>
            </footer>
          </section>
        </>
      )}
    </div>
  );
}

function EvidenceLibrary({
  records,
  candidates,
  searchRuns,
  busy,
  onOpenRecord,
  onSearch,
  onReview,
  onToast,
}: {
  records: EvidenceRecord[];
  candidates: EvidenceCandidate[];
  searchRuns: number;
  busy: boolean;
  onOpenRecord: (evidenceId: string) => void;
  onSearch: (
    query: string,
    candidateType: "literature" | "data_study",
  ) => Promise<void>;
  onReview: (
    candidate: EvidenceCandidate,
    decision: "approve" | "reject" | "request_changes",
    reason: string,
    evidenceLevel: EvidenceLevel,
    edits: Record<string, unknown>,
  ) => Promise<void>;
  onToast: (message: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState("全部");
  const [searchOpen, setSearchOpen] = useState(false);
  const [draftQuery, setDraftQuery] = useState("");
  const [candidateType, setCandidateType] = useState<"literature" | "data_study">("literature");
  const [queueOpen, setQueueOpen] = useState(true);
  const filtered = records.filter((item) => {
    const haystack = `${item.title} ${item.authors} ${item.stream} ${item.method}`.toLowerCase();
    const queryTerms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const matchesQuery = queryTerms.length === 0 || queryTerms.some((term) => haystack.includes(term));
    const matchesFilter = activeFilter === "全部" || item.stream === activeFilter;
    return matchesQuery && matchesFilter;
  });
  const streams = ["全部", ...Array.from(new Set(records.map((item) => item.stream)))];
  const pending = candidates.filter((item) => item.status === "pending" || item.status === "changes_requested");
  const approvedCandidates = candidates.filter((item) => item.status === "approved").length;
  const verified = records.filter((item) => item.evidenceLevel === "full_text" || item.evidenceLevel === "source_page").length;
  return (
    <div className="library-view page-view">
      <header className="view-header"><div><p className="eyebrow">Evidence governance · candidate → human review → authority</p><h1>证据库</h1><p>智能体找到的文献与数据研究先进入候选队列；只有人工批准的版本才可被论文引用。</p></div><button className="primary-compact" onClick={() => setSearchOpen((open) => !open)}>＋ 智能体联网发现</button></header>
      <div className="metric-strip">
        <div><strong>{pending.length}</strong><span>等待人工处理</span></div><div><strong>{records.length}</strong><span>权威证据记录</span></div><div><strong>{searchRuns}</strong><span>已保存检索批次</span></div><div><strong>{verified}</strong><span>全文 / 来源页核验</span></div>
      </div>
      {searchOpen && <section className="search-composer evidence-search-composer" aria-label="新建证据发现任务"><div><p className="eyebrow">Agent discovery</p><h2>创建可复核候选发现任务</h2><p>搜索结果不会直接进入权威库。来源、查询、快照和 AI 报告会随候选保存，等待人工审阅。</p></div><label><span>候选类型</span><select value={candidateType} onChange={(event) => setCandidateType(event.target.value as "literature" | "data_study")}><option value="literature">学术文献</option><option value="data_study">数据来源与数据研究</option></select></label><label><span>检索问题</span><input value={draftQuery} onChange={(event) => setDraftQuery(event.target.value)} placeholder={candidateType === "literature" ? "例如：生成式 AI 企业创新 双重差分" : "例如：中国企业数字化转型 面板数据 官方来源"} autoFocus /></label><div><button onClick={() => setSearchOpen(false)} disabled={busy}>取消</button><button className="primary-action" disabled={busy} onClick={() => { const nextQuery = draftQuery.trim(); if (nextQuery.length < 3) { onToast("检索问题至少需要 3 个字符"); return; } void onSearch(nextQuery, candidateType).then(() => { setSearchOpen(false); setQueueOpen(true); }); }}>{busy ? "发现中…" : "联网发现候选"}</button></div></section>}

      <section className="evidence-governance-panel">
        <header><div><p className="eyebrow">Human review queue</p><h2>候选审核队列</h2><p>批准前可修改题名、作者 / 机构、年份、来源与摘要；每次决定都会生成新的 S1 revision。</p></div><div><span>{pending.length} 待处理 · {approvedCandidates} 已批准 · {candidates.length - pending.length - approvedCandidates} 已拒绝</span><button onClick={() => setQueueOpen((open) => !open)}>{queueOpen ? "收起队列" : "展开队列"}</button></div></header>
        {queueOpen && <div className="evidence-candidate-list">
          {pending.map((candidate) => <EvidenceCandidateReviewCard key={`${candidate.candidate_id}:${candidate.revision}`} candidate={candidate} busy={busy} onReview={onReview} />)}
          {pending.length === 0 && <div className="empty-state">{candidates.length ? "所有当前候选均已处理。新的联网发现结果会先进入这里。" : "尚无候选。运行一次“智能体联网发现”，再由研究者逐条审核。"}</div>}
        </div>}
      </section>

      <section className="content-card library-panel">
        <header className="authority-library-heading"><div><p className="eyebrow">Authoritative evidence</p><h2>已批准证据</h2><p>论文参考文献、主张与 AI 报告只链接这里的 `EVLIB_*` 记录。</p></div><span>{records.length} 条 active authority</span></header>
        <div className="library-tools">
          <label className="search-field"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索题名、作者、方法或流派" aria-label="搜索证据库" /></label>
          <div className="filter-chips" aria-label="研究流派筛选">
            {streams.map((filter) => <button className={activeFilter === filter ? "is-active" : ""} onClick={() => setActiveFilter(filter)} key={filter}>{filter}</button>)}
          </div>
        </div>
        <div className="library-table-wrap">
          <table className="library-table"><thead><tr><th>权威记录</th><th>类型 / 来源</th><th>年份</th><th>版本</th><th>证据等级</th><th /></tr></thead><tbody>
            {filtered.map((item) => <tr key={item.id}><td><strong>{item.title}</strong><span>{item.id} · {item.authors || "作者 / 机构待补充"}</span></td><td>{item.evidenceType === "data_study" ? "数据研究" : "学术文献"}<br /><small>{item.stream}</small></td><td>{item.year || "待核验"}</td><td>Revision {item.revision ?? 1}</td><td><span className={`source-level ${item.evidenceLevel === "full_text" || item.evidenceLevel === "source_page" ? "verified" : ""}`}>{item.status}</span></td><td><button className="row-action" onClick={() => onOpenRecord(item.id)}>打开并编辑</button></td></tr>)}
          </tbody></table>
          {filtered.length === 0 && <div className="empty-state">{records.length === 0 ? "权威证据库为空。候选必须先经过人工批准，才会出现在这里并允许进入参考文献。" : "没有匹配的证据，试试调整关键词或流派。"}</div>}
        </div>
      </section>
    </div>
  );
}

function EvidenceCandidateReviewCard({
  candidate,
  busy,
  onReview,
}: {
  candidate: EvidenceCandidate;
  busy: boolean;
  onReview: (
    candidate: EvidenceCandidate,
    decision: "approve" | "reject" | "request_changes",
    reason: string,
    evidenceLevel: EvidenceLevel,
    edits: Record<string, unknown>,
  ) => Promise<void>;
}) {
  const [title, setTitle] = useState(candidate.title);
  const [authors, setAuthors] = useState(candidate.authors.join("；"));
  const [year, setYear] = useState(candidate.year ? String(candidate.year) : "");
  const [venue, setVenue] = useState(candidate.venue);
  const [url, setUrl] = useState(candidate.url);
  const [abstract, setAbstract] = useState(candidate.abstract || candidate.summary || "");
  const [reason, setReason] = useState(candidate.review?.reason ?? "已核对来源相关性、稳定链接与当前可用证据等级。");
  const [evidenceLevel, setEvidenceLevel] = useState<EvidenceLevel>(
    candidate.candidate_type === "data_study"
      ? "source_page"
      : candidate.abstract
        ? "abstract"
        : "metadata",
  );
  const edits = {
    title: title.trim(),
    authors: authors.split(/；|;|\n/).map((item) => item.trim()).filter(Boolean),
    year: year.trim() ? Number(year) : null,
    venue: venue.trim(),
    url: url.trim(),
    abstract: abstract.trim(),
  };
  const canSubmit = reason.trim().length >= 3 && title.trim().length > 0 && /^https?:\/\//.test(url.trim());
  return <article className="evidence-candidate-card">
    <header><div><span>{candidate.candidate_type === "literature" ? "文献候选" : "数据研究候选"}</span><strong>{candidate.candidate_id}</strong></div><small>{candidate.status === "changes_requested" ? "已退回，等待再次审阅" : "等待首次人工审阅"} · Revision {candidate.revision}</small></header>
    <div className="candidate-edit-grid">
      <label className="wide"><span>题名 / 数据研究名称</span><input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
      <label><span>作者 / 机构（分号分隔）</span><input value={authors} onChange={(event) => setAuthors(event.target.value)} /></label>
      <label><span>年份</span><input inputMode="numeric" value={year} onChange={(event) => setYear(event.target.value.replace(/[^\d]/g, "").slice(0, 4))} /></label>
      <label><span>期刊 / 数据机构</span><input value={venue} onChange={(event) => setVenue(event.target.value)} /></label>
      <label className="wide"><span>稳定来源链接</span><input value={url} onChange={(event) => setUrl(event.target.value)} /></label>
      <label className="wide"><span>摘要 / 来源页证据概括</span><textarea rows={4} value={abstract} onChange={(event) => setAbstract(event.target.value)} /></label>
      <label><span>当前证据等级</span><select value={evidenceLevel} onChange={(event) => setEvidenceLevel(event.target.value as EvidenceLevel)}><option value="metadata">仅元数据</option><option value="abstract">已核验摘要</option><option value="full_text">已核验全文</option><option value="source_page">已核验来源页</option></select></label>
      <label className="wide"><span>人工决定理由</span><textarea rows={3} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
    </div>
    <footer><a href={candidate.url} target="_blank" rel="noreferrer">核对原始来源 ↗</a><div><button disabled={busy || reason.trim().length < 3} onClick={() => void onReview(candidate, "reject", reason.trim(), evidenceLevel, edits)}>拒绝</button><button disabled={busy || reason.trim().length < 3} onClick={() => void onReview(candidate, "request_changes", reason.trim(), evidenceLevel, edits)}>退回补充</button><button className="primary-action" disabled={busy || !canSubmit} onClick={() => void onReview(candidate, "approve", reason.trim(), evidenceLevel, edits)}>{busy ? "保存中…" : "批准进入证据库"}</button></div></footer>
  </article>;
}

function MethodsView({
  methods,
  formulas,
  governanceCandidates,
  governanceRecords,
  diagnosticRules,
  diagnosticRegistryVersion,
  evaluation,
  busy,
  onEvaluate,
  onOpenMethod,
  onOpenFormula,
  onAdd,
  onDiscover,
  onReviewCandidate,
  onCreateRecord,
  onPatchRecord,
  onToast,
}: {
  methods: MethodRecord[];
  formulas: FormulaRecord[];
  governanceCandidates: KnowledgeGovernanceCandidate[];
  governanceRecords: KnowledgeGovernanceRecord[];
  diagnosticRules: DiagnosticRule[];
  diagnosticRegistryVersion: string;
  evaluation?: KnowledgeEvaluation;
  busy: boolean;
  onEvaluate: () => Promise<void>;
  onOpenMethod: (methodId: string) => void;
  onOpenFormula: (formulaId: string) => void;
  onAdd: (methodId: string) => void;
  onDiscover: (kind: KnowledgeAssetKind, query: string) => Promise<void>;
  onReviewCandidate: (
    candidate: KnowledgeGovernanceCandidate,
    decision: "approve" | "reject" | "request_changes",
    reason: string,
    content: Record<string, unknown>,
  ) => Promise<void>;
  onCreateRecord: (
    kind: KnowledgeAssetKind,
    content: Record<string, unknown>,
    reason: string,
  ) => Promise<KnowledgeGovernanceRecord | null>;
  onPatchRecord: (
    record: KnowledgeGovernanceRecord,
    content: Record<string, unknown>,
    reason: string,
  ) => Promise<void>;
  onToast: (message: string) => void;
}) {
  const [tab, setTab] = useState<"methods" | "formulas" | "diagnostics" | "governance" | "design">("methods");
  const [selected, setSelected] = useState(methods[0].id);
  const [query, setQuery] = useState("");
  const [family, setFamily] = useState("全部");
  const [compare, setCompare] = useState<string[]>(["M01", "M02"]);
  const [expandedDiagnostic, setExpandedDiagnostic] = useState<string | null>("D01");
  const families = ["全部", ...Array.from(new Set((tab === "diagnostics" ? diagnosticRules.map((rule) => rule.family) : methods.map((method) => method.family))))];
  const filteredMethods = methods.filter((method) => (family === "全部" || method.family === family) && `${method.name} ${method.goal} ${method.tags.join(" ")}`.toLowerCase().includes(query.trim().toLowerCase()));
  const filteredFormulas = formulas.filter((formula) => (family === "全部" || formula.family.includes(family) || methods.find((method) => method.id === formula.methodId)?.family === family) && `${formula.title} ${formula.formula} ${formula.purpose}`.toLowerCase().includes(query.trim().toLowerCase()));
  const filteredDiagnostics = diagnosticRules.filter((rule) => (family === "全部" || rule.family === family) && `${rule.id} ${rule.family} ${rule.name} ${rule.appliesTo} ${rule.trigger} ${rule.evidence} ${rule.action} ${rule.implementation}`.toLowerCase().includes(query.trim().toLowerCase()));
  const activeMethod = filteredMethods.find((method) => method.id === selected) ?? filteredMethods[0] ?? methods.find((method) => method.id === selected) ?? methods[0];
  const toggleCompare = (methodId: string) => setCompare((current) => current.includes(methodId) ? current.filter((item) => item !== methodId) : current.length < 3 ? [...current, methodId] : [...current.slice(1), methodId]);
  const changeTab = (next: typeof tab) => { setTab(next); setQuery(""); setFamily("全部"); };
  return <div className="methods-view page-view method-studio">
    <header className="view-header method-studio-header"><div><p className="eyebrow">Method & Formula Studio · versioned registry</p><h1>方法与公式库</h1><p>从研究目标和数据结构出发，连接公式、假设、诊断、代码与人工选择记录。</p><small>{evaluation?.status === "current" ? `${evaluation.model} · ${new Date(evaluation.evaluated_at).toLocaleString("zh-CN")}` : evaluation?.status === "stale" ? "研究上下文已变化，原 AI 评分已过期" : "尚未针对当前项目运行 AI 适配评估"}</small></div><div className="studio-metrics"><div><strong>{methods.length}</strong><span>核心方法</span></div><div><strong>{formulas.length}</strong><span>公式模板</span></div><div><strong>{diagnosticRules.length}</strong><span>诊断规则</span></div><button className="primary-compact" disabled={busy} onClick={() => void onEvaluate()}>{busy ? "AI 评估中…" : "AI 评估当前课题"}</button></div></header>
    <nav className="studio-tabs" aria-label="方法工作台分区">{[["methods", "方法库"], ["formulas", "公式库"], ["diagnostics", "诊断规则"], ["governance", "联网与审核"], ["design", "当前研究设计"]].map(([key, label]) => <button className={tab === key ? "is-active" : ""} onClick={() => changeTab(key as typeof tab)} key={key}>{label}<span>{key === "methods" ? methods.length : key === "formulas" ? formulas.length : key === "diagnostics" ? diagnosticRules.length : key === "governance" ? governanceCandidates.filter((item) => item.status === "pending" || item.status === "changes_requested").length : compare.length}</span></button>)}</nav>
    {tab !== "governance" && <section className="studio-toolbar"><label className="search-field"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={tab === "diagnostics" ? "搜索规则、适用方法、触发条件或 Stata 命令" : "搜索目标、方法、公式、诊断或标签"} aria-label="搜索方法、公式与诊断规则" /></label><select value={family} onChange={(event) => setFamily(event.target.value)} aria-label="筛选知识家族">{families.map((item) => <option key={item}>{item}</option>)}</select><button onClick={() => { setQuery(""); setFamily("全部"); }}>清除筛选</button></section>}

    {tab === "methods" && <div className="method-library-shell"><section className="method-library-list" aria-label="候选方法">{filteredMethods.map((method) => <article className={`method-library-row ${selected === method.id ? "is-selected" : ""}`} key={method.id}><button className="method-row-main" onClick={() => setSelected(method.id)}><span className="method-code">{method.id}</span><div><div><b>{method.family}</b><small>{method.dataShape}</small></div><h2>{method.name}</h2><p>{method.goal}</p><div className="method-tag-row">{method.tags.slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}</div></div><strong className="method-row-fit">{method.fit === null ? "待评估" : <>{method.fit}<small>%</small></>}</strong></button><div className="method-row-actions"><button className={compare.includes(method.id) ? "is-active" : ""} onClick={() => toggleCompare(method.id)}>{compare.includes(method.id) ? "已加入比较" : "加入比较"}</button><button onClick={() => onOpenMethod(method.id)}>完整方法卡 →</button></div></article>)}{filteredMethods.length === 0 && <div className="empty-state">没有匹配的方法，请调整关键词或方法家族。</div>}</section><aside className="method-detail method-studio-detail"><p className="eyebrow">Selected method</p><div className="selected-method-title"><div><span>{activeMethod.id}</span><h2>{activeMethod.name}</h2></div><strong>{activeMethod.fit === null ? "待 AI 评估" : `${activeMethod.fit}%`}</strong></div><pre>{activeMethod.formula}</pre>{activeMethod.fitRationale && <p>{activeMethod.fitRationale}</p>}<dl><div><dt>目标</dt><dd>{activeMethod.estimand}</dd></div><div><dt>数据</dt><dd>{activeMethod.dataShape}</dd></div><div><dt>实现</dt><dd>{activeMethod.engine}</dd></div></dl><h3>关键假设</h3><ul>{activeMethod.assumptions.map((item) => <li key={item}><span>!</span>{item}</li>)}</ul><div className="method-warning"><strong>失败规则</strong><p>{activeMethod.failureRule}</p></div><div className="method-detail-actions"><button onClick={() => onOpenMethod(activeMethod.id)}>审阅完整方法卡</button><button className="primary-action" onClick={() => onAdd(activeMethod.id)}>加入研究设计</button></div></aside></div>}

    {tab === "formulas" && <section className="formula-library-grid">{filteredFormulas.map((formula) => <article className="formula-library-card" key={formula.id}><header><span>{formula.id}</span><b>{formula.family}</b><small>{formula.fit == null ? "待 AI 评估" : `AI 适配度 ${formula.fit}%`}</small></header><h2>{formula.title}</h2><p>{formula.fitRationale || formula.purpose}</p><pre>{formula.formula}</pre><div className="formula-card-meta"><span>{formula.symbols.length} 个符号</span><span>{formula.assumptions.length} 项假设</span><span>{formula.diagnostics.length} 项诊断</span></div><footer><button onClick={() => { void navigator.clipboard?.writeText(formula.formula); onToast(`${formula.id} 公式已复制`); }}>复制公式</button><button className="primary-action" onClick={() => onOpenFormula(formula.id)}>打开公式卡 →</button></footer></article>)}</section>}

    {tab === "diagnostics" && <section className="diagnostic-registry"><header><div><p className="eyebrow">Diagnostic policy registry · {diagnosticRegistryVersion || "正在加载后端注册表"}</p><h2>诊断不是附录，是方法的退出条件</h2><p>规则由后端权威注册表提供；每条都包含适用方法、触发时点、所需证据、失败动作和实现提示。</p></div><div><span>当前显示 <strong>{filteredDiagnostics.length}</strong> / {diagnosticRules.length}</span><button disabled={!filteredDiagnostics.length} onClick={() => onToast(`已在当前页选中 ${filteredDiagnostics.length} 条候选规则；请到 S5 草稿保存正式 revision`)}>标记当前结果</button></div></header><div className="diagnostic-rule-grid">{filteredDiagnostics.map((rule) => { const expanded = expandedDiagnostic === rule.id; return <article className={`diagnostic-rule-card level-${rule.level} ${expanded ? "is-expanded" : ""}`} key={rule.id}><header><span>{rule.id}</span><b>{rule.level}</b><small>{rule.stage}</small></header><div className="diagnostic-rule-family">{rule.family}</div><h3>{rule.name}</h3><p>{rule.appliesTo}</p><dl><div><dt>触发</dt><dd>{rule.trigger}</dd></div>{expanded && <><div><dt>证据</dt><dd>{rule.evidence}</dd></div><div><dt>失败动作</dt><dd>{rule.action}</dd></div></>}</dl>{expanded && <div className="diagnostic-implementation"><span>实现提示</span><code>{rule.implementation}</code></div>}<footer><button onClick={() => onToast(`${rule.id} ${rule.name} 仅标记为候选；尚未写入后端分析计划`)}>标记候选</button><button className="primary-action" onClick={() => setExpandedDiagnostic(expanded ? null : rule.id)}>{expanded ? "收起规则" : "查看完整规则"}</button></footer></article>; })}{filteredDiagnostics.length === 0 && <div className="empty-state">{diagnosticRules.length === 0 ? "正在连接后端诊断注册表；加载失败时请检查 FastAPI 服务。" : "没有匹配的诊断规则，请清除筛选或更换关键词。"}</div>}</div></section>}

    {tab === "governance" && <KnowledgeGovernancePanel candidates={governanceCandidates} records={governanceRecords} busy={busy} onDiscover={onDiscover} onReviewCandidate={onReviewCandidate} onCreateRecord={onCreateRecord} onPatchRecord={onPatchRecord} />}

    {tab === "design" && <section className="current-design-board"><header><div><p className="eyebrow">Research design bundle</p><h2>当前候选方法比较</h2><p>最多同时比较 3 个候选；确定主模型前必须记录未采用理由。</p></div><button className="primary-action" disabled={!compare.length} onClick={() => { if (compare[0]) onAdd(compare[0]); }}>将首项设为主方案草稿</button></header><div className="design-compare-grid">{compare.map((methodId, index) => { const method = methods.find((item) => item.id === methodId); if (!method) return null; return <article key={method.id}><div><span>{index === 0 ? "PRIMARY CANDIDATE" : `ALTERNATIVE ${index}`}</span><button onClick={() => toggleCompare(method.id)}>移除</button></div><h2>{method.name}</h2><pre>{method.formula}</pre><dl><div><dt>估计 / 决策目标</dt><dd>{method.estimand}</dd></div><div><dt>数据结构</dt><dd>{method.dataShape}</dd></div><div><dt>失败规则</dt><dd>{method.failureRule}</dd></div></dl><button onClick={() => onOpenMethod(method.id)}>打开方法卡核对</button></article>; })}{!compare.length && <div className="empty-state">从“方法库”加入 1–3 个候选方法进行比较。</div>}</div></section>}
  </div>;
}

const knowledgeFieldDefinitions = {
  method: [
    ["name", "方法名称"],
    ["family", "方法家族"],
    ["goal", "研究目标 / estimand"],
    ["data", "适用数据结构"],
    ["assumptions", "关键假设"],
    ["workflow", "标准流程"],
    ["diagnostics", "必须诊断"],
    ["robustness", "稳健性要求"],
    ["packages", "Stata / Python / Solver 包"],
    ["failure", "失败与退出规则"],
    ["source_urls", "原始来源链接"],
  ],
  formula: [
    ["name", "公式名称"],
    ["category", "公式类别"],
    ["latex", "LaTeX / 纯文本公式"],
    ["use_when", "适用条件"],
    ["notation", "符号定义"],
    ["assumptions", "关键假设"],
    ["diagnostics", "关联诊断"],
    ["packages", "实现命令 / 软件包"],
    ["warning", "误用警告"],
    ["source_urls", "原始来源链接"],
  ],
} as const;

function editableKnowledgeValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join("\n");
  return value === null || value === undefined ? "" : String(value);
}

function KnowledgeContentEditor({
  kind,
  content,
  onChange,
}: {
  kind: KnowledgeAssetKind;
  content: Record<string, unknown>;
  onChange: (content: Record<string, unknown>) => void;
}) {
  const update = (key: string, raw: string) => {
    const value = key === "source_urls"
      ? raw.split(/\r?\n|；|;/).map((item) => item.trim()).filter(Boolean)
      : raw;
    onChange({ ...content, [key]: value });
  };
  return <div className="knowledge-content-editor">
    {knowledgeFieldDefinitions[kind].map(([key, label]) => {
      const multiline = ["goal", "assumptions", "workflow", "diagnostics", "robustness", "failure", "latex", "use_when", "notation", "warning", "source_urls"].includes(key);
      return <label className={multiline ? "is-wide" : ""} key={key}><span>{label}</span>{multiline
        ? <textarea rows={key === "latex" ? 3 : 4} value={editableKnowledgeValue(content[key])} onChange={(event) => update(key, event.target.value)} />
        : <input value={editableKnowledgeValue(content[key])} onChange={(event) => update(key, event.target.value)} />}</label>;
    })}
  </div>;
}

function KnowledgeCandidateReviewCard({
  candidate,
  busy,
  onReview,
}: {
  candidate: KnowledgeGovernanceCandidate;
  busy: boolean;
  onReview: (
    candidate: KnowledgeGovernanceCandidate,
    decision: "approve" | "reject" | "request_changes",
    reason: string,
    content: Record<string, unknown>,
  ) => Promise<void>;
}) {
  const [content, setContent] = useState(candidate.proposed_content);
  const [reason, setReason] = useState(candidate.review?.reason ?? "已对照原始来源核定方法 / 公式定义、适用条件、假设、诊断与失败规则。");
  const sourceUrl = candidate.source_links.find((item) => item.url)?.url;
  return <article className="knowledge-review-card">
    <header><div><span>{candidate.kind === "method" ? "方法候选" : "公式候选"}</span><strong>{candidate.candidate_id}</strong></div><small>Revision {candidate.revision} · {candidate.status === "changes_requested" ? "退回后再审" : "等待人工审核"}</small></header>
    <KnowledgeContentEditor kind={candidate.kind} content={content} onChange={setContent} />
    <label className="knowledge-review-reason"><span>人工审核理由</span><textarea rows={3} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
    <footer>{sourceUrl ? <a href={sourceUrl} target="_blank" rel="noreferrer">核对原始来源 ↗</a> : <span>缺少可打开来源，不能批准</span>}<div><button disabled={busy || reason.trim().length < 3} onClick={() => void onReview(candidate, "reject", reason.trim(), content)}>拒绝</button><button disabled={busy || reason.trim().length < 3} onClick={() => void onReview(candidate, "request_changes", reason.trim(), content)}>退回补全</button><button className="primary-action" disabled={busy || reason.trim().length < 3 || !sourceUrl} onClick={() => void onReview(candidate, "approve", reason.trim(), content)}>{busy ? "保存中…" : "批准入库"}</button></div></footer>
  </article>;
}

function KnowledgeRecordEditor({
  record,
  busy,
  onPatch,
}: {
  record: KnowledgeGovernanceRecord;
  busy: boolean;
  onPatch: (
    record: KnowledgeGovernanceRecord,
    content: Record<string, unknown>,
    reason: string,
  ) => Promise<void>;
}) {
  const [content, setContent] = useState(record.content);
  const [reason, setReason] = useState("人工修订权威知识记录");
  return <section className="knowledge-record-editor">
    <header><div><p className="eyebrow">Authority editor</p><h3>{String(content.name || record.record_id)}</h3></div><span>{record.record_id} · Revision {record.revision}</span></header>
    <KnowledgeContentEditor kind={record.kind} content={content} onChange={setContent} />
    <label className="knowledge-review-reason"><span>修改理由（写入版本历史）</span><textarea rows={3} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
    <footer><small>{record.content_hash.slice(0, 16)}… · {new Date(record.updated_at).toLocaleString("zh-CN")}</small><button className="primary-action" disabled={busy || reason.trim().length < 3} onClick={() => void onPatch(record, content, reason.trim())}>{busy ? "保存中…" : "保存新 Revision"}</button></footer>
  </section>;
}

function KnowledgeGovernancePanel({
  candidates,
  records,
  busy,
  onDiscover,
  onReviewCandidate,
  onCreateRecord,
  onPatchRecord,
}: {
  candidates: KnowledgeGovernanceCandidate[];
  records: KnowledgeGovernanceRecord[];
  busy: boolean;
  onDiscover: (kind: KnowledgeAssetKind, query: string) => Promise<void>;
  onReviewCandidate: (
    candidate: KnowledgeGovernanceCandidate,
    decision: "approve" | "reject" | "request_changes",
    reason: string,
    content: Record<string, unknown>,
  ) => Promise<void>;
  onCreateRecord: (
    kind: KnowledgeAssetKind,
    content: Record<string, unknown>,
    reason: string,
  ) => Promise<KnowledgeGovernanceRecord | null>;
  onPatchRecord: (
    record: KnowledgeGovernanceRecord,
    content: Record<string, unknown>,
    reason: string,
  ) => Promise<void>;
}) {
  const [kind, setKind] = useState<KnowledgeAssetKind>("method");
  const [query, setQuery] = useState("");
  const [manualOpen, setManualOpen] = useState(false);
  const [manualReason, setManualReason] = useState("研究者人工创建并核验知识记录");
  const [manualContent, setManualContent] = useState<Record<string, unknown>>({
    name: "",
    family: "",
    goal: "",
    data: "",
    assumptions: "",
    workflow: "",
    diagnostics: "",
    robustness: "",
    packages: "",
    failure: "",
    source_urls: [],
  });
  const [selectedRecordId, setSelectedRecordId] = useState("");
  const pending = candidates.filter((item) => item.status === "pending" || item.status === "changes_requested");
  const selectedRecord = records.find((item) => item.record_id === selectedRecordId) ?? records[0];
  const changeKind = (next: KnowledgeAssetKind) => {
    setKind(next);
    setManualContent(next === "method" ? {
      name: "", family: "", goal: "", data: "", assumptions: "", workflow: "",
      diagnostics: "", robustness: "", packages: "", failure: "", source_urls: [],
    } : {
      name: "", category: "", latex: "", use_when: "", notation: "",
      assumptions: "", diagnostics: "", packages: "", warning: "", source_urls: [],
    });
  };
  const createManualRecord = async () => {
    const created = await onCreateRecord(
      kind,
      manualContent,
      manualReason.trim(),
    );
    if (created) setSelectedRecordId(created.record_id);
  };
  return <section className="knowledge-governance">
    <header><div><p className="eyebrow">Knowledge governance</p><h2>联网候选、人工批准、版本化编辑</h2><p>智能体只能创建候选；研究者核对原始来源和适用边界后，才可提升为方法 / 公式权威记录。</p></div><div><strong>{pending.length}</strong><span>待人工审核</span><strong>{records.length}</strong><span>自定义权威记录</span></div></header>
    <section className="knowledge-discovery-bar">
      <select value={kind} onChange={(event) => changeKind(event.target.value as KnowledgeAssetKind)}><option value="method">搜索方法</option><option value="formula">搜索公式</option></select>
      <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={kind === "method" ? "例如：分期处理双重差分 管理学应用 诊断" : "例如：Callaway Sant'Anna group-time ATT 公式"} />
      <button className="primary-action" disabled={busy || query.trim().length < 3} onClick={() => void onDiscover(kind, query.trim())}>{busy ? "联网中…" : "智能体联网发现"}</button>
      <button onClick={() => setManualOpen((open) => !open)}>{manualOpen ? "关闭人工新建" : "＋ 人工新建"}</button>
    </section>
    {manualOpen && <section className="manual-knowledge-record"><header><div><p className="eyebrow">Human authored</p><h3>人工创建{kind === "method" ? "方法" : "公式"}记录</h3></div><span>至少保留一个可核验的 HTTP(S) 原始来源</span></header><KnowledgeContentEditor kind={kind} content={manualContent} onChange={setManualContent} /><label className="knowledge-review-reason"><span>创建理由</span><textarea rows={3} value={manualReason} onChange={(event) => setManualReason(event.target.value)} /></label><button className="primary-action" disabled={busy || manualReason.trim().length < 3} onClick={() => void createManualRecord()}>创建权威记录</button></section>}
    <section className="knowledge-queue"><header><div><h3>候选审核队列</h3><p>候选内容可在批准前直接修改；不完整的来源、假设或诊断应退回补全。</p></div><span>{pending.length} 项</span></header>{pending.map((candidate) => <KnowledgeCandidateReviewCard key={`${candidate.candidate_id}:${candidate.revision}`} candidate={candidate} busy={busy} onReview={onReviewCandidate} />)}{pending.length === 0 && <div className="empty-state">当前没有待审核候选。</div>}</section>
    <section className="knowledge-authority-workbench"><aside><p className="eyebrow">Custom authority</p><h3>人工批准记录</h3>{records.map((record) => <button className={selectedRecord?.record_id === record.record_id ? "is-active" : ""} key={record.record_id} onClick={() => setSelectedRecordId(record.record_id)}><span>{record.kind === "method" ? "方法" : "公式"}</span><strong>{String(record.content.name || record.record_id)}</strong><small>{record.record_id} · r{record.revision}</small></button>)}{records.length === 0 && <p>尚无自定义权威记录。</p>}</aside>{selectedRecord ? <KnowledgeRecordEditor key={`${selectedRecord.record_id}:${selectedRecord.revision}`} record={selectedRecord} busy={busy} onPatch={onPatchRecord} /> : <div className="empty-state">批准候选或人工新建后，可以在这里继续版本化编辑。</div>}</section>
  </section>;
}

function RunsView({
  project,
  apiProject,
  onProjectUpdated,
  onOpenGate,
  onToast,
}: {
  project: ResearchProject;
  apiProject?: ApiProject;
  onProjectUpdated: (project: ApiProject) => void;
  onOpenGate: (gateId: string) => void;
  onToast: (message: string) => void;
}) {
  const tabs = ["分析计划", "Do-file", "运行前检查", "正式运行", "结果审阅"];
  const [tab, setTab] = useState(2);
  const [runner, setRunner] = useState<RunnerStatus | null>(null);
  const [selectedAssetId, setSelectedAssetId] = useState("");
  const [preflight, setPreflight] = useState<AnalysisPreflight | null>(null);
  const [activeJob, setActiveJob] = useState<AnalysisJob | null>(null);
  const [jobResult, setJobResult] = useState<AnalysisRun | null>(null);
  const [timeoutSeconds, setTimeoutSeconds] = useState(3600);
  const [busy, setBusy] = useState<"upload" | "preflight" | "submit" | "cancel" | "rerun" | "runner" | "">("");
  const [error, setError] = useState("");
  const identification = apiProject?.stages.find((stage) => stage.key === "identification");
  const analysis = apiProject?.stages.find((stage) => stage.key === "analysis");
  const plan = identification?.content ?? {};
  const analysisContent = analysis?.content ?? {};
  const assets = useMemo(() => apiProject?.data_assets ?? [], [apiProject?.data_assets]);
  const effectiveAssetId = assets.some((asset) => asset.asset_id === selectedAssetId)
    ? selectedAssetId
    : assets[0]?.asset_id ?? "";
  const activePreflight = (
    preflight?.input_asset_id === effectiveAssetId
    && preflight.analysis_plan_revision === (identification?.revision ?? 0)
  ) ? preflight : null;
  const runs = (Array.isArray(analysisContent.runs) ? analysisContent.runs : []) as AnalysisRun[];
  const latestRun = jobResult ?? runs.at(-1);
  const structuredResults = latestRun?.structured_results ?? [];
  const doFile = typeof analysisContent.do_file === "string"
    ? analysisContent.do_file
    : typeof plan.stata_do_file === "string"
      ? plan.stata_do_file
      : "";
  const runLocked = identification?.status !== "approved";
  const selectedAsset = assets.find((asset) => asset.asset_id === effectiveAssetId);
  const passedChecks = activePreflight
    ? Object.values(activePreflight.checks).filter(Boolean).length
    : 0;
  const jobActive = Boolean(
    activeJob && ["queued", "running", "canceling"].includes(activeJob.status),
  );
  const canRerun = Boolean(
    activeJob
    && ["succeeded", "failed", "canceled", "interrupted"].includes(activeJob.status)
    && activeJob.request.input_asset_id === effectiveAssetId,
  );
  const activeRunId = activeJob?.run_id ?? "";
  const activeJobStatus = activeJob?.status ?? "";
  const displayedError = error || (
    activeJobStatus === "interrupted"
      ? "后台曾重启，此任务已中断；请检查输入与审批状态后重跑。"
      : ""
  );

  useEffect(() => {
    let cancelled = false;
    const refresh = () => {
      Promise.all([getStataRunnerStatus(), listAnalysisJobs(project.id)])
        .then(([status, jobs]) => {
          if (!cancelled) {
            setRunner(status);
            setActiveJob(jobs[0] ?? null);
          }
        })
        .catch((cause) => {
          if (!cancelled) setError(cause instanceof Error ? cause.message : "无法读取 Runner 状态");
        });
    };
    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [project.id]);

  useEffect(() => {
    if (!activeRunId || !["queued", "running", "canceling"].includes(activeJobStatus)) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const job = await getAnalysisJob(project.id, activeRunId);
        if (!cancelled) {
          setActiveJob(job);
        }
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "无法读取运行状态");
      }
    };
    const timer = window.setInterval(() => void poll(), 1500);
    void poll();
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [activeRunId, activeJobStatus, project.id]);

  useEffect(() => {
    if (
      !activeRunId
      || !["succeeded", "failed", "canceled"].includes(activeJobStatus)
      || jobResult?.run_id === activeRunId
    ) return;
    let cancelled = false;
    Promise.all([
      getAnalysisRunResult(project.id, activeRunId),
      getApiProject(project.id),
    ])
      .then(([result, refreshed]) => {
        if (cancelled) return;
        setJobResult(result);
        onProjectUpdated(refreshed);
        setTab(result.status === "succeeded" ? 4 : 3);
        onToast(
          result.status === "succeeded"
            ? `运行成功，回收 ${result.structured_results.length} 条结构化结果`
            : `运行结束：${result.reason_code}`,
        );
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "无法读取运行结果");
      });
    return () => { cancelled = true; };
  }, [activeRunId, activeJobStatus, jobResult?.run_id, onProjectUpdated, onToast, project.id]);

  async function upload(file: File) {
    if (!apiProject) {
      onToast("当前项目尚未连接 FastAPI");
      return;
    }
    setBusy("upload");
    setError("");
    try {
      const asset = await uploadDataAsset(project.id, file);
      const refreshed = await getApiProject(project.id);
      onProjectUpdated(refreshed);
      setSelectedAssetId(asset.asset_id);
      setPreflight(null);
      onToast(`已登记 ${asset.original_name}，SHA-256 与元信息已保存`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "数据上传失败");
    } finally {
      setBusy("");
    }
  }

  async function refreshRunnerStatus() {
    setBusy("runner");
    setError("");
    try {
      const status = await getStataRunnerStatus();
      setRunner(status);
      onToast(status.available ? "Stata Local Runner 已连接" : status.reason || "Stata Local Runner 尚不可用");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "无法读取 Runner 状态");
    } finally {
      setBusy("");
    }
  }

  async function runPreflight() {
    if (!effectiveAssetId) {
      setError("请先上传并选择一个 .dta 数据资产");
      return;
    }
    setBusy("preflight");
    setError("");
    try {
      const result = await preflightAnalysisRun(project.id, effectiveAssetId);
      setPreflight(result);
      onToast(result.status === "ready" ? "运行前检查全部通过" : `预检阻塞：${result.reason_code}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "运行前检查失败");
    } finally {
      setBusy("");
    }
  }

  async function startRun() {
    if (runLocked || activePreflight?.status !== "ready") {
      onToast(runLocked ? "需先完成 S5 并通过 G3 人工审批" : "请先完成运行前检查");
      return;
    }
    setBusy("submit");
    setError("");
    try {
      const job = await submitAnalysisRun(project.id, effectiveAssetId, timeoutSeconds);
      setActiveJob(job);
      setJobResult(null);
      setTab(3);
      onToast(`已提交后台任务 ${job.run_id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Stata 运行提交失败");
    } finally {
      setBusy("");
    }
  }

  async function cancelRun() {
    if (!activeJob || !["queued", "running", "canceling"].includes(activeJob.status)) return;
    setBusy("cancel");
    setError("");
    try {
      const job = await cancelAnalysisRun(project.id, activeJob.run_id);
      setActiveJob(job);
      onToast(`已请求取消 ${job.run_id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "取消运行失败");
    } finally {
      setBusy("");
    }
  }

  async function rerun() {
    if (!activeJob || !["succeeded", "failed", "canceled", "interrupted"].includes(activeJob.status)) return;
    setBusy("rerun");
    setError("");
    try {
      const job = await rerunAnalysis(project.id, activeJob.run_id, timeoutSeconds);
      setActiveJob(job);
      setJobResult(null);
      setTab(3);
      onToast(`已从 ${activeJob.run_id} 创建重跑 ${job.run_id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "创建重跑失败");
    } finally {
      setBusy("");
    }
  }

  const checkLabels: Record<string, string> = {
    gate_passed: "G3 分析计划已批准",
    binding_passed: "S6 与批准的 revision/hash 一致",
    engine_passed: "执行引擎为 Stata",
    policy_passed: "do-file 代码策略通过",
    input_passed: "项目数据文件存在且格式正确",
    asset_hash_passed: "文件 SHA-256 与资产登记一致",
    variable_mapping_passed: "S5 所需变量在数据中存在",
    runner_passed: "研究者本机 Local Runner 可连接",
    license_passed: "本机已确认合法 Stata 许可",
  };

  return (
    <div className="runs-view page-view">
      <header className="view-header">
        <div><p className="eyebrow">Stata Workbench</p><h1>可审批、可复现的分析运行</h1><p>Docker 工作台把签名运行包交给研究者本机 Stata，并回收结构化 Result Bundle。</p></div>
        <div className={`runner-status ${!runner?.available ? "is-waiting" : ""}`}>
          <span /> {!runner ? "正在检查 Local Runner" : runner.available
            ? <>Local Runner 在线 <b>{runner.edition} {runner.version}</b></>
            : `Local Runner 不可用：${runner.reason || "未连接"}`}
          <button data-testid="refresh-stata-runner" disabled={busy === "runner"} onClick={() => void refreshRunnerStatus()}>{busy === "runner" ? "检查中…" : "重新检查"}</button>
        </div>
      </header>
      {runner && !runner.available && <div className="runner-setup-hint"><div><strong>先在安装了合法 Stata 的电脑上配置 Local Runner</strong><p>Windows 运行 <code>scripts\stata-runner\SETUP_STATA_RUNNER.bat</code>，再运行 <code>START_STATA_RUNNER.bat</code>；平台不会捆绑 Stata 或许可证。</p></div><button onClick={() => void refreshRunnerStatus()}>配置后重新检查</button></div>}
      <div className={`run-gate-banner ${runLocked ? "is-locked" : ""}`}>
        <div><span>G3</span><div><strong>{runLocked ? "正式运行尚未解锁" : "分析计划与代码已冻结"}</strong><small>{runLocked ? `当前项目位于 S${project.stageIndex}；需完成 S5 分析计划并通过 G3` : `AnalysisPlan revision ${identification?.revision ?? 0} · ${identification?.content_hash?.slice(0, 12) ?? "无 hash"}`}</small></div></div>
        <button onClick={() => onOpenGate("G3")}>{runLocked ? "查看解锁条件" : "查看审批包"}</button>
      </div>
      {displayedError && <div className="run-error-banner">{displayedError}</div>}
      <div className="workbench-shell">
        <nav className="workbench-tabs" aria-label="Stata 工作台步骤">{tabs.map((item, index) => <button className={tab === index ? "is-active" : ""} onClick={() => setTab(index)} key={item}><span>{index + 1}</span>{item}</button>)}</nav>
        <section className="workbench-content">
          {tab === 0 && <div className="plan-grid">
            <article><p className="eyebrow">Approved objective</p><h3>{String(plan.estimand_or_objective || "等待 S5 冻结估计目标")}</h3><dl><div><dt>样本</dt><dd>{String(plan.analysis_sample || "待确认")}</dd></div><div><dt>分析单位</dt><dd>{String(plan.unit_of_analysis || "待确认")}</dd></div><div><dt>执行引擎</dt><dd>{String(plan.execution_engine || "unknown")}</dd></div><div><dt>计划 revision</dt><dd>{identification?.revision ?? 0}</dd></div></dl></article>
            <article><p className="eyebrow">Expected outputs</p><ul className="check-list">{(Array.isArray(plan.expected_outputs) ? plan.expected_outputs : []).map((item) => <li key={String(item)}>○ {String(item)}</li>)}{!Array.isArray(plan.expected_outputs) && <li>○ 等待 S5 定义输出</li>}</ul></article>
          </div>}
          {tab === 1 && <div className="code-pane"><div className="code-toolbar"><span>analysis.do · AnalysisPlan revision {identification?.revision ?? 0}</span><div><button onClick={() => onToast("代码修改必须返回 S5，生成新 revision 并重新通过 G3")}>修改规则</button></div></div><pre><code>{doFile || "* 尚无获批 Stata do-file"}</code></pre></div>}
          {tab === 2 && <div className="real-preflight">
            <div className="data-asset-toolbar">
              <div><p className="eyebrow">Input data asset</p><h3>选择项目内已登记的 `.dta`</h3></div>
              <label className="data-upload-button">{busy === "upload" ? "正在读取元信息…" : "上传 .dta"}<input type="file" accept=".dta,application/x-stata" disabled={busy !== ""} onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file); event.target.value = ""; }} /></label>
            </div>
            {assets.length > 0 ? <div className="asset-selection-row"><select value={effectiveAssetId} onChange={(event) => { setSelectedAssetId(event.target.value); setPreflight(null); }}><option value="">选择数据资产</option>{assets.map((asset) => <option value={asset.asset_id} key={asset.asset_id}>{asset.original_name} · {asset.metadata.row_count} 行 × {asset.metadata.column_count} 列</option>)}</select><button className="primary-action" disabled={busy !== "" || runLocked} onClick={() => void runPreflight()}>{busy === "preflight" ? "正在检查…" : "运行真实 Preflight"}</button></div> : <div className="empty-run-data"><strong>尚无项目数据资产</strong><p>上传后系统会登记文件、计算 SHA-256，并读取行列数、变量名、标签和 Stata 格式版本。</p></div>}
            {selectedAsset && <div className="asset-facts"><span><b>{selectedAsset.metadata.row_count}</b> 行</span><span><b>{selectedAsset.metadata.column_count}</b> 列</span><span><b>{selectedAsset.metadata.format_version}</b> 格式版本</span><code>SHA-256 {selectedAsset.sha256.slice(0, 16)}…</code></div>}
            {runLocked ? <div className="locked-workbench-state"><span>G3</span><div><p className="eyebrow">Preflight blocked</p><h3>等待 S5/G3 人工批准</h3><p>数据可以先登记，但只有获批的分析计划和 do-file 才能进入本机 Runner。</p></div><button onClick={() => onOpenGate("G3")}>查看 G3 条件</button></div> : activePreflight && <div className="preflight-layout"><div className="preflight-score"><div className="score-circle"><strong>{passedChecks}/{Object.keys(activePreflight.checks).length}</strong><span>{activePreflight.status === "ready" ? "检查通过" : "存在阻塞"}</span></div><h3>{activePreflight.status === "ready" ? "可以提交正式运行" : activePreflight.reason_code}</h3><p>{activePreflight.status === "ready" ? "审批、代码、资产哈希、变量、Runner 与许可一致。" : activePreflight.issues.map((issue) => issue.message).join("；")}</p></div><div className="preflight-checks">{Object.entries(activePreflight.checks).map(([key, passed]) => <div className={passed ? "" : "is-failed"} key={key}><span>{passed ? "✓" : "!"}</span>{checkLabels[key] ?? key}</div>)}</div></div>}
          </div>}
          {tab === 3 && <div className={`run-console ${runLocked ? "is-locked" : ""}`}>
            <div className="console-status">
              <div className={`run-state-icon state-${runLocked ? "locked" : activeJob?.status ?? latestRun?.status ?? "ready"}`}>
                {runLocked ? "锁" : jobActive ? "…" : latestRun?.status === "succeeded" ? "✓" : "▶"}
              </div>
              <div>
                <p className="eyebrow">Formal run</p>
                <h3>{runLocked ? "等待 G3 人工批准" : activeJob ? `${activeJob.run_id} · ${activeJob.status}` : latestRun ? `${latestRun.run_id} · ${latestRun.status}` : "等待人工启动"}</h3>
                <p>{runLocked ? "智能体不能绕过审批启动正式分析。" : activeJob ? `${activeJob.reason_code} · 超时 ${activeJob.timeout_seconds} 秒${activeJob.parent_run_id ? ` · rerun of ${activeJob.parent_run_id}` : ""}` : latestRun ? `${latestRun.reason_code} · exit ${latestRun.exit_code ?? "n/a"} · ${latestRun.structured_results.length} 条结构化结果` : "提交签名运行包前必须完成真实 Preflight。"}</p>
              </div>
            </div>
            <div className="run-controls">
              <label>超时（秒）<input type="number" min={1} max={7200} value={timeoutSeconds} disabled={jobActive} onChange={(event) => setTimeoutSeconds(Math.max(1, Math.min(7200, Number(event.target.value) || 1)))} /></label>
              {jobActive
                ? <button className="run-cancel-action" onClick={() => void cancelRun()} disabled={busy !== "" || activeJob?.status === "canceling"}>{busy === "cancel" || activeJob?.status === "canceling" ? "正在取消…" : "取消运行"}</button>
                : canRerun
                  ? <button className="primary-action" onClick={() => void rerun()} disabled={runLocked || busy !== "" || activePreflight?.status !== "ready"}>{busy === "rerun" ? "正在创建…" : "按原请求重跑"}</button>
                  : <button className="primary-action" onClick={() => void startRun()} disabled={runLocked || busy !== "" || activePreflight?.status !== "ready"}>{busy === "submit" ? "正在提交…" : "人工确认并启动"}</button>}
            </div>
            <div className="run-log" data-testid="stata-run-log">
              <span>[asset] {selectedAsset?.asset_id || "not selected"}</span>
              <span>[preflight] {activePreflight?.status || "not checked"}</span>
              <span>[runner] {runner?.available ? `${runner.executable_name} ${runner.version}` : "not available"}</span>
              {activeJob && <span className={activeJob.status === "succeeded" ? "log-success" : ""}>[job] {activeJob.status} · {activeJob.reason_code}</span>}
              {latestRun && <span className={latestRun.status === "succeeded" ? "log-success" : ""}>[result] {latestRun.status} · {latestRun.reason_code}</span>}
              {latestRun?.logs?.map((path) => <a href={analysisRunArtifactUrl(project.id, latestRun.run_id, path)} target="_blank" rel="noreferrer" key={path}>[log] {path}</a>)}
            </div>
          </div>}
          {tab === 4 && (!latestRun || latestRun.status !== "succeeded" ? <div className="locked-results-state"><span>∅</span><h3>尚无符合契约的正式运行结果</h3><p>这里只显示通过 run_id、数据 SHA-256、do-file hash 和 Result Bundle 校验的结果。</p><button onClick={() => setTab(2)}>返回运行前检查</button></div> : <div className="real-results-review"><header><div><p className="eyebrow">Result Bundle 1.0</p><h3>{latestRun.run_id}</h3></div><div><span>数据签名</span><code>{latestRun.data_signature || "未返回"}</code></div></header><div className="result-table"><div className="result-table-head"><span>规格 / 变量</span><span>估计值</span><span>标准误</span><span>p 值</span><span>95% CI</span><span>N</span></div>{structuredResults.map((result) => <div key={result.result_id}><span><b>{result.term || result.label}</b><small>{result.specification_id}</small></span><code>{result.estimate?.toPrecision(5) ?? "—"}</code><code>{result.std_error?.toPrecision(4) ?? "—"}</code><code>{result.p_value?.toPrecision(4) ?? "—"}</code><code>{result.ci_lower?.toPrecision(4) ?? "—"} – {result.ci_upper?.toPrecision(4) ?? "—"}</code><code>{result.sample_size ?? "—"}</code></div>)}</div><footer><strong>{latestRun.output_artifacts.length} 项产物已登记 SHA-256</strong><span>结果解释和科学主张仍需进入 S7、S8 与 G4。</span></footer></div>)}
        </section>
      </div>
    </div>
  );
}

function ApprovalsView({ project, apiProject, onOpenGate, onOpenDetail }: { project: ResearchProject; apiProject?: ApiProject; onOpenGate: (gateId: string) => void; onOpenDetail: (detail: DetailPanel) => void }) {
  const cards = projectGateCards(project, apiProject);
  const countByStatus = (status: string) => cards.filter((gate) => gate.status === status).length;
  const invalidatedCount = cards.filter((gate) => (
    gate.status !== "approved"
    && gate.history?.some((event) => event.decision === "approve")
  )).length;
  return (
    <div className="approvals-view page-view">
      <header className="view-header"><div><p className="eyebrow">Human Approval Center</p><h1>人工审批中心</h1><p>批准的是确定版本和哈希。上游语义变化会使受影响的下游审批自动失效。</p></div><button className="outline-compact" onClick={() => onOpenDetail({ eyebrow: "Approval policy", title: "人工审批与失效规则", description: "智能体不能成为批准人。平台冻结 revision 和内容哈希，并在上游语义变化时使受影响的下游审批失效。", rows: [{ label: "G0", value: "选题价值与已有研究" }, { label: "G1", value: "理论与研究设计" }, { label: "G2", value: "数据、伦理与许可" }, { label: "G3", value: "分析计划与代码" }, { label: "G4", value: "结果与核心主张" }, { label: "G5", value: "成稿与发布" }], bullets: ["课题边界变化：G0–G5 失效", "主设计变化：G1–G5 失效", "主模型或 do-file 变化：G3–G5 失效", "纯排版变化：仅重查 G5 输出"] })}>查看审批规则</button></header>
      <div className="approval-summary"><div><strong>{countByStatus("approved")}</strong><span>已批准</span></div><div><strong>{countByStatus("review")}</strong><span>待审批</span></div><div><strong>{countByStatus("blocked")}</strong><span>前置阻塞</span></div><div><strong>{invalidatedCount}</strong><span>失效待复核</span></div></div>
      <div className="approval-layout">
        <section className="gate-list">{cards.map((gate) => <button className={`gate-card gate-${gate.status}`} onClick={() => onOpenGate(gate.id)} key={gate.id}><span className="gate-code">{gate.id}</span><div><h2>{gate.title}</h2><p>{gate.asset}</p><small>批准人：{gate.owner}</small></div><div className="gate-state"><StateBadge state={gate.status} /><small>{gate.time}</small></div><span className="gate-arrow">→</span></button>)}</section>
        <aside className="approval-rule-card"><p className="eyebrow">Four-eyes policy</p><h2>关键决定至少经过两种角色</h2><div className="reviewer-stack"><span>研</span><span>导</span><span>法</span></div><p>研究者提交，导师或 PI 与方法审核者分别确认价值和方法。Agent 永远不能成为批准人。</p><hr /><h3>上游变化会发生什么？</h3><ul><li>课题边界变化 → G0–G5 失效</li><li>主设计变化 → G1–G5 失效</li><li>主模型或 do-file 变化 → G3–G5 失效</li><li>纯排版变化 → 仅重查 G5 输出</li></ul></aside>
      </div>
    </div>
  );
}

function ApprovalModal({
  open,
  stageIndex,
  revision,
  contentHash,
  onClose,
  onConfirm,
}: {
  open: boolean;
  stageIndex: number;
  revision: number;
  contentHash: string | null;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const [checked, setChecked] = useState([true, true, false]);
  if (!open) return null;
  const stage = stages[stageIndex];
  const approvalCopy: Record<string, { owner: string; checks: string[]; note: string }> = {
    G0: { owner: "研究者 + 导师", checks: ["我已检查研究问题、研究边界与已有研究报告", "我已阅读相似课题、冲突证据与当前创新性限制", "我理解选题修改会使后续阶段资产与审批失效"], note: "请重点审核课题价值、研究边界、已有研究覆盖与可行性。" },
    G1: { owner: "导师 + 方法审核者", checks: ["我已检查研究问题、变量口径和主设计", "我已阅读冲突证据与当前覆盖限制", "我理解批准后再修改主设计会使下游审批失效"], note: "主设计、备选设计与识别边界已经人工复核，请重点审核关键假设与失败条件。" },
    G2: { owner: "数据负责人", checks: ["我已核验数据许可、隐私要求与运行位置", "我已检查变量字典、样本口径和数据血缘", "我理解数据口径变化会使 G2 之后的审批失效"], note: "请审核数据许可、关键变量口径、伦理限制与受控运行方案。" },
    G3: { owner: "方法审核者", checks: ["我已逐项核对 AnalysisPlan 与 do-file", "我已检查数据签名、软件版本、失败条件和输出路径", "我理解正式运行只能由人启动，智能体不能绕过冻结版本"], note: "请审核主次分析、代码哈希、诊断计划和正式运行边界。" },
    G4: { owner: "PI + 方法审核者", checks: ["我已审阅完整结果、失败检验与重跑记录", "我已检查每条核心主张的证据边和适用范围", "我理解证据不足的结论必须降级、改写或撤回"], note: "请审核核心结果、失败项、稳健性与主张强度是否匹配。" },
    G5: { owner: "通讯作者", checks: ["我已核对正文数字、图表、引用与结果资产", "我已检查限制披露、伦理说明和复现包", "我确认当前版本可以进入最终发布流程"], note: "请完成发布前的引用、数字、披露与复现包最终核验。" },
  };
  const copy = approvalCopy[stage.gate] ?? approvalCopy.G1;
  const allChecked = checked.every(Boolean);
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.currentTarget === event.target && onClose()}>
      <section className="approval-modal" role="dialog" aria-modal="true" aria-labelledby="approval-title">
        <button className="modal-close" onClick={onClose} aria-label="关闭审批窗口">×</button>
        <p className="eyebrow">Human approval · {stage.gate}</p>
        <h2 id="approval-title">人工批准“{stage.name}”</h2>
        <p>你将以研究者身份批准当前 revision。批准后会记录人工决定，并解锁下一阶段。</p>
        <div className="review-packet"><div><span>审批对象</span><strong>{stage.output}</strong></div><div><span>当前版本</span><strong>Revision {revision} · {contentHash ? `${contentHash.slice(0, 8)}…${contentHash.slice(-4)}` : "尚无内容哈希"}</strong></div><div><span>默认批准人</span><strong>{copy.owner}</strong></div></div>
        <h3>提交前由研究者确认</h3>
        <div className="modal-checks">
          {copy.checks.map((item, index) => <label key={item}><input type="checkbox" checked={checked[index]} onChange={() => setChecked((current) => current.map((value, itemIndex) => itemIndex === index ? !value : value))} /><span>{item}</span></label>)}
        </div>
        <label className="reason-field"><span>提交说明</span><textarea key={stage.gate} defaultValue={copy.note} /></label>
        <div className="modal-actions"><button onClick={onClose}>继续修改</button><button className="primary-action" disabled={!allChecked} onClick={onConfirm}>确认批准当前 Revision</button></div>
      </section>
    </div>
  );
}

export default function Home() {
  const [view, setView] = useState<ViewKey>("journey");
  const [projects, setProjects] = useState<ResearchProject[]>([newProjectPlaceholder]);
  const [activeProjectId, setActiveProjectId] = useState(newProjectPlaceholder.id);
  const [activeStage, setActiveStage] = useState(3);
  const [selectedDesign, setSelectedDesign] = useState("fe");
  const [question, setQuestion] = useState(newProjectPlaceholder.question);
  const [deepStack, setDeepStack] = useState<DeepRoute[]>([]);
  const [stageDrafts, setStageDrafts] = useState<Record<string, StageDraft>>({});
  const [resolvedIssues, setResolvedIssues] = useState<Record<string, boolean>>({});
  const [stageDefinitions, setStageDefinitions] = useState<ApiStageDefinition[]>([]);
  const [stageSuggestions, setStageSuggestions] = useState<Record<string, StageSuggestionSet>>({});
  const [suggestionBusyKey, setSuggestionBusyKey] = useState("");
  const [toolBusyId, setToolBusyId] = useState("");
  const [approvalStageIndex, setApprovalStageIndex] = useState<number | null>(null);
  const [stageRevisions, setStageRevisions] = useState<Record<string, StageRevision[]>>({});
  const [restoringRevision, setRestoringRevision] = useState<number | null>(null);
  const [knowledgeEvaluations, setKnowledgeEvaluations] = useState<Record<string, KnowledgeEvaluation>>({});
  const [knowledgeGovernanceCandidates, setKnowledgeGovernanceCandidates] = useState<KnowledgeGovernanceCandidate[]>([]);
  const [knowledgeGovernanceRecords, setKnowledgeGovernanceRecords] = useState<KnowledgeGovernanceRecord[]>([]);
  const [knowledgeBusy, setKnowledgeBusy] = useState(false);
  const [diagnosticRules, setDiagnosticRules] = useState<DiagnosticRule[]>([]);
  const [diagnosticRegistryVersion, setDiagnosticRegistryVersion] = useState("");
  const [apiProjectIds, setApiProjectIds] = useState<Record<string, boolean>>({});
  const [apiProjects, setApiProjects] = useState<Record<string, ApiProject>>({});
  const [apiMode, setApiMode] = useState<"loading" | "connected" | "fallback">("loading");
  const [apiBusy, setApiBusy] = useState(false);
  const [apiError, setApiError] = useState("");
  const [projectMenu, setProjectMenu] = useState(false);
  const [userMenu, setUserMenu] = useState(false);
  const [preferencesOpen, setPreferencesOpen] = useState(false);
  const [interfaceTheme, setInterfaceTheme] = useState<InterfaceTheme>("graphite");
  const [detail, setDetail] = useState<DetailPanel | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatAgent, setChatAgent] = useState(3);
  const [chatMessages, setChatMessages] = useState<Record<string, ChatMessage[]>>({});
  const [chatLoadingKey, setChatLoadingKey] = useState("");
  const [chatBusyKey, setChatBusyKey] = useState("");
  const [toast, setToast] = useState("");
  const activeProject = projects.find((project) => project.id === activeProjectId) ?? projects[0];
  const activeChatKey = `${activeProject.id}:${stages[chatAgent].key}`;
  const activeApiProject = apiProjects[activeProject.id];
  const activeStageData = stages[activeStage];
  const activeRemoteStage = activeApiProject?.stages.find((stage) => stage.key === activeStageData.key);
  const activeSuggestionKey = `${activeProject.id}:${activeStageData.key}`;
  const activeStageSuggestions = stageSuggestions[activeSuggestionKey];
  const deepRoute = deepStack[deepStack.length - 1];
  const deepStageDraftIndex = deepRoute?.kind === "stage-draft" ? deepRoute.stageIndex : null;
  const activeEvidence = projectEvidenceRecords(activeApiProject);
  const activeEvidenceCandidates = projectEvidenceCandidates(activeApiProject);
  const literatureContent = activeApiProject?.stages.find((stage) => stage.key === "literature")?.content;
  const literatureSearchRuns = (
    Array.isArray(literatureContent?.search_runs) ? literatureContent.search_runs.length : 0
  ) + (
    Array.isArray(literatureContent?.evidence_discovery_runs)
      ? literatureContent.evidence_discovery_runs.length
      : 0
  );
  const activeKnowledgeEvaluation = knowledgeEvaluations[activeProject.id];
  const methodAssessments = new Map((activeKnowledgeEvaluation?.status === "current" ? activeKnowledgeEvaluation.methods : []).map((item) => [item.candidate_id, item]));
  const formulaAssessments = new Map((activeKnowledgeEvaluation?.status === "current" ? activeKnowledgeEvaluation.formulas : []).map((item) => [item.candidate_id, item]));
  const allMethods = [
    ...methods,
    ...knowledgeGovernanceRecords
      .filter((record) => record.kind === "method")
      .map(knowledgeMethodRecord),
  ];
  const allFormulas = [
    ...formulas,
    ...knowledgeGovernanceRecords
      .filter((record) => record.kind === "formula")
      .map(knowledgeFormulaRecord),
  ];
  const evaluatedMethods = allMethods.map((method) => {
    const assessment = methodAssessments.get(method.id);
    return { ...method, fit: assessment?.score ?? null, fitRationale: assessment?.rationale };
  });
  const evaluatedFormulas = allFormulas.map((formula) => {
    const assessment = formulaAssessments.get(formula.id);
    return { ...formula, fit: assessment?.score ?? null, fitRationale: assessment?.rationale };
  });
  const approvalOpen = approvalStageIndex !== null;
  const approvalStageData = stages[approvalStageIndex ?? activeStage];
  const approvalRemoteStage = activeApiProject?.stages.find((stage) => stage.key === approvalStageData.key);
  const pageTitle = useMemo(() => navItems.find((item) => item.key === view)?.short ?? "研究旅程", [view]);

  useEffect(() => {
    const saved = window.localStorage.getItem("ai4ms-interface-theme");
    let cancelled = false;
    const frame = window.requestAnimationFrame(() => {
      if (saved === "graphite" || saved === "blueprint" || saved === "paper") setInterfaceTheme(saved);
    });
    void getApiUserProfile().then((profile) => {
      if (cancelled) return;
      setInterfaceTheme(profile.interface_theme);
      window.localStorage.setItem("ai4ms-interface-theme", profile.interface_theme);
    }).catch(() => undefined);
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(frame);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      listApiKnowledgeGovernanceCandidates(),
      listApiKnowledgeGovernanceRecords(),
    ]).then(([candidates, records]) => {
      if (cancelled) return;
      setKnowledgeGovernanceCandidates(candidates);
      setKnowledgeGovernanceRecords(records);
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      getApiDiagnosticRegistry().then((registry) => {
        if (cancelled) return;
        setDiagnosticRules(registry.items);
        setDiagnosticRegistryVersion(`v${registry.registry_version} · ${registry.total} / ${registry.total}`);
      }).catch(() => {
        if (!cancelled) setDiagnosticRegistryVersion("后端注册表不可用");
      }),
      getApiStageDefinitions().then((items) => {
        if (!cancelled) setStageDefinitions(items);
      }).catch(() => {
        if (!cancelled) setStageDefinitions([]);
      }),
    ]);
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!activeApiProject || !activeRemoteStage) return;
    const projectId = activeProject.id;
    const stageKey = activeStageData.key;
    const key = `${projectId}:${stageKey}`;
    let cancelled = false;
    void getApiStageSuggestions(projectId, stageKey).then((result) => {
      if (!cancelled) {
        setStageSuggestions((current) => ({ ...current, [key]: result }));
      }
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [activeProject.id, activeStageData.key, activeRemoteStage, activeApiProject]);

  useEffect(() => {
    if (!activeApiProject) return;
    let cancelled = false;
    void getApiKnowledgeEvaluation(activeProject.id).then((evaluation) => {
      if (!cancelled) {
        setKnowledgeEvaluations((current) => ({
          ...current,
          [activeProject.id]: evaluation,
        }));
      }
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [activeApiProject, activeProject.id]);

  useEffect(() => {
    if (deepStageDraftIndex === null || !apiProjectIds[activeProject.id]) return;
    const stageIndex = deepStageDraftIndex;
    const stageKey = stages[stageIndex].key;
    const key = `${activeProject.id}:${stageKey}`;
    let cancelled = false;
    void listApiStageRevisions(activeProject.id, stageKey).then((items) => {
      if (!cancelled) {
        setStageRevisions((current) => ({ ...current, [key]: items }));
      }
    }).catch((error) => {
      if (!cancelled) setApiError(readApiError(error));
    });
    return () => { cancelled = true; };
  }, [activeProject.id, apiProjectIds, deepStageDraftIndex]);

  useEffect(() => {
    let cancelled = false;
    async function loadApiProjects() {
      try {
        const summaries = await listApiProjects();
        if (cancelled) return;
        setApiMode("connected");
        setApiError("");
        setApiProjectIds(Object.fromEntries(summaries.map((item) => [item.project_id, true])));
        if (!summaries.length) {
          setProjects([newProjectPlaceholder]);
          setActiveProjectId(newProjectPlaceholder.id);
          setActiveStage(0);
          setQuestion(newProjectPlaceholder.question);
          setDeepStack([{ kind: "project-wizard" }]);
          return;
        }
        const mapped = summaries.map((item) => mapApiProject(item));
        setProjects(mapped);
        setActiveProjectId(mapped[0].id);
        setActiveStage(mapped[0].stageIndex);
        setQuestion(mapped[0].question);
        try {
          const full = await getApiProject(mapped[0].id);
          if (cancelled) return;
          const hydrated = mapApiProject(full, mapped[0]);
          setApiProjects({ [full.project_id]: full });
          setProjects((current) => current.map((item) => item.id === hydrated.id ? hydrated : item));
          setStageDrafts((current) => ({ ...current, ...mapApiDrafts(full, hydrated) }));
          setActiveStage(hydrated.stageIndex);
          setQuestion(hydrated.question);
          setSelectedDesign(designSelection(full));
        } catch (error) {
          if (!cancelled) setApiError(readApiError(error));
        }
      } catch (error) {
        if (cancelled) return;
        setApiMode("fallback");
        setApiError(readApiError(error));
      }
    }
    void loadApiProjects();
    return () => { cancelled = true; };
  }, []);

  function readApiError(error: unknown) {
    if (error instanceof ApiError) return error.message;
    if (error instanceof Error) return error.message;
    return "无法连接 FastAPI 服务";
  }

  function showToast(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(""), 2400);
  }
  function selectInterfaceTheme(theme: InterfaceTheme) {
    setInterfaceTheme(theme);
    window.localStorage.setItem("ai4ms-interface-theme", theme);
    void updateApiUserProfile(theme).then((profile) => {
      window.localStorage.setItem("ai4ms-interface-theme", profile.interface_theme);
      setApiError("");
      showToast("界面偏好已同步到用户 profile");
    }).catch((error) => {
      setApiError(readApiError(error));
      showToast("界面偏好已保存在本机，后端 profile 同步待重试");
    });
  }
  async function refreshStageSuggestions() {
    const projectId = activeProject.id;
    const stageKey = activeStageData.key;
    const key = `${projectId}:${stageKey}`;
    if (!apiProjectIds[projectId] || !activeRemoteStage) {
      showToast("请先连接 FastAPI 项目并保存当前阶段草稿");
      return;
    }
    setSuggestionBusyKey(key);
    try {
      const result = await generateApiStageSuggestions(projectId, stageKey);
      setStageSuggestions((current) => ({ ...current, [key]: result }));
      setApiError("");
      showToast(`已根据 Revision ${result.stage_revision} 生成 ${result.suggestions.length} 条 AI 建议`);
    } catch (error) {
      const message = readApiError(error);
      setApiError(message);
      showToast(`AI 建议生成失败：${message}`);
    } finally {
      setSuggestionBusyKey((current) => current === key ? "" : current);
    }
  }
  async function decideSuggestion(id: string, state: SuggestionDecision) {
    const projectId = activeProject.id;
    const stageKey = activeStageData.key;
    const key = `${projectId}:${stageKey}`;
    try {
      const result = await decideApiStageSuggestion(projectId, stageKey, id, state);
      setStageSuggestions((current) => ({ ...current, [key]: result }));
      const verb = state === "accepted" ? "接受" : state === "modified" ? "转为人工修改" : state === "rejected" ? "拒绝" : "撤销处理";
      showToast(`已${verb}建议，处理记录已保存`);
    } catch (error) {
      showToast(`建议状态保存失败：${readApiError(error)}`);
    }
  }
  function applyApiProject(updated: ApiProject, preferred?: ResearchProject) {
    const existing = preferred ?? projects.find((item) => item.id === updated.project_id);
    const hydrated = mapApiProject(updated, existing);
    setApiProjects((current) => ({ ...current, [updated.project_id]: updated }));
    setApiProjectIds((current) => ({ ...current, [updated.project_id]: true }));
    setProjects((current) => {
      const found = current.some((item) => item.id === updated.project_id);
      return found
        ? current.map((item) => item.id === updated.project_id ? hydrated : item)
        : [...current, hydrated];
    });
    setStageDrafts((current) => ({ ...current, ...mapApiDrafts(updated, hydrated) }));
    if (activeProjectId === updated.project_id) {
      setActiveStage(hydrated.stageIndex);
      setQuestion(hydrated.question);
      setSelectedDesign(designSelection(updated));
    }
    return hydrated;
  }
  function confirmApproval() {
    const targetIndex = approvalStageIndex;
    if (targetIndex === null) return;
    const targetStage = stages[targetIndex];
    if (!apiProjectIds[activeProject.id]) {
      setApiError("审批必须连接 FastAPI，不能只修改前端演示状态");
      showToast("审批未提交：当前项目未连接后端");
      return;
    }
    setApiBusy(true);
    void decideApiStage(
      activeProject.id,
      targetStage.key,
      "approve",
      "研究者已人工核对当前 revision，并批准进入下一阶段。",
    ).then((updated) => {
      applyApiProject(updated);
      setApprovalStageIndex(null);
      setApiError("");
      showToast(`${targetStage.gate} 已保存人工审批事件，流程进入下一阶段`);
    }).catch((error) => {
      setApiError(readApiError(error));
      showToast(`审批未完成：${readApiError(error)}`);
    }).finally(() => setApiBusy(false));
  }

  async function runEvidenceSearch(
    query: string,
    candidateType: "literature" | "data_study",
  ) {
    if (!apiProjectIds[activeProject.id]) {
      setApiError("证据检索必须连接 FastAPI 项目");
      showToast("检索未运行：当前项目未连接后端");
      return;
    }
    const literature = apiProjects[activeProject.id]?.stages.find(
      (stage) => stage.key === "literature",
    );
    if (!literature || literature.status === "not_started") {
      showToast("请先完成上游审批并解锁 S1，再运行证据发现");
      return;
    }
    setApiBusy(true);
    try {
      const updated = await discoverApiEvidenceCandidates(
        activeProject.id,
        query,
        candidateType,
        literature.revision,
      );
      applyApiProject(updated);
      setApiError("");
      const count = projectEvidenceCandidates(updated).filter(
        (item) => item.status === "pending",
      ).length;
      showToast(`联网发现已保存，当前有 ${count} 条候选等待人工审核；尚未进入权威证据库`);
    } catch (error) {
      setApiError(readApiError(error));
      showToast(`检索未完成：${readApiError(error)}`);
    } finally {
      setApiBusy(false);
    }
  }

  async function reviewEvidenceCandidate(
    candidate: EvidenceCandidate,
    decision: "approve" | "reject" | "request_changes",
    reason: string,
    evidenceLevel: EvidenceLevel,
    edits: Record<string, unknown>,
  ) {
    const literature = apiProjects[activeProject.id]?.stages.find(
      (stage) => stage.key === "literature",
    );
    if (!literature) {
      showToast("S1 后端阶段尚未加载");
      return;
    }
    setApiBusy(true);
    try {
      const updated = await reviewApiEvidenceCandidate(
        activeProject.id,
        candidate.candidate_id,
        decision,
        reason,
        evidenceLevel,
        literature.revision,
        edits,
      );
      applyApiProject(updated);
      setApiError("");
      showToast(decision === "approve"
        ? "候选已由研究者批准并生成 EVLIB 权威记录"
        : decision === "reject"
          ? "候选已拒绝，不会进入论文引用"
          : "候选已退回补充，仍不可进入论文引用");
    } catch (error) {
      setApiError(readApiError(error));
      showToast(`候选审核未保存：${readApiError(error)}`);
    } finally {
      setApiBusy(false);
    }
  }

  async function updateEvidenceRecord(
    record: EvidenceRecord,
    edits: Record<string, unknown>,
    reason: string,
  ) {
    const literature = apiProjects[activeProject.id]?.stages.find(
      (stage) => stage.key === "literature",
    );
    if (!literature) {
      showToast("S1 后端阶段尚未加载");
      return;
    }
    setApiBusy(true);
    try {
      const updated = await patchApiEvidenceRecord(
        activeProject.id,
        record.id,
        edits,
        reason,
        literature.revision,
      );
      applyApiProject(updated);
      setApiError("");
      showToast(`${record.id} 已保存为新的权威证据 revision`);
    } catch (error) {
      setApiError(readApiError(error));
      showToast(`证据记录保存失败：${readApiError(error)}`);
      throw error;
    } finally {
      setApiBusy(false);
    }
  }

  async function selectResearchQuestion(questionId: string, rationale: string) {
    const problemStage = apiProjects[activeProject.id]?.stages.find(
      (stage) => stage.key === "problem",
    );
    if (!apiProjectIds[activeProject.id] || !problemStage) {
      const message = "研究问题选择必须连接 FastAPI 项目并完成 S0 加载";
      setApiError(message);
      showToast(message);
      return;
    }
    setApiBusy(true);
    try {
      const updated = await selectApiProblemQuestion(
        activeProject.id,
        questionId,
        rationale,
        problemStage.revision,
      );
      applyApiProject(updated);
      setApiError("");
      showToast(`${questionId} 已由研究者选定；候选集变化时该选择会自动失效`);
    } catch (error) {
      setApiError(readApiError(error));
      showToast(`研究问题选择未保存：${readApiError(error)}`);
    } finally {
      setApiBusy(false);
    }
  }

  async function reviewCurrentLiteraturePlan(
    decision: "approve" | "request_changes",
    reason: string,
  ) {
    const literatureStage = apiProjects[activeProject.id]?.stages.find(
      (stage) => stage.key === "literature",
    );
    if (!apiProjectIds[activeProject.id] || !literatureStage) {
      const message = "检索计划审阅必须连接 FastAPI 项目并完成 S1 加载";
      setApiError(message);
      showToast(message);
      return;
    }
    setApiBusy(true);
    try {
      const updated = await reviewApiLiteraturePlan(
        activeProject.id,
        decision,
        reason,
        literatureStage.revision,
      );
      applyApiProject(updated);
      setApiError("");
      showToast(decision === "approve"
        ? "当前检索计划已由研究者批准，可以执行检索"
        : "检索计划已退回；修改查询与纳排范围后需重新批准");
    } catch (error) {
      setApiError(readApiError(error));
      showToast(`检索计划审阅未保存：${readApiError(error)}`);
    } finally {
      setApiBusy(false);
    }
  }

  async function runKnowledgeEvaluation() {
    if (!apiProjectIds[activeProject.id]) {
      setApiError("方法评估必须连接 FastAPI 项目");
      showToast("AI 评估未运行：当前项目未连接后端");
      return;
    }
    setKnowledgeBusy(true);
    try {
      let job = await submitApiKnowledgeEvaluation(
        activeProject.id,
        allMethods.map((method) => ({
          candidate_id: method.id,
          name: method.name,
          description: `${method.goal}\n估计目标：${method.estimand}\n数据结构：${method.dataShape}`,
          assumptions: [...method.assumptions],
        })),
        allFormulas.map((formula) => ({
          candidate_id: formula.id,
          name: formula.title,
          description: `${formula.purpose}\n公式：${formula.formula}`,
          assumptions: [...formula.assumptions],
        })),
      );
      const deadline = Date.now() + 6 * 60 * 1000;
      while (job.status === "queued" || job.status === "running") {
        if (Date.now() >= deadline) {
          throw new Error("AI 评估后台任务等待超时，请稍后重试");
        }
        await new Promise((resolve) => window.setTimeout(resolve, 900));
        job = await getApiKnowledgeEvaluationJob(activeProject.id, job.job_id);
      }
      if (job.status !== "succeeded" || !job.result) {
        throw new Error(job.error || "AI 评估后台任务未完成");
      }
      const evaluation = job.result;
      setKnowledgeEvaluations((current) => ({
        ...current,
        [activeProject.id]: evaluation,
      }));
      setApiError("");
      showToast(`AI 已评估 ${evaluation.methods.length} 个方法和 ${evaluation.formulas.length} 个公式`);
    } catch (error) {
      setApiError(readApiError(error));
      showToast(`AI 评估未完成：${readApiError(error)}`);
    } finally {
      setKnowledgeBusy(false);
    }
  }

  async function refreshKnowledgeGovernance() {
    const [candidates, records] = await Promise.all([
      listApiKnowledgeGovernanceCandidates(),
      listApiKnowledgeGovernanceRecords(),
    ]);
    setKnowledgeGovernanceCandidates(candidates);
    setKnowledgeGovernanceRecords(records);
  }

  async function discoverKnowledgeCandidate(
    kind: KnowledgeAssetKind,
    query: string,
  ) {
    setKnowledgeBusy(true);
    try {
      const result = await discoverApiKnowledgeCandidates(kind, query);
      await refreshKnowledgeGovernance();
      setApiError("");
      showToast(`智能体发现 ${result.count} 条${kind === "method" ? "方法" : "公式"}候选，均等待人工审核`);
    } catch (error) {
      setApiError(readApiError(error));
      showToast(`知识候选发现失败：${readApiError(error)}`);
    } finally {
      setKnowledgeBusy(false);
    }
  }

  async function reviewKnowledgeGovernanceCandidate(
    candidate: KnowledgeGovernanceCandidate,
    decision: "approve" | "reject" | "request_changes",
    reason: string,
    content: Record<string, unknown>,
  ) {
    setKnowledgeBusy(true);
    try {
      await reviewApiKnowledgeCandidate(
        candidate.candidate_id,
        decision,
        reason,
        candidate.revision,
        content,
      );
      await refreshKnowledgeGovernance();
      setApiError("");
      showToast(decision === "approve"
        ? "候选已由研究者批准并写入版本化知识库"
        : decision === "reject"
          ? "候选已拒绝"
          : "候选已退回补全");
    } catch (error) {
      setApiError(readApiError(error));
      showToast(`候选审核失败：${readApiError(error)}`);
    } finally {
      setKnowledgeBusy(false);
    }
  }

  async function createKnowledgeGovernanceRecord(
    kind: KnowledgeAssetKind,
    content: Record<string, unknown>,
    reason: string,
  ): Promise<KnowledgeGovernanceRecord | null> {
    setKnowledgeBusy(true);
    try {
      const record = await createApiKnowledgeRecord(kind, content, reason);
      await refreshKnowledgeGovernance();
      setApiError("");
      showToast(`${record.record_id} 已由研究者创建并写入权威知识库`);
      return record;
    } catch (error) {
      setApiError(readApiError(error));
      showToast(`人工知识记录创建失败：${readApiError(error)}`);
      return null;
    } finally {
      setKnowledgeBusy(false);
    }
  }

  async function patchKnowledgeGovernanceRecord(
    record: KnowledgeGovernanceRecord,
    content: Record<string, unknown>,
    reason: string,
  ) {
    setKnowledgeBusy(true);
    try {
      const updated = await patchApiKnowledgeRecord(
        record.record_id,
        content,
        reason,
        record.revision,
      );
      await refreshKnowledgeGovernance();
      setApiError("");
      showToast(`${updated.record_id} 已保存 Revision ${updated.revision}`);
    } catch (error) {
      setApiError(readApiError(error));
      showToast(`知识记录保存失败：${readApiError(error)}`);
    } finally {
      setKnowledgeBusy(false);
    }
  }

  async function refreshStageRevisions(projectId: string, stageIndex: number) {
    const stageKey = stages[stageIndex].key;
    const items = await listApiStageRevisions(projectId, stageKey);
    setStageRevisions((current) => ({
      ...current,
      [`${projectId}:${stageKey}`]: items,
    }));
  }

  async function restoreStageRevision(stageIndex: number, revision: number) {
    const projectId = activeProject.id;
    const stageKey = stages[stageIndex].key;
    const remoteStage = apiProjects[projectId]?.stages.find((item) => item.key === stageKey);
    if (!remoteStage) {
      showToast("恢复失败：后端阶段尚未加载");
      return;
    }
    setRestoringRevision(revision);
    try {
      const updated = await restoreApiStageRevision(
        projectId,
        stageKey,
        revision,
        remoteStage.revision,
      );
      applyApiProject(updated);
      await refreshStageRevisions(projectId, stageIndex);
      setApiError("");
      showToast(`Revision ${revision} 已复制为新的未确认草稿`);
    } catch (error) {
      setApiError(readApiError(error));
      showToast(`恢复失败：${readApiError(error)}`);
    } finally {
      setRestoringRevision(null);
    }
  }

  async function saveAssetSection(
    stageIndex: number,
    sectionKey: string,
    title: string,
    content: string,
  ) {
    const projectId = activeProject.id;
    const stageKey = stages[stageIndex].key;
    const remoteStage = apiProjects[projectId]?.stages.find(
      (item) => item.key === stageKey,
    );
    if (!apiProjectIds[projectId] || !remoteStage) {
      const message = "资产章节必须连接 FastAPI 项目后才能保存";
      setApiError(message);
      showToast(message);
      throw new Error(message);
    }
    setApiBusy(true);
    try {
      const updated = await patchApiStageAssetSection(
        projectId,
        stageKey,
        sectionKey,
        title,
        content,
        remoteStage.revision,
      );
      applyApiProject(updated);
      await refreshStageRevisions(projectId, stageIndex);
      setApiError("");
      showToast(`资产章节「${title}」已保存为新的 FastAPI revision`);
    } catch (error) {
      const message = readApiError(error);
      setApiError(message);
      showToast(`资产章节保存失败：${message}`);
      throw error instanceof Error ? error : new Error(message);
    } finally {
      setApiBusy(false);
    }
  }

  async function generateActiveStageAssets() {
    const projectId = activeProject.id;
    const stageKey = activeStageData.key;
    if (!apiProjectIds[projectId] || !activeRemoteStage) {
      showToast("请先连接 FastAPI 项目，再生成正式阶段资产");
      return;
    }
    if (activeRemoteStage.status === "not_started") {
      showToast("请先批准上游阶段，解锁当前阶段");
      return;
    }
    if (activeRemoteStage.status === "approved") {
      showToast("当前阶段已批准；如需重开，请先修改上游或当前资产");
      return;
    }

    setApiBusy(true);
    setApiError("");
    try {
      let updated: ApiProject;
      if (stageKey === "literature") {
        const working = apiProjects[projectId] ?? await getApiProject(projectId);
        const literature = working.stages.find((item) => item.key === "literature");
        const queryBlocks = literature?.content.query_blocks;
        if (!Array.isArray(queryBlocks) || queryBlocks.length === 0) {
          updated = await createApiStageDraft(
            projectId,
            stageKey,
            "先形成覆盖经典、前沿、相邻概念、争议和反向证据的可执行检索协议。",
          );
          applyApiProject(updated);
          showToast("S1 检索计划已生成；请先人工审阅并批准，再执行检索与综述");
          return;
        }
        const planReview = asRecord(literature?.content.literature_plan_review);
        if (planReview?.status !== "approved") {
          showToast("检索尚未执行：请先在阶段页面批准当前检索计划");
          return;
        }
        const candidates = projectEvidenceCandidates(working);
        const library = projectEvidenceRecords(working);
        if (candidates.length === 0) {
          updated = await searchApiLiterature(projectId);
          applyApiProject(updated);
          showToast("检索结果已保存为候选；请到证据库逐条审核，批准后才能生成综述");
          return;
        }
        const unresolvedCount = candidates.filter(
          (item) => item.status === "pending" || item.status === "changes_requested",
        ).length;
        if (unresolvedCount > 0) {
          showToast(`综述尚未生成：还有 ${unresolvedCount} 条证据候选需要人工处理`);
          return;
        }
        if (library.length === 0) {
          showToast("综述尚未生成：没有人工批准的权威证据，请扩大检索或批准至少一条合格候选");
          return;
        }
        updated = await createApiStageDraft(
          projectId,
          stageKey,
          "只基于已保存的检索结果形成可追溯综述，保留争议、反证、候选空白和覆盖限制。",
        );
      } else {
        updated = await createApiStageDraft(
          projectId,
          stageKey,
          `为 ${activeStageData.id} ${activeStageData.name} 生成可审阅、可追溯且符合阶段契约的正式草稿。`,
        );
        if (stageKey === "delivery") {
          updated = await exportApiDelivery(projectId);
        }
      }
      applyApiProject(updated);
      showToast(
        stageKey === "delivery"
          ? "S9 阶段资产、HTML 报告和研究包已生成"
          : stageKey === "literature"
            ? "S1 检索、论文入库与 AO 综述已完成"
            : `${activeStageData.id} 阶段资产已生成，等待人工审阅`,
      );
    } catch (error) {
      const message = readApiError(error);
      setApiError(message);
      showToast(`阶段生成未完成：${message}`);
    } finally {
      setApiBusy(false);
    }
  }

  async function refreshDeliveryExport() {
    const projectId = activeProject.id;
    const delivery = apiProjects[projectId]?.stages.find((stage) => stage.key === "delivery");
    if (!delivery || delivery.revision < 1 || delivery.status === "not_started") {
      showToast("请先生成并保存 S9 阶段草稿");
      return;
    }
    setApiBusy(true);
    setApiError("");
    try {
      const updated = await exportApiDelivery(projectId);
      applyApiProject(updated);
      showToast("HTML、Word、PDF、图表、Mermaid 与 Stata 复现包已更新");
    } catch (error) {
      const message = readApiError(error);
      setApiError(message);
      showToast(`交付物生成失败：${message}`);
    } finally {
      setApiBusy(false);
    }
  }

  async function saveDesignPanel() {
    const projectId = activeProject.id;
    const remote = apiProjects[projectId]?.stages.find((stage) => stage.key === "design");
    if (!remote) {
      showToast("S3 后端阶段尚未加载");
      return;
    }
    if (remote.status === "not_started" || remote.status === "approved") {
      showToast(remote.status === "approved" ? "S3 已批准，不能直接覆盖当前 revision" : "请先批准上游阶段并生成 S3 资产");
      return;
    }
    if (question.trim().length < 5) {
      showToast("研究问题至少需要 5 个字符");
      return;
    }
    const methodId = selectedMethodId(selectedDesign);
    const options = (Array.isArray(remote.content.method_options)
      ? remote.content.method_options
      : [])
      .map(asRecord)
      .filter((item): item is Record<string, unknown> => Boolean(item));
    if (!options.some((item) => item.method_id === methodId)) {
      showToast(`当前 S3 资产还没有候选方法 ${methodId}；请先生成阶段资产或让智能体补充候选`);
      return;
    }
    const methodOptions = options.map((item) => ({
      ...item,
      role: item.method_id === methodId
        ? "primary"
        : item.role === "primary"
          ? "alternative"
          : item.role,
    }));
    setApiBusy(true);
    setApiError("");
    try {
      const updated = await saveApiStage(
        projectId,
        "design",
        {
          ...remote.content,
          research_question: question.trim(),
          method_options: methodOptions,
          primary_method_id: methodId,
        },
        "研究者从 S3 设计面板更新研究问题与主方案",
      );
      applyApiProject(updated);
      await refreshStageRevisions(projectId, 3);
      const revision = updated.stages.find((stage) => stage.key === "design")?.revision;
      showToast(`S3 已保存 Revision ${revision ?? ""}`);
    } catch (error) {
      setApiError(readApiError(error));
      showToast(`S3 保存失败：${readApiError(error)}`);
    } finally {
      setApiBusy(false);
    }
  }
  function navigateView(nextView: ViewKey) {
    setView(nextView);
    setDeepStack([]);
    setProjectMenu(false);
    setUserMenu(false);
  }
  function openDeep(route: DeepRoute) {
    setDeepStack((current) => [...current, route]);
    setProjectMenu(false);
    setUserMenu(false);
  }
  function replaceDeep(route: DeepRoute) {
    setDeepStack([route]);
    setProjectMenu(false);
  }
  function backDeep() {
    setDeepStack((current) => current.slice(0, -1));
  }
  function selectStage(index: number) {
    setActiveStage(index);
    navigateView("journey");
  }
  function activateProject(projectId: string) {
    const project = projects.find((item) => item.id === projectId);
    if (!project) return;
    setActiveProjectId(project.id);
    setActiveStage(project.stageIndex);
    setQuestion(project.question);
    navigateView("journey");
    showToast(`已切换到项目：${project.name}`);
    if (apiProjectIds[project.id]) {
      setApiBusy(true);
      void getApiProject(project.id).then((full) => {
        const hydrated = mapApiProject(full, project);
        setApiProjects((current) => ({ ...current, [full.project_id]: full }));
        setProjects((current) => current.map((item) => item.id === hydrated.id ? hydrated : item));
        setStageDrafts((current) => ({ ...current, ...mapApiDrafts(full, hydrated) }));
        setActiveStage(hydrated.stageIndex);
        setQuestion(hydrated.question);
        setSelectedDesign(designSelection(full));
        setApiError("");
      }).catch((error) => setApiError(readApiError(error))).finally(() => setApiBusy(false));
    }
  }
  function mapChatMessage(message: ApiStageChatMessage): ChatMessage {
    const totalTokens = Number(message.usage.total_tokens ?? 0);
    return {
      id: message.message_id,
      role: message.role,
      text: message.content,
      time: new Date(message.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
      model: message.model || undefined,
      totalTokens: Number.isFinite(totalTokens) && totalTokens > 0 ? totalTokens : undefined,
      citations: message.citations ?? [],
      search: message.search,
    };
  }
  async function loadAgentChat(index: number, projectId = activeProject.id) {
    const key = `${projectId}:${stages[index].key}`;
    if (!apiProjectIds[projectId]) {
      setChatMessages((current) => ({ ...current, [key]: [] }));
      return;
    }
    setChatLoadingKey(key);
    try {
      const messages = await listApiStageChat(projectId, stages[index].key);
      const loadedMessages = messages.map(mapChatMessage);
      setChatMessages((current) => {
        const loadedIds = new Set(loadedMessages.map((message) => message.id));
        const messagesCreatedWhileLoading = (current[key] ?? []).filter(
          (message) => !loadedIds.has(message.id),
        );
        return {
          ...current,
          [key]: [...loadedMessages, ...messagesCreatedWhileLoading],
        };
      });
    } catch (error) {
      showToast(`对话历史读取失败：${readApiError(error)}`);
    } finally {
      setChatLoadingKey((current) => current === key ? "" : current);
    }
  }
  function openAgentChat(index = activeStage) {
    setChatAgent(index);
    setChatOpen(true);
    void loadAgentChat(index);
  }
  function selectChatAgent(index: number) {
    setChatAgent(index);
    void loadAgentChat(index);
  }
  async function sendAgentMessage(text: string, searchMode: ChatSearchMode) {
    const index = chatAgent;
    const projectId = activeProject.id;
    const stageKey = stages[index].key;
    const key = `${projectId}:${stageKey}`;
    if (!apiProjectIds[projectId]) {
      showToast("请先连接 FastAPI 项目，再使用真实智能体");
      return;
    }
    const time = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    const optimisticId = `pending-${Date.now()}`;
    const userMessage: ChatMessage = { id: optimisticId, role: "user", text, time };
    setChatMessages((current) => ({ ...current, [key]: [...(current[key] ?? []), userMessage] }));
    setChatBusyKey(key);
    try {
      const turn = await sendApiStageChat(projectId, stageKey, text, searchMode);
      setChatMessages((current) => ({
        ...current,
        [key]: [
          ...(current[key] ?? []).filter((message) => message.id !== optimisticId),
          mapChatMessage(turn.user_message),
          mapChatMessage(turn.assistant_message),
        ],
      }));
    } catch (error) {
      const message = readApiError(error);
      const reply: ChatMessage = {
        id: `error-${Date.now()}`,
        role: "assistant",
        time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
        text: `模型调用失败：${message}`,
        error: true,
      };
      setChatMessages((current) => ({ ...current, [key]: [...(current[key] ?? []), reply] }));
      showToast(`智能体调用失败：${message}`);
    } finally {
      setChatBusyKey((current) => current === key ? "" : current);
    }
  }
  async function invokeAgentTool(tool: StageToolPolicy) {
    const index = chatAgent;
    const projectId = activeProject.id;
    const stageKey = stages[index].key;
    const key = `${projectId}:${stageKey}`;
    if (!apiProjectIds[projectId]) {
      showToast("请先连接 FastAPI 项目，再调用阶段工具");
      return;
    }
    setToolBusyId(tool.tool_id);
    try {
      const run = await invokeApiStageTool(projectId, stageKey, tool.tool_id, question);
      const message: ChatMessage = {
        id: `tool-${run.tool_run_id}`,
        role: "assistant",
        text: run.summary,
        time: new Date(run.finished_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
        model: `${stageToolLabels[run.tool_id] ?? run.tool_id} · ${run.status}`,
        error: run.status === "failed",
      };
      setChatMessages((current) => ({ ...current, [key]: [...(current[key] ?? []), message] }));
      showToast(run.status === "confirmation_required" ? "工具调用已进入人工确认流程" : `工具调用${run.status === "completed" ? "完成" : "失败"}`);
    } catch (error) {
      const message = readApiError(error);
      setChatMessages((current) => ({
        ...current,
        [key]: [
          ...(current[key] ?? []),
          {
            id: `tool-error-${Date.now()}`,
            role: "assistant",
            text: `工具调用失败：${message}`,
            time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
            error: true,
          },
        ],
      }));
      showToast(`工具调用失败：${message}`);
    } finally {
      setToolBusyId("");
    }
  }
  function syncAgentOutput(text: string, target: ChatSyncTarget, mode: ChatSyncMode) {
    const stageIndex = chatAgent;
    const draft = getDraft(stageIndex);
    const stage = stages[stageIndex];
    const targetLabels: Record<ChatSyncTarget, string> = { content: "交付正文", summary: "阶段摘要", evidenceNote: "证据说明", decision: "决定记录草稿" };
    const stamp = new Date().toLocaleString("zh-CN", { hour12: false });
    const block = `【${stage.agent} 协作建议 · ${stamp} · 待人工审阅】\n${text}`;
    const currentValue = draft[target];
    const nextValue = mode === "replace" ? block : `${currentValue.trim()}\n\n${block}`.trim();
    saveDraft(stageIndex, { ...draft, [target]: nextValue, savedAt: "刚刚由研究者确认同步", syncHistory: [`${stamp} · ${stage.agent} → ${targetLabels[target]}（${mode === "replace" ? "替换" : "追加"}）`, ...draft.syncHistory] }, `已同步到 ${stage.id} ${targetLabels[target]}，可继续人工修改`);
  }
  function addMethodToDesign(methodId: string) {
    setSelectedDesign(methodSelection(methodId));
    setActiveStage(3);
    setView("journey");
    setDeepStack([]);
    showToast("已选择候选方法；请在 S3 阶段资产中写入并保存正式 revision");
  }
  function draftKey(stageIndex: number) {
    return `${activeProject.id}:${stageIndex}`;
  }
  function getDraft(stageIndex: number) {
    const key = draftKey(stageIndex);
    return stageDrafts[key] ?? createLocalStageDraft(stages[stageIndex], activeProject);
  }
  function saveDraft(stageIndex: number, draft: StageDraft, message: string) {
    const key = draftKey(stageIndex);
    const projectId = activeProject.id;
    setStageDrafts((current) => ({ ...current, [key]: draft }));
    showToast(message);
    if (apiProjectIds[projectId]) {
      const remoteProject = apiProjects[projectId];
      const remoteStage = remoteProject?.stages.find((item) => item.key === stages[stageIndex].key);
      if (!remoteStage) {
        setApiError("当前项目尚未完成后端加载，请重新进入项目后再保存");
        showToast("后端阶段尚未加载，本地编辑已保留");
        return;
      }
      const existingWorkspace = stageWorkspace(remoteStage.content);
      const existingContext = asRecord(existingWorkspace.project_context) as StageWorkspacePayload["project_context"];
      setApiBusy(true);
      void saveApiStageWorkspace(
        projectId,
        stages[stageIndex].key,
        draftWorkspace(draft, existingContext),
        remoteStage.revision,
        message,
      ).then(async (updated) => {
        applyApiProject(updated);
        await refreshStageRevisions(projectId, stageIndex);
        setApiError("");
        showToast(`${stages[stageIndex].id} 已同步到 FastAPI revision`);
      }).catch((error) => {
        setApiError(readApiError(error));
        showToast(error instanceof ApiError && error.code === "revision_conflict"
          ? "阶段已有新版本，请重新进入项目后合并修改"
          : "本地编辑已保留，后端同步待重试");
      }).finally(() => setApiBusy(false));
    }
  }
  function openStageDraft() {
    openDeep({ kind: "stage-draft", stageIndex: activeStage });
  }
  function runStageCheck() {
    if (activeStageData.key === "delivery" && apiProjectIds[activeProject.id]) {
      setApiBusy(true);
      void getApiDeliveryQuality(activeProject.id).then((quality) => {
        const statusLabel = {
          needs_revision: "需要整改",
          ready_with_advisories: "可交付，但有改进项",
          ready: "可以交付",
        }[quality.status];
        setDetail({
          eyebrow: `S9 · Academic output quality · ${quality.schema_version}`,
          title: `交付质量检查：${statusLabel}`,
          description: "按结构、引文双向一致性、证据可追溯、逻辑闭环和管理学适用规则检查。必须修复项会阻止 G5 与导出。",
          rows: [
            { label: "交付 revision", value: String(quality.delivery_revision) },
            { label: "必须修复", value: String(quality.counts.must_fix) },
            { label: "建议改进", value: String(quality.counts.should_improve) },
            { label: "正文小节", value: String(quality.traceability.section_count) },
            { label: "已引用论文", value: String(quality.traceability.cited_paper_ids.length) },
          ],
          bullets: quality.issues.length
            ? quality.issues.slice(0, 12).map((issue) => `[${issue.rule_id}] ${issue.location}：${issue.finding}；处理：${issue.required_action}`)
            : ["未发现阻塞项或建议改进项。仍需由指定人工角色完成 G5 审批。"],
        });
        setApiError("");
      }).catch((error) => {
        setApiError(readApiError(error));
        showToast(`交付质量检查失败：${readApiError(error)}`);
      }).finally(() => setApiBusy(false));
      return;
    }
    openDeep({ kind: "stage-check", stageIndex: activeStage });
  }
  function completeProject(project: ResearchProject) {
    const exists = projects.some((item) => item.id === project.id);
    const isApiProject = Boolean(apiProjectIds[project.id]);
    if (apiMode === "connected") {
      setApiBusy(true);
      const persist = isApiProject
        ? updateApiProject(project.id, project.name, project.question)
        : createApiProject(project.name, project.question);
      void persist.then(async (remoteProject) => {
        const problemStage = remoteProject.stages.find((stage) => stage.key === "problem");
        if (!problemStage) throw new Error("后端缺少 S0 阶段");
        const localDraft = stageDrafts[`${project.id}:0`] ?? createLocalStageDraft(stages[0], project);
        const updatedDraft = {
          ...localDraft,
          objective: project.objective,
          scope: project.boundary,
          savedAt: "刚刚由研究者保存",
        };
        return saveApiStageWorkspace(
          remoteProject.project_id,
          "problem",
          draftWorkspace(updatedDraft, projectContext(project)),
          problemStage.revision,
          exists ? "更新项目设置" : "创建项目工作区",
        );
      }).then((updated) => {
        const hydrated = mapApiProject(updated, { ...project, id: updated.project_id });
        setApiProjects((current) => ({ ...current, [updated.project_id]: updated }));
        setApiProjectIds((current) => ({ ...current, [updated.project_id]: true }));
        setProjects((current) => [
          ...current.filter((item) => item.id !== project.id && item.id !== updated.project_id && item.id !== newProjectPlaceholder.id),
          hydrated,
        ]);
        setStageDrafts((current) => ({ ...current, ...mapApiDrafts(updated, hydrated) }));
        setActiveProjectId(updated.project_id);
        setActiveStage(hydrated.stageIndex);
        setQuestion(hydrated.question);
        setSelectedDesign(designSelection(updated));
        setView("journey");
        replaceDeep({ kind: "project-overview", projectId: updated.project_id });
        setApiError("");
        showToast(exists ? "项目设置已同步到 FastAPI" : "新项目已创建并同步到 FastAPI");
      }).catch((error) => {
        setApiError(readApiError(error));
        showToast(`项目保存失败：${readApiError(error)}`);
      }).finally(() => setApiBusy(false));
      return;
    }
    setProjects((current) => exists ? current.map((item) => item.id === project.id ? project : item) : [...current, project]);
    setActiveProjectId(project.id);
    setActiveStage(project.stageIndex);
    setQuestion(project.question);
    setView("journey");
    replaceDeep({ kind: "project-overview", projectId: project.id });
    showToast(exists ? "项目设置已保存在本地演示状态" : "新项目已加入本地演示列表");
  }
  function applyIssueFix(stageIndex: number, issueId: string, value: string, resolve: boolean) {
    const draft = getDraft(stageIndex);
    const issue = createCheckIssues(stages[stageIndex], draft).find((item) => item.id === issueId);
    if (!issue) return;
    saveDraft(stageIndex, { ...draft, [issue.field]: value, savedAt: "刚刚由研究者整改" }, resolve ? "整改内容已写入草稿并标记完成" : "修改已保存到草稿，检查项仍保持待处理");
    if (resolve) setResolvedIssues((current) => ({ ...current, [`${draftKey(stageIndex)}:${issueId}`]: true }));
    backDeep();
  }

  function renderDeepPage() {
    if (!deepRoute) return null;
    if (deepRoute.kind === "stage-draft") {
      const stage = stages[deepRoute.stageIndex];
      const draft = getDraft(deepRoute.stageIndex);
      const revisions = stageRevisions[`${activeProject.id}:${stage.key}`] ?? [];
      return <StageDraftWorkspace key={`${draft.version}:${draft.savedAt}:${draft.syncHistory.length}`} stage={stage} project={activeProject} draft={draft} evidenceRecords={activeEvidence} revisions={revisions} restoringRevision={restoringRevision} onRestore={(revision) => void restoreStageRevision(deepRoute.stageIndex, revision)} onBack={backDeep} onSave={(nextDraft, message) => saveDraft(deepRoute.stageIndex, nextDraft, message)} onOpenCheck={() => openDeep({ kind: "stage-check", stageIndex: deepRoute.stageIndex })} onOpenDecisions={() => openDeep({ kind: "stage-decisions", stageIndex: deepRoute.stageIndex })} onOpenChat={() => openAgentChat(deepRoute.stageIndex)} onOpenEvidence={() => navigateView("evidence")} />;
    }
    if (deepRoute.kind === "stage-check") {
      const stage = stages[deepRoute.stageIndex];
      const issues = createCheckIssues(stage, getDraft(deepRoute.stageIndex));
      const resolved = Object.fromEntries(issues.map((issue) => [issue.id, Boolean(resolvedIssues[`${draftKey(deepRoute.stageIndex)}:${issue.id}`])]));
      return <ConsistencyCheckWorkspace stage={stage} project={activeProject} issues={issues} resolved={resolved} onBack={backDeep} onOpenIssue={(issueId) => openDeep({ kind: "stage-issue", stageIndex: deepRoute.stageIndex, issueId })} onOpenDraft={() => openDeep({ kind: "stage-draft", stageIndex: deepRoute.stageIndex })} onRunAgain={() => showToast("已按当前草稿重新计算本页检查项；审批仍以后端阶段契约为准")} />;
    }
    if (deepRoute.kind === "stage-issue") {
      const stage = stages[deepRoute.stageIndex];
      const draft = getDraft(deepRoute.stageIndex);
      const issue = createCheckIssues(stage, draft).find((item) => item.id === deepRoute.issueId) ?? createCheckIssues(stage, draft)[0];
      return <IssueRemediationPage stage={stage} project={activeProject} issue={issue} resolved={Boolean(resolvedIssues[`${draftKey(deepRoute.stageIndex)}:${issue.id}`])} onBack={backDeep} onApply={(value, resolve) => applyIssueFix(deepRoute.stageIndex, issue.id, value, resolve)} />;
    }
    if (deepRoute.kind === "stage-decisions") {
      const stage = stages[deepRoute.stageIndex];
      const draft = getDraft(deepRoute.stageIndex);
      return <StageDecisionsWorkspace stage={stage} project={activeProject} draft={draft} onBack={backDeep} onSave={(decision) => saveDraft(deepRoute.stageIndex, { ...draft, decision, humanConfirmed: true, savedAt: "刚刚保存人工决定" }, "人工决定记录已保存")} onOpenChat={() => openAgentChat(deepRoute.stageIndex)} onOpenDraft={() => openDeep({ kind: "stage-draft", stageIndex: deepRoute.stageIndex })} />;
    }
    if (deepRoute.kind === "project-wizard") {
      const initial = deepRoute.projectId ? projects.find((project) => project.id === deepRoute.projectId) : undefined;
      return <ProjectWizard initial={initial} onBack={backDeep} onComplete={completeProject} />;
    }
    if (deepRoute.kind === "project-overview") {
      const project = projects.find((item) => item.id === deepRoute.projectId) ?? activeProject;
      return <ProjectOverviewPage project={project} onBack={backDeep} onStart={() => activateProject(project.id)} onEdit={() => openDeep({ kind: "project-wizard", projectId: project.id })} onNew={() => openDeep({ kind: "project-wizard" })} />;
    }
    if (deepRoute.kind === "evidence-record") {
      const record = activeEvidence.find((item) => item.id === deepRoute.evidenceId);
      return record ? <EvidenceRecordPage record={record} busy={apiBusy} onBack={backDeep} onSave={(edits, reason) => updateEvidenceRecord(record, edits, reason)} /> : null;
    }
    if (deepRoute.kind === "method-record") {
      const method = evaluatedMethods.find((item) => item.id === deepRoute.methodId) ?? evaluatedMethods[0];
      return <MethodRecordWorkspace method={method} onBack={backDeep} onAdd={() => addMethodToDesign(method.id)} onSave={() => showToast("本页备注仅临时保留；请写入 S3/S5 阶段草稿并保存正式 revision")} />;
    }
    if (deepRoute.kind === "formula-record") {
      const formula = evaluatedFormulas.find((item) => item.id === deepRoute.formulaId) ?? evaluatedFormulas[0];
      return <FormulaRecordPage formula={formula} onBack={backDeep} onAdd={() => addMethodToDesign(formula.methodId)} onSave={() => showToast("本页说明仅临时保留；请写入 S5 阶段草稿并保存正式 revision")} />;
    }
    if (deepRoute.kind === "approval-gate") {
      const cards = projectGateCards(activeProject, activeApiProject);
      const gate = cards.find((item) => item.id === deepRoute.gateId) ?? cards[0];
      const gateStage: Record<string, number> = { G0: 0, G1: 3, G2: 4, G3: 5, G4: 8, G5: 9 };
      return <ApprovalGatePage gate={gate} onBack={backDeep} onOpenAsset={() => openDeep({ kind: "asset-version", gateId: gate.id })} onSubmit={() => setApprovalStageIndex(gateStage[gate.id] ?? activeStage)} />;
    }
    if (deepRoute.kind === "asset-version") {
      const cards = projectGateCards(activeProject, activeApiProject);
      const gate = cards.find((item) => item.id === deepRoute.gateId) ?? cards[0];
      const gateStage: Record<string, number> = { G0: 0, G1: 3, G2: 4, G3: 5, G4: 8, G5: 9 };
      const stageIndex = gateStage[gate.id] ?? activeStage;
      const remoteStage = activeApiProject?.stages.find(
        (item) => item.key === stages[stageIndex].key,
      );
      return <AssetVersionPage gate={gate} snapshot={assetVersionSnapshot(remoteStage)} onBack={backDeep} onSave={(sectionKey, title, content) => saveAssetSection(stageIndex, sectionKey, title, content)} />;
    }
    return null;
  }

  return (
    <div className="app-shell" data-interface-theme={interfaceTheme}>
      <header className="topbar">
        <button className="brand" onClick={() => navigateView("journey")} aria-label="返回研究旅程"><span>AI</span>4MS</button>
        <nav className="topnav" aria-label="主导航">
          {navItems.map((item) => <button className={view === item.key ? "is-active" : ""} onClick={() => navigateView(item.key)} key={item.key}><span>{item.label}</span><small>{item.short}</small></button>)}
        </nav>
        <div className="topbar-actions">
          <div className="project-switcher-wrap">
            <button className="project-switcher" onClick={() => setProjectMenu((open) => !open)} aria-expanded={projectMenu}><span>当前项目</span><strong>{activeProject.name}</strong><b>⌄</b></button>
            {projectMenu && <div className="project-menu">
              <div className="project-menu-label">项目列表 · {projects.length}</div>
              <button className="new-project" onClick={() => { setView("journey"); replaceDeep({ kind: "project-wizard" }); }}>＋ 创建新课题</button>
              <button className="project-center-link" onClick={() => { setView("journey"); replaceDeep({ kind: "project-overview", projectId: activeProject.id }); }}>查看当前项目中心 <span>→</span></button>
              <hr />
              {projects.map((project) => <button className={project.id === activeProject.id ? "is-current" : ""} onClick={() => activateProject(project.id)} key={project.id}><span>{project.icon}</span><div><strong>{project.name}</strong><small>S{project.stageIndex} · {stages[project.stageIndex].name}</small></div>{project.id === activeProject.id && <b>✓</b>}</button>)}
              <div className={`project-api-state state-${apiMode}`} title={apiError || "FastAPI connection ready"}><span /><div><strong>{apiBusy ? "正在同步" : apiMode === "connected" ? "FastAPI 已连接" : apiMode === "loading" ? "正在连接项目服务" : "前端演示数据模式"}</strong><small>{apiMode === "fallback" ? "恢复后端后可继续同步" : "项目与阶段 revision 保持一致"}</small></div></div>
            </div>}
          </div>
          <button className="icon-button" onClick={() => { navigateView("approvals"); showToast("已打开人工审批中心"); }} aria-label="通知">●<i>2</i></button>
          <div className="user-menu-wrap">
            <button className="user-button" onClick={() => setUserMenu((open) => !open)} aria-expanded={userMenu} aria-label="用户菜单">N</button>
            {userMenu && <div className="user-menu-popover">
              <strong>研究者工作区</strong><span>Human reviewer</span>
              <button onClick={() => { setUserMenu(false); openAgentChat(); }}>打开当前智能体</button>
              <button onClick={() => { setUserMenu(false); window.open("/ai4ms-user-guide.html", "_blank", "noopener,noreferrer"); }}>使用说明</button>
              <button onClick={() => { setUserMenu(false); setPreferencesOpen(true); }}>界面偏好</button>
            </div>}
          </div>
        </div>
      </header>

      <main className={`main-shell view-${view} ${deepRoute ? "view-deep" : ""}`}>
        {view === "journey" && !deepRoute && <StageRail activeIndex={activeStage} remoteStages={apiProjects[activeProject.id]?.stages} onSelect={selectStage} />}
        <div className="main-content">
          {deepRoute ? renderDeepPage() : <>
          {view === "journey" && (
            <>
              <header className="journey-header">
                <div><p className="eyebrow">Research Journey · {activeStageData.agent}</p><h1>{activeStageData.name}</h1><p><strong>{activeStage + 1}/10</strong> 阶段 <span>·</span> <b>{activeStageData.gate} {activeRemoteStage?.status === "approved" ? "已批准" : "待确认"}</b></p></div>
                <ProgressNodes activeIndex={activeStage} remoteStages={apiProjects[activeProject.id]?.stages} />
              </header>
              <div className="journey-grid">
                <section className="stage-content">
                  <nav className="stage-action-strip" aria-label="阶段工作入口"><div><span>{activeStageData.id}</span><strong>阶段工作资产</strong><small>草稿、人工决定与检查结果均可继续修改</small></div><button onClick={openStageDraft}>打开当前草稿</button><button onClick={() => openDeep({ kind: "stage-decisions", stageIndex: activeStage })}>待决定项</button><button className="is-primary" onClick={runStageCheck}>一致性检查</button></nav>
                  {activeStage === 3
                    ? <DesignWorkspace question={question} setQuestion={setQuestion} selectedDesign={selectedDesign} setSelectedDesign={setSelectedDesign} onCompareMethods={() => setView("methods")} onSave={() => void saveDesignPanel()} remoteStage={activeRemoteStage} methodRecords={evaluatedMethods} busy={apiBusy} />
                    : activeStage === 9
                      ? <DeliveryCenter projectId={activeProject.id} remoteStage={activeRemoteStage} busy={apiBusy} onExport={() => void refreshDeliveryExport()} />
                      : <div className="stage-control-stack">
                        {activeStage === 0 && <ProblemQuestionControl key={`problem-${activeRemoteStage?.revision ?? 0}`} stage={activeRemoteStage} busy={apiBusy} onSelect={selectResearchQuestion} />}
                        {activeStage === 1 && <LiteraturePlanControl key={`literature-${activeRemoteStage?.revision ?? 0}`} stage={activeRemoteStage} busy={apiBusy} onReview={reviewCurrentLiteraturePlan} />}
                        <GenericStage stageIndex={activeStage} remoteStage={activeRemoteStage} onOpenDraft={openStageDraft} onOpenDecision={() => openDeep({ kind: "stage-decisions", stageIndex: activeStage })} onRunCheck={runStageCheck} />
                      </div>}
                </section>
                <AgentPanel
                  stageIndex={activeStage}
                  suggestions={activeStageSuggestions}
                  suggestionBusy={suggestionBusyKey === activeSuggestionKey}
                  remoteStage={activeRemoteStage}
                  busy={apiBusy}
                  onRefreshSuggestions={() => void refreshStageSuggestions()}
                  onDecision={decideSuggestion}
                  onGenerate={generateActiveStageAssets}
                  onSubmit={() => setApprovalStageIndex(activeStage)}
                  onOpenChat={() => openAgentChat()}
                />
              </div>
            </>
          )}
          {view === "evidence" && <EvidenceLibrary records={activeEvidence} candidates={activeEvidenceCandidates} searchRuns={literatureSearchRuns} busy={apiBusy} onSearch={runEvidenceSearch} onReview={reviewEvidenceCandidate} onOpenRecord={(evidenceId) => openDeep({ kind: "evidence-record", evidenceId })} onToast={showToast} />}
          {view === "methods" && <MethodsView methods={evaluatedMethods} formulas={evaluatedFormulas} governanceCandidates={knowledgeGovernanceCandidates} governanceRecords={knowledgeGovernanceRecords} diagnosticRules={diagnosticRules} diagnosticRegistryVersion={diagnosticRegistryVersion} evaluation={activeKnowledgeEvaluation} busy={knowledgeBusy} onEvaluate={runKnowledgeEvaluation} onOpenMethod={(methodId) => openDeep({ kind: "method-record", methodId })} onOpenFormula={(formulaId) => openDeep({ kind: "formula-record", formulaId })} onAdd={addMethodToDesign} onDiscover={discoverKnowledgeCandidate} onReviewCandidate={reviewKnowledgeGovernanceCandidate} onCreateRecord={createKnowledgeGovernanceRecord} onPatchRecord={patchKnowledgeGovernanceRecord} onToast={showToast} />}
          {view === "runs" && <RunsView project={activeProject} apiProject={apiProjects[activeProject.id]} onProjectUpdated={applyApiProject} onOpenGate={(gateId) => openDeep({ kind: "approval-gate", gateId })} onToast={showToast} />}
          {view === "approvals" && <ApprovalsView project={activeProject} apiProject={activeApiProject} onOpenGate={(gateId) => openDeep({ kind: "approval-gate", gateId })} onOpenDetail={setDetail} />}
          </>}
        </div>
      </main>

      <ApprovalModal
        key={`${activeProject.id}:${approvalStageData.gate}:${approvalOpen}`}
        open={approvalOpen}
        stageIndex={approvalStageIndex ?? activeStage}
        revision={approvalRemoteStage?.revision ?? getDraft(approvalStageIndex ?? activeStage).version}
        contentHash={approvalRemoteStage?.content_hash ?? null}
        onClose={() => setApprovalStageIndex(null)}
        onConfirm={confirmApproval}
      />
      <DetailModal detail={detail} onClose={() => setDetail(null)} />
      <PreferencesModal open={preferencesOpen} value={interfaceTheme} onSelect={selectInterfaceTheme} onClose={() => setPreferencesOpen(false)} />
      <AgentChatDrawer
        open={chatOpen}
        agentIndex={chatAgent}
        messages={chatMessages[activeChatKey] ?? []}
        loading={chatLoadingKey === activeChatKey}
        busy={chatBusyKey === activeChatKey}
        tools={stageDefinitions.find((item) => item.key === stages[chatAgent].key)?.agent_policy.tools ?? []}
        toolBusyId={toolBusyId}
        onClose={() => setChatOpen(false)}
        onSelectAgent={selectChatAgent}
        onSend={(text, searchMode) => void sendAgentMessage(text, searchMode)}
        onInvokeTool={(tool) => void invokeAgentTool(tool)}
        onCapture={syncAgentOutput}
      />
      {toast && <div className="toast" role="status"><span>✓</span>{toast}</div>}
      <div className="screen-reader-status" aria-live="polite">当前页面：{pageTitle}</div>
    </div>
  );
}
