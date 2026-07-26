#!/usr/bin/env python3
"""Build a balanced 100-paper management-science design corpus from OpenAlex.

The corpus is intentionally balanced by journal and by time horizon:
five all-time highly cited articles plus five recent high-velocity articles
per journal.  It is a design corpus for product discovery, not a claim that
these are the globally definitive top 100 papers.
"""

from __future__ import annotations

import csv
import html
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


AS_OF_DATE = "2026-07-12"
RECENT_START = 2021
RECENT_END = 2025

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "01_research_corpus" / "raw"
OUT_DIR = ROOT / "01_research_corpus"

JOURNALS = [
    {
        "journal": "Management Science",
        "issn": "0025-1909",
        "tier_basis": "UTD24; INFORMS flagship",
        "domain": "综合管理科学",
    },
    {
        "journal": "Operations Research",
        "issn": "0030-364X",
        "tier_basis": "UTD24; INFORMS flagship",
        "domain": "运筹学与决策分析",
    },
    {
        "journal": "Manufacturing & Service Operations Management",
        "issn": "1523-4614",
        "tier_basis": "UTD24",
        "domain": "制造与服务运营",
    },
    {
        "journal": "Production and Operations Management",
        "issn": "1059-1478",
        "tier_basis": "UTD24",
        "domain": "生产与运营管理",
    },
    {
        "journal": "Journal of Operations Management",
        "issn": "0272-6963",
        "tier_basis": "UTD24",
        "domain": "运营管理实证与理论",
    },
    {
        "journal": "Information Systems Research",
        "issn": "1047-7047",
        "tier_basis": "UTD24",
        "domain": "信息系统",
    },
    {
        "journal": "MIS Quarterly",
        "issn": "0276-7783",
        "tier_basis": "UTD24; AIS Senior Scholars' Basket",
        "domain": "信息系统",
    },
    {
        "journal": "INFORMS Journal on Computing",
        "issn": "1091-9856",
        "tier_basis": "UTD24",
        "domain": "计算方法与运筹算法",
    },
    {
        "journal": "Transportation Science",
        "issn": "0041-1655",
        "tier_basis": "INFORMS field flagship",
        "domain": "交通运输与物流",
    },
    {
        "journal": "Decision Sciences",
        "issn": "0011-7315",
        "tier_basis": "Decision Sciences Institute flagship",
        "domain": "决策科学",
    },
]

SELECT_FIELDS = ",".join(
    [
        "id",
        "doi",
        "display_name",
        "publication_year",
        "publication_date",
        "cited_by_count",
        "counts_by_year",
        "abstract_inverted_index",
        "authorships",
        "primary_location",
        "topics",
        "keywords",
        "type",
        "language",
        "is_retracted",
    ]
)

EXCLUDE_TITLE = re.compile(
    r"\b(editorial|erratum|corrigendum|retraction|call for papers|"
    r"in memoriam|volume index|reviewer acknowledg|from the editor|"
    r"introduction to the (special|specialized) issue)\b",
    re.IGNORECASE,
)


def http_json(url: str, retries: int = 4) -> dict[str, Any]:
    headers = {"User-Agent": "AI4MS-design-corpus/0.1 (research prototype)"}
    request = urllib.request.Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def openalex(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode(params or {}, safe=":,|")
    url = f"https://api.openalex.org/{endpoint}"
    if query:
        url += f"?{query}"
    return http_json(url)


def reconstruct_abstract(index: Any) -> str:
    if not isinstance(index, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for token, raw_positions in index.items():
        if not isinstance(raw_positions, list):
            continue
        for raw_position in raw_positions:
            try:
                positions.append((int(raw_position), str(token)))
            except (TypeError, ValueError):
                continue
    positions.sort(key=lambda pair: pair[0])
    return " ".join(token for _, token in positions)


def clean_doi(raw: Any) -> str:
    value = str(raw or "").strip()
    return re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.I)


def authors(work: dict[str, Any]) -> str:
    values: list[str] = []
    for authorship in work.get("authorships") or []:
        author = authorship.get("author") if isinstance(authorship, dict) else {}
        name = str((author or {}).get("display_name") or "").strip()
        if name and name not in values:
            values.append(name)
    return "; ".join(values[:12])


def count_recent(work: dict[str, Any], start: int = 2024, end: int = 2026) -> int:
    return sum(
        int(row.get("cited_by_count", 0) or 0)
        for row in (work.get("counts_by_year") or [])
        if start <= int(row.get("year", 0) or 0) <= end
    )


def hot_score(work: dict[str, Any]) -> float:
    year = int(work.get("publication_year", RECENT_START) or RECENT_START)
    exposure = max(1, 2026 - year + 1)
    recent = count_recent(work)
    total = int(work.get("cited_by_count", 0) or 0)
    # Recent citation flow dominates; annualized total breaks ties and helps
    # papers whose 2026 count is incomplete at the mid-year snapshot.
    return round((recent + 1) / math.sqrt(exposure) + 0.15 * total / exposure, 3)


def work_is_eligible(work: dict[str, Any]) -> bool:
    title = str(work.get("display_name") or "").strip()
    if not title or EXCLUDE_TITLE.search(title):
        return False
    if bool(work.get("is_retracted")):
        return False
    year = int(work.get("publication_year", 0) or 0)
    if year <= 0 or year > RECENT_END:
        return False
    return str(work.get("type") or "") == "article"


def dedupe_works(works: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for work in works:
        doi = clean_doi(work.get("doi")).lower()
        title = re.sub(r"[^a-z0-9]+", " ", str(work.get("display_name") or "").lower()).strip()
        key = doi or title
        # OpenAlex occasionally carries two records for the same article under
        # distinct DOIs/versions, so title identity is also checked.
        title_key = f"title:{title}"
        if not key or key in seen or title_key in seen:
            continue
        seen.add(key)
        seen.add(title_key)
        output.append(work)
    return output


def text_blob(title: str, abstract: str, topics: list[str], keywords: list[str]) -> str:
    return " ".join([title, abstract, *topics, *keywords]).lower()


METHOD_RULES: list[tuple[str, list[str]]] = [
    (
        "综述/理论整合/元分析",
        [
            "systematic review",
            "meta-analysis",
            "meta analysis",
            "literature review",
            "bibliometric",
            "research synthesis",
            "tutorial",
            "research overview",
            "review and research prospects",
            "research prospects",
            "research agenda",
            "research opportunities",
            "conceptual foundations",
            "an overview of",
            "om forum",
        ],
    ),
    (
        "实验研究",
        [
            "randomized experiment",
            "field experiment",
            "laboratory experiment",
            "lab experiment",
            "controlled experiment",
            "a/b test",
            "experimental study",
        ],
    ),
    (
        "因果推断/计量经济学",
        [
            "difference-in-differences",
            "difference in differences",
            "instrumental variable",
            "regression discontinuity",
            "synthetic control",
            "natural experiment",
            "fixed effects",
            "panel data",
            "causal inference",
            "event study",
            "quasi-experiment",
            "quasi experiment",
            "we exploit",
            "propensity score",
            "two-stage least squares",
        ],
    ),
    (
        "结构方程/问卷实证",
        [
            "structural equation",
            "partial least squares",
            "questionnaire",
            "survey data",
            "survey of",
            "latent variable",
            "scale development",
            "technology acceptance model",
            "user acceptance of information technology",
            "perceived ease of use",
            "perceived usefulness",
            "instrument to measure",
            "constructs and measurements",
            "longitudinal field studies",
        ],
    ),
    (
        "设计科学/构建研究",
        [
            "design science",
            "design artifact",
            "action design research",
            "build and evaluate",
        ],
    ),
    (
        "机器学习/文本与预测分析",
        [
            "machine learning",
            "deep learning",
            "neural network",
            "random forest",
            "gradient boosting",
            "natural language processing",
            "text mining",
            "transformer",
            "prediction model",
            "predictive model",
            "reinforcement learning",
        ],
    ),
    (
        "优化与算法",
        [
            "mixed-integer",
            "mixed integer",
            "integer programming",
            "linear programming",
            "convex optimization",
            "robust optimization",
            "stochastic programming",
            "benders decomposition",
            "column generation",
            "branch-and-bound",
            "metaheuristic",
            "heuristic algorithm",
            "approximation algorithm",
            "vehicle routing",
            "scheduling problem",
            "facility location",
            "robustness",
            "robust satisficing",
            "inverse optimization",
            "chance constrained",
            "data envelopment analysis",
            "traveling-salesman",
            "traveling salesman",
            "travelling salesman",
            "shop scheduling",
            "location selection",
            "charging station placement",
            "routing problem",
            "routing and scheduling",
            "network design",
            "solver package",
        ],
    ),
    (
        "随机过程/动态规划/仿真",
        [
            "queueing",
            "queuing",
            "markov decision",
            "dynamic programming",
            "stochastic process",
            "inventory model",
            "newsvendor",
            "simulation study",
            "discrete-event simulation",
            "monte carlo",
            "call centers",
            "call center",
            "traffic flow",
            "shock waves",
        ],
    ),
    (
        "博弈论/机制与契约",
        [
            "game theory",
            "nash equilibrium",
            "stackelberg",
            "auction",
            "mechanism design",
            "contract theory",
            "principal-agent",
            "competition between",
            "competitive pricing",
            "strategic interaction",
            "price-only contracts",
            "price competition",
            "channel conflict",
            "channel coordination",
            "channel structures",
            "supplier encroachment",
            "retail platforms",
            "information sharing",
        ],
    ),
    (
        "离散选择/结构估计",
        [
            "discrete choice",
            "multinomial logit",
            "nested logit",
            "random coefficients",
            "structural estimation",
            "demand estimation",
        ],
    ),
    (
        "定性/案例研究",
        [
            "case study",
            "case studies",
            "qualitative study",
            "grounded theory",
            "interview data",
            "ethnograph",
        ],
    ),
]

TITLE_OVERRIDES: list[tuple[str, str]] = [
    ("organizational information requirements media richness", "概念/理论构建"),
    ("asset stock accumulation and sustainability", "概念/理论构建"),
    ("climate change firm performance and investor surprises", "因果推断/计量经济学"),
    ("climate risk and capital structure", "回归/统计实证"),
    ("green vs brown stocks", "回归/统计实证"),
    ("disruption and rerouting in supply chain networks", "优化与算法"),
    ("sustainable operations management", "综述/理论整合/元分析"),
    ("combating copycats in the supply chain", "博弈论/机制与契约"),
    ("how will artificial intelligence and industry 4 0", "综述/理论整合/元分析"),
    ("lean manufacturing context practice bundles", "回归/统计实证"),
    ("arcs of integration an international study", "结构方程/问卷实证"),
    ("customer and supplier concentrations on firm resilience", "回归/统计实证"),
    ("how information technology automates and augments processes", "定性/案例研究"),
    ("information systems success the quest", "概念/理论构建"),
    ("cognitive challenges in human artificial intelligence collaboration", "实验研究"),
    ("augmenting medical diagnosis decisions", "实验研究"),
    ("janus effect of generative ai", "概念/理论构建"),
    ("achieving supply chain efficiency and resilience", "概念/理论构建"),
]


def classify_method(blob: str) -> tuple[str, list[str]]:
    normalized_blob = re.sub(r"[^a-z0-9]+", " ", blob.lower()).strip()
    for title_fragment, family in TITLE_OVERRIDES:
        if title_fragment in normalized_blob:
            return family, [f"title_override:{title_fragment}"]
    hits: list[tuple[str, list[str]]] = []
    for family, patterns in METHOD_RULES:
        matched = [pattern for pattern in patterns if pattern in blob]
        if matched:
            hits.append((family, matched))
    if hits:
        return hits[0][0], [pattern for _, values in hits for pattern in values][:8]

    fallback = [
        (
            "回归/统计实证",
            [
                "regression",
                "empirical analysis",
                "empirical examination",
                "empirical study",
                "empirically examine",
                "longitudinal",
                "statistical analysis",
                "sample of firms",
                "using data from",
                "we use data",
                "we examine whether",
                "we investigate whether",
            ],
        ),
        (
            "解析建模",
            [
                "analytical model",
                "theoretical model",
                "we model",
                "equilibrium",
                "we characterize",
                "optimal policy",
                "optimal decision",
                "comparative statics",
            ],
        ),
        ("算法设计", ["algorithm", "computational study", "computational results", "exact method"]),
        (
            "概念/理论构建",
            [
                "conceptual framework",
                "theory development",
                "theoretical framework",
                "we develop a theory",
                "theory of supply chain",
                "managing artificial intelligence",
            ],
        ),
    ]
    for family, patterns in fallback:
        matched = [pattern for pattern in patterns if pattern in blob]
        if matched:
            return family, matched
    return "方法待全文确认", []


def paradigm_for(method_family: str) -> str:
    if method_family in {"优化与算法", "随机过程/动态规划/仿真", "算法设计"}:
        return "规范型/处方型"
    if method_family in {"博弈论/机制与契约", "解析建模", "离散选择/结构估计"}:
        return "解析型/机制解释"
    if method_family in {"机器学习/文本与预测分析"}:
        return "预测型/计算型"
    if method_family in {"实验研究", "因果推断/计量经济学"}:
        return "因果解释型"
    if method_family in {"结构方程/问卷实证", "回归/统计实证"}:
        return "实证解释型"
    if method_family == "综述/理论整合/元分析":
        return "证据综合型"
    if method_family == "设计科学/构建研究":
        return "设计构建型"
    if method_family == "定性/案例研究":
        return "探索/理论生成型"
    if method_family == "概念/理论构建":
        return "理论构建型"
    return "待全文确认"


FLOW_TEMPLATES = {
    "规范型/处方型": "管理决策→系统边界与假设→目标函数/约束→算法或求解器→理论性质→算例/仿真→敏感性→管理洞见",
    "解析型/机制解释": "现实现象→参与者与机制→效用/利润/约束→均衡或结构参数→比较静态→经验/数值校准→机制含义",
    "预测型/计算型": "预测/分类任务→数据与标签→特征/表示→训练与验证→基线比较→误差与解释→决策/部署约束",
    "因果解释型": "理论机制→可检验假设→识别设计→样本与变量→估计→平行趋势/有效性→稳健性→机制与异质性",
    "实证解释型": "理论框架→假设→构念/变量→样本与测量→统计模型→信效度/拟合→稳健性→理论与管理含义",
    "证据综合型": "检索协议→纳排标准→编码→质量/偏倚评估→主题或效应综合→异质性→研究议程",
    "设计构建型": "问题/需求→设计目标→构件与机制→原型实现→技术/实验/场景评估→迭代→设计原则与边界",
    "探索/理论生成型": "现象与案例选择→资料采集→开放编码→范畴/机制→跨案例比较→理论命题→边界条件",
    "理论构建型": "现象/悖论→概念界定→理论锚点→机制与命题→边界条件→可检验含义→后续验证议程",
    "待全文确认": "问题界定→理论/机制→设计与数据→分析→验证→解释→可复现产物（具体分支待全文确认）",
}


def infer_data_type(method_family: str, blob: str) -> str:
    if method_family == "综述/理论整合/元分析":
        return "文献与已发表效应量"
    if method_family == "设计科学/构建研究":
        return "需求/场景证据 + 构建与评估数据"
    if method_family in {"优化与算法", "解析建模", "博弈论/机制与契约", "随机过程/动态规划/仿真", "算法设计"}:
        if any(token in blob for token in ["real data", "field data", "empirical data", "case data"]):
            return "模型参数 + 真实案例/二手数据"
        return "模型参数/仿真或算例"
    if method_family == "实验研究":
        return "实验生成数据"
    if method_family == "结构方程/问卷实证":
        return "问卷/量表数据"
    if method_family == "定性/案例研究":
        return "访谈、档案或案例材料"
    if method_family == "机器学习/文本与预测分析":
        return "观察数据/数字痕迹/文本/时序"
    if method_family in {"因果推断/计量经济学", "回归/统计实证", "离散选择/结构估计"}:
        return "观察性微观/面板/交易数据"
    return "摘要未明确"


def sentence_excerpt(text: str, max_chars: int = 420) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= max_chars:
        return value
    cut = value[:max_chars].rsplit(" ", 1)[0]
    return f"{cut}…"


def extract_data_evidence(abstract: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", abstract)
    tokens = [
        "data",
        "sample",
        "survey",
        "experiment",
        "dataset",
        "transactions",
        "records",
        "firms",
        "customers",
        "users",
        "hospitals",
        "stores",
    ]
    for sentence in sentences:
        lower = sentence.lower()
        if any(token in lower for token in tokens):
            return sentence_excerpt(sentence, 320)
    return "摘要未明确；需全文补录具体数据源、样本期与变量定义。"


def normalize_work(
    work: dict[str, Any],
    journal: dict[str, str],
    sample_type: str,
    within_journal_rank: int,
) -> dict[str, Any]:
    title = html.unescape(re.sub(r"<[^>]+>", "", str(work.get("display_name") or ""))).strip()
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    topics = [str(row.get("display_name") or "") for row in (work.get("topics") or [])[:5]]
    keywords = [str(row.get("display_name") or "") for row in (work.get("keywords") or [])[:8]]
    blob = text_blob(title, abstract, topics, keywords)
    method_family, method_hits = classify_method(blob)
    paradigm = paradigm_for(method_family)
    doi = clean_doi(work.get("doi"))
    source_url = f"https://doi.org/{doi}" if doi else str(work.get("id") or "")
    primary_topic = topics[0] if topics else ""
    year = int(work.get("publication_year") or 0)
    return {
        "sample_id": "",
        "sample_type": sample_type,
        "within_journal_rank": within_journal_rank,
        "journal": journal["journal"],
        "journal_issn": journal["issn"],
        "tier_basis": journal["tier_basis"],
        "domain": journal["domain"],
        "title": title,
        "authors": authors(work),
        "year": year,
        "publication_date": str(work.get("publication_date") or ""),
        "doi": doi,
        "openalex_id": str(work.get("id") or ""),
        "source_url": source_url,
        "cited_by_count": int(work.get("cited_by_count") or 0),
        "citations_2024_2026": count_recent(work),
        "hot_score": hot_score(work),
        "citation_snapshot_date": AS_OF_DATE,
        "primary_topic": primary_topic,
        "topic_keywords": "; ".join(topics[:5]),
        "research_paradigm": paradigm,
        "method_family": method_family,
        "method_evidence_keywords": "; ".join(method_hits),
        "inferred_data_type": infer_data_type(method_family, blob),
        "data_evidence_from_abstract": extract_data_evidence(abstract),
        "inferred_research_flow": FLOW_TEMPLATES[paradigm],
        "framework_summary": (
            f"以“{primary_topic or title}”为对象，采用{method_family}，"
            f"属于{paradigm}研究；具体识别、模型与数据细节以全文复核为准。"
        ),
        "abstract_excerpt": sentence_excerpt(abstract),
        "abstract_available": bool(abstract),
        "extraction_evidence_level": "abstract" if abstract else "metadata",
        "manual_review_status": "待逐篇全文复核",
    }


def select_papers(source_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base_filter = f"primary_location.source.id:{source_id},type:article,to_publication_date:{RECENT_END}-12-31"
    classic_payload = openalex(
        "works",
        {
            "filter": base_filter,
            "sort": "cited_by_count:desc",
            "per_page": 40,
            "select": SELECT_FIELDS,
        },
    )
    recent_filter = (
        f"primary_location.source.id:{source_id},type:article,"
        f"from_publication_date:{RECENT_START}-01-01,to_publication_date:{RECENT_END}-12-31"
    )
    recent_payload = openalex(
        "works",
        {
            "filter": recent_filter,
            "sort": "cited_by_count:desc",
            "per_page": 100,
            "select": SELECT_FIELDS,
        },
    )
    classic_candidates = dedupe_works(
        [work for work in classic_payload.get("results", []) if work_is_eligible(work)]
    )
    classic = classic_candidates[:5]
    classic_ids = {str(work.get("id")) for work in classic}
    recent_candidates = dedupe_works(
        [
            work
            for work in recent_payload.get("results", [])
            if work_is_eligible(work) and str(work.get("id")) not in classic_ids
        ]
    )
    recent_candidates.sort(key=lambda work: (hot_score(work), int(work.get("cited_by_count") or 0)), reverse=True)
    hot = recent_candidates[:5]
    return classic + hot, {
        "classic_meta": classic_payload.get("meta", {}),
        "recent_meta": recent_payload.get("meta", {}),
        "classic_candidate_count": len(classic_candidates),
        "recent_candidate_count": len(recent_candidates),
    }


def write_outputs(records: list[dict[str, Any]], provenance: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for index, record in enumerate(records, start=1):
        record["sample_id"] = f"P{index:03d}"

    json_path = OUT_DIR / "papers_100.json"
    csv_path = OUT_DIR / "papers_100.csv"
    provenance_path = OUT_DIR / "corpus_provenance.json"
    summary_path = OUT_DIR / "corpus_summary.json"

    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "as_of_date": AS_OF_DATE,
        "record_count": len(records),
        "journals": Counter(row["journal"] for row in records),
        "sample_types": Counter(row["sample_type"] for row in records),
        "year_min": min(row["year"] for row in records),
        "year_max": max(row["year"] for row in records),
        "abstract_coverage": sum(bool(row["abstract_available"]) for row in records),
        "paradigms": Counter(row["research_paradigm"] for row in records),
        "method_families": Counter(row["method_family"] for row in records),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    all_records: list[dict[str, Any]] = []
    provenance: dict[str, Any] = {
        "as_of_date": AS_OF_DATE,
        "provider": "OpenAlex",
        "provider_docs": "https://developers.openalex.org/api-reference/works",
        "selection_design": "10 journals × (5 all-time highly cited + 5 recent high-velocity), article type, through 2025-12-31",
        "recent_window": [RECENT_START, RECENT_END],
        "hot_score_formula": "(citations_2024_2026 + 1) / sqrt(2026 - publication_year + 1) + 0.15 * total_citations / (2026 - publication_year + 1)",
        "journal_runs": [],
    }

    def fetch_journal(journal: dict[str, str]) -> tuple[dict[str, str], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
        source = openalex(f"sources/issn:{journal['issn']}")
        source_id = str(source.get("id") or "").rsplit("/", 1)[-1]
        selected, run_meta = select_papers(source_id)
        if len(selected) != 10:
            raise RuntimeError(f"Expected 10 eligible papers for {journal['journal']}, got {len(selected)}")
        return journal, source, selected, run_meta

    fetched: dict[str, tuple[dict[str, str], dict[str, Any], list[dict[str, Any]], dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_journal, journal): journal for journal in JOURNALS}
        for future in as_completed(futures):
            journal, source, selected, run_meta = future.result()
            fetched[journal["journal"]] = (journal, source, selected, run_meta)
            print(f"fetched: {journal['journal']}", flush=True)

    # Preserve the declared journal order so sample IDs remain stable.
    for declared in JOURNALS:
        journal, source, selected, run_meta = fetched[declared["journal"]]
        for index, work in enumerate(selected[:5], start=1):
            all_records.append(normalize_work(work, journal, "classic_high_cited", index))
        for index, work in enumerate(selected[5:], start=1):
            all_records.append(normalize_work(work, journal, "recent_hot_2021_2025", index))
        provenance["journal_runs"].append(
            {
                "journal": journal["journal"],
                "issn": journal["issn"],
                "openalex_source_id": source.get("id"),
                "openalex_display_name": source.get("display_name"),
                "works_count": source.get("works_count"),
                "selected_count": len(selected),
                **run_meta,
            }
        )
        print(f"selected 10: {journal['journal']}", flush=True)

    if len(all_records) != 100:
        raise RuntimeError(f"Expected 100 papers, got {len(all_records)}")
    write_outputs(all_records, provenance)
    print(f"wrote {len(all_records)} records to {OUT_DIR}")


if __name__ == "__main__":
    main()
