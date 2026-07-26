#!/usr/bin/env python3
"""Generate the method, data-source, and formula libraries in JSON/CSV/Markdown."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "02_knowledge_bases"


def method(
    method_id: str,
    family: str,
    name: str,
    lane: str,
    goal: str,
    data: str,
    assumptions: str,
    workflow: str,
    diagnostics: str,
    robustness: str,
    packages: str,
    formula_ids: str,
    failure: str,
) -> dict[str, Any]:
    return locals()


METHODS = [
    method("M01", "基础统计", "描述统计与探索性数据分析", "共享基础", "理解分布、缺失、异常、关联与数据生成过程", "结构化或半结构化样本", "样本定义一致；统计口径可比", "口径表→缺失/异常→分布→分组→相关→可视化→异常说明", "缺失机制、极端值、重复记录、单位与时间对齐", "替代口径、缩尾/稳健统计、分层描述", "pandas/Polars; R tidyverse; DuckDB", "STAT-01", "把相关性当因果，或在清洗前就开始建模"),
    method("M02", "统计实证", "OLS/GLM 回归", "实证解释", "估计条件相关或广义响应关系", "截面、面板或计数/二元结果", "线性/链接函数正确；误差与解释变量关系满足估计要求", "理论→变量→基准式→估计→诊断→替代式→解释", "残差、异方差、共线性、聚类结构、过度离散", "稳健/聚类标准误、替代因变量、非线性、删样本", "statsmodels; R fixest/glm", "STAT-02; STAT-03; STAT-04", "只报告显著性，不报告效应量、区间与实际意义"),
    method("M03", "统计实证", "面板固定效应/随机效应", "实证解释", "控制不可观测个体或时间不变异质性", "个体×时间面板", "严格外生或给定效应下外生；组内变异足够", "面板审计→FE/RE 选择→双向效应→聚类误差→动态/滞后检验", "组内变异、序列相关、横截面相关、短面板偏误", "双向聚类、趋势项、滞后、Arellano-Bond/系统 GMM", "linearmodels; R fixest/plm", "STAT-04", "固定效应吸收了核心变量后仍强行解释"),
    method("M04", "测量模型", "结构方程模型/PLS-SEM", "实证解释", "估计潜变量、测量关系与结构路径", "问卷、量表、多指标构念", "构念有效；样本与估计器匹配；模型可识别", "理论构念→量表→预测试→测量模型→结构模型→中介/调节", "信度、聚合/区分效度、共同方法偏差、拟合", "替代测量、竞争模型、多群组、不变性检验", "R lavaan/seminr; Mplus; SmartPLS", "STAT-06", "用 PLS 规避糟糕测量，或用拟合指标替代理论"),
    method("M05", "事件过程", "生存分析/风险模型", "实证解释", "分析事件发生时间与删失", "持续时间、事件状态、协变量", "删失机制合理；比例风险等模型假设可检验", "定义起点/事件→删失→KM→Cox/AFT→时变协变量→预测", "比例风险、竞争风险、信息性删失", "AFT、分层 Cox、Fine-Gray、替代时间窗", "lifelines; scikit-survival; R survival", "STAT-05", "忽略左截断、重复事件或竞争风险"),
    method("M06", "因果推断", "双重差分与事件研究", "因果识别", "估计政策/冲击对处理组的平均影响", "处理组、对照组、处理时间、面板/重复截面", "平行趋势、无提前反应、无干扰；分期处理需正确估计", "DAG→处理定义→样本→动态效应→平行趋势→异质性→安慰剂", "预趋势、处理时点异质、组别构成、溢出", "Callaway-Sant'Anna/Sun-Abraham、替代对照、placebo", "R did/fixest; Stata csdid; Python linearmodels", "CAUS-02; CAUS-03", "对分期处理直接使用传统 TWFE 并误读权重"),
    method("M07", "因果推断", "工具变量/2SLS", "因果识别", "处理内生性并估计局部平均处理效应", "结果、内生处理、工具变量、控制变量", "相关性、排除限制、独立性、单调性", "机制/DAG→一阶段→弱工具检验→2SLS→过识别→LATE 解释", "第一阶段 F、弱工具、排除限制、异质效应", "LIML、不同工具、Conley bounds、负向对照", "linearmodels IV; R AER/fixest; Stata ivreg2", "CAUS-04", "只证明工具相关，不论证排除限制"),
    method("M08", "因果推断", "回归不连续设计", "因果识别", "利用阈值规则识别局部因果效应", "运行变量、阈值、处理状态、结果", "阈值附近连续、不可精确操纵、函数形式局部有效", "制度规则→带宽→图形→局部多项式→密度/协变量检验→稳健性", "McCrary 密度、协变量平衡、带宽、donut RDD", "多带宽/核、局部随机化、placebo cutoff", "R rdrobust; Python rdrobust", "CAUS-05", "高阶全局多项式造成虚假跳跃"),
    method("M09", "因果推断", "合成控制", "因果识别", "为单个或少数处理单位构造反事实", "长处理前序列、供体池、处理后结果", "供体池未受处理；处理前拟合充分；无强溢出", "供体池→预测变量→权重→前期拟合→后期差距→置换检验", "RMSPE、供体权重集中、处理前拟合、溢出", "leave-one-out、augmented SC、matrix completion", "R Synth/augsynth; Python SyntheticControlMethods", "CAUS-06", "供体池不合格或前期拟合差仍宣称因果"),
    method("M10", "因果机器学习", "DML/因果森林与异质效应", "因果识别", "在高维控制下估计 ATE/CATE", "个体级处理、结果、高维协变量", "重叠、无未观测混杂或有效工具；交叉拟合正确", "DAG→样本分割→nuisance 模型→正交化→ATE/CATE→校准", "重叠、nuisance 误差、校准、CATE 稳定性", "不同 learner、敏感性分析、honest splitting", "EconML; DoubleML; grf", "CAUS-08", "把异质性排序当成已验证的个体因果效应"),
    method("M11", "实验", "实验室/现场/在线随机实验", "因果识别", "通过随机化估计干预效应与机制", "处理分配、结果、预注册指标", "随机化有效；SUTVA；流失与不依从可处理", "理论→预注册→功效→随机化→操纵→估计→多重检验→外部效度", "平衡、操纵检验、流失、不依从、干扰", "ITT/TOT、随机化推断、分层、替代指标", "R DeclareDesign; statsmodels; Qualtrics/oTree", "EXP-01; EXP-02", "事后改主指标、低功效或多重比较未校正"),
    method("M12", "定性研究", "案例研究/访谈/扎根理论", "探索与理论生成", "解释新现象、过程与机制并生成理论", "访谈、档案、观察、过程资料", "理论抽样合理；证据链与反例处理透明", "研究边界→理论抽样→协议→编码→范畴→机制→跨案例→饱和", "编码一致性、负例、三角验证、研究者反思", "替代解释、成员核验、审计轨迹、不同编码者", "NVivo/Atlas.ti; Python/R text tooling", "", "把少数案例频数化，或没有证据链就做普遍因果主张"),
    method("M13", "证据综合", "系统综述/文献计量/元分析", "证据综合", "系统识别、编码并综合研究结论", "文献记录、效应量、编码表", "检索与纳排可复现；效应量可比；偏倚可评估", "协议→多库检索→去重→筛选→编码→质量→综合→偏倚→议程", "覆盖率、双人一致性、发表偏倚、异质性", "替代检索式、leave-one-out、质量加权、p-curve", "ASReview; revtools; metafor; bibliometrix", "META-01", "只用单一关键词/数据库，或把引用量当质量"),
    method("M14", "设计科学", "设计科学研究/Action Design Research", "设计构建", "构建并评估解决组织问题的人工制品", "需求证据、构件日志、评估指标与场景数据", "问题重要；设计知识可抽象；评估与主张匹配", "问题→设计目标→构件→原型→评估→迭代→设计原则", "效用、可用性、技术正确性、场景适配、可迁移性", "多场景评估、基线、消融、对抗/极端案例", "Git; experiment harness; UX analytics", "DSR-01", "只做软件开发，没有研究问题、评估和可迁移设计知识"),
    method("M15", "运筹优化", "线性规划/混合整数规划", "规范决策", "在约束下求最优资源配置与计划", "参数、决策变量、目标、约束", "线性关系；参数口径一致；可行域与整数性正确", "业务规则→变量→目标→约束→小例验证→求解→gap→敏感性", "可行性、最优 gap、规模、对偶值、约束绑定", "替代目标/权重、场景、松弛、warm start", "Pyomo/PuLP/OR-Tools; Gurobi/CPLEX/HiGHS", "OPT-01; OPT-02", "模型可解但业务不可执行，或把单位/索引写错"),
    method("M16", "运筹优化", "随机规划/鲁棒优化/机会约束", "规范决策", "在不确定性下给出可控风险的决策", "场景/不确定集合/概率分布、成本与约束", "不确定性表示与业务风险一致；样本外可验证", "不确定源→场景/集合→两阶段/鲁棒模型→求解→样本外→保守度", "样本外违约率、VSS/EVPI、价格鲁棒性、分布漂移", "不同集合半径、bootstrap 场景、DRO、stress test", "Pyomo; CVXPY; Gurobi; RSOME", "OPT-03; OPT-04; OPT-05", "在训练场景内漂亮、样本外失效；鲁棒半径任意"),
    method("M17", "动态决策", "动态规划/MDP/强化学习", "规范决策", "在状态随时间演化时学习最优策略", "状态、动作、转移、奖励、折扣/终止", "马尔可夫性近似成立；奖励与真实目标一致；离线数据覆盖", "状态/动作→Bellman→基线策略→求解/学习→离线评估→安全约束", "收敛、策略价值、覆盖、分布外动作、奖励黑客", "替代奖励、保守离线 RL、模拟器、策略约束", "Gymnasium; Stable-Baselines3; Ray RLlib; JAX/PyTorch", "STO-04; ML-05", "只看累计奖励，不检查可解释性、安全与分布外风险"),
    method("M18", "随机系统", "排队论/离散事件仿真/仿真优化", "规范决策", "评估拥堵、容量、服务和随机流程", "到达/服务分布、流程、资源、策略", "到达服务过程有可辩护模型；稳态/热身处理正确", "流程映射→分布拟合→模型→验证→实验设计→置信区间→优化", "守恒关系、热身期、独立重复、校准、极端负载", "替代分布、压力场景、方差缩减、仿真优化", "SimPy; AnyLogic; Arena; simmer", "STO-01; STO-02", "单次仿真当结论，或不做真实系统校准"),
    method("M19", "组合优化", "网络流/选址/路径与调度", "规范决策", "优化物流、交通、网络设计和资源时空匹配", "图、需求、容量、成本、时间窗", "网络与约束真实；规模与求解策略匹配", "图建模→基准 MILP→分解/启发式→算例→真实实例→敏感性", "可行率、最优 gap、运行时、不同规模、业务 KPI", "多初值、精确算法对照、消融、扰动测试", "OR-Tools; NetworkX; PyVRP; Gurobi", "OPT-06; OPT-07; OPT-08", "只和弱基线比较，或测试实例与真实规模不匹配"),
    method("M20", "运营模型", "库存/收益管理/定价", "规范决策", "平衡缺货、持有、容量与价格收益", "需求分布、成本、提前期、容量、价格响应", "需求和成本估计可用；政策边界清晰", "需求→成本→基准模型→最优政策→估计/校准→仿真→敏感性", "服务水平、缺货/积压、估计误差、非平稳性", "分布鲁棒、滚动窗口、情景、行为偏差", "Pyomo; scipy; inventory/forecast packages", "OPT-09; OPT-10", "用历史均值代替需求不确定性，或忽略执行约束"),
    method("M21", "解析建模", "博弈论/机制设计/契约", "机制解释", "解释战略互动并设计激励、平台或供应链机制", "参与者、行动、信息、效用/利润、时序", "理性与信息结构适配；均衡存在/唯一性与边界明确", "参与者→时序→收益→均衡→比较静态→福利→机制设计→数值校准", "均衡多重性、参数边界、参与约束、社会福利", "替代时序/信息、行为偏差、经验校准、数值全局搜索", "Mathematica/Maple; SymPy; scipy/JAX", "GAME-01; GAME-02; GAME-03", "数学均衡漂亮但参数区间不现实、管理含义不可执行"),
    method("M22", "结构估计", "离散选择/需求与结构模型", "机制解释", "估计偏好、替代关系与反事实政策", "个体/市场选择、属性、价格、可用集合", "效用设定合理；选择集正确；价格内生性处理", "效用→选择集→识别→估计→拟合→弹性→反事实→福利", "IIA、弱识别、价格内生、外部有效性", "mixed logit、工具变量、不同市场定义、holdout", "PyLogit; Biogeme; R mlogit; pyblp", "DEMAND-01", "遗漏选择集或忽略价格内生性"),
    method("M23", "时序预测", "ARIMA/VAR/状态空间", "预测与解释", "预测单变量或多变量动态并分析冲击", "等频时序、外生变量、足够历史", "平稳/协整与误差结构可检验；无未来泄漏", "时间切分→平稳性→基线→识别→估计→残差→滚动回测", "ACF/PACF、单位根、残差白噪声、结构突变", "滚动窗、不同滞后、状态空间、结构断点", "statsmodels; sktime; R forecast/fable/vars", "TIME-01; TIME-02", "随机打乱时序交叉验证造成信息泄漏"),
    method("M24", "机器学习", "监督学习/集成学习", "预测计算", "预测分类、回归、排序或风险", "特征、标签、时间/组别结构", "训练与部署分布可比；标签与决策目标一致", "任务→切分→特征→基线→训练→调参→评估→解释→监控", "泄漏、校准、组别/时间外推、类别不平衡", "时间/组 CV、消融、外部测试、漂移与公平性", "scikit-learn; XGBoost; LightGBM; CatBoost", "ML-01; ML-02", "只追求一个指标，不做基线、校准和决策价值评估"),
    method("M25", "文本与生成式AI", "NLP/嵌入/主题与文本因果", "预测计算", "把论文、评论、公告和对话转为变量或预测", "文本、时间戳、作者/实体、标签或弱监督", "语料权限清楚；时间切分；标注有效；提示与模型版本可追踪", "语料→清洗→标注→表示→模型→人工审计→稳定性→下游验证", "标注一致性、漂移、幻觉、提示敏感、去标识化", "多模型/提示、人工复核、词典基线、时间外测试", "spaCy; transformers; sentence-transformers; BERTopic", "ML-02; ML-04", "把 LLM 输出直接当真值，或无法复现模型/提示版本"),
    method("M26", "网络科学", "社会/供应链/金融网络分析", "解释与预测", "分析关系结构、传播、中心性与系统风险", "节点、边、权重、时间或多层关系", "边定义与缺失机制合理；网络边界清楚", "关系定义→图构建→描述→中心性/社区→传播/因果→稳健性", "边阈值、边界、同配性、置换、时间演化", "替代边定义、随机网络基线、留边/留点、动态网络", "NetworkX; igraph; graph-tool; PyG", "NET-01", "把中心性当因果影响，或忽略网络采样偏误"),
    method("M27", "贝叶斯", "贝叶斯层级模型", "实证解释", "合并先验与数据、部分池化并传播不确定性", "多层/小样本/异质群组数据", "生成模型可辨识；先验可解释；采样收敛", "DGP→先验→似然→后验采样→PPC→比较→决策", "R-hat、ESS、发散、PPC、先验敏感性", "弱/强先验、不同层级、LOO-CV、模拟校准", "PyMC; Stan; brms", "BAYES-01", "只报告后验均值，不做收敛与后验预测检查"),
    method("M28", "复杂系统", "主体仿真/系统动力学", "探索与规范", "研究涌现、反馈、扩散和非线性政策效果", "规则、主体、网络、状态、校准目标", "规则有证据基础；宏观模式可校准；不确定性透明", "机制→主体规则→实现→验证→校准→实验→敏感性→模式解释", "代码验证、模式复现、参数不可辨识、随机性", "全局敏感性、替代规则、真实模式校准、重复实验", "Mesa; NetLogo; AnyLogic; SALib", "STO-03", "用仿真讲故事而不做校准、验证和敏感性分析"),
]


def data_source(
    source_id: str,
    domain: str,
    name: str,
    geography: str,
    access: str,
    cost: str,
    interface: str,
    typical_data: str,
    common_use: str,
    compliance: str,
    url: str,
    connector_priority: str,
) -> dict[str, Any]:
    return locals()


DATA_SOURCES = [
    data_source("D01", "文献元数据", "OpenAlex", "全球", "开放 API/快照", "免费；高级功能可能需 key", "REST/快照", "论文、作者、机构、期刊、主题、引用", "检索、引文网络、热点与作者机构分析", "记录检索日期；引用量是动态指标", "https://openalex.org/", "P0"),
    data_source("D02", "文献元数据", "Crossref", "全球", "开放 API", "免费", "REST", "DOI、题名、作者、期刊、参考文献元数据", "DOI 核验、BibTeX、出版元数据补全", "遵守 polite pool；字段完整性依出版商", "https://www.crossref.org/", "P0"),
    data_source("D03", "文献元数据", "Semantic Scholar", "全球", "API；有速率限制", "免费/申请 key", "REST", "论文、摘要、引用、嵌入、推荐", "语义检索、引用补全、相似论文", "记录语料覆盖与计数差异", "https://www.semanticscholar.org/product/api", "P0"),
    data_source("D04", "文献全文", "arXiv", "全球", "开放 API/OAI", "免费", "Atom API/OAI-PMH", "预印本元数据与 PDF", "新兴主题、方法论文、版本追踪", "预印本不等同同行评审版本", "https://arxiv.org/", "P0"),
    data_source("D05", "开放获取", "Unpaywall", "全球", "API/快照", "免费；需邮箱", "REST/快照", "DOI 对应 OA 状态与合法全文位置", "合法全文发现与 OA 覆盖", "只使用合法位置；遵守全文许可", "https://unpaywall.org/products/api", "P1"),
    data_source("D06", "宏观经济", "World Bank Data", "全球", "开放", "免费", "API/下载", "发展、贸易、人口、营商、治理指标", "国家/地区面板、政策与发展研究", "核对指标定义、修订与可比性", "https://data.worldbank.org/", "P0"),
    data_source("D07", "宏观经济", "IMF Data", "全球", "开放/注册", "多数免费", "API/下载", "金融、国际收支、财政、汇率", "宏观金融、国家风险、政策研究", "系列口径和修订频繁", "https://www.imf.org/en/Data", "P1"),
    data_source("D08", "宏观经济", "OECD Data Explorer", "OECD及伙伴", "开放", "免费", "API/下载", "产业、生产率、创新、教育、TiVA", "跨国制度与产业比较", "版本、季调与国家可比性", "https://data-explorer.oecd.org/", "P1"),
    data_source("D09", "贸易供应链", "UN Comtrade", "全球", "开放/订阅层", "免费额度 + 付费", "API/下载", "双边商品贸易、HS 编码、数量与价值", "贸易网络、供应链冲击、产业依赖", "HS 版本、镜像差异、再出口与缺失", "https://comtradeplus.un.org/", "P1"),
    data_source("D10", "宏观金融", "FRED", "美国/全球系列", "开放 API", "免费；API key", "REST/下载", "利率、通胀、就业、金融与宏观时序", "事件研究控制、预测、宏观背景", "系列来源不同；记录 vintage", "https://fred.stlouisfed.org/", "P0"),
    data_source("D11", "美国企业与披露", "SEC EDGAR", "美国", "开放", "免费", "REST/文件", "10-K/10-Q/8-K/XBRL、公司事实", "公司披露、文本、财务与事件", "必须遵守 SEC fair-access 速率和 UA", "https://www.sec.gov/edgar/sec-api-documentation", "P0"),
    data_source("D12", "美国劳动力", "BLS Public Data", "美国", "开放 API", "免费", "REST/下载", "就业、工资、价格、生产率", "劳动力与产业面板、宏观控制", "系列代码、季调与修订", "https://www.bls.gov/developers/", "P1"),
    data_source("D13", "美国人口企业", "U.S. Census / ACS", "美国", "开放 API", "免费；key 推荐", "REST/下载", "人口、住房、企业动态、贸易", "地区面板、市场规模、政策评估", "地理边界、抽样误差与 disclosure rules", "https://www.census.gov/data/developers.html", "P1"),
    data_source("D14", "中国宏观", "国家统计局国家数据", "中国", "公开查询", "免费", "网页/下载", "国民经济、人口、工业、地区指标", "省市面板、产业与政策背景", "接口稳定性与口径变更需人工核验", "https://data.stats.gov.cn/", "P1"),
    data_source("D15", "中国金融企业", "CSMAR 国泰安", "中国", "机构订阅", "付费", "下载/API视授权", "上市公司、证券、治理、分析师、事件", "公司金融、会计、治理与市场研究", "严格遵守机构许可，不可公开再分发", "https://www.gtarsc.com/", "P1"),
    data_source("D16", "中国金融企业", "CNRDS", "中国", "机构订阅", "付费", "下载", "上市公司、治理、专利、供应链、文本", "公司与创新、供应链、ESG研究", "许可与变量定义需逐库核对", "https://www.cnrds.com/", "P1"),
    data_source("D17", "中国金融宏观", "Wind", "中国/全球", "终端/机构授权", "付费", "终端/API", "证券、公司、基金、宏观、行业", "金融与企业面板、事件研究", "不得把授权数据上传外部模型或再分发", "https://www.wind.com.cn/", "P2"),
    data_source("D18", "中国调查", "CFPS 中国家庭追踪调查", "中国", "注册申请", "研究用途免费", "下载", "个人、家庭、教育、就业、收入、健康", "家庭行为、劳动力与社会政策", "伦理审批、去标识、引用与申请条款", "https://www.isss.pku.edu.cn/cfps/", "P1"),
    data_source("D19", "中国调查", "CGSS 中国综合社会调查", "中国", "注册申请", "研究用途免费", "下载", "社会态度、行为、职业、家庭", "组织行为、制度信任、消费与社会研究", "权重、抽样设计与使用协议", "http://cgss.ruc.edu.cn/", "P2"),
    data_source("D20", "中国调查", "CHARLS", "中国", "注册申请", "研究用途免费", "下载", "中老年健康、家庭、劳动、养老", "医疗服务运营、劳动与老龄化", "伦理与敏感变量保护", "https://charls.charlsdata.com/", "P2"),
    data_source("D21", "金融研究", "WRDS", "全球/美国为主", "机构订阅", "付费", "SQL/Python/R/SAS", "CRSP、Compustat、IBES、TAQ等统一入口", "资产定价、公司金融、市场微观结构", "子库许可独立；不得再分发", "https://wrds-www.wharton.upenn.edu/", "P1"),
    data_source("D22", "企业数据库", "Orbis", "全球", "机构订阅", "付费", "平台/下载", "私营与上市企业、所有权、财务、关联关系", "企业网络、国际化、供应链与治理", "匹配与覆盖偏差；严格许可", "https://www.bvdinfo.com/en-gb/our-products/data/international/orbis", "P2"),
    data_source("D23", "企业金融", "S&P Capital IQ / Compustat", "全球", "机构订阅", "付费", "平台/API", "公司财务、交易、估值、证券、行业", "公司面板、并购、资本市场", "许可、实体匹配与存活偏差", "https://www.spglobal.com/marketintelligence/", "P2"),
    data_source("D24", "金融新闻", "LSEG Data & Analytics", "全球", "机构订阅", "付费", "Workspace/API", "市场、公司、新闻、ESG、分析师", "事件、文本、金融与ESG", "新闻与数据授权限制严格", "https://www.lseg.com/en/data-analytics", "P2"),
    data_source("D25", "新闻事件", "GDELT", "全球", "开放", "免费", "BigQuery/API/文件", "全球新闻、事件、语调、实体", "事件检测、媒体关注、地缘风险", "自动编码噪声、媒体覆盖偏差", "https://www.gdeltproject.org/", "P1"),
    data_source("D26", "网页语料", "Common Crawl", "全球", "开放", "免费（计算有成本）", "S3/索引", "网页抓取、WARC、链接与文本", "大规模网页、企业与产品文本", "robots/版权/隐私与去重；只处理合规内容", "https://commoncrawl.org/", "P2"),
    data_source("D27", "软件与协作", "GitHub Archive", "全球", "开放事件流", "免费", "BigQuery/文件", "公开 GitHub 事件", "开源协作、创新、开发者行为", "仅公开事件；账号去标识与平台条款", "https://www.gharchive.org/", "P1"),
    data_source("D28", "知识社区", "Stack Exchange Data Dump / SEDE", "全球", "开放", "免费", "SQL/下载", "问答、标签、投票、用户与时间", "知识生产、社区、技术扩散", "遵守 CC BY-SA 与去标识原则", "https://data.stackexchange.com/", "P1"),
    data_source("D29", "消费与服务", "Yelp Open Dataset", "指定城市/商户", "开放研究数据", "免费", "JSON", "评论、评分、商户、用户、签到", "推荐、服务运营、文本与网络", "只按数据集许可使用；不外推到总体", "https://business.yelp.com/data/resources/open-dataset/", "P1"),
    data_source("D30", "趋势关注", "Google Trends", "全球", "公开界面", "免费", "网页/非正式接口", "相对搜索兴趣", "关注度、需求先行指标、事件反应", "抽样与归一化；接口与服务条款风险", "https://trends.google.com/trends/", "P2"),
    data_source("D31", "交通出行", "NYC TLC Trip Record Data", "纽约市", "开放", "免费", "Parquet/CSV", "出租车/网约车行程、时间、费用、区域", "需求预测、定价、匹配、交通政策", "地理/时间口径、异常与隐私聚合", "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page", "P0"),
    data_source("D32", "交通流", "Caltrans PeMS", "加州", "注册/开放", "免费", "下载/API工具", "高速路检测器流量、速度、占有率", "交通预测、拥堵与控制", "传感器缺失、漂移、站点变更", "https://pems.dot.ca.gov/", "P1"),
    data_source("D33", "地理网络", "OpenStreetMap", "全球", "开放数据库", "免费", "Overpass/Planet/PBF", "道路、POI、建筑与关系", "选址、网络、物流与城市研究", "ODbL 署名/同许可；区域质量差异", "https://www.openstreetmap.org/", "P0"),
    data_source("D34", "公共交通", "GTFS / MobilityData", "全球各城市", "开放程度依发布者", "通常免费", "ZIP/静态与实时", "站点、班次、线路、实时车辆", "公共交通可达性、可靠性与调度", "各运营者许可和覆盖不同", "https://gtfs.org/", "P1"),
    data_source("D35", "能源", "U.S. EIA Open Data", "美国/国际部分", "开放 API", "免费；key", "REST/下载", "电力、石油、天然气、价格与容量", "能源运营、市场、政策与碳研究", "系列修订、单位与时区", "https://www.eia.gov/opendata/", "P1"),
    data_source("D36", "天气气候", "NOAA Climate Data Online", "全球/美国", "开放 API", "免费；token", "REST/下载", "气象站、温度、降水、极端天气", "需求、物流、灾害与运营冲击", "站点缺失、空间插值、极端值口径", "https://www.ncei.noaa.gov/cdo-web/webservices/v2", "P1"),
    data_source("D37", "天气气候", "Copernicus ERA5", "全球", "注册开放", "免费（计算/下载有成本）", "API/NetCDF", "再分析气象时空网格", "气候风险、能源与供应链冲击", "再分析非观测真值；空间尺度匹配", "https://cds.climate.copernicus.eu/", "P2"),
    data_source("D38", "医疗运营", "CMS Data", "美国", "开放/受限子库", "多数免费", "API/下载", "医疗服务、质量、支付、机构", "医疗运营、质量、政策评估", "HIPAA/小样本披露与机构匹配", "https://data.cms.gov/", "P1"),
    data_source("D39", "医疗运营", "MIMIC-IV", "美国单一医疗系统", "凭证与培训", "免费研究用途", "PhysioNet/SQL", "去标识 EHR、ICU、急诊、用药、流程", "医疗资源、风险预测、临床运营", "需 DUA/培训；不得重识别；外部有效性有限", "https://physionet.org/content/mimiciv/", "P2"),
    data_source("D40", "劳动力职业", "O*NET", "美国", "开放", "免费", "API/下载", "职业技能、任务、知识、工作活动", "人力资本、自动化、技能匹配", "职业分类版本与跨国外推", "https://www.onetcenter.org/database.html", "P1"),
]


def formula(
    formula_id: str,
    category: str,
    name: str,
    latex: str,
    use_when: str,
    notation: str,
    assumptions: str,
    diagnostics: str,
    packages: str,
    warning: str,
) -> dict[str, Any]:
    return locals()


FORMULAS = [
    formula("STAT-01", "描述统计", "样本均值与方差", r"\bar{x}=\frac{1}{n}\sum_{i=1}^{n}x_i,\quad s^2=\frac{1}{n-1}\sum_{i=1}^{n}(x_i-\bar{x})^2", "概括中心与离散", "n样本数；x_i观测", "独立性仅影响推断，不影响定义", "缺失、极端值、分组口径", "numpy/pandas; R base", "偏态数据同时报告中位数/IQR"),
    formula("STAT-02", "回归", "OLS", r"y_i=\beta_0+x_i'\beta+\varepsilon_i,\quad \hat\beta=(X'X)^{-1}X'y", "连续结果的基准关系", "X设计矩阵；β系数", "线性可加；条件均值为零；满秩", "残差、异方差、共线性、聚类", "statsmodels; fixest", "统计显著不等于因果或管理显著"),
    formula("STAT-03", "广义线性", "Logit/Poisson", r"\Pr(y_i=1|x_i)=\Lambda(x_i'\beta);\quad E[y_i|x_i]=\exp(x_i'\beta)", "二元或计数结果", "Λ为logistic CDF", "链接函数与条件分布/均值正确", "校准、过度离散、边际效应", "statsmodels; glm", "系数需转成概率/发生率含义"),
    formula("STAT-04", "面板", "双向固定效应", r"y_{it}=\beta x_{it}+\alpha_i+\lambda_t+\varepsilon_{it}", "控制个体与共同时间冲击", "α_i个体效应；λ_t时间效应", "组内外生；有足够组内变化", "聚类误差、序列相关、趋势", "linearmodels; fixest", "它本身不是因果识别策略"),
    formula("STAT-05", "生存分析", "Cox 比例风险", r"h(t|x)=h_0(t)\exp(x'\beta)", "事件发生时间与删失", "h_0基准风险；expβ风险比", "比例风险；删失机制合理", "Schoenfeld残差、竞争风险", "lifelines; R survival", "风险比不是发生概率比"),
    formula("STAT-06", "测量模型", "SEM 测量与结构方程", r"x=\Lambda_x\xi+\delta,\quad y=\Lambda_y\eta+\epsilon,\quad \eta=B\eta+\Gamma\xi+\zeta", "潜变量与结构路径", "Λ载荷；ξ外生潜变量；η内生潜变量", "可识别、测量有效、样本适配", "CFI/TLI/RMSEA、CR/AVE、区分效度", "lavaan; Mplus", "拟合优不代表理论真"),
    formula("CAUS-01", "因果", "ATE/ATT", r"ATE=E[Y(1)-Y(0)],\quad ATT=E[Y(1)-Y(0)|D=1]", "定义平均处理效应目标量", "Y(d)潜在结果；D处理", "一致性、可识别条件取决于设计", "重叠、平衡、敏感性", "EconML/DoubleML", "先定义 estimand 再选估计器"),
    formula("CAUS-02", "因果", "双重差分", r"\hat\tau_{DID}=(\bar Y_{T,post}-\bar Y_{T,pre})-(\bar Y_{C,post}-\bar Y_{C,pre})", "处理/对照的政策冲击", "T/C组；pre/post时期", "平行趋势、无提前、无溢出", "预趋势与placebo", "did/fixest/csdid", "分期处理需现代异质处理估计器"),
    formula("CAUS-03", "因果", "事件研究", r"y_{it}=\alpha_i+\lambda_t+\sum_{k\ne-1}\beta_k1[t-G_i=k]+\varepsilon_{it}", "展示处理前后动态效应", "G_i首次处理期；k相对时间", "动态平行趋势；权重正确", "处理前系数、组群异质", "fixest; eventstudyinteract", "传统TWFE事件研究可能有污染"),
    formula("CAUS-04", "因果", "2SLS/IV", r"D_i=\pi Z_i+X_i'\gamma+u_i;\quad Y_i=\beta\hat D_i+X_i'\theta+\varepsilon_i", "处理内生且有有效工具", "Z工具；D内生处理", "相关、排除、独立、单调", "弱工具F、过识别、LATE", "linearmodels; ivreg2", "排除限制主要靠制度与机制论证"),
    formula("CAUS-05", "因果", "RDD 局部跳跃", r"\tau=\lim_{x\downarrow c}E[Y|X=x]-\lim_{x\uparrow c}E[Y|X=x]", "阈值决定处理", "X运行变量；c阈值", "阈值附近连续且不可精确操纵", "密度、协变量平衡、带宽", "rdrobust", "估计的是阈值附近局部效应"),
    formula("CAUS-06", "因果", "合成控制", r"\min_{w_j\ge0,\sum w_j=1}\|X_1-X_0w\|_V;\quad \hat\tau_t=Y_{1t}-\sum_jw_jY_{jt}", "单一处理单位构造反事实", "w供体权重；V预测变量权重", "供体未处理；前期拟合；无溢出", "RMSPE、置换、leave-one-out", "Synth/augsynth", "前期拟合差则后期差距不可解释"),
    formula("CAUS-07", "因果", "逆概率加权", r"\hat\tau=\frac1n\sum_i\left[\frac{D_iY_i}{\hat e(X_i)}-\frac{(1-D_i)Y_i}{1-\hat e(X_i)}\right]", "可观测混杂下加权平衡", "e(X)倾向得分", "条件可忽略、重叠、一致性", "极端权重、平衡、截尾", "causalml; WeightIt", "不能解决未观测混杂"),
    formula("CAUS-08", "因果ML", "DML 正交得分", r"\tilde Y=Y-\hat m(X),\;\tilde D=D-\hat g(X),\;\hat\theta=\frac{\sum\tilde D\tilde Y}{\sum\tilde D^2}", "高维控制下的处理效应", "m结果nuisance；g处理nuisance", "交叉拟合、正交性、重叠", "nuisance性能、敏感性、校准", "DoubleML/EconML", "预测强不自动意味着因果有效"),
    formula("CAUS-09", "机制", "线性中介分解", r"M=aD+X'\gamma+u,\quad Y=c'D+bM+X'\theta+\varepsilon,\quad indirect=ab", "探索处理通过中介的路径", "a,b路径系数", "顺序可忽略等强假设", "bootstrap CI、替代顺序、敏感性", "statsmodels; mediation", "横截面中介通常难以支持因果机制"),
    formula("EXP-01", "实验", "随机实验差均值", r"\hat\tau=\bar Y_1-\bar Y_0", "随机分配两组的ITT", "Y_1/Y_0为处理/对照观测均值", "随机化、SUTVA、流失可忽略/处理", "平衡、随机化推断、聚类设计", "statsmodels; DeclareDesign", "按随机化单元计算标准误"),
    formula("EXP-02", "实验", "两组均值近似样本量", r"n_{per\ group}\approx\frac{2(z_{1-\alpha/2}+z_{1-\beta})^2\sigma^2}{\Delta^2}", "规划检测最小效应", "Δ最小效应；σ标准差；1-β功效", "独立、近似正态；复杂设计需修正", "ICC、流失、多重检验", "statsmodels; G*Power", "不要用事后功效替代置信区间"),
    formula("META-01", "元分析", "随机效应元分析", r"\hat\mu=\frac{\sum_i w_i y_i}{\sum_i w_i},\quad w_i=\frac{1}{s_i^2+\tau^2}", "跨研究综合效应", "y_i效应；s_i标准误；τ²异质性", "效应可比；研究独立或已建模", "I²、τ²、漏斗图、影响诊断", "metafor", "高异质时总体均值可能掩盖机制"),
    formula("DSR-01", "设计科学", "效用增益/基线差", r"\Delta U=U(artifact)-U(baseline)", "评估人工制品相对基线的价值", "U可为正确率、时间、成本、采用等", "指标与设计目标一致；评估样本适当", "消融、多场景、用户与技术指标", "实验框架", "必须同时报告失败条件与设计边界"),
    formula("OPT-01", "优化", "线性规划", r"\min_x c'x\quad s.t.\quad Ax\le b,\;x\ge0", "连续资源配置", "x决策；c成本；A,b约束", "线性、参数已知", "可行性、对偶、敏感性", "Pyomo/CVXPY/HiGHS", "单位与方向错误比求解器错误更常见"),
    formula("OPT-02", "优化", "混合整数规划", r"\min_{x,y} c'x+f'y\quad s.t.\quad Ax+By\le b,\;x\ge0,\;y\in\{0,1\}^m", "开关、指派、选址与调度", "y二元决策", "线性且整数语义正确", "MIP gap、节点、松弛、big-M", "Gurobi/CPLEX/OR-Tools", "big-M 过大导致数值与松弛问题"),
    formula("OPT-03", "不确定优化", "两阶段随机规划", r"\min_x c'x+E_\xi[Q(x,\xi)],\quad Q=\min_y\{q(\xi)'y:W(\xi)y\ge h(\xi)-T(\xi)x\}", "先决策后观察不确定性", "x一阶段；y补救；ξ场景", "场景代表未来；可补救", "VSS、EVPI、样本外成本", "Pyomo/PySP", "场景生成与概率比求解更关键"),
    formula("OPT-04", "不确定优化", "鲁棒优化", r"\min_x\max_{\xi\in\mathcal U} f(x,\xi)\quad s.t.\quad g(x,\xi)\le0,\;\forall\xi\in\mathcal U", "最坏情形可控", "U不确定集合", "集合覆盖合理风险", "价格鲁棒性、样本外压力", "CVXPY/RSOME", "集合过大会过度保守"),
    formula("OPT-05", "不确定优化", "机会约束", r"\Pr_\xi(g(x,\xi)\le0)\ge1-\alpha", "允许小概率违约", "α风险容忍", "分布/样本近似可信", "样本外违约率、置信界", "CVXPY/Pyomo", "名义α不等于真实样本外违约率"),
    formula("OPT-06", "网络优化", "最小费用流", r"\min\sum_{(i,j)}c_{ij}x_{ij}\;s.t.\;\sum_jx_{ij}-\sum_jx_{ji}=b_i,\;0\le x_{ij}\le u_{ij}", "运输、分配与网络流", "b_i供需；u容量", "流守恒与网络定义正确", "可行、瓶颈、对偶价格", "OR-Tools/NetworkX", "节点口径和方向最易出错"),
    formula("OPT-07", "选址", "容量设施选址", r"\min\sum_j f_jy_j+\sum_{i,j}c_{ij}x_{ij}\;s.t.\;\sum_jx_{ij}=d_i,\;\sum_ix_{ij}\le K_jy_j", "仓库、站点、医院与充电设施", "y开站；x分配；K容量", "需求与成本空间化正确", "容量、覆盖、公平、敏感性", "Pyomo/Gurobi", "只最小化成本会忽略服务与公平"),
    formula("OPT-08", "路径", "容量车辆路径", r"\min\sum_{i,j}c_{ij}x_{ij}\quad s.t.\;\text{visit once, flow balance, capacity, subtour elimination}", "配送、取送与移动服务", "x_{ij}是否走边", "图、需求、车队与时间窗正确", "可行率、gap、运行时、业务KPI", "OR-Tools/PyVRP", "必须显式防子回路并验证路线可执行"),
    formula("OPT-09", "库存", "报童临界分位", r"F(q^*)=\frac{C_u}{C_u+C_o}", "单期不确定需求订货", "C_u缺货成本；C_o过量成本", "需求分布与边际成本稳定", "服务水平、分布误差、敏感性", "scipy", "成本口径决定分位点，需与业务核对"),
    formula("OPT-10", "库存", "(s,S)策略", r"q_t=\begin{cases}S-I_t,&I_t\le s\\0,&I_t>s\end{cases}", "有固定订货成本的补货", "I库存位置；s触发点；S目标", "状态可观测；需求/提前期模型可用", "缺货、服务、成本、漂移", "仿真/Pyomo", "策略参数需滚动更新与样本外验证"),
    formula("STO-01", "排队", "Little 定律", r"L=\lambda W", "稳态系统中人数、流率与时间关系", "L平均在制；λ吞吐；W平均时间", "稳定、流守恒、长期平均", "单位一致、边界一致", "SimPy/手算", "不能单独给出等待时间分布"),
    formula("STO-02", "排队", "M/M/1", r"\rho=\lambda/\mu<1,\quad W=\frac{1}{\mu-\lambda},\quad L=\frac{\lambda}{\mu-\lambda}", "指数到达服务的单服务台基准", "λ到达率；μ服务率", "Poisson到达、指数服务、FCFS、稳态", "分布拟合、ρ、尾部等待", "queueing-tool/SimPy", "真实服务时间重尾时会严重低估等待"),
    formula("STO-03", "随机过程", "马尔可夫链稳态", r"\pi=\pi P,\quad \sum_i\pi_i=1", "长期状态占比与转移", "P转移矩阵；π稳态", "齐次、不可约/遍历等", "转移稳定、状态定义、收敛", "numpy/scipy", "状态聚合不当会破坏马尔可夫性"),
    formula("STO-04", "动态决策", "Bellman 最优方程", r"V^*(s)=\max_a\{r(s,a)+\gamma E[V^*(s')|s,a]\}", "MDP的最优价值与策略", "s状态；a动作；γ折扣", "近似马尔可夫；模型/数据覆盖", "Bellman误差、策略价值、覆盖", "MDPtoolbox/RLlib", "奖励必须对应真实管理目标"),
    formula("GAME-01", "博弈", "Nash 均衡", r"u_i(a_i^*,a_{-i}^*)\ge u_i(a_i,a_{-i}^*),\;\forall i,a_i", "同时战略互动", "u_i效用；a_i行动", "参与者与信息结构明确", "存在、唯一、多均衡选择", "SymPy/Mathematica", "均衡是模型内结论，不自动是行为预测"),
    formula("GAME-02", "博弈", "Stackelberg 领导者问题", r"\max_{a_L}u_L(a_L,a_F^*(a_L)),\quad a_F^*(a_L)\in\arg\max_{a_F}u_F(a_L,a_F)", "先行者与跟随者", "L领导者；F跟随者", "时序与承诺可信", "反应函数、边界解、多均衡", "bilevel/Pyomo", "错误时序会改变全部结论"),
    formula("GAME-03", "契约", "参与约束与激励相容", r"EU_A(a^*,w)\ge\bar U,\quad a^*\in\arg\max_a EU_A(a,w)", "设计工资、分成、平台或供应链契约", "A代理人；w契约；U保留效用", "信息结构与可执行契约明确", "IR/IC、福利、风险分担", "符号/数值优化", "不要忽略有限责任与执行成本"),
    formula("DEMAND-01", "选择", "多项Logit", r"P_{ij}=\frac{\exp(V_{ij})}{\sum_{k\in C_i}\exp(V_{ik})}", "多选一的偏好与需求", "V系统效用；C选择集", "IID极值误差导致IIA", "IIA、选择集、弹性、价格内生", "Biogeme/pylogit", "替代关系过强时用nested/mixed logit"),
    formula("TIME-01", "时序", "ARIMA", r"\phi(B)(1-B)^d y_t=c+\theta(B)\varepsilon_t", "单变量时序预测", "B滞后算子；d差分阶数", "差分后平稳；残差白噪声", "ADF/KPSS、ACF、滚动回测", "statsmodels/fable", "不得随机切分训练测试"),
    formula("TIME-02", "时序", "VAR", r"y_t=c+A_1y_{t-1}+\cdots+A_py_{t-p}+\varepsilon_t", "多变量动态、冲击与预测", "A_l滞后系数矩阵", "平稳或协整处理；滞后充分", "稳定性、残差、IRF识别", "statsmodels/vars", "IRF的因果解释依赖识别假设"),
    formula("ML-01", "机器学习", "经验风险最小化", r"\hat f=\arg\min_{f\in\mathcal F}\frac1n\sum_i\ell(y_i,f(x_i))+\lambda\Omega(f)", "监督学习通用目标", "ℓ损失；Ω正则；λ强度", "训练与部署分布可比", "CV、学习曲线、校准、漂移", "scikit-learn/PyTorch", "测试集只用于最终一次评估"),
    formula("ML-02", "机器学习", "交叉熵", r"\mathcal L=-\sum_i\sum_k y_{ik}\log p_{ik}", "多分类概率学习", "y one-hot；p预测概率", "标签和样本权重合理", "校准、类不平衡、ECE", "PyTorch/sklearn", "高准确率可能掩盖概率失准"),
    formula("ML-03", "深度学习", "LSTM 状态更新", r"f_t=\sigma(W_f[x_t,h_{t-1}]+b_f),\;c_t=f_t\odot c_{t-1}+i_t\odot\tilde c_t", "序列与长依赖", "f遗忘门；c记忆；h隐状态", "序列切分无泄漏；数据量足够", "基线、消融、滚动回测", "PyTorch/Keras", "先与简单时序和树模型比较"),
    formula("ML-04", "深度学习", "缩放点积注意力", r"Attention(Q,K,V)=softmax(QK'/\sqrt{d_k})V", "文本、多变量时序与关系表示", "Q查询；K键；V值", "位置/掩码和切分正确", "消融、归因稳定、长度外推", "transformers/PyTorch", "注意力权重不等同因果解释"),
    formula("ML-05", "强化学习", "Q-learning", r"Q(s,a)\leftarrow Q(s,a)+\alpha[r+\gamma\max_{a'}Q(s',a')-Q(s,a)]", "未知转移下学习控制策略", "α学习率；γ折扣", "探索覆盖；近似马尔可夫", "离线价值、覆盖、收敛", "Gymnasium/SB3", "离线数据分布外动作会造成过估计"),
    formula("NET-01", "网络", "PageRank/特征向量中心性", r"r=\alpha P'r+(1-\alpha)v", "识别网络中的结构性重要节点", "P转移；v跳转；α阻尼", "边方向/权重定义合理", "替代边、随机网络、稳定性", "NetworkX/igraph", "中心性是结构指标，不是因果影响"),
    formula("BAYES-01", "贝叶斯", "Bayes 后验", r"p(\theta|y)=\frac{p(y|\theta)p(\theta)}{p(y)}\propto p(y|\theta)p(\theta)", "合并先验与数据并量化不确定性", "θ参数；y数据", "生成模型与先验可辩护", "R-hat、ESS、PPC、先验敏感", "PyMC/Stan", "后验可信度不修复错误的似然或数据"),
    formula("EFF-01", "效率分析", "DEA 输入导向CCR", r"\min_{\theta,\lambda}\theta\;s.t.\;Y\lambda\ge y_o,\;X\lambda\le\theta x_o,\;\lambda\ge0", "多投入多产出相对效率", "DMU o；θ效率；λ参照组合", "同质DMU；投入产出口径可比；CRS", "规模报酬、异常点、权重敏感", "pyDEA/R Benchmarking", "相对前沿受样本和异常点强影响"),
]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown() -> None:
    method_lines = [
        "# 管科研究方法库",
        "",
        "> 每张卡片都必须与研究问题、数据生成过程和识别/求解目标匹配；工具不替代研究设计。",
        "",
    ]
    for row in METHODS:
        method_lines.extend(
            [
                f"## {row['method_id']} {row['name']}",
                "",
                f"- 方法族/分支：{row['family']} / {row['lane']}",
                f"- 目标：{row['goal']}",
                f"- 数据：{row['data']}",
                f"- 核心假设：{row['assumptions']}",
                f"- 工作流：{row['workflow']}",
                f"- 诊断：{row['diagnostics']}",
                f"- 稳健性：{row['robustness']}",
                f"- 推荐工具：{row['packages']}",
                f"- 公式卡：{row['formula_ids'] or '无单一核心公式'}",
                f"- 常见失败：{row['failure']}",
                "",
            ]
        )
    (OUT / "methods_library.md").write_text("\n".join(method_lines), encoding="utf-8")

    data_lines = [
        "# 管科常用数据源库",
        "",
        "> 接入前必须复核最新许可、访问方式、隐私要求和机构授权。P0/P1/P2 是产品连接器优先级，不是数据质量排名。",
        "",
        "|ID|领域|数据源|地域|访问/成本|典型数据|常见用途|合规要点|优先级|",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in DATA_SOURCES:
        data_lines.append(
            f"|{row['source_id']}|{row['domain']}|[{row['name']}]({row['url']})|{row['geography']}|{row['access']}；{row['cost']}|{row['typical_data']}|{row['common_use']}|{row['compliance']}|{row['connector_priority']}|"
        )
    (OUT / "data_sources_library.md").write_text("\n".join(data_lines) + "\n", encoding="utf-8")

    formula_lines = [
        "# 管科常用模型与公式库",
        "",
        "> 公式卡用于选型、解释与生成代码骨架；不能脱离假设、诊断和数据口径单独调用。",
        "",
    ]
    for row in FORMULAS:
        formula_lines.extend(
            [
                f"## {row['formula_id']} {row['name']}",
                "",
                f"类别：{row['category']}  ",
                f"公式：$${row['latex']}$$",
                f"使用场景：{row['use_when']}  ",
                f"符号：{row['notation']}  ",
                f"假设：{row['assumptions']}  ",
                f"诊断：{row['diagnostics']}  ",
                f"工具：{row['packages']}  ",
                f"警告：{row['warning']}",
                "",
            ]
        )
    (OUT / "formula_library.md").write_text("\n".join(formula_lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    payloads = [
        ("methods_library", METHODS),
        ("data_sources_library", DATA_SOURCES),
        ("formula_library", FORMULAS),
    ]
    for name, rows in payloads:
        (OUT / f"{name}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        write_csv(OUT / f"{name}.csv", rows)
    write_markdown()
    print(
        json.dumps(
            {
                "methods": len(METHODS),
                "data_sources": len(DATA_SOURCES),
                "formulas": len(FORMULAS),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
