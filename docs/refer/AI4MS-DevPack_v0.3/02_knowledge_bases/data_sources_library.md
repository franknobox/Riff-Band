# 管科常用数据源库

> 接入前必须复核最新许可、访问方式、隐私要求和机构授权。P0/P1/P2 是产品连接器优先级，不是数据质量排名。

|ID|领域|数据源|地域|访问/成本|典型数据|常见用途|合规要点|优先级|
|---|---|---|---|---|---|---|---|---|
|D01|文献元数据|[OpenAlex](https://openalex.org/)|全球|开放 API/快照；免费；高级功能可能需 key|论文、作者、机构、期刊、主题、引用|检索、引文网络、热点与作者机构分析|记录检索日期；引用量是动态指标|P0|
|D02|文献元数据|[Crossref](https://www.crossref.org/)|全球|开放 API；免费|DOI、题名、作者、期刊、参考文献元数据|DOI 核验、BibTeX、出版元数据补全|遵守 polite pool；字段完整性依出版商|P0|
|D03|文献元数据|[Semantic Scholar](https://www.semanticscholar.org/product/api)|全球|API；有速率限制；免费/申请 key|论文、摘要、引用、嵌入、推荐|语义检索、引用补全、相似论文|记录语料覆盖与计数差异|P0|
|D04|文献全文|[arXiv](https://arxiv.org/)|全球|开放 API/OAI；免费|预印本元数据与 PDF|新兴主题、方法论文、版本追踪|预印本不等同同行评审版本|P0|
|D05|开放获取|[Unpaywall](https://unpaywall.org/products/api)|全球|API/快照；免费；需邮箱|DOI 对应 OA 状态与合法全文位置|合法全文发现与 OA 覆盖|只使用合法位置；遵守全文许可|P1|
|D06|宏观经济|[World Bank Data](https://data.worldbank.org/)|全球|开放；免费|发展、贸易、人口、营商、治理指标|国家/地区面板、政策与发展研究|核对指标定义、修订与可比性|P0|
|D07|宏观经济|[IMF Data](https://www.imf.org/en/Data)|全球|开放/注册；多数免费|金融、国际收支、财政、汇率|宏观金融、国家风险、政策研究|系列口径和修订频繁|P1|
|D08|宏观经济|[OECD Data Explorer](https://data-explorer.oecd.org/)|OECD及伙伴|开放；免费|产业、生产率、创新、教育、TiVA|跨国制度与产业比较|版本、季调与国家可比性|P1|
|D09|贸易供应链|[UN Comtrade](https://comtradeplus.un.org/)|全球|开放/订阅层；免费额度 + 付费|双边商品贸易、HS 编码、数量与价值|贸易网络、供应链冲击、产业依赖|HS 版本、镜像差异、再出口与缺失|P1|
|D10|宏观金融|[FRED](https://fred.stlouisfed.org/)|美国/全球系列|开放 API；免费；API key|利率、通胀、就业、金融与宏观时序|事件研究控制、预测、宏观背景|系列来源不同；记录 vintage|P0|
|D11|美国企业与披露|[SEC EDGAR](https://www.sec.gov/edgar/sec-api-documentation)|美国|开放；免费|10-K/10-Q/8-K/XBRL、公司事实|公司披露、文本、财务与事件|必须遵守 SEC fair-access 速率和 UA|P0|
|D12|美国劳动力|[BLS Public Data](https://www.bls.gov/developers/)|美国|开放 API；免费|就业、工资、价格、生产率|劳动力与产业面板、宏观控制|系列代码、季调与修订|P1|
|D13|美国人口企业|[U.S. Census / ACS](https://www.census.gov/data/developers.html)|美国|开放 API；免费；key 推荐|人口、住房、企业动态、贸易|地区面板、市场规模、政策评估|地理边界、抽样误差与 disclosure rules|P1|
|D14|中国宏观|[国家统计局国家数据](https://data.stats.gov.cn/)|中国|公开查询；免费|国民经济、人口、工业、地区指标|省市面板、产业与政策背景|接口稳定性与口径变更需人工核验|P1|
|D15|中国金融企业|[CSMAR 国泰安](https://www.gtarsc.com/)|中国|机构订阅；付费|上市公司、证券、治理、分析师、事件|公司金融、会计、治理与市场研究|严格遵守机构许可，不可公开再分发|P1|
|D16|中国金融企业|[CNRDS](https://www.cnrds.com/)|中国|机构订阅；付费|上市公司、治理、专利、供应链、文本|公司与创新、供应链、ESG研究|许可与变量定义需逐库核对|P1|
|D17|中国金融宏观|[Wind](https://www.wind.com.cn/)|中国/全球|终端/机构授权；付费|证券、公司、基金、宏观、行业|金融与企业面板、事件研究|不得把授权数据上传外部模型或再分发|P2|
|D18|中国调查|[CFPS 中国家庭追踪调查](https://www.isss.pku.edu.cn/cfps/)|中国|注册申请；研究用途免费|个人、家庭、教育、就业、收入、健康|家庭行为、劳动力与社会政策|伦理审批、去标识、引用与申请条款|P1|
|D19|中国调查|[CGSS 中国综合社会调查](http://cgss.ruc.edu.cn/)|中国|注册申请；研究用途免费|社会态度、行为、职业、家庭|组织行为、制度信任、消费与社会研究|权重、抽样设计与使用协议|P2|
|D20|中国调查|[CHARLS](https://charls.charlsdata.com/)|中国|注册申请；研究用途免费|中老年健康、家庭、劳动、养老|医疗服务运营、劳动与老龄化|伦理与敏感变量保护|P2|
|D21|金融研究|[WRDS](https://wrds-www.wharton.upenn.edu/)|全球/美国为主|机构订阅；付费|CRSP、Compustat、IBES、TAQ等统一入口|资产定价、公司金融、市场微观结构|子库许可独立；不得再分发|P1|
|D22|企业数据库|[Orbis](https://www.bvdinfo.com/en-gb/our-products/data/international/orbis)|全球|机构订阅；付费|私营与上市企业、所有权、财务、关联关系|企业网络、国际化、供应链与治理|匹配与覆盖偏差；严格许可|P2|
|D23|企业金融|[S&P Capital IQ / Compustat](https://www.spglobal.com/marketintelligence/)|全球|机构订阅；付费|公司财务、交易、估值、证券、行业|公司面板、并购、资本市场|许可、实体匹配与存活偏差|P2|
|D24|金融新闻|[LSEG Data & Analytics](https://www.lseg.com/en/data-analytics)|全球|机构订阅；付费|市场、公司、新闻、ESG、分析师|事件、文本、金融与ESG|新闻与数据授权限制严格|P2|
|D25|新闻事件|[GDELT](https://www.gdeltproject.org/)|全球|开放；免费|全球新闻、事件、语调、实体|事件检测、媒体关注、地缘风险|自动编码噪声、媒体覆盖偏差|P1|
|D26|网页语料|[Common Crawl](https://commoncrawl.org/)|全球|开放；免费（计算有成本）|网页抓取、WARC、链接与文本|大规模网页、企业与产品文本|robots/版权/隐私与去重；只处理合规内容|P2|
|D27|软件与协作|[GitHub Archive](https://www.gharchive.org/)|全球|开放事件流；免费|公开 GitHub 事件|开源协作、创新、开发者行为|仅公开事件；账号去标识与平台条款|P1|
|D28|知识社区|[Stack Exchange Data Dump / SEDE](https://data.stackexchange.com/)|全球|开放；免费|问答、标签、投票、用户与时间|知识生产、社区、技术扩散|遵守 CC BY-SA 与去标识原则|P1|
|D29|消费与服务|[Yelp Open Dataset](https://business.yelp.com/data/resources/open-dataset/)|指定城市/商户|开放研究数据；免费|评论、评分、商户、用户、签到|推荐、服务运营、文本与网络|只按数据集许可使用；不外推到总体|P1|
|D30|趋势关注|[Google Trends](https://trends.google.com/trends/)|全球|公开界面；免费|相对搜索兴趣|关注度、需求先行指标、事件反应|抽样与归一化；接口与服务条款风险|P2|
|D31|交通出行|[NYC TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)|纽约市|开放；免费|出租车/网约车行程、时间、费用、区域|需求预测、定价、匹配、交通政策|地理/时间口径、异常与隐私聚合|P0|
|D32|交通流|[Caltrans PeMS](https://pems.dot.ca.gov/)|加州|注册/开放；免费|高速路检测器流量、速度、占有率|交通预测、拥堵与控制|传感器缺失、漂移、站点变更|P1|
|D33|地理网络|[OpenStreetMap](https://www.openstreetmap.org/)|全球|开放数据库；免费|道路、POI、建筑与关系|选址、网络、物流与城市研究|ODbL 署名/同许可；区域质量差异|P0|
|D34|公共交通|[GTFS / MobilityData](https://gtfs.org/)|全球各城市|开放程度依发布者；通常免费|站点、班次、线路、实时车辆|公共交通可达性、可靠性与调度|各运营者许可和覆盖不同|P1|
|D35|能源|[U.S. EIA Open Data](https://www.eia.gov/opendata/)|美国/国际部分|开放 API；免费；key|电力、石油、天然气、价格与容量|能源运营、市场、政策与碳研究|系列修订、单位与时区|P1|
|D36|天气气候|[NOAA Climate Data Online](https://www.ncei.noaa.gov/cdo-web/webservices/v2)|全球/美国|开放 API；免费；token|气象站、温度、降水、极端天气|需求、物流、灾害与运营冲击|站点缺失、空间插值、极端值口径|P1|
|D37|天气气候|[Copernicus ERA5](https://cds.climate.copernicus.eu/)|全球|注册开放；免费（计算/下载有成本）|再分析气象时空网格|气候风险、能源与供应链冲击|再分析非观测真值；空间尺度匹配|P2|
|D38|医疗运营|[CMS Data](https://data.cms.gov/)|美国|开放/受限子库；多数免费|医疗服务、质量、支付、机构|医疗运营、质量、政策评估|HIPAA/小样本披露与机构匹配|P1|
|D39|医疗运营|[MIMIC-IV](https://physionet.org/content/mimiciv/)|美国单一医疗系统|凭证与培训；免费研究用途|去标识 EHR、ICU、急诊、用药、流程|医疗资源、风险预测、临床运营|需 DUA/培训；不得重识别；外部有效性有限|P2|
|D40|劳动力职业|[O*NET](https://www.onetcenter.org/database.html)|美国|开放；免费|职业技能、任务、知识、工作活动|人力资本、自动化、技能匹配|职业分类版本与跨国外推|P1|
