from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ai4ms.inference.gateway import (
    InferenceGateway,
    OpenAICompatibleGateway,
)
from ai4ms.inference.structured import StructuredOutputError, validate_structured_output
from ai4ms.reporting import build_ai_report_envelope
from ai4ms.services.models import KnowledgeCandidateInput, KnowledgeEvaluationRequest


class CandidateAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    score: int = Field(ge=0, le=100)
    rationale: str = Field(min_length=1, max_length=1000)
    missing_information: list[str] = Field(default_factory=list, max_length=8)


class KnowledgeAssessmentContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    methods: list[CandidateAssessment] = Field(default_factory=list)
    formulas: list[CandidateAssessment] = Field(default_factory=list)
    summary: str = Field(default="", max_length=2000)


class KnowledgeEvaluationOutputError(RuntimeError):
    pass


class KnowledgeEvaluationService:
    def __init__(
        self,
        projects_dir: str | Path,
        gateway_factory: Callable[[], InferenceGateway] | None = None,
    ) -> None:
        self.projects_dir = Path(projects_dir)
        self.gateway_factory = gateway_factory or self._default_gateway

    @staticmethod
    def _default_gateway() -> InferenceGateway:
        model = os.getenv(
            "AI4MS_KNOWLEDGE_EVAL_MODEL",
            "deepseek-v4-flash",
        ).strip()
        return OpenAICompatibleGateway(model=model or None)

    def load(self, project: dict[str, Any]) -> dict[str, Any]:
        path = self._artifact_path(str(project["project_id"]))
        if not path.exists():
            return self._empty(project, "not_evaluated")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._empty(project, "invalid")
        if not isinstance(payload, dict):
            return self._empty(project, "invalid")
        payload["status"] = (
            "current"
            if payload.get("context_hash") == self.context_hash(project)
            else "stale"
        )
        return payload

    async def evaluate(
        self,
        project: dict[str, Any],
        request: KnowledgeEvaluationRequest,
    ) -> dict[str, Any]:
        context = self._project_context(project)
        system_prompt = (
            "你是管理科学研究方法审核者。请比较候选方法和公式与当前课题的适配性。"
            "分数是基于当前输入的相对适配判断，不是成功概率或统计显著性。"
            "不得补造数据、识别条件或已满足的假设。缺少信息必须写入 missing_information。"
            "必须逐一返回输入中的每个 candidate_id，不得漏项、改写 ID 或增加输入之外的 ID。"
            "只输出符合给定 JSON 结构的对象。"
        )
        gateway = self.gateway_factory()
        batch_size = max(
            2,
            min(
                int(os.getenv("AI4MS_KNOWLEDGE_EVAL_BATCH_SIZE", "16")),
                20,
            ),
        )
        compact_context = self._compact_prompt_context(context)
        (methods, method_meta), (formulas, formula_meta) = await asyncio.gather(
            self._evaluate_candidates(
                gateway,
                system_prompt,
                compact_context,
                "methods",
                request.methods,
                batch_size,
            ),
            self._evaluate_candidates(
                gateway,
                system_prompt,
                compact_context,
                "formulas",
                request.formulas,
                batch_size,
            ),
        )
        summaries = [
            item
            for item in [
                *method_meta["summaries"],
                *formula_meta["summaries"],
            ]
            if item
        ]
        models = list(
            dict.fromkeys(
                [
                    *method_meta["models"],
                    *formula_meta["models"],
                ]
            )
        )
        payload = {
            "evaluation_id": f"eval_{uuid4().hex[:12]}",
            "project_id": project["project_id"],
            "status": "current",
            "context_hash": self.context_hash(project),
            "model": " + ".join(models),
            "evaluated_at": datetime.now(UTC).isoformat(),
            "summary": "\n".join(dict.fromkeys(summaries))[:2000],
            "methods": methods,
            "formulas": formulas,
            "usage": self._merge_usage(
                [
                    *method_meta["usage"],
                    *formula_meta["usage"],
                ]
            ),
        }
        payload["ai_report"] = build_ai_report_envelope(
            project_id=str(project["project_id"]),
            stage_key="design",
            content={
                "executive_summary": payload["summary"]
                or "方法与公式候选适配性评估，等待研究者审核。",
                "method_ids": [
                    item["candidate_id"] for item in methods
                ],
                "formula_ids": [
                    item["candidate_id"] for item in formulas
                ],
                "reasoning_trace": {
                    "problem_framing": "比较候选方法与公式对当前管理科学课题的相对适配性。",
                    "logic_chain": [],
                    "assumptions": [],
                    "alternatives": [
                        "保留低分候选作为敏感性或替代设计，需人工判断。"
                    ],
                    "uncertainties": sorted(
                        {
                            missing
                            for item in [*methods, *formulas]
                            for missing in item.get("missing_information", [])
                        }
                    ),
                    "human_decisions": [
                        "研究者决定主方法、备选方法、公式和失败退出规则。"
                    ],
                    "next_verifications": [
                        "逐项核验方法假设、数据可得性和公式符号定义。"
                    ],
                },
            },
            prompt_id="ai4ms.knowledge.evaluation",
            prompt_version="1.0.0",
            model=str(payload["model"] or "unknown"),
            generated_at=payload["evaluated_at"],
            evidence_library=_evidence_library(project),
        )
        path = self._artifact_path(str(project["project_id"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(path)
        return payload

    async def _evaluate_candidates(
        self,
        gateway: InferenceGateway,
        system_prompt: str,
        context: dict[str, Any],
        kind: Literal["methods", "formulas"],
        candidates: list[KnowledgeCandidateInput],
        batch_size: int,
    ) -> tuple[list[dict[str, Any]], dict[str, list[Any]]]:
        if not candidates:
            return [], {"models": [], "summaries": [], "usage": []}

        completed: dict[str, dict[str, Any]] = {}
        models: list[str] = []
        summaries: list[str] = []
        usage: list[dict[str, Any]] = []
        for start in range(0, len(candidates), batch_size):
            batch = candidates[start : start + batch_size]
            pending = list(batch)
            last_error = ""
            for attempt in range(2):
                payload = {
                    "task": (
                        f"评估本批全部候选{('方法' if kind == 'methods' else '公式')}，"
                        "返回 0-100 整数分数、简短理由和缺失信息。"
                    ),
                    "candidate_kind": kind,
                    "required_candidate_ids": [
                        item.candidate_id for item in pending
                    ],
                    "project_context": context,
                    "methods": (
                        [item.model_dump() for item in pending]
                        if kind == "methods"
                        else []
                    ),
                    "formulas": (
                        [item.model_dump() for item in pending]
                        if kind == "formulas"
                        else []
                    ),
                    "repair_instruction": (
                        ""
                        if attempt == 0
                        else (
                            "上一次响应漏评或格式无效。"
                            "本次只返回 required_candidate_ids 中仍缺失的候选。"
                        )
                    ),
                    "output_schema": KnowledgeAssessmentContract.model_json_schema(),
                }
                response = await gateway.generate(
                    system_prompt,
                    json.dumps(payload, ensure_ascii=False),
                )
                models.append(response.model)
                usage.append(response.usage)
                try:
                    assessed = validate_structured_output(
                        response.text,
                        KnowledgeAssessmentContract,
                    )
                except StructuredOutputError as exc:
                    last_error = str(exc)
                    continue

                assessments = (
                    assessed.methods if kind == "methods" else assessed.formulas
                )
                validated = self._validated_assessments(assessments, pending)
                for item in validated:
                    completed[item["candidate_id"]] = item
                if assessed.summary:
                    summaries.append(assessed.summary)
                pending = [
                    item
                    for item in pending
                    if item.candidate_id not in completed
                ]
                if not pending:
                    break

            if pending:
                missing = ", ".join(item.candidate_id for item in pending)
                detail = f"; last error: {last_error}" if last_error else ""
                raise KnowledgeEvaluationOutputError(
                    f"model did not evaluate required {kind}: {missing}{detail}"
                )

        ordered = [completed[item.candidate_id] for item in candidates]
        return ordered, {
            "models": models,
            "summaries": summaries,
            "usage": usage,
        }

    @staticmethod
    def _validated_assessments(
        assessments: list[CandidateAssessment],
        candidates: list[KnowledgeCandidateInput],
    ) -> list[dict[str, Any]]:
        allowed = {item.candidate_id for item in candidates}
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for assessment in assessments:
            if assessment.candidate_id not in allowed or assessment.candidate_id in seen:
                continue
            seen.add(assessment.candidate_id)
            result.append(assessment.model_dump())
        return result

    @staticmethod
    def context_hash(project: dict[str, Any]) -> str:
        context = KnowledgeEvaluationService._project_context(project)
        encoded = json.dumps(
            context, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _project_context(project: dict[str, Any]) -> dict[str, Any]:
        stage_keys = {"problem", "literature", "theory", "design", "data"}
        return {
            "title": project.get("title", ""),
            "initial_idea": project.get("initial_idea", ""),
            "stages": [
                {
                    "key": stage.get("key"),
                    "revision": stage.get("revision", 0),
                    "content": stage.get("content", {}),
                }
                for stage in project.get("stages", [])
                if stage.get("key") in stage_keys
            ],
        }

    @classmethod
    def _compact_prompt_context(
        cls,
        value: Any,
        depth: int = 0,
    ) -> Any:
        if depth >= 5:
            return "[内容层级已截断]"
        if isinstance(value, str):
            return value[:3000]
        if isinstance(value, list):
            return [
                cls._compact_prompt_context(item, depth + 1)
                for item in value[:12]
            ]
        if isinstance(value, dict):
            return {
                str(key): cls._compact_prompt_context(item, depth + 1)
                for key, item in list(value.items())[:40]
                if key not in {"logs", "stata_do_file"}
            }
        return value

    @staticmethod
    def _merge_usage(items: list[dict[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for item in items:
            for key, value in item.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    result[key] = result.get(key, 0) + value
        result["batch_calls"] = len(items)
        return result

    def _artifact_path(self, project_id: str) -> Path:
        return (
            self.projects_dir
            / project_id
            / "artifacts"
            / "knowledge"
            / "evaluation.json"
        )

    @staticmethod
    def _empty(
        project: dict[str, Any],
        status: Literal["not_evaluated", "invalid"],
    ) -> dict[str, Any]:
        return {
            "evaluation_id": "",
            "project_id": project["project_id"],
            "status": status,
            "context_hash": KnowledgeEvaluationService.context_hash(project),
            "model": "",
            "evaluated_at": "",
            "summary": "",
            "methods": [],
            "formulas": [],
            "usage": {},
            "ai_report": None,
        }


def _evidence_library(project: dict[str, Any]) -> list[dict[str, Any]]:
    literature = next(
        (
            stage
            for stage in project.get("stages", [])
            if stage.get("key") == "literature"
        ),
        {},
    )
    content = literature.get("content", {})
    if not isinstance(content, dict):
        return []
    return [
        item
        for item in content.get("evidence_library", [])
        if isinstance(item, dict)
    ]
