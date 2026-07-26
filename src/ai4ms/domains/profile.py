from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DomainProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    name: str
    research_lanes: tuple[str, ...]
    method_families: tuple[str, ...]
    required_trace_fields: tuple[str, ...]


MANAGEMENT_SCIENCE_PROFILE = DomainProfile(
    key="management_science",
    name="管理科学",
    research_lanes=(
        "empirical_and_causal",
        "analytical_and_optimization",
        "predictive_and_computational",
        "behavioral_and_qualitative",
        "review_and_design_science",
    ),
    method_families=(
        "econometrics",
        "operations_research",
        "machine_learning",
        "survey_and_experiment",
        "qualitative_and_case_study",
        "evidence_synthesis",
    ),
    required_trace_fields=(
        "source_url",
        "evidence_level",
        "revision",
        "content_hash",
        "approval_status",
    ),
)
