from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)


InferenceType = Literal[
    "deduction",
    "induction",
    "abduction",
    "causal",
    "comparison",
    "calculation",
    "synthesis",
    "design_choice",
]


class LogicStepDraft(StrictContract):
    """Auditable scientific rationale, never private token-level chain of thought."""

    step_id: str = Field(pattern=r"^L[0-9]{2,3}$")
    question: str = Field(min_length=3, max_length=600)
    evidence_refs: list[str] = Field(min_length=1, max_length=30)
    inference_type: InferenceType
    conclusion: str = Field(min_length=3, max_length=1000)
    confidence: Literal["low", "medium", "high"]
    falsifier: str = Field(min_length=3, max_length=800)


class ReasoningTraceDraft(StrictContract):
    """Compact, inspectable research rationale attached to every model draft."""

    problem_framing: str = Field(min_length=5, max_length=1500)
    logic_chain: list[LogicStepDraft] = Field(min_length=1, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=30)
    alternatives: list[str] = Field(default_factory=list, max_length=20)
    uncertainties: list[str] = Field(default_factory=list, max_length=30)
    human_decisions: list[str] = Field(min_length=1, max_length=20)
    next_verifications: list[str] = Field(min_length=1, max_length=20)


class ConceptBlock(StrictContract):
    label: str = Field(min_length=1, max_length=120)
    terms: list[str] = Field(min_length=1, max_length=20)
    exclude_terms: list[str] = Field(default_factory=list, max_length=20)


class GapDraft(StrictContract):
    gap_type: Literal["theory", "context", "data", "method", "time", "practice"]
    statement: str = Field(min_length=5, max_length=500)
    why_only_candidate: str = Field(min_length=5, max_length=500)
    counter_search: str = Field(min_length=3, max_length=500)


class ResearchQuestionCandidateDraft(StrictContract):
    question_id: str = Field(pattern=r"^RQ[0-9_-]+$")
    statement: str = Field(min_length=5, max_length=800)
    question_type: Literal[
        "describe",
        "explore",
        "explain",
        "causal",
        "predict",
        "optimize",
        "synthesize",
        "theory_build",
    ]
    management_decision: str = Field(min_length=3, max_length=600)
    unit_of_analysis: str = Field(min_length=1, max_length=300)
    outcome_or_objective: str = Field(min_length=3, max_length=500)
    candidate_contribution: Literal[
        "theory",
        "method",
        "data",
        "context",
        "design",
        "practice",
        "none",
        "unknown",
    ]
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    feasibility_status: Literal["feasible", "conditional", "blocked", "unknown"]
    data_needs: list[str] = Field(default_factory=list, max_length=12)
    falsifier: str = Field(min_length=3, max_length=800)


class ProblemDiagnosticDraft(StrictContract):
    diagnostic_id: str = Field(pattern=r"^PD[0-9_-]+$")
    dimension: Literal[
        "problem_clarity",
        "management_relevance",
        "theoretical_relevance",
        "novelty",
        "feasibility",
        "data_access",
        "ethics",
        "unit_alignment",
    ]
    status: Literal["pass", "warning", "blocking", "not_assessed"]
    finding: str = Field(min_length=3, max_length=800)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    required_action: str = Field(min_length=3, max_length=800)


class ProblemDraft(StrictContract):
    reasoning_trace: ReasoningTraceDraft | None = None
    initial_idea: str = Field(min_length=3, max_length=4000)
    research_object: str = Field(min_length=1, max_length=500)
    problem_boundary: str = Field(min_length=3, max_length=1000)
    objective: Literal["explore", "explain", "causal", "predict", "optimize", "synthesize", "theory_build", "unknown"]
    units: list[str] = Field(default_factory=list, max_length=10)
    geography: list[str] = Field(default_factory=list, max_length=10)
    time_window: str = Field(default="", max_length=200)
    concepts: list[ConceptBlock] = Field(min_length=1, max_length=12)
    questions: list[str] = Field(min_length=1, max_length=5)
    candidate_gaps: list[GapDraft] = Field(default_factory=list, max_length=6)
    question_candidates: list[ResearchQuestionCandidateDraft] = Field(
        default_factory=list, max_length=8
    )
    problem_diagnostics: list[ProblemDiagnosticDraft] = Field(
        default_factory=list, max_length=12
    )
    selection_tradeoffs: list[str] = Field(default_factory=list, max_length=12)
    counter_searches: list[str] = Field(default_factory=list, max_length=10)
    unknowns: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("objective", mode="before")
    @classmethod
    def normalize_objective(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().casefold()
        allowed = {
            "explore",
            "explain",
            "causal",
            "predict",
            "optimize",
            "synthesize",
            "theory_build",
            "unknown",
        }
        if normalized in allowed:
            return normalized
        aliases = (
            (("因果", "causal", "effect", "impact"), "causal"),
            (("预测", "predict", "forecast"), "predict"),
            (("优化", "optimize", "optimization"), "optimize"),
            (("综述", "综合", "synthesize", "review"), "synthesize"),
            (("理论构建", "理论建构", "theory"), "theory_build"),
            (("解释", "机制", "explain", "mechanism"), "explain"),
            (("探索", "探究", "explore"), "explore"),
        )
        for terms, objective in aliases:
            if any(term in normalized for term in terms):
                return objective
        return "unknown"


class QueryBlock(StrictContract):
    label: str = Field(min_length=1, max_length=120)
    terms: list[str] = Field(min_length=1, max_length=30)
    exclude_terms: list[str] = Field(default_factory=list, max_length=20)
    query_zh: str = Field(min_length=3, max_length=1000)
    query_en: str = Field(min_length=3, max_length=1000)
    purpose: str = Field(min_length=3, max_length=500)


class LiteraturePlanDraft(StrictContract):
    reasoning_trace: ReasoningTraceDraft | None = None
    topic_summary: str = Field(min_length=5, max_length=1000)
    query_blocks: list[QueryBlock] = Field(min_length=2, max_length=12)
    databases: list[Literal["openalex", "crossref", "semantic_scholar", "arxiv"]] = Field(min_length=2, max_length=4)
    languages: list[str] = Field(min_length=1, max_length=8)
    year_from: int | None = Field(default=None, ge=1800, le=2100)
    year_to: int | None = Field(default=None, ge=1800, le=2100)
    inclusion_criteria: list[str] = Field(min_length=1, max_length=20)
    exclusion_criteria: list[str] = Field(min_length=1, max_length=20)
    screening_questions: list[str] = Field(min_length=1, max_length=15)
    counter_searches: list[str] = Field(min_length=1, max_length=12)
    unknowns: list[str] = Field(default_factory=list, max_length=20)
    coverage_limits: list[str] = Field(min_length=1, max_length=15)


class ResearchStreamDraft(StrictContract):
    stream_id: str = Field(pattern=r"^stream_[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=5, max_length=800)
    paper_ids: list[str] = Field(min_length=1, max_length=30)
    naming_evidence: str = Field(min_length=5, max_length=500)


class SynthesisStatementDraft(StrictContract):
    statement: str = Field(min_length=5, max_length=800)
    status: Literal["supported", "contested", "limited", "not_found", "inference"]
    supporting_paper_ids: list[str] = Field(default_factory=list, max_length=30)
    opposing_paper_ids: list[str] = Field(default_factory=list, max_length=30)
    qualifiers: list[str] = Field(default_factory=list, max_length=12)


class EvidenceGapDraft(StrictContract):
    gap_type: Literal["theory", "context", "data", "method", "time", "practice"]
    statement: str = Field(min_length=5, max_length=600)
    supporting_paper_ids: list[str] = Field(default_factory=list, max_length=20)
    opposing_paper_ids: list[str] = Field(default_factory=list, max_length=20)
    counter_search: str = Field(min_length=3, max_length=500)
    coverage_limitations: list[str] = Field(min_length=1, max_length=10)


class PaperExtractionLocatorDraft(StrictContract):
    field_name: str = Field(min_length=1, max_length=120)
    locator: str = Field(min_length=3, max_length=500)
    evidence_level: Literal["metadata", "abstract", "full_text"]


class PaperFindingDraft(StrictContract):
    finding_id: str = Field(pattern=r"^PF[0-9_-]+$")
    statement: str = Field(min_length=3, max_length=1000)
    direction: Literal["supports", "contradicts", "qualifies", "descriptive", "not_reported"]
    evidence_basis: Literal[
        "explicit_full_text",
        "explicit_abstract",
        "abstract_inference",
        "metadata_only",
        "not_reported",
    ]
    locator: str = Field(min_length=3, max_length=500)
    reported_values: list[str] = Field(default_factory=list, max_length=20)


class PaperMethodProfileDraft(StrictContract):
    research_design: str = Field(min_length=2, max_length=500)
    unit_of_analysis: str = Field(min_length=1, max_length=300)
    sample_and_context: str = Field(min_length=2, max_length=800)
    data_sources: list[str] = Field(default_factory=list, max_length=15)
    analysis_methods: list[str] = Field(default_factory=list, max_length=15)
    identification_or_solution_logic: str = Field(min_length=3, max_length=1000)


class PaperEvidenceCardDraft(StrictContract):
    paper_id: str = Field(min_length=1, max_length=120)
    evidence_level: Literal["metadata", "abstract", "full_text"]
    core_problem: str = Field(min_length=3, max_length=1000)
    theoretical_lenses: list[str] = Field(default_factory=list, max_length=12)
    methodology: PaperMethodProfileDraft
    findings: list[PaperFindingDraft] = Field(default_factory=list, max_length=20)
    contributions: list[str] = Field(default_factory=list, max_length=15)
    limitations: list[str] = Field(default_factory=list, max_length=15)
    extraction_locators: list[PaperExtractionLocatorDraft] = Field(
        min_length=1, max_length=30
    )
    unknowns: list[str] = Field(default_factory=list, max_length=20)


class MethodComparisonDraft(StrictContract):
    method_label: str = Field(min_length=2, max_length=200)
    paper_ids: list[str] = Field(min_length=1, max_length=30)
    strengths: list[str] = Field(min_length=1, max_length=12)
    limitations: list[str] = Field(min_length=1, max_length=12)
    suitable_contexts: list[str] = Field(default_factory=list, max_length=12)
    identification_limits: list[str] = Field(default_factory=list, max_length=12)


class LiteratureContradictionDraft(StrictContract):
    issue: str = Field(min_length=5, max_length=800)
    supporting_paper_ids: list[str] = Field(default_factory=list, max_length=30)
    opposing_paper_ids: list[str] = Field(default_factory=list, max_length=30)
    possible_explanations: list[str] = Field(min_length=1, max_length=12)
    resolution_search: str = Field(min_length=3, max_length=500)


class ReviewOutlineSectionDraft(StrictContract):
    section_id: str = Field(pattern=r"^LR[0-9_-]+$")
    title: str = Field(min_length=2, max_length=200)
    purpose: str = Field(min_length=3, max_length=600)
    paper_ids: list[str] = Field(min_length=1, max_length=40)
    synthesis_focus: Literal[
        "concept",
        "theory",
        "method",
        "evidence",
        "contradiction",
        "gap",
        "research_entry",
    ]
    required_contrasts: list[str] = Field(default_factory=list, max_length=12)


class LiteratureSynthesisDraft(StrictContract):
    reasoning_trace: ReasoningTraceDraft | None = None
    paper_evidence_cards: list[PaperEvidenceCardDraft] = Field(
        default_factory=list, max_length=50
    )
    research_streams: list[ResearchStreamDraft] = Field(min_length=1, max_length=8)
    syntheses: list[SynthesisStatementDraft] = Field(min_length=1, max_length=15)
    method_comparisons: list[MethodComparisonDraft] = Field(
        default_factory=list, max_length=12
    )
    contradictions: list[LiteratureContradictionDraft] = Field(
        default_factory=list, max_length=12
    )
    gap_candidates: list[EvidenceGapDraft] = Field(default_factory=list, max_length=8)
    review_outline: list[ReviewOutlineSectionDraft] = Field(
        default_factory=list, max_length=15
    )
    recommended_next_steps: list[str] = Field(min_length=1, max_length=12)
    unknowns: list[str] = Field(default_factory=list, max_length=20)
    coverage_limits: list[str] = Field(min_length=1, max_length=15)


class TheoreticalLensDraft(StrictContract):
    name: str = Field(min_length=2, max_length=160)
    relevance: str = Field(min_length=5, max_length=600)
    limits: list[str] = Field(min_length=1, max_length=8)
    supporting_paper_ids: list[str] = Field(default_factory=list, max_length=20)


class ConstructDraft(StrictContract):
    name: str = Field(min_length=1, max_length=120)
    definition: str = Field(min_length=5, max_length=500)
    role: Literal["antecedent", "outcome", "mediator", "moderator", "control", "context", "parameter"]
    measurement_unknowns: list[str] = Field(default_factory=list, max_length=8)


class MechanismDraft(StrictContract):
    name: str = Field(min_length=2, max_length=120)
    chain: list[str] = Field(min_length=2, max_length=8)
    boundary_conditions: list[str] = Field(default_factory=list, max_length=10)
    supporting_paper_ids: list[str] = Field(default_factory=list, max_length=20)
    evidence_status: Literal["supported", "contested", "limited", "inference", "needs_evidence"]


class CompetingExplanationDraft(StrictContract):
    explanation: str = Field(min_length=5, max_length=600)
    distinguishing_observation: str = Field(min_length=5, max_length=600)


class PropositionDraft(StrictContract):
    proposition_id: str = Field(pattern=r"^(RQ|H|P)[0-9_-]+$")
    statement: str = Field(min_length=5, max_length=600)
    falsification: str = Field(min_length=5, max_length=600)


class TheoryDraft(StrictContract):
    reasoning_trace: ReasoningTraceDraft | None = None
    theoretical_lenses: list[TheoreticalLensDraft] = Field(min_length=1, max_length=6)
    constructs: list[ConstructDraft] = Field(min_length=2, max_length=20)
    mechanisms: list[MechanismDraft] = Field(min_length=1, max_length=10)
    research_questions: list[str] = Field(min_length=1, max_length=5)
    competing_explanations: list[CompetingExplanationDraft] = Field(min_length=1, max_length=8)
    falsifiable_propositions: list[PropositionDraft] = Field(min_length=1, max_length=10)
    contribution_boundary: str = Field(min_length=5, max_length=1000)
    unknowns: list[str] = Field(default_factory=list, max_length=20)


class MethodOptionDraft(StrictContract):
    method_id: str = Field(pattern=r"^M[A-Z0-9_-]{2,31}$")
    role: Literal["primary", "alternative", "supporting"]
    rationale: str = Field(min_length=5, max_length=600)
    fit_conditions: list[str] = Field(min_length=1, max_length=10)
    risks: list[str] = Field(min_length=1, max_length=10)


class AssumptionDraft(StrictContract):
    assumption_id: str = Field(min_length=2, max_length=80)
    category: Literal["identification", "measurement", "behavioral", "mathematical", "data", "deployment"]
    statement: str = Field(min_length=5, max_length=600)
    testability: Literal["testable", "partially_testable", "untestable"]
    planned_check: str = Field(min_length=3, max_length=500)


class DesignDraft(StrictContract):
    reasoning_trace: ReasoningTraceDraft | None = None
    design_lane: Literal["empirical_causal", "analytical_optimization", "predictive_computational", "behavioral_qualitative", "synthesis_design_science"]
    research_question: str = Field(min_length=5, max_length=800)
    unit_of_analysis: str = Field(min_length=1, max_length=300)
    estimand_or_objective: str = Field(min_length=5, max_length=800)
    method_options: list[MethodOptionDraft] = Field(min_length=2, max_length=8)
    primary_method_id: str = Field(pattern=r"^M[A-Z0-9_-]{2,31}$")
    assumptions: list[AssumptionDraft] = Field(min_length=1, max_length=20)
    falsification: list[str] = Field(min_length=1, max_length=12)
    threats_to_validity: list[str] = Field(min_length=1, max_length=15)
    stopping_conditions: list[str] = Field(min_length=1, max_length=10)
    unknowns: list[str] = Field(default_factory=list, max_length=20)


class DataSourceChoiceDraft(StrictContract):
    source_id: str = Field(pattern=r"^D[0-9]{2}$")
    role: Literal["primary", "supplementary", "validation", "candidate"]
    access_status: Literal["unknown", "available", "requested", "blocked"]
    license_status: Literal["unknown", "cleared", "restricted", "pending", "not_applicable"]
    rationale: str = Field(min_length=5, max_length=600)
    required_fields: list[str] = Field(default_factory=list, max_length=30)
    risks: list[str] = Field(min_length=1, max_length=12)


class VariableDraft(StrictContract):
    name: str = Field(min_length=1, max_length=160)
    role: Literal["outcome", "treatment", "exposure", "predictor", "control", "mediator", "moderator", "parameter", "index"]
    construct_name: str = Field(alias="construct", min_length=1, max_length=200)
    operationalization: str = Field(min_length=3, max_length=800)
    unit: str = Field(min_length=1, max_length=160)
    source_ids: list[str] = Field(default_factory=list, max_length=10)
    missing_data_plan: str = Field(min_length=3, max_length=500)


class DataDraft(StrictContract):
    reasoning_trace: ReasoningTraceDraft | None = None
    data_sources: list[DataSourceChoiceDraft] = Field(min_length=1, max_length=10)
    variables: list[VariableDraft] = Field(min_length=2, max_length=30)
    sample_definition: str = Field(min_length=5, max_length=800)
    time_coverage: str = Field(min_length=1, max_length=300)
    join_keys: list[str] = Field(default_factory=list, max_length=15)
    pii_class: Literal["none", "low", "sensitive", "restricted", "unknown"]
    privacy_risks: list[str] = Field(default_factory=list, max_length=15)
    ethics_checks: list[str] = Field(min_length=1, max_length=15)
    quality_checks: list[str] = Field(min_length=1, max_length=20)
    blocking_issues: list[str] = Field(default_factory=list, max_length=15)
    unknowns: list[str] = Field(default_factory=list, max_length=20)


ExecutionEngine = Literal["stata", "python", "r", "julia", "matlab", "manual", "other", "unknown"]


class AnalysisVariableDraft(StrictContract):
    name: str = Field(min_length=1, max_length=160)
    role: Literal["outcome", "treatment", "exposure", "predictor", "control", "mediator", "moderator", "parameter", "index", "identifier", "time"]
    source_variable: str = Field(min_length=1, max_length=160)
    transformation: str = Field(default="none", max_length=500)
    rationale: str = Field(min_length=3, max_length=600)


class ModelSpecificationDraft(StrictContract):
    specification_id: str = Field(pattern=r"^SPEC[0-9_-]+$")
    label: str = Field(min_length=2, max_length=160)
    role: Literal["primary", "secondary", "diagnostic", "exploratory"]
    method_id: str | None = Field(
        default=None,
        pattern=r"^M[A-Z0-9_-]{2,31}$",
    )
    formula_id: str | None = Field(
        default=None,
        pattern=r"^[A-Z][A-Z0-9_-]{2,47}$",
    )
    equation_or_objective: str = Field(min_length=3, max_length=1200)
    outcome_or_target: list[str] = Field(min_length=1, max_length=10)
    predictors_or_decisions: list[str] = Field(default_factory=list, max_length=30)
    fixed_effects: list[str] = Field(default_factory=list, max_length=15)
    uncertainty_or_standard_errors: str = Field(min_length=2, max_length=500)
    weights: str = Field(default="none", max_length=300)
    sample_restrictions: list[str] = Field(default_factory=list, max_length=15)


class DiagnosticPlanDraft(StrictContract):
    diagnostic_id: str = Field(pattern=r"^DIAG[0-9_-]+$")
    target: str = Field(min_length=2, max_length=200)
    procedure: str = Field(min_length=3, max_length=800)
    pass_condition: str = Field(min_length=3, max_length=600)
    failure_action: str = Field(min_length=3, max_length=600)


class AnalysisStepDraft(StrictContract):
    step_id: str = Field(pattern=r"^STEP[0-9_-]+$")
    purpose: str = Field(min_length=3, max_length=500)
    inputs: list[str] = Field(default_factory=list, max_length=20)
    operation: str = Field(min_length=3, max_length=1000)
    outputs: list[str] = Field(min_length=1, max_length=20)
    linked_specification_ids: list[str] = Field(default_factory=list, max_length=12)


class AnalysisPlanDraft(StrictContract):
    reasoning_trace: ReasoningTraceDraft | None = None
    design_lane: Literal["empirical_causal", "analytical_optimization", "predictive_computational", "behavioral_qualitative", "synthesis_design_science"]
    estimand_or_objective: str = Field(min_length=5, max_length=1000)
    analysis_sample: str = Field(min_length=5, max_length=800)
    unit_of_analysis: str = Field(min_length=1, max_length=300)
    variable_roles: list[AnalysisVariableDraft] = Field(min_length=2, max_length=35)
    model_specifications: list[ModelSpecificationDraft] = Field(min_length=1, max_length=12)
    diagnostics: list[DiagnosticPlanDraft] = Field(min_length=1, max_length=20)
    analysis_steps: list[AnalysisStepDraft] = Field(min_length=2, max_length=30)
    missing_data_plan: str = Field(min_length=3, max_length=800)
    multiplicity_plan: str = Field(min_length=3, max_length=800)
    robustness_plan: list[str] = Field(min_length=1, max_length=20)
    stopping_conditions: list[str] = Field(min_length=1, max_length=12)
    execution_engine: ExecutionEngine
    code_language: str = Field(min_length=1, max_length=80)
    stata_do_file: str = Field(default="", max_length=16000)
    seed: int | None = Field(default=None, ge=0)
    expected_outputs: list[str] = Field(min_length=1, max_length=20)
    reproducibility_requirements: list[str] = Field(min_length=1, max_length=20)
    unknowns: list[str] = Field(default_factory=list, max_length=25)


class RunPreparationDraft(StrictContract):
    reasoning_trace: ReasoningTraceDraft | None = None
    execution_engine: ExecutionEngine
    readiness_summary: str = Field(min_length=5, max_length=800)
    expected_outputs: list[str] = Field(min_length=1, max_length=20)
    preflight_checks: list[str] = Field(min_length=1, max_length=20)
    result_review_checks: list[str] = Field(min_length=1, max_length=20)
    blocking_issues: list[str] = Field(default_factory=list, max_length=20)
    unknowns: list[str] = Field(default_factory=list, max_length=20)


class RobustnessCheckDraft(StrictContract):
    check_id: str = Field(pattern=r"^ROB[0-9_-]+$")
    category: Literal["alternative_measure", "alternative_model", "alternative_sample", "placebo", "sensitivity", "falsification", "benchmark", "reproduction"]
    rationale: str = Field(min_length=3, max_length=600)
    specification: str = Field(min_length=3, max_length=1000)
    linked_specification_ids: list[str] = Field(default_factory=list, max_length=12)
    required_run_ids: list[str] = Field(default_factory=list, max_length=12)
    status: Literal["planned", "not_run", "blocked", "passed", "failed", "inconclusive"]
    result_summary: str = Field(default="", max_length=1000)
    implication: str = Field(min_length=3, max_length=800)


class RobustnessDraft(StrictContract):
    reasoning_trace: ReasoningTraceDraft | None = None
    robustness_matrix: list[RobustnessCheckDraft] = Field(min_length=2, max_length=30)
    failed_checks: list[str] = Field(default_factory=list, max_length=20)
    interpretation_limits: list[str] = Field(min_length=1, max_length=20)
    next_runs: list[str] = Field(default_factory=list, max_length=20)
    reproducibility_report: str = Field(min_length=5, max_length=1200)
    unknowns: list[str] = Field(default_factory=list, max_length=20)


class ClaimScopeDraft(StrictContract):
    population_or_system: str = Field(min_length=1, max_length=500)
    time: str = Field(min_length=1, max_length=300)
    geography: str = Field(min_length=1, max_length=300)
    boundary_conditions: list[str] = Field(default_factory=list, max_length=15)


class ClaimEvidenceItemDraft(StrictContract):
    evidence_id: str = Field(pattern=r"^EV[0-9_-]+$")
    evidence_type: Literal[
        "paper",
        "data",
        "estimate",
        "proof",
        "simulation",
        "experiment",
        "qualitative_excerpt",
        "reviewer_note",
    ]
    artifact_id: str = Field(min_length=1, max_length=500)
    locator: str = Field(min_length=1, max_length=500)
    direction: Literal["supports", "contradicts", "qualifies"]
    strength: Literal["weak", "moderate", "strong"]
    method_id: str | None = Field(default=None, max_length=80)
    run_id: str | None = Field(default=None, max_length=120)
    source_url: str | None = Field(default=None, max_length=1000)


class ClaimAssumptionLinkDraft(StrictContract):
    assumption_id: str = Field(min_length=1, max_length=120)
    impact_if_violated: str = Field(min_length=3, max_length=800)


class ClaimRecordDraft(StrictContract):
    claim_id: str = Field(pattern=r"^C[0-9_-]+$")
    claim_text: str = Field(min_length=10, max_length=1200)
    claim_type: Literal[
        "descriptive",
        "associational",
        "causal",
        "predictive",
        "optimality",
        "mechanism",
        "design_principle",
        "literature_synthesis",
    ]
    status: Literal["candidate", "supported", "mixed", "refuted", "withdrawn"]
    confidence: Literal["low", "medium", "high"]
    scope: ClaimScopeDraft
    evidence: list[ClaimEvidenceItemDraft] = Field(min_length=1, max_length=30)
    assumptions: list[ClaimAssumptionLinkDraft] = Field(default_factory=list, max_length=20)
    counterevidence: list[str] = Field(default_factory=list, max_length=20)
    uncertainty_note: str = Field(min_length=3, max_length=1000)
    robustness_check_ids: list[str] = Field(default_factory=list, max_length=30)
    mechanism_ids: list[str] = Field(default_factory=list, max_length=12)


class MechanismAssessmentDraft(StrictContract):
    mechanism_id: str = Field(pattern=r"^MECH[0-9_-]+$")
    statement: str = Field(min_length=5, max_length=1000)
    claim_ids: list[str] = Field(min_length=1, max_length=15)
    evidence_ids: list[str] = Field(min_length=1, max_length=30)
    status: Literal["candidate", "supported", "mixed", "refuted"]
    competing_explanation: str = Field(min_length=3, max_length=800)


class HeterogeneityAssessmentDraft(StrictContract):
    heterogeneity_id: str = Field(pattern=r"^HET[0-9_-]+$")
    dimension: str = Field(min_length=1, max_length=200)
    finding: str = Field(min_length=5, max_length=1000)
    claim_ids: list[str] = Field(min_length=1, max_length=15)
    evidence_ids: list[str] = Field(min_length=1, max_length=30)
    status: Literal["candidate", "supported", "mixed", "refuted", "not_tested"]
    interpretation_limit: str = Field(min_length=3, max_length=800)


class ClaimEvidenceDraft(StrictContract):
    reasoning_trace: ReasoningTraceDraft | None = None
    claims: list[ClaimRecordDraft] = Field(min_length=1, max_length=30)
    mechanisms: list[MechanismAssessmentDraft] = Field(default_factory=list, max_length=12)
    heterogeneity: list[HeterogeneityAssessmentDraft] = Field(default_factory=list, max_length=15)
    limitations: list[str] = Field(min_length=1, max_length=25)
    interpretation: str = Field(min_length=5, max_length=2000)
    unknowns: list[str] = Field(default_factory=list, max_length=25)


class DeliveryConclusionDraft(StrictContract):
    conclusion_id: str = Field(pattern=r"^CON[0-9_-]+$")
    statement: str = Field(min_length=10, max_length=1200)
    claim_ids: list[str] = Field(min_length=1, max_length=12)
    evidence_ids: list[str] = Field(min_length=1, max_length=30)
    status: Literal["supported", "mixed", "limited"]
    scope_note: str = Field(min_length=3, max_length=800)


class PolicyImplicationDraft(StrictContract):
    implication_id: str = Field(pattern=r"^POL[0-9_-]+$")
    statement: str = Field(min_length=10, max_length=1200)
    audience: str = Field(min_length=1, max_length=300)
    claim_ids: list[str] = Field(min_length=1, max_length=12)
    conditions: list[str] = Field(min_length=1, max_length=12)
    risk_note: str = Field(min_length=3, max_length=800)


class DeliveryOutlineSectionDraft(StrictContract):
    section_id: str = Field(pattern=r"^SEC[0-9_-]+$")
    title: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=3, max_length=600)
    claim_ids: list[str] = Field(default_factory=list, max_length=20)
    evidence_ids: list[str] = Field(default_factory=list, max_length=30)


class AcademicOutputProfileDraft(StrictContract):
    document_type: Literal[
        "management_research_article",
        "research_report",
        "thesis_chapter",
        "literature_review",
        "policy_brief",
    ]
    research_paradigm: Literal[
        "empirical_quantitative",
        "qualitative",
        "mixed_methods",
        "optimization",
        "simulation",
        "theory_build",
        "systematic_review",
        "other",
    ]
    audience: str = Field(min_length=2, max_length=300)
    language: Literal["zh-CN", "en", "bilingual"]
    citation_style: Literal[
        "gbt7714_numeric",
        "apa7_author_date",
        "chicago_author_date",
        "journal_custom",
    ]
    journal_or_institution_requirements: list[str] = Field(
        default_factory=list, max_length=20
    )
    common_method_bias_applicability: Literal[
        "required",
        "not_applicable",
        "undetermined",
    ]


class ManuscriptSectionDraft(StrictContract):
    section_id: str = Field(pattern=r"^SEC[0-9_-]+$")
    title: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=3, max_length=600)
    body_markdown: str = Field(default="", max_length=20_000)
    claim_ids: list[str] = Field(default_factory=list, max_length=30)
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    citation_paper_ids: list[str] = Field(default_factory=list, max_length=80)
    citation_evidence_ids: list[str] = Field(default_factory=list, max_length=80)
    content_status: Literal["draft", "needs_evidence", "blocked"]
    unresolved_items: list[str] = Field(default_factory=list, max_length=20)


class LogicClosureDraft(StrictContract):
    link_id: str = Field(pattern=r"^LC[0-9_-]+$")
    research_question_refs: list[str] = Field(min_length=1, max_length=8)
    method_or_design_refs: list[str] = Field(min_length=1, max_length=15)
    claim_ids: list[str] = Field(min_length=1, max_length=20)
    conclusion_ids: list[str] = Field(min_length=1, max_length=12)
    closure_status: Literal["closed", "partial", "blocked"]
    missing_link: str = Field(default="", max_length=800)


class OutputSelfReviewIssueDraft(StrictContract):
    issue_id: str = Field(pattern=r"^OI[0-9_-]+$")
    severity: Literal["must_fix", "should_improve", "note"]
    dimension: Literal[
        "structure",
        "logic",
        "variable_consistency",
        "data_consistency",
        "citation",
        "academic_style",
        "format",
        "ethics_disclosure",
    ]
    location: str = Field(min_length=1, max_length=300)
    finding: str = Field(min_length=3, max_length=1000)
    required_action: str = Field(min_length=3, max_length=1000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)


class DeliveryDraft(StrictContract):
    reasoning_trace: ReasoningTraceDraft | None = None
    title: str = Field(min_length=3, max_length=240)
    document_profile: AcademicOutputProfileDraft | None = None
    abstract: str = Field(default="", max_length=3000)
    keywords: list[str] = Field(default_factory=list, max_length=10)
    executive_summary: str = Field(min_length=20, max_length=3000)
    conclusions: list[DeliveryConclusionDraft] = Field(min_length=1, max_length=20)
    policy_implications: list[PolicyImplicationDraft] = Field(default_factory=list, max_length=15)
    outline: list[DeliveryOutlineSectionDraft] = Field(min_length=3, max_length=20)
    manuscript_sections: list[ManuscriptSectionDraft] = Field(
        default_factory=list, max_length=20
    )
    logic_closure: list[LogicClosureDraft] = Field(default_factory=list, max_length=20)
    author_self_review: list[OutputSelfReviewIssueDraft] = Field(
        default_factory=list, max_length=40
    )
    reference_paper_ids: list[str] = Field(default_factory=list, max_length=80)
    reference_evidence_ids: list[str] = Field(default_factory=list, max_length=80)
    limitations: list[str] = Field(min_length=1, max_length=25)
    reproducibility_notes: list[str] = Field(min_length=1, max_length=20)
    disclosure: str = Field(min_length=5, max_length=1600)
    release_notes: str = Field(min_length=3, max_length=1200)
    unknowns: list[str] = Field(default_factory=list, max_length=25)
