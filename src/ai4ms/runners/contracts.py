from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StructuredResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: str = Field(pattern=r"^RES[0-9A-Za-z_-]+$")
    kind: Literal["estimate", "diagnostic", "test", "summary"]
    specification_id: str = Field(default="", max_length=120)
    term: str = Field(default="", max_length=300)
    label: str = Field(default="", max_length=1000)
    estimate: float | None = None
    std_error: float | None = Field(default=None, ge=0)
    statistic: float | None = None
    p_value: float | None = Field(default=None, ge=0, le=1)
    ci_lower: float | None = None
    ci_upper: float | None = None
    sample_size: int | None = Field(default=None, ge=0)
    status: Literal["observed", "passed", "failed", "inconclusive"] = "observed"
    unit: str = Field(default="", max_length=80)
    source_file: str = Field(default="structured_results.csv", max_length=240)

    @field_validator("estimate", "std_error", "statistic", "p_value", "ci_lower", "ci_upper")
    @classmethod
    def finite_numbers(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("structured result numbers must be finite")
        return value


class BundleArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=500)
    size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ResultBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(pattern=r"^run_[0-9A-Za-z_-]+$")
    engine: Literal["stata"] = "stata"
    status: Literal["succeeded", "failed", "blocked", "canceled"]
    reason_code: str
    exit_code: int | None = None
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float | None = Field(default=None, ge=0)
    input_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    do_file_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    data_signature: str = ""
    runner: dict[str, Any] = Field(default_factory=dict)
    structured_results: list[StructuredResult] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    figures: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    artifacts: list[BundleArtifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    bundle_signature: str = Field(default="", pattern=r"^(|[a-f0-9]{64})$")


class RunBundleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(pattern=r"^run_[0-9A-Za-z_-]+$")
    project_id: str = Field(min_length=1, max_length=120)
    input_filename: Literal["input.dta"] = "input.dta"
    input_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    do_file_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    timeout_seconds: int = Field(ge=1, le=7200)
    analysis_plan_revision: int = Field(ge=1)
    analysis_plan_hash: str = Field(min_length=1, max_length=128)
    seed: int | None = Field(default=None, ge=0)
    parameters: dict[str, Any] = Field(default_factory=dict)
    bundle_signature: str = Field(default="", pattern=r"^(|[a-f0-9]{64})$")
