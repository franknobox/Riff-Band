# 管科常用模型与公式库

> 公式卡用于选型、解释与生成代码骨架；不能脱离假设、诊断和数据口径单独调用。

## STAT-01 样本均值与方差

类别：描述统计  
公式：$$\bar{x}=\frac{1}{n}\sum_{i=1}^{n}x_i,\quad s^2=\frac{1}{n-1}\sum_{i=1}^{n}(x_i-\bar{x})^2$$
使用场景：概括中心与离散  
符号：n样本数；x_i观测  
假设：独立性仅影响推断，不影响定义  
诊断：缺失、极端值、分组口径  
工具：numpy/pandas; R base  
警告：偏态数据同时报告中位数/IQR

## STAT-02 OLS

类别：回归  
公式：$$y_i=\beta_0+x_i'\beta+\varepsilon_i,\quad \hat\beta=(X'X)^{-1}X'y$$
使用场景：连续结果的基准关系  
符号：X设计矩阵；β系数  
假设：线性可加；条件均值为零；满秩  
诊断：残差、异方差、共线性、聚类  
工具：statsmodels; fixest  
警告：统计显著不等于因果或管理显著

## STAT-03 Logit/Poisson

类别：广义线性  
公式：$$\Pr(y_i=1|x_i)=\Lambda(x_i'\beta);\quad E[y_i|x_i]=\exp(x_i'\beta)$$
使用场景：二元或计数结果  
符号：Λ为logistic CDF  
假设：链接函数与条件分布/均值正确  
诊断：校准、过度离散、边际效应  
工具：statsmodels; glm  
警告：系数需转成概率/发生率含义

## STAT-04 双向固定效应

类别：面板  
公式：$$y_{it}=\beta x_{it}+\alpha_i+\lambda_t+\varepsilon_{it}$$
使用场景：控制个体与共同时间冲击  
符号：α_i个体效应；λ_t时间效应  
假设：组内外生；有足够组内变化  
诊断：聚类误差、序列相关、趋势  
工具：linearmodels; fixest  
警告：它本身不是因果识别策略

## STAT-05 Cox 比例风险

类别：生存分析  
公式：$$h(t|x)=h_0(t)\exp(x'\beta)$$
使用场景：事件发生时间与删失  
符号：h_0基准风险；expβ风险比  
假设：比例风险；删失机制合理  
诊断：Schoenfeld残差、竞争风险  
工具：lifelines; R survival  
警告：风险比不是发生概率比

## STAT-06 SEM 测量与结构方程

类别：测量模型  
公式：$$x=\Lambda_x\xi+\delta,\quad y=\Lambda_y\eta+\epsilon,\quad \eta=B\eta+\Gamma\xi+\zeta$$
使用场景：潜变量与结构路径  
符号：Λ载荷；ξ外生潜变量；η内生潜变量  
假设：可识别、测量有效、样本适配  
诊断：CFI/TLI/RMSEA、CR/AVE、区分效度  
工具：lavaan; Mplus  
警告：拟合优不代表理论真

## CAUS-01 ATE/ATT

类别：因果  
公式：$$ATE=E[Y(1)-Y(0)],\quad ATT=E[Y(1)-Y(0)|D=1]$$
使用场景：定义平均处理效应目标量  
符号：Y(d)潜在结果；D处理  
假设：一致性、可识别条件取决于设计  
诊断：重叠、平衡、敏感性  
工具：EconML/DoubleML  
警告：先定义 estimand 再选估计器

## CAUS-02 双重差分

类别：因果  
公式：$$\hat\tau_{DID}=(\bar Y_{T,post}-\bar Y_{T,pre})-(\bar Y_{C,post}-\bar Y_{C,pre})$$
使用场景：处理/对照的政策冲击  
符号：T/C组；pre/post时期  
假设：平行趋势、无提前、无溢出  
诊断：预趋势与placebo  
工具：did/fixest/csdid  
警告：分期处理需现代异质处理估计器

## CAUS-03 事件研究

类别：因果  
公式：$$y_{it}=\alpha_i+\lambda_t+\sum_{k\ne-1}\beta_k1[t-G_i=k]+\varepsilon_{it}$$
使用场景：展示处理前后动态效应  
符号：G_i首次处理期；k相对时间  
假设：动态平行趋势；权重正确  
诊断：处理前系数、组群异质  
工具：fixest; eventstudyinteract  
警告：传统TWFE事件研究可能有污染

## CAUS-04 2SLS/IV

类别：因果  
公式：$$D_i=\pi Z_i+X_i'\gamma+u_i;\quad Y_i=\beta\hat D_i+X_i'\theta+\varepsilon_i$$
使用场景：处理内生且有有效工具  
符号：Z工具；D内生处理  
假设：相关、排除、独立、单调  
诊断：弱工具F、过识别、LATE  
工具：linearmodels; ivreg2  
警告：排除限制主要靠制度与机制论证

## CAUS-05 RDD 局部跳跃

类别：因果  
公式：$$\tau=\lim_{x\downarrow c}E[Y|X=x]-\lim_{x\uparrow c}E[Y|X=x]$$
使用场景：阈值决定处理  
符号：X运行变量；c阈值  
假设：阈值附近连续且不可精确操纵  
诊断：密度、协变量平衡、带宽  
工具：rdrobust  
警告：估计的是阈值附近局部效应

## CAUS-06 合成控制

类别：因果  
公式：$$\min_{w_j\ge0,\sum w_j=1}\|X_1-X_0w\|_V;\quad \hat\tau_t=Y_{1t}-\sum_jw_jY_{jt}$$
使用场景：单一处理单位构造反事实  
符号：w供体权重；V预测变量权重  
假设：供体未处理；前期拟合；无溢出  
诊断：RMSPE、置换、leave-one-out  
工具：Synth/augsynth  
警告：前期拟合差则后期差距不可解释

## CAUS-07 逆概率加权

类别：因果  
公式：$$\hat\tau=\frac1n\sum_i\left[\frac{D_iY_i}{\hat e(X_i)}-\frac{(1-D_i)Y_i}{1-\hat e(X_i)}\right]$$
使用场景：可观测混杂下加权平衡  
符号：e(X)倾向得分  
假设：条件可忽略、重叠、一致性  
诊断：极端权重、平衡、截尾  
工具：causalml; WeightIt  
警告：不能解决未观测混杂

## CAUS-08 DML 正交得分

类别：因果ML  
公式：$$\tilde Y=Y-\hat m(X),\;\tilde D=D-\hat g(X),\;\hat\theta=\frac{\sum\tilde D\tilde Y}{\sum\tilde D^2}$$
使用场景：高维控制下的处理效应  
符号：m结果nuisance；g处理nuisance  
假设：交叉拟合、正交性、重叠  
诊断：nuisance性能、敏感性、校准  
工具：DoubleML/EconML  
警告：预测强不自动意味着因果有效

## CAUS-09 线性中介分解

类别：机制  
公式：$$M=aD+X'\gamma+u,\quad Y=c'D+bM+X'\theta+\varepsilon,\quad indirect=ab$$
使用场景：探索处理通过中介的路径  
符号：a,b路径系数  
假设：顺序可忽略等强假设  
诊断：bootstrap CI、替代顺序、敏感性  
工具：statsmodels; mediation  
警告：横截面中介通常难以支持因果机制

## EXP-01 随机实验差均值

类别：实验  
公式：$$\hat\tau=\bar Y_1-\bar Y_0$$
使用场景：随机分配两组的ITT  
符号：Y_1/Y_0为处理/对照观测均值  
假设：随机化、SUTVA、流失可忽略/处理  
诊断：平衡、随机化推断、聚类设计  
工具：statsmodels; DeclareDesign  
警告：按随机化单元计算标准误

## EXP-02 两组均值近似样本量

类别：实验  
公式：$$n_{per\ group}\approx\frac{2(z_{1-\alpha/2}+z_{1-\beta})^2\sigma^2}{\Delta^2}$$
使用场景：规划检测最小效应  
符号：Δ最小效应；σ标准差；1-β功效  
假设：独立、近似正态；复杂设计需修正  
诊断：ICC、流失、多重检验  
工具：statsmodels; G*Power  
警告：不要用事后功效替代置信区间

## META-01 随机效应元分析

类别：元分析  
公式：$$\hat\mu=\frac{\sum_i w_i y_i}{\sum_i w_i},\quad w_i=\frac{1}{s_i^2+\tau^2}$$
使用场景：跨研究综合效应  
符号：y_i效应；s_i标准误；τ²异质性  
假设：效应可比；研究独立或已建模  
诊断：I²、τ²、漏斗图、影响诊断  
工具：metafor  
警告：高异质时总体均值可能掩盖机制

## DSR-01 效用增益/基线差

类别：设计科学  
公式：$$\Delta U=U(artifact)-U(baseline)$$
使用场景：评估人工制品相对基线的价值  
符号：U可为正确率、时间、成本、采用等  
假设：指标与设计目标一致；评估样本适当  
诊断：消融、多场景、用户与技术指标  
工具：实验框架  
警告：必须同时报告失败条件与设计边界

## OPT-01 线性规划

类别：优化  
公式：$$\min_x c'x\quad s.t.\quad Ax\le b,\;x\ge0$$
使用场景：连续资源配置  
符号：x决策；c成本；A,b约束  
假设：线性、参数已知  
诊断：可行性、对偶、敏感性  
工具：Pyomo/CVXPY/HiGHS  
警告：单位与方向错误比求解器错误更常见

## OPT-02 混合整数规划

类别：优化  
公式：$$\min_{x,y} c'x+f'y\quad s.t.\quad Ax+By\le b,\;x\ge0,\;y\in\{0,1\}^m$$
使用场景：开关、指派、选址与调度  
符号：y二元决策  
假设：线性且整数语义正确  
诊断：MIP gap、节点、松弛、big-M  
工具：Gurobi/CPLEX/OR-Tools  
警告：big-M 过大导致数值与松弛问题

## OPT-03 两阶段随机规划

类别：不确定优化  
公式：$$\min_x c'x+E_\xi[Q(x,\xi)],\quad Q=\min_y\{q(\xi)'y:W(\xi)y\ge h(\xi)-T(\xi)x\}$$
使用场景：先决策后观察不确定性  
符号：x一阶段；y补救；ξ场景  
假设：场景代表未来；可补救  
诊断：VSS、EVPI、样本外成本  
工具：Pyomo/PySP  
警告：场景生成与概率比求解更关键

## OPT-04 鲁棒优化

类别：不确定优化  
公式：$$\min_x\max_{\xi\in\mathcal U} f(x,\xi)\quad s.t.\quad g(x,\xi)\le0,\;\forall\xi\in\mathcal U$$
使用场景：最坏情形可控  
符号：U不确定集合  
假设：集合覆盖合理风险  
诊断：价格鲁棒性、样本外压力  
工具：CVXPY/RSOME  
警告：集合过大会过度保守

## OPT-05 机会约束

类别：不确定优化  
公式：$$\Pr_\xi(g(x,\xi)\le0)\ge1-\alpha$$
使用场景：允许小概率违约  
符号：α风险容忍  
假设：分布/样本近似可信  
诊断：样本外违约率、置信界  
工具：CVXPY/Pyomo  
警告：名义α不等于真实样本外违约率

## OPT-06 最小费用流

类别：网络优化  
公式：$$\min\sum_{(i,j)}c_{ij}x_{ij}\;s.t.\;\sum_jx_{ij}-\sum_jx_{ji}=b_i,\;0\le x_{ij}\le u_{ij}$$
使用场景：运输、分配与网络流  
符号：b_i供需；u容量  
假设：流守恒与网络定义正确  
诊断：可行、瓶颈、对偶价格  
工具：OR-Tools/NetworkX  
警告：节点口径和方向最易出错

## OPT-07 容量设施选址

类别：选址  
公式：$$\min\sum_j f_jy_j+\sum_{i,j}c_{ij}x_{ij}\;s.t.\;\sum_jx_{ij}=d_i,\;\sum_ix_{ij}\le K_jy_j$$
使用场景：仓库、站点、医院与充电设施  
符号：y开站；x分配；K容量  
假设：需求与成本空间化正确  
诊断：容量、覆盖、公平、敏感性  
工具：Pyomo/Gurobi  
警告：只最小化成本会忽略服务与公平

## OPT-08 容量车辆路径

类别：路径  
公式：$$\min\sum_{i,j}c_{ij}x_{ij}\quad s.t.\;\text{visit once, flow balance, capacity, subtour elimination}$$
使用场景：配送、取送与移动服务  
符号：x_{ij}是否走边  
假设：图、需求、车队与时间窗正确  
诊断：可行率、gap、运行时、业务KPI  
工具：OR-Tools/PyVRP  
警告：必须显式防子回路并验证路线可执行

## OPT-09 报童临界分位

类别：库存  
公式：$$F(q^*)=\frac{C_u}{C_u+C_o}$$
使用场景：单期不确定需求订货  
符号：C_u缺货成本；C_o过量成本  
假设：需求分布与边际成本稳定  
诊断：服务水平、分布误差、敏感性  
工具：scipy  
警告：成本口径决定分位点，需与业务核对

## OPT-10 (s,S)策略

类别：库存  
公式：$$q_t=\begin{cases}S-I_t,&I_t\le s\\0,&I_t>s\end{cases}$$
使用场景：有固定订货成本的补货  
符号：I库存位置；s触发点；S目标  
假设：状态可观测；需求/提前期模型可用  
诊断：缺货、服务、成本、漂移  
工具：仿真/Pyomo  
警告：策略参数需滚动更新与样本外验证

## STO-01 Little 定律

类别：排队  
公式：$$L=\lambda W$$
使用场景：稳态系统中人数、流率与时间关系  
符号：L平均在制；λ吞吐；W平均时间  
假设：稳定、流守恒、长期平均  
诊断：单位一致、边界一致  
工具：SimPy/手算  
警告：不能单独给出等待时间分布

## STO-02 M/M/1

类别：排队  
公式：$$\rho=\lambda/\mu<1,\quad W=\frac{1}{\mu-\lambda},\quad L=\frac{\lambda}{\mu-\lambda}$$
使用场景：指数到达服务的单服务台基准  
符号：λ到达率；μ服务率  
假设：Poisson到达、指数服务、FCFS、稳态  
诊断：分布拟合、ρ、尾部等待  
工具：queueing-tool/SimPy  
警告：真实服务时间重尾时会严重低估等待

## STO-03 马尔可夫链稳态

类别：随机过程  
公式：$$\pi=\pi P,\quad \sum_i\pi_i=1$$
使用场景：长期状态占比与转移  
符号：P转移矩阵；π稳态  
假设：齐次、不可约/遍历等  
诊断：转移稳定、状态定义、收敛  
工具：numpy/scipy  
警告：状态聚合不当会破坏马尔可夫性

## STO-04 Bellman 最优方程

类别：动态决策  
公式：$$V^*(s)=\max_a\{r(s,a)+\gamma E[V^*(s')|s,a]\}$$
使用场景：MDP的最优价值与策略  
符号：s状态；a动作；γ折扣  
假设：近似马尔可夫；模型/数据覆盖  
诊断：Bellman误差、策略价值、覆盖  
工具：MDPtoolbox/RLlib  
警告：奖励必须对应真实管理目标

## GAME-01 Nash 均衡

类别：博弈  
公式：$$u_i(a_i^*,a_{-i}^*)\ge u_i(a_i,a_{-i}^*),\;\forall i,a_i$$
使用场景：同时战略互动  
符号：u_i效用；a_i行动  
假设：参与者与信息结构明确  
诊断：存在、唯一、多均衡选择  
工具：SymPy/Mathematica  
警告：均衡是模型内结论，不自动是行为预测

## GAME-02 Stackelberg 领导者问题

类别：博弈  
公式：$$\max_{a_L}u_L(a_L,a_F^*(a_L)),\quad a_F^*(a_L)\in\arg\max_{a_F}u_F(a_L,a_F)$$
使用场景：先行者与跟随者  
符号：L领导者；F跟随者  
假设：时序与承诺可信  
诊断：反应函数、边界解、多均衡  
工具：bilevel/Pyomo  
警告：错误时序会改变全部结论

## GAME-03 参与约束与激励相容

类别：契约  
公式：$$EU_A(a^*,w)\ge\bar U,\quad a^*\in\arg\max_a EU_A(a,w)$$
使用场景：设计工资、分成、平台或供应链契约  
符号：A代理人；w契约；U保留效用  
假设：信息结构与可执行契约明确  
诊断：IR/IC、福利、风险分担  
工具：符号/数值优化  
警告：不要忽略有限责任与执行成本

## DEMAND-01 多项Logit

类别：选择  
公式：$$P_{ij}=\frac{\exp(V_{ij})}{\sum_{k\in C_i}\exp(V_{ik})}$$
使用场景：多选一的偏好与需求  
符号：V系统效用；C选择集  
假设：IID极值误差导致IIA  
诊断：IIA、选择集、弹性、价格内生  
工具：Biogeme/pylogit  
警告：替代关系过强时用nested/mixed logit

## TIME-01 ARIMA

类别：时序  
公式：$$\phi(B)(1-B)^d y_t=c+\theta(B)\varepsilon_t$$
使用场景：单变量时序预测  
符号：B滞后算子；d差分阶数  
假设：差分后平稳；残差白噪声  
诊断：ADF/KPSS、ACF、滚动回测  
工具：statsmodels/fable  
警告：不得随机切分训练测试

## TIME-02 VAR

类别：时序  
公式：$$y_t=c+A_1y_{t-1}+\cdots+A_py_{t-p}+\varepsilon_t$$
使用场景：多变量动态、冲击与预测  
符号：A_l滞后系数矩阵  
假设：平稳或协整处理；滞后充分  
诊断：稳定性、残差、IRF识别  
工具：statsmodels/vars  
警告：IRF的因果解释依赖识别假设

## ML-01 经验风险最小化

类别：机器学习  
公式：$$\hat f=\arg\min_{f\in\mathcal F}\frac1n\sum_i\ell(y_i,f(x_i))+\lambda\Omega(f)$$
使用场景：监督学习通用目标  
符号：ℓ损失；Ω正则；λ强度  
假设：训练与部署分布可比  
诊断：CV、学习曲线、校准、漂移  
工具：scikit-learn/PyTorch  
警告：测试集只用于最终一次评估

## ML-02 交叉熵

类别：机器学习  
公式：$$\mathcal L=-\sum_i\sum_k y_{ik}\log p_{ik}$$
使用场景：多分类概率学习  
符号：y one-hot；p预测概率  
假设：标签和样本权重合理  
诊断：校准、类不平衡、ECE  
工具：PyTorch/sklearn  
警告：高准确率可能掩盖概率失准

## ML-03 LSTM 状态更新

类别：深度学习  
公式：$$f_t=\sigma(W_f[x_t,h_{t-1}]+b_f),\;c_t=f_t\odot c_{t-1}+i_t\odot\tilde c_t$$
使用场景：序列与长依赖  
符号：f遗忘门；c记忆；h隐状态  
假设：序列切分无泄漏；数据量足够  
诊断：基线、消融、滚动回测  
工具：PyTorch/Keras  
警告：先与简单时序和树模型比较

## ML-04 缩放点积注意力

类别：深度学习  
公式：$$Attention(Q,K,V)=softmax(QK'/\sqrt{d_k})V$$
使用场景：文本、多变量时序与关系表示  
符号：Q查询；K键；V值  
假设：位置/掩码和切分正确  
诊断：消融、归因稳定、长度外推  
工具：transformers/PyTorch  
警告：注意力权重不等同因果解释

## ML-05 Q-learning

类别：强化学习  
公式：$$Q(s,a)\leftarrow Q(s,a)+\alpha[r+\gamma\max_{a'}Q(s',a')-Q(s,a)]$$
使用场景：未知转移下学习控制策略  
符号：α学习率；γ折扣  
假设：探索覆盖；近似马尔可夫  
诊断：离线价值、覆盖、收敛  
工具：Gymnasium/SB3  
警告：离线数据分布外动作会造成过估计

## NET-01 PageRank/特征向量中心性

类别：网络  
公式：$$r=\alpha P'r+(1-\alpha)v$$
使用场景：识别网络中的结构性重要节点  
符号：P转移；v跳转；α阻尼  
假设：边方向/权重定义合理  
诊断：替代边、随机网络、稳定性  
工具：NetworkX/igraph  
警告：中心性是结构指标，不是因果影响

## BAYES-01 Bayes 后验

类别：贝叶斯  
公式：$$p(\theta|y)=\frac{p(y|\theta)p(\theta)}{p(y)}\propto p(y|\theta)p(\theta)$$
使用场景：合并先验与数据并量化不确定性  
符号：θ参数；y数据  
假设：生成模型与先验可辩护  
诊断：R-hat、ESS、PPC、先验敏感  
工具：PyMC/Stan  
警告：后验可信度不修复错误的似然或数据

## EFF-01 DEA 输入导向CCR

类别：效率分析  
公式：$$\min_{\theta,\lambda}\theta\;s.t.\;Y\lambda\ge y_o,\;X\lambda\le\theta x_o,\;\lambda\ge0$$
使用场景：多投入多产出相对效率  
符号：DMU o；θ效率；λ参照组合  
假设：同质DMU；投入产出口径可比；CRS  
诊断：规模报酬、异常点、权重敏感  
工具：pyDEA/R Benchmarking  
警告：相对前沿受样本和异常点强影响
