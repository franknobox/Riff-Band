from __future__ import annotations

import asyncio
import json

import pytest

from ai4ms.inference.gateway import InferenceResponse
from ai4ms.inference.structured import extract_json_object
from ai4ms.orchestration import AORCHESTRA_PAPER, OrchestrationResult
from ai4ms.prompts.catalog import PromptCatalog
from ai4ms.services.stage_generation import (
    StageGenerationNotSupportedError,
    StageGenerationService,
)


def _reasoning_trace(evidence_ref: str = "project.initial_idea") -> dict:
    return {
        "problem_framing": "基于当前项目资产形成可供研究者审阅的阶段草稿。",
        "logic_chain": [
            {
                "step_id": "L01",
                "question": "当前证据允许形成什么范围的阶段判断？",
                "evidence_refs": [evidence_ref],
                "inference_type": "synthesis",
                "conclusion": "只形成受输入与证据边界约束的候选内容。",
                "confidence": "medium",
                "falsifier": "后续证据与当前输入冲突或研究者修改研究边界。",
            }
        ],
        "assumptions": ["输入资产代表当前项目状态"],
        "alternatives": ["保留更多候选并推迟冻结"],
        "uncertainties": ["仍需人工核验的字段"],
        "human_decisions": ["研究者确认本阶段边界与是否采纳草稿"],
        "next_verifications": ["核对引用 ID、关键假设和上游 revision"],
    }


def _problem_payload() -> dict:
    return {
        "reasoning_trace": _reasoning_trace(),
        "initial_idea": "A model must not replace this authoritative field",
        "research_object": "使用生成式 AI 的企业",
        "problem_boundary": "考察企业采用生成式 AI 与创新结果之间的关系，不预设因果成立",
        "objective": "explain",
        "units": ["企业"],
        "geography": ["中国"],
        "time_window": "待研究者确认",
        "concepts": [
            {
                "label": "生成式 AI 采用",
                "terms": ["generative AI adoption", "生成式人工智能采用"],
                "exclude_terms": ["仅讨论算法性能"],
            }
        ],
        "questions": ["生成式 AI 采用与企业创新结果之间存在什么关系？"],
        "candidate_gaps": [
            {
                "gap_type": "context",
                "statement": "不同企业情境下的关系可能不同",
                "why_only_candidate": "尚未执行系统检索，不能确认是否构成研究空白",
                "counter_search": "generative AI adoption firm innovation heterogeneity",
            }
        ],
        "question_candidates": [
            {
                "question_id": "RQ1",
                "statement": "生成式 AI 采用与企业创新结果之间存在什么关系？",
                "question_type": "explain",
                "management_decision": "企业是否以及如何配置生成式 AI 投资",
                "unit_of_analysis": "企业",
                "outcome_or_objective": "解释企业创新结果的差异",
                "candidate_contribution": "theory",
                "evidence_refs": ["project.initial_idea"],
                "feasibility_status": "conditional",
                "data_needs": ["企业 AI 采用与创新结果的同层级数据"],
                "falsifier": "系统检索显示关系和机制已在相同情境中得到充分检验。",
            },
            {
                "question_id": "RQ2",
                "statement": "哪些组织条件会改变生成式 AI 采用与企业创新结果的关系？",
                "question_type": "explore",
                "management_decision": "企业应在何种组织条件下优先配置生成式 AI",
                "unit_of_analysis": "企业",
                "outcome_or_objective": "识别关系的组织边界条件",
                "candidate_contribution": "context",
                "evidence_refs": ["project.initial_idea"],
                "feasibility_status": "unknown",
                "data_needs": ["组织能力与治理条件数据"],
                "falsifier": "可用数据无法测量关键组织条件。",
            },
        ],
        "problem_diagnostics": [
            {
                "diagnostic_id": "PD1",
                "dimension": "unit_alignment",
                "status": "warning",
                "finding": "研究单位为企业，但 AI 采用可能在团队层级发生。",
                "evidence_refs": ["project.initial_idea"],
                "required_action": "由研究者确认采用指标与结果变量是否处于同一层级。",
            }
        ],
        "selection_tradeoffs": [
            "RQ1 更聚焦但需要可靠的企业层采用指标；RQ2 更能体现边界条件但数据需求更高。"
        ],
        "counter_searches": ["生成式 AI 企业创新 相邻术语 已有研究"],
        "unknowns": ["采用指标口径", "可获得数据范围"],
    }


def _project() -> dict:
    return {
        "project_id": "prj_test",
        "title": "生成式 AI 与企业创新",
        "initial_idea": "生成式 AI 是否影响企业创新？",
        "stages": [
            {"key": "problem", "revision": 1, "content": {"initial_idea": "生成式 AI 是否影响企业创新？"}},
            {"key": "literature", "revision": 0, "content": {}},
        ],
    }


class _FakeGateway:
    def __init__(self, responses: list[InferenceResponse]):
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    async def generate(self, system_prompt: str, user_prompt: str) -> InferenceResponse:
        self.calls.append((system_prompt, user_prompt))
        return self.responses.pop(0)


class _FakeOrchestrator:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    async def analyze(self, project, stage_key, instruction, context):
        self.calls.append((stage_key, instruction))
        return OrchestrationResult(
            run_id="ao_problem_test",
            stage_key=stage_key,
            status="complete",
            summary="两个 SubAgent 分别完成边界审查和反向检索。",
            report="## 阶段编排结论\n候选空白仍需检索确认。",
            report_path="agent-runs/ao_problem_test/stage_analysis.md",
            subagent_runs=2,
            attempts=4,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            total_cost=0.01,
            cost_known=True,
        )


class _SlowOrchestrator:
    async def analyze(self, project, stage_key, instruction, context):
        await asyncio.sleep(0.05)
        raise AssertionError("orchestrator should have timed out")


def test_extract_json_object_accepts_fenced_output():
    assert extract_json_object('```json\n{"value": 1}\n```') == {"value": 1}


def test_problem_generation_is_validated_and_preserves_initial_idea():
    response = InferenceResponse(
        text=json.dumps(_problem_payload(), ensure_ascii=False),
        model="test-model",
        usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30, "call_count": 1},
    )
    gateway = _FakeGateway([response])
    service = StageGenerationService(gateway_factory=lambda: gateway)

    content = asyncio.run(service.generate(_project(), "problem", "不要预设因果"))

    assert content["initial_idea"] == "生成式 AI 是否影响企业创新？"
    assert content["generation"]["prompt_id"] == "ai4ms.stage.problem"
    assert content["generation"]["model"] == "test-model"
    assert content["generation"]["attempts"] == 1
    assert content["ai_report"]["schema_version"] == "ai4ms.ai-report.v1"
    assert (
        content["ai_report"]["paradigm"]
        == "evidence_linked_management_science"
    )
    assert (
        content["ai_report"]["auditable_rationale"][
            "private_chain_of_thought"
        ]
        is False
    )
    assert content["ai_report"]["human_control"]["review_required"] is True
    assert len(gateway.calls) == 1


def test_problem_generation_uses_aorchestra_context_and_records_provenance():
    response = InferenceResponse(
        text=json.dumps(_problem_payload(), ensure_ascii=False),
        model="test-model",
        usage={},
    )
    gateway = _FakeGateway([response])
    orchestrator = _FakeOrchestrator()
    service = StageGenerationService(
        gateway_factory=lambda: gateway,
        orchestrator=orchestrator,
    )

    content = asyncio.run(service.generate(_project(), "problem", "优先检查反证"))

    assert orchestrator.calls == [("problem", "优先检查反证")]
    assert AORCHESTRA_PAPER in gateway.calls[0][1]
    metadata = content["generation"]["orchestration"]
    assert metadata["runtime"] == "AOrchestra"
    assert metadata["subagent_runs"] == 2
    assert "report" not in metadata


def test_problem_generation_normalizes_free_text_objective():
    payload = _problem_payload()
    payload["objective"] = "检验 AI 采用对创新绩效的因果影响"
    gateway = _FakeGateway(
        [
            InferenceResponse(
                text=json.dumps(payload, ensure_ascii=False),
                model="test-model",
                usage={},
            )
        ]
    )

    content = asyncio.run(
        StageGenerationService(gateway_factory=lambda: gateway).generate(
            _project(),
            "problem",
        )
    )

    assert content["objective"] == "causal"
    assert content["generation"]["attempts"] == 1


def test_aorchestra_timeout_degrades_to_direct_generation():
    gateway = _FakeGateway(
        [
            InferenceResponse(
                text=json.dumps(_problem_payload(), ensure_ascii=False),
                model="test-model",
                usage={},
            )
        ]
    )
    service = StageGenerationService(
        gateway_factory=lambda: gateway,
        orchestrator=_SlowOrchestrator(),
        orchestration_timeout_seconds=0.01,
    )

    content = asyncio.run(service.generate(_project(), "problem"))

    metadata = content["generation"]["orchestration"]
    assert metadata["runtime"] == "AOrchestra"
    assert metadata["status"] == "timed_out"
    assert metadata["degraded"] is True
    assert len(gateway.calls) == 1


def test_invalid_model_json_gets_one_repair_attempt():
    repaired = InferenceResponse(
        text=json.dumps(_problem_payload(), ensure_ascii=False),
        model="test-model",
        usage={"total_tokens": 40, "call_count": 1},
    )
    gateway = _FakeGateway(
        [
            InferenceResponse(text="{}", model="test-model", usage={"total_tokens": 5, "call_count": 1}),
            repaired,
        ]
    )
    service = StageGenerationService(gateway_factory=lambda: gateway)

    content = asyncio.run(service.generate(_project(), "problem"))

    assert content["generation"]["attempts"] == 2
    assert content["generation"]["usage"]["total_tokens"] == 45
    assert "未通过结构或引用约束" in gateway.calls[1][1]


def test_model_generation_rejects_unknown_stage_before_calling_gateway():
    gateway = _FakeGateway([])
    service = StageGenerationService(gateway_factory=lambda: gateway)

    with pytest.raises(StageGenerationNotSupportedError):
        asyncio.run(service.generate(_project(), "unknown"))

    assert gateway.calls == []


def test_literature_prompt_contract_has_no_paper_or_approval_fields():
    prompt = PromptCatalog.get("literature")
    assert prompt is not None
    properties = prompt.contract.model_json_schema()["properties"]
    assert "papers" not in properties
    assert "sources" not in properties
    assert "approval" not in properties


def test_prompt_catalog_supports_s0_through_s9():
    assert PromptCatalog.supported_stage_keys() == (
        "problem",
        "literature",
        "theory",
        "design",
        "data",
        "identification",
        "analysis",
        "robustness",
        "evidence",
        "delivery",
    )


def _s1_s4_project() -> dict:
    project = _project()
    project["stages"] = [
        {
            "key": "problem",
            "revision": 2,
            "content": {
                "objective": "causal",
                "questions": ["AI 采用如何影响企业创新？"],
            },
        },
        {
            "key": "literature",
            "revision": 2,
            "content": {
                "papers": [
                    {
                        "paper_id": "paper_a",
                        "title": "AI adoption and innovation",
                        "authors": ["Li Ming"],
                        "year": 2024,
                        "abstract": "A study of enterprise AI adoption and innovation.",
                    }
                ],
                "evidence_library": [
                    {
                        "evidence_id": "EVLIB_A",
                        "evidence_type": "paper",
                        "status": "active",
                        "revision": 1,
                        "paper_id": "paper_a",
                        "title": "AI adoption and innovation",
                        "authors": ["Li Ming"],
                        "year": 2024,
                        "url": "https://example.org/paper-a",
                        "evidence_level": "abstract",
                        "content_hash": "a" * 64,
                    }
                ],
                "syntheses": [
                    {
                        "statement": "现有证据提示二者相关，但识别仍有限。",
                        "supporting_paper_ids": ["paper_a"],
                    }
                ],
                "coverage_limits": ["当前仅有一篇论文"],
            },
        },
        {"key": "theory", "revision": 0, "content": {}},
        {"key": "design", "revision": 0, "content": {}},
        {"key": "data", "revision": 0, "content": {}},
    ]
    return project


def _literature_synthesis_payload(evidence_level: str = "abstract") -> dict:
    basis = "explicit_full_text" if evidence_level == "full_text" else "explicit_abstract"
    return {
        "reasoning_trace": _reasoning_trace("paper_a"),
        "paper_evidence_cards": [
            {
                "paper_id": "paper_a",
                "evidence_level": evidence_level,
                "core_problem": "考察企业采用 AI 与创新结果之间的关系。",
                "theoretical_lenses": ["组织信息处理理论"],
                "methodology": {
                    "research_design": "观察性企业研究",
                    "unit_of_analysis": "企业",
                    "sample_and_context": "摘要只说明企业情境，样本细节待全文核验。",
                    "data_sources": [],
                    "analysis_methods": [],
                    "identification_or_solution_logic": "摘要未提供足以确认因果识别的设计信息。",
                },
                "findings": [
                    {
                        "finding_id": "PF1",
                        "statement": "摘要提示 AI 采用与创新之间存在关系。",
                        "direction": "supports",
                        "evidence_basis": basis,
                        "locator": "abstract",
                        "reported_values": [],
                    }
                ],
                "contributions": ["把 AI 采用置于企业创新情境中讨论"],
                "limitations": ["当前只有摘要级证据"],
                "extraction_locators": [
                    {
                        "field_name": "core_problem",
                        "locator": "abstract",
                        "evidence_level": evidence_level,
                    }
                ],
                "unknowns": ["样本量与具体识别策略"],
            }
        ],
        "research_streams": [
            {
                "stream_id": "stream_adoption",
                "name": "AI 采用与创新",
                "description": "讨论企业采用 AI 与创新结果之间关系的研究。",
                "paper_ids": ["paper_a"],
                "naming_evidence": "paper_a 的题名与摘要。",
            }
        ],
        "syntheses": [
            {
                "statement": "当前摘要级证据提示二者相关，但不能支持因果结论。",
                "status": "limited",
                "supporting_paper_ids": ["paper_a"],
                "opposing_paper_ids": [],
                "qualifiers": ["只有一篇摘要级记录"],
            }
        ],
        "method_comparisons": [
            {
                "method_label": "观察性企业研究",
                "paper_ids": ["paper_a"],
                "strengths": ["贴近企业管理情境"],
                "limitations": ["摘要不足以确认识别策略"],
                "suitable_contexts": ["企业采用研究"],
                "identification_limits": ["不能由相关性推出因果"],
            }
        ],
        "contradictions": [],
        "gap_candidates": [],
        "review_outline": [
            {
                "section_id": "LR1",
                "title": "AI 采用与创新关系的证据边界",
                "purpose": "综合理论、方法和情境限制，而非逐篇罗列。",
                "paper_ids": ["paper_a"],
                "synthesis_focus": "evidence",
                "required_contrasts": ["关系证据与因果识别"],
            }
        ],
        "recommended_next_steps": ["补充全文并执行反向检索。"],
        "unknowns": ["全文方法与结果数值"],
        "coverage_limits": ["当前只有一篇摘要级论文。"],
    }


def test_literature_synthesis_downgrades_full_text_claim_to_available_abstract():
    project = _s1_s4_project()
    gateway = _FakeGateway(
        [
            InferenceResponse(
                text=json.dumps(_literature_synthesis_payload("full_text"), ensure_ascii=False),
                model="test",
                usage={},
            ),
            InferenceResponse(
                text=json.dumps(_literature_synthesis_payload("abstract"), ensure_ascii=False),
                model="test",
                usage={},
            ),
        ]
    )

    content = asyncio.run(
        StageGenerationService(lambda: gateway).generate(project, "literature")
    )

    assert content["paper_evidence_cards"][0]["evidence_level"] == "abstract"
    assert content["review_outline"][0]["synthesis_focus"] == "evidence"
    assert content["generation"]["attempts"] == 2


def _theory_payload() -> dict:
    return {
        "reasoning_trace": _reasoning_trace("paper_a"),
        "theoretical_lenses": [
            {
                "name": "组织信息处理理论",
                "relevance": "用于解释信息处理能力与创新活动之间的关系。",
                "limits": ["不能单独确认因果方向"],
                "supporting_paper_ids": ["paper_a"],
            }
        ],
        "constructs": [
            {"name": "AI 采用", "definition": "企业部署并使用 AI 的程度。", "role": "antecedent", "measurement_unknowns": ["口径待定"]},
            {"name": "企业创新", "definition": "企业产生创新成果的表现。", "role": "outcome", "measurement_unknowns": ["指标待定"]},
        ],
        "mechanisms": [
            {
                "name": "信息处理机制",
                "chain": ["AI 采用提高信息处理能力", "信息处理能力支持创新"],
                "boundary_conditions": ["组织吸收能力"],
                "supporting_paper_ids": ["paper_a"],
                "evidence_status": "limited",
            }
        ],
        "research_questions": ["AI 采用如何通过信息处理能力影响企业创新？"],
        "competing_explanations": [{"explanation": "创新能力强的企业更早采用 AI。", "distinguishing_observation": "采用前创新趋势能够区分反向因果。"}],
        "falsifiable_propositions": [{"proposition_id": "H1", "statement": "AI 采用与企业创新正相关。", "falsification": "在可比样本中未观察到该关系。"}],
        "contribution_boundary": "只提出待检验机制，不把相关性写成因果事实。",
        "unknowns": ["构念测量方式"],
    }


def test_theory_generation_accepts_only_existing_paper_ids():
    gateway = _FakeGateway([InferenceResponse(text=json.dumps(_theory_payload(), ensure_ascii=False), model="test", usage={})])
    content = asyncio.run(StageGenerationService(lambda: gateway).generate(_s1_s4_project(), "theory"))

    assert content["generation"]["prompt_id"] == "ai4ms.stage.theory"
    assert content["mechanisms"][0]["supporting_paper_ids"] == ["paper_a"]


def test_design_generation_repairs_method_id_outside_registry_shortlist():
    project = _s1_s4_project()
    project["stages"][2]["content"] = _theory_payload()
    context = StageGenerationService._build_context(project, "design")
    method_ids = [item["method_id"] for item in context["method_candidates"][:2]]

    def payload(primary: str) -> dict:
        return {
            "reasoning_trace": _reasoning_trace("method_candidates"),
            "design_lane": "empirical_causal",
            "research_question": "AI 采用如何影响企业创新？",
            "unit_of_analysis": "企业年度观测",
            "estimand_or_objective": "估计 AI 采用对企业创新结果的平均影响。",
            "method_options": [
                {"method_id": primary, "role": "primary", "rationale": "匹配因果研究目标与面板结构。", "fit_conditions": ["存在可比组"], "risks": ["残余混杂"]},
                {"method_id": method_ids[1], "role": "alternative", "rationale": "用于替代识别与结果复核。", "fit_conditions": ["数据满足方法要求"], "risks": ["估计精度不足"]},
            ],
            "primary_method_id": primary,
            "assumptions": [{"assumption_id": "A1", "category": "identification", "statement": "处理组与对照组满足方法所需可比性。", "testability": "partially_testable", "planned_check": "检验处理前趋势与协变量平衡。"}],
            "falsification": ["安慰剂时间检验"],
            "threats_to_validity": ["选择偏差"],
            "stopping_conditions": ["关键识别假设明显不成立"],
            "unknowns": ["实际可得面板长度"],
        }

    gateway = _FakeGateway(
        [
            InferenceResponse(text=json.dumps(payload("M99"), ensure_ascii=False), model="test", usage={}),
            InferenceResponse(text=json.dumps(payload(method_ids[0]), ensure_ascii=False), model="test", usage={}),
        ]
    )
    content = asyncio.run(StageGenerationService(lambda: gateway).generate(project, "design"))

    assert content["primary_method_id"] == method_ids[0]
    assert content["generation"]["attempts"] == 2
    assert "可用 ID" in gateway.calls[1][1]


def test_data_generation_uses_registry_source_ids():
    project = _s1_s4_project()
    project["stages"][2]["content"] = _theory_payload()
    project["stages"][3]["content"] = {"design_lane": "empirical_causal", "primary_method_id": "M02"}
    context = StageGenerationService._build_context(project, "data")
    source_id = context["data_source_candidates"][0]["source_id"]
    payload = {
        "reasoning_trace": _reasoning_trace("data_source_candidates"),
        "data_sources": [{"source_id": source_id, "role": "candidate", "access_status": "unknown", "license_status": "unknown", "rationale": "候选数据源与企业创新变量可能相关。", "required_fields": ["企业标识", "年份"], "risks": ["授权状态未知"]}],
        "variables": [
            {"name": "AI 采用", "role": "treatment", "construct": "企业 AI 采用", "operationalization": "根据可得字段构建，口径待确认。", "unit": "企业-年", "source_ids": [source_id], "missing_data_plan": "先描述缺失机制再决定处理方式。"},
            {"name": "创新结果", "role": "outcome", "construct": "企业创新", "operationalization": "根据可得创新字段构建，口径待确认。", "unit": "企业-年", "source_ids": [source_id], "missing_data_plan": "报告缺失比例并进行敏感性分析。"},
        ],
        "sample_definition": "具有企业标识、年份及关键变量的企业年度样本。",
        "time_coverage": "取决于候选数据源实际可得年份",
        "join_keys": ["企业标识", "年份"],
        "pii_class": "unknown",
        "privacy_risks": ["字段级隐私分类尚未确认"],
        "ethics_checks": ["确认授权范围和数据最小化原则"],
        "quality_checks": ["主键唯一性", "时间覆盖", "缺失与异常值"],
        "blocking_issues": ["尚未确认访问权限"],
        "unknowns": ["许可条款"],
    }
    gateway = _FakeGateway([InferenceResponse(text=json.dumps(payload, ensure_ascii=False), model="test", usage={})])

    content = asyncio.run(StageGenerationService(lambda: gateway).generate(project, "data"))

    assert content["data_sources"][0]["source_id"] == source_id
    assert content["generation"]["prompt_id"] == "ai4ms.stage.data"


def _s5_s7_project() -> dict:
    project = _s1_s4_project()
    project["stages"][3]["content"] = {
        "design_lane": "empirical_causal",
        "research_question": "AI 采用如何影响企业创新？",
        "unit_of_analysis": "企业-年",
        "estimand_or_objective": "估计 AI 采用对企业创新的平均影响。",
        "method_options": [
            {"method_id": "M06", "role": "primary"},
            {"method_id": "M02", "role": "alternative"},
        ],
        "primary_method_id": "M06",
    }
    project["stages"][4]["content"] = {
        "variables": [
            {"name": "创新结果", "role": "outcome", "operationalization": "innovation"},
            {"name": "AI 采用", "role": "treatment", "operationalization": "ai_adoption"},
        ],
        "sample_definition": "企业年度面板",
        "join_keys": ["firm_id", "year"],
        "blocking_issues": ["数据权限待确认"],
    }
    project["stages"].extend(
        [
            {"key": "identification", "revision": 0, "content_hash": None, "content": {}},
            {"key": "analysis", "revision": 0, "content_hash": None, "content": {}},
            {"key": "robustness", "revision": 0, "content_hash": None, "content": {}},
        ]
    )
    return project


def _analysis_plan_payload(formula_id: str) -> dict:
    return {
        "reasoning_trace": _reasoning_trace(formula_id),
        "design_lane": "empirical_causal",
        "estimand_or_objective": "估计 AI 采用对企业创新结果的平均处理效应。",
        "analysis_sample": "满足企业标识、年份及主变量完整要求的企业年度样本。",
        "unit_of_analysis": "企业-年",
        "variable_roles": [
            {"name": "创新结果", "role": "outcome", "source_variable": "innovation", "transformation": "none", "rationale": "对应研究结果构念。"},
            {"name": "AI 采用", "role": "treatment", "source_variable": "ai_adoption", "transformation": "none", "rationale": "对应核心处理变量。"},
        ],
        "model_specifications": [
            {
                "specification_id": "SPEC1",
                "label": "主模型",
                "role": "primary",
                "method_id": "M06",
                "formula_id": formula_id,
                "equation_or_objective": "innovation_it = beta * ai_adoption_it + firm_fe + year_fe + error_it",
                "outcome_or_target": ["innovation"],
                "predictors_or_decisions": ["ai_adoption"],
                "fixed_effects": ["firm", "year"],
                "uncertainty_or_standard_errors": "按企业聚类稳健标准误",
                "weights": "none",
                "sample_restrictions": ["主变量非缺失"],
            }
        ],
        "diagnostics": [
            {"diagnostic_id": "DIAG1", "target": "处理前趋势", "procedure": "估计事件研究的处理前系数。", "pass_condition": "处理前系数整体不能拒绝为零。", "failure_action": "停止因果解释并考虑替代设计。"}
        ],
        "analysis_steps": [
            {"step_id": "STEP1", "purpose": "检查数据结构", "inputs": ["input.dta"], "operation": "检查变量、缺失和主键。", "outputs": ["data_audit"], "linked_specification_ids": []},
            {"step_id": "STEP2", "purpose": "估计主模型", "inputs": ["analysis_sample"], "operation": "执行已冻结主规格。", "outputs": ["main_results"], "linked_specification_ids": ["SPEC1"]},
        ],
        "missing_data_plan": "先报告缺失机制，主分析使用完整样本并进行敏感性检查。",
        "multiplicity_plan": "预先区分主要与次要结果，不根据显著性选择报告。",
        "robustness_plan": ["替代创新指标", "替代样本窗口", "安慰剂处理时间"],
        "stopping_conditions": ["关键变量不存在", "处理前趋势明显不成立"],
        "execution_engine": "stata",
        "code_language": "Stata do-file",
        "stata_do_file": "version 18.0\nset more off\nset varabbrev off\nargs project_dir run_id input_dta output_dir\nuse `\"`input_dta'\"', clear\nset seed 20260721\nxtset firm_id year\nxtreg innovation ai_adoption i.year, fe vce(cluster firm_id)\n",
        "seed": 20260721,
        "expected_outputs": ["数据审计日志", "主模型结果表"],
        "reproducibility_requirements": ["固定 Stata version", "保存 do-file 与输入输出 hash"],
        "unknowns": ["实际数据是否满足面板唯一键"],
    }


def test_identification_generation_uses_approved_methods_and_formula_registry():
    project = _s5_s7_project()
    context = StageGenerationService._build_context(project, "identification")
    formula_id = context["formula_candidates"][0]["formula_id"]
    gateway = _FakeGateway([InferenceResponse(text=json.dumps(_analysis_plan_payload(formula_id), ensure_ascii=False), model="test", usage={})])

    content = asyncio.run(StageGenerationService(lambda: gateway).generate(project, "identification"))

    assert content["model_specifications"][0]["method_id"] == "M06"
    assert content["model_specifications"][0]["formula_id"] == formula_id
    assert content["generation"]["prompt_id"] == "ai4ms.stage.identification"


def test_analysis_generation_cannot_modify_approved_do_file_binding():
    project = _s5_s7_project()
    context = StageGenerationService._build_context(project, "identification")
    plan = _analysis_plan_payload(context["formula_candidates"][0]["formula_id"])
    project["stages"][5].update({"revision": 2, "content_hash": "plan_hash", "content": plan})
    preserved_run = {
        "run_id": "run_preserved",
        "status": "blocked",
        "reason_code": "no_runner",
        "preflight": {"issues": [{"code": "no_runner", "message": "not available"}]},
        "manifest_path": "artifacts/runs/run_preserved/manifest.json",
    }
    project["stages"][6]["content"] = {"runs": [preserved_run]}
    payload = {
        "reasoning_trace": _reasoning_trace("analysis_plan_hash"),
        "execution_engine": "stata",
        "readiness_summary": "分析计划已冻结，但仍需执行确定性预检。",
        "expected_outputs": ["日志", "主结果表"],
        "preflight_checks": ["检查 G3 与代码 hash", "检查输入文件与变量"],
        "result_review_checks": ["检查退出码", "检查失败诊断和样本量"],
        "blocking_issues": ["Runner 与输入文件状态尚未检查"],
        "unknowns": ["Stata 许可状态"],
    }
    gateway = _FakeGateway([InferenceResponse(text=json.dumps(payload, ensure_ascii=False), model="test", usage={})])

    content = asyncio.run(StageGenerationService(lambda: gateway).generate(project, "analysis"))

    assert content["do_file"] == plan["stata_do_file"]
    assert content["approved_analysis_plan_revision"] == 2
    assert content["approved_analysis_plan_hash"] == "plan_hash"
    assert content["runs"] == [preserved_run]


def _robustness_payload(status: str = "blocked") -> dict:
    return {
        "reasoning_trace": _reasoning_trace("run_blocked"),
        "robustness_matrix": [
            {"check_id": "ROB1", "category": "alternative_measure", "rationale": "检查指标口径依赖。", "specification": "使用替代创新指标重估主规格。", "linked_specification_ids": ["SPEC1"], "required_run_ids": ["run_blocked"], "status": status, "result_summary": "" if status == "blocked" else "声称稳健", "implication": "完成运行前不得提升结论强度。"},
            {"check_id": "ROB2", "category": "placebo", "rationale": "检查虚假处理时间。", "specification": "把处理时间提前并重估。", "linked_specification_ids": ["SPEC1"], "required_run_ids": [], "status": "planned", "result_summary": "", "implication": "显著安慰剂结果将削弱识别可信度。"},
        ],
        "failed_checks": [],
        "interpretation_limits": ["当前没有成功且结构化的稳健性运行结果"],
        "next_runs": ["创建替代指标和安慰剂运行分支"],
        "reproducibility_report": "现有 blocked Run 可追溯，但尚不能形成数值复现结论。",
        "unknowns": ["Runner 可用性"],
    }


def test_robustness_generation_rejects_claims_without_structured_run_evidence():
    project = _s5_s7_project()
    context = StageGenerationService._build_context(project, "identification")
    plan = _analysis_plan_payload(context["formula_candidates"][0]["formula_id"])
    project["stages"][5].update({"revision": 2, "content_hash": "plan_hash", "content": plan})
    project["stages"][6]["content"] = {"runs": [{"run_id": "run_blocked", "status": "blocked", "structured_results": []}]}
    gateway = _FakeGateway(
        [
            InferenceResponse(text=json.dumps(_robustness_payload("passed"), ensure_ascii=False), model="test", usage={}),
            InferenceResponse(text=json.dumps(_robustness_payload("blocked"), ensure_ascii=False), model="test", usage={}),
        ]
    )

    content = asyncio.run(StageGenerationService(lambda: gateway).generate(project, "robustness"))

    assert content["robustness_matrix"][0]["status"] == "blocked"
    assert content["generation"]["attempts"] == 2


def test_s7_accepts_status_only_when_s6_run_has_structured_results():
    project = _s5_s7_project()
    context = StageGenerationService._build_context(project, "identification")
    plan = _analysis_plan_payload(context["formula_candidates"][0]["formula_id"])
    project["stages"][5].update({"revision": 2, "content_hash": "plan_hash", "content": plan})
    project["stages"][6]["content"] = {
        "runs": [
            {
                "run_id": "run_blocked",
                "status": "succeeded",
                "reason_code": "completed",
                "structured_results": [
                    {
                        "result_id": "RES_1",
                        "kind": "estimate",
                        "term": "treatment",
                        "estimate": 0.2,
                        "std_error": 0.05,
                    }
                ],
            }
        ]
    }
    payload = _robustness_payload("passed")
    gateway = _FakeGateway(
        [InferenceResponse(text=json.dumps(payload, ensure_ascii=False), model="test", usage={})]
    )

    content = asyncio.run(
        StageGenerationService(lambda: gateway).generate(project, "robustness")
    )

    assert content["robustness_matrix"][0]["status"] == "passed"
    assert content["generation"]["attempts"] == 1


def _claim_evidence_payload(confidence: str = "low") -> dict:
    return {
        "reasoning_trace": _reasoning_trace("paper_a"),
        "claims": [
            {
                "claim_id": "C1",
                "claim_text": "现有文献提示 AI 采用与企业创新存在关系，但当前运行阻塞，不能据此作因果判断。",
                "claim_type": "causal",
                "status": "mixed",
                "confidence": confidence,
                "scope": {
                    "population_or_system": "采用 AI 的企业",
                    "time": "现有论文覆盖期，具体年份待核验",
                    "geography": "论文样本所覆盖地区",
                    "boundary_conditions": ["当前没有成功的本地模型运行"],
                },
                "evidence": [
                    {
                        "evidence_id": "EV1",
                        "evidence_type": "paper",
                        "artifact_id": "EVLIB_A",
                        "locator": "title and abstract metadata",
                        "direction": "supports",
                        "strength": "moderate",
                    },
                    {
                        "evidence_id": "EV2",
                        "evidence_type": "reviewer_note",
                        "artifact_id": "run_blocked",
                        "locator": "run status and reason_code",
                        "direction": "qualifies",
                        "strength": "weak",
                        "run_id": "run_blocked",
                    },
                ],
                "assumptions": [
                    {"assumption_id": "A1", "impact_if_violated": "因果解释需要撤回并降级为相关性描述。"}
                ],
                "counterevidence": ["EV2"],
                "uncertainty_note": "当前只能形成有边界的候选解释。",
                "robustness_check_ids": ["ROB1"],
                "mechanism_ids": ["MECH1"],
            }
        ],
        "mechanisms": [
            {
                "mechanism_id": "MECH1",
                "statement": "信息处理能力可能连接 AI 采用与创新结果。",
                "claim_ids": ["C1"],
                "evidence_ids": ["EV1", "EV2"],
                "status": "candidate",
                "competing_explanation": "创新能力更强的企业可能更早采用 AI。",
            }
        ],
        "heterogeneity": [],
        "limitations": ["Runner 不可用，尚无结构化模型结果。"],
        "interpretation": "文献证据仅支持候选关系，运行阻塞要求保留低置信和因果解释限制。",
        "unknowns": ["本地数据估计结果"],
    }


def _s8_project() -> dict:
    project = _s5_s7_project()
    project["stages"][6]["content"] = {
        "runs": [
            {
                "run_id": "run_blocked",
                "status": "blocked",
                "reason_code": "no_runner",
                "structured_results": [],
                "output_artifacts": [],
            }
        ]
    }
    project["stages"][7]["content"] = {
        "robustness_matrix": [
            {
                "check_id": "ROB1",
                "status": "blocked",
                "result_summary": "",
                "implication": "完成运行前不得形成因果结论。",
            }
        ],
        "interpretation_limits": ["当前无可验证的模型结果"],
    }
    project["stages"].extend(
        [
            {"key": "evidence", "status": "in_progress", "revision": 0, "content_hash": None, "content": {}},
            {"key": "delivery", "status": "not_started", "revision": 0, "content_hash": None, "content": {}},
        ]
    )
    return project


def test_evidence_generation_downgrades_claim_when_run_and_robustness_are_blocked():
    project = _s8_project()
    gateway = _FakeGateway(
        [
            InferenceResponse(text=json.dumps(_claim_evidence_payload("high"), ensure_ascii=False), model="test", usage={}),
            InferenceResponse(text=json.dumps(_claim_evidence_payload("low"), ensure_ascii=False), model="test", usage={}),
        ]
    )

    content = asyncio.run(StageGenerationService(lambda: gateway).generate(project, "evidence"))

    assert content["claims"][0]["confidence"] == "low"
    assert content["claims"][0]["evidence"][1]["artifact_id"] == "run_blocked"
    assert content["generation"]["attempts"] == 2


def test_s8_accepts_structured_s6_run_as_estimate_evidence():
    project = _s8_project()
    project["stages"][6]["content"]["runs"][0].update(
        {
            "status": "succeeded",
            "reason_code": "completed",
            "structured_results": [
                {
                    "result_id": "RES_1",
                    "kind": "estimate",
                    "term": "treatment",
                    "estimate": 0.2,
                    "std_error": 0.05,
                }
            ],
        }
    )
    project["stages"][7]["content"]["robustness_matrix"][0]["status"] = "passed"
    payload = _claim_evidence_payload("medium")
    claim = payload["claims"][0]
    claim["claim_text"] = "在当前批准样本与模型中，AI 采用与企业创新结果存在正向估计关系。"
    claim["status"] = "supported"
    claim["evidence"][1] = {
        "evidence_id": "EV2",
        "evidence_type": "estimate",
        "artifact_id": "run_blocked",
        "locator": "structured_results.RES_1",
        "direction": "supports",
        "strength": "strong",
        "run_id": "run_blocked",
    }
    claim["counterevidence"] = []
    claim["scope"]["boundary_conditions"] = ["仅限批准样本、变量口径与主规格"]
    payload["limitations"] = ["结果仍需结合稳健性矩阵与识别假设解释。"]
    payload["unknowns"] = []
    gateway = _FakeGateway(
        [InferenceResponse(text=json.dumps(payload, ensure_ascii=False), model="test", usage={})]
    )

    content = asyncio.run(
        StageGenerationService(lambda: gateway).generate(project, "evidence")
    )

    run_evidence = content["claims"][0]["evidence"][1]
    assert run_evidence["evidence_type"] == "estimate"
    assert run_evidence["artifact_id"] == "run_blocked"
    assert content["generation"]["attempts"] == 1


def _delivery_payload(evidence_id: str = "EV1") -> dict:
    return {
        "reasoning_trace": _reasoning_trace(evidence_id),
        "title": "AI 采用与企业创新：受当前证据约束的研究报告",
        "document_profile": {
            "document_type": "research_report",
            "research_paradigm": "empirical_quantitative",
            "audience": "管理科学研究者与企业管理者",
            "language": "zh-CN",
            "citation_style": "gbt7714_numeric",
            "journal_or_institution_requirements": [],
            "common_method_bias_applicability": "not_applicable",
        },
        "abstract": "本报告评估生成式 AI 采用与企业创新的现有证据，并明确本地运行阻塞所造成的解释边界。",
        "keywords": ["生成式 AI", "企业创新", "证据综合"],
        "executive_summary": "现有论文提示二者存在关系，但本地运行阻塞，因此报告只保留低置信、有限范围的结论。",
        "conclusions": [
            {
                "conclusion_id": "CON1",
                "statement": "当前证据只能支持 AI 采用与创新关系的有限判断，不能确认因果效应。",
                "claim_ids": ["C1"],
                "evidence_ids": [evidence_id],
                "status": "limited",
                "scope_note": "仅适用于现有论文覆盖范围，且不包含本地估计。",
            }
        ],
        "policy_implications": [
            {
                "implication_id": "POL1",
                "statement": "管理者可将 AI 采用作为创新能力建设的候选方向，但不应据此承诺确定收益。",
                "audience": "企业管理者",
                "claim_ids": ["C1"],
                "conditions": ["先完成数据验证和稳健性运行"],
                "risk_note": "当前因果效应未经本地数据验证。",
            }
        ],
        "outline": [
            {"section_id": "SEC1", "title": "问题与证据", "purpose": "说明研究问题和文献边界。", "claim_ids": ["C1"], "evidence_ids": ["EV1"]},
            {"section_id": "SEC2", "title": "结果限制", "purpose": "披露运行阻塞及其解释影响。", "claim_ids": ["C1"], "evidence_ids": ["EV2"]},
            {"section_id": "SEC3", "title": "结论", "purpose": "给出受证据约束的结论。", "claim_ids": ["C1"], "evidence_ids": ["EV1", "EV2"]},
        ],
        "manuscript_sections": [
            {
                "section_id": "SEC1",
                "title": "问题与证据",
                "purpose": "说明研究问题和文献边界。",
                "body_markdown": "现有论文只能支持有限的关系判断 [paper:paper_a] [claim:C1] [evidence:EV1]。",
                "claim_ids": ["C1"],
                "evidence_ids": ["EV1"],
                "citation_paper_ids": ["paper_a"],
                "citation_evidence_ids": ["EVLIB_A"],
                "content_status": "draft",
                "unresolved_items": [],
            },
            {
                "section_id": "SEC2",
                "title": "结果限制",
                "purpose": "披露运行阻塞及其解释影响。",
                "body_markdown": "本地运行当前阻塞，因此不得报告未产生的估计结果 [claim:C1] [evidence:EV2]。",
                "claim_ids": ["C1"],
                "evidence_ids": ["EV2"],
                "citation_paper_ids": [],
                "citation_evidence_ids": [],
                "content_status": "draft",
                "unresolved_items": [],
            },
            {
                "section_id": "SEC3",
                "title": "结论",
                "purpose": "给出受证据约束的结论。",
                "body_markdown": "综合现有论文和运行限制，只能形成有限结论 [paper:paper_a] [claim:C1] [evidence:EV1] [evidence:EV2]。",
                "claim_ids": ["C1"],
                "evidence_ids": ["EV1", "EV2"],
                "citation_paper_ids": ["paper_a"],
                "citation_evidence_ids": ["EVLIB_A"],
                "content_status": "draft",
                "unresolved_items": [],
            },
        ],
        "logic_closure": [
            {
                "link_id": "LC1",
                "research_question_refs": ["生成式 AI 采用如何影响企业创新？"],
                "method_or_design_refs": ["当前文献综合与获批证据资产"],
                "claim_ids": ["C1"],
                "conclusion_ids": ["CON1"],
                "closure_status": "partial",
                "missing_link": "本地模型运行阻塞，尚无项目内估计。",
            }
        ],
        "author_self_review": [],
        "reference_paper_ids": ["paper_a"],
        "reference_evidence_ids": ["EVLIB_A"],
        "limitations": ["本地 Runner 不可用。"],
        "reproducibility_notes": ["所有结论保留 claim_id 和 evidence_id。"],
        "disclosure": "本报告由 AI 生成结构草稿并由研究者审阅，未把阻塞运行表述为成功结果。",
        "release_notes": "首次生成受 G4 约束的交付草稿。",
        "unknowns": ["本地估计值"],
    }


def test_delivery_generation_only_uses_approved_claims_and_their_evidence():
    project = _s8_project()
    project["stages"][8].update(
        {"status": "approved", "revision": 2, "content_hash": "evidence_hash", "content": _claim_evidence_payload()}
    )
    project["stages"][9]["status"] = "in_progress"
    gateway = _FakeGateway(
        [
            InferenceResponse(text=json.dumps(_delivery_payload("EV_UNKNOWN"), ensure_ascii=False), model="test", usage={}),
            InferenceResponse(text=json.dumps(_delivery_payload("EV1"), ensure_ascii=False), model="test", usage={}),
        ]
    )

    content = asyncio.run(StageGenerationService(lambda: gateway).generate(project, "delivery"))

    assert content["conclusions"][0]["evidence_ids"] == ["EV1"]
    assert content["approved_claims"] == ["C1"]
    assert content["references"][0]["paper_id"] == "paper_a"
    assert content["references"][0]["evidence_id"] == "EVLIB_A"
    assert content["source_evidence_hash"] == "evidence_hash"
    assert content["generation"]["attempts"] == 2
