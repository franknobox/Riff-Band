from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Callable

from pydantic import ValidationError

from ai4ms.inference.gateway import InferenceGateway, InferenceResponse, OpenAICompatibleGateway
from ai4ms.inference.structured import StructuredOutputError, validate_structured_output
from ai4ms.knowledge import KnowledgeRegistry
from ai4ms.orchestration import AO_STAGE_KEYS, OrchestrationResult, StageOrchestrator
from ai4ms.prompts.catalog import PromptCatalog
from ai4ms.runners.stata import StataPolicyScanner


class StageGenerationNotSupportedError(LookupError):
    pass


class StageGenerationOutputError(RuntimeError):
    pass


class StageContentValidationError(ValueError):
    pass


class StageGenerationService:
    def __init__(
        self,
        gateway_factory: Callable[[], InferenceGateway] | None = None,
        orchestrator: StageOrchestrator | None = None,
    ) -> None:
        self.gateway_factory = gateway_factory or OpenAICompatibleGateway
        self.orchestrator = orchestrator

    async def generate(
        self,
        project: dict[str, Any],
        stage_key: str,
        instruction: str = "",
    ) -> dict[str, Any]:
        context = self._build_context(project, stage_key)
        orchestration: OrchestrationResult | None = None
        should_orchestrate = (
            self.orchestrator is not None
            and stage_key in AO_STAGE_KEYS
            and not (
                stage_key == "literature"
                and not context.get("current_stage_content", {}).get("papers")
            )
        )
        if should_orchestrate and self.orchestrator is not None:
            try:
                orchestration = await self.orchestrator.analyze(
                    project,
                    stage_key,
                    instruction,
                    context,
                )
            except Exception as exc:
                raise StageGenerationOutputError(
                    f"AOrchestra failed for stage '{stage_key}': {exc}"
                ) from exc
            context["aorchestra_analysis"] = orchestration.prompt_context()
        prompt = PromptCatalog.get(stage_key, context)
        if prompt is None:
            raise StageGenerationNotSupportedError(
                f"model generation is not implemented for stage '{stage_key}'"
            )

        system_prompt, user_prompt = prompt.render(context, instruction)
        gateway = self.gateway_factory()
        responses: list[InferenceResponse] = []

        first = await gateway.generate(system_prompt, user_prompt)
        responses.append(first)
        try:
            draft = validate_structured_output(first.text, prompt.contract)
            validated_content = draft.model_dump(mode="json")
            self._validate_reasoning_trace(validated_content)
            self._validate_domain_references(validated_content, prompt.prompt_id, context)
        except StructuredOutputError as first_error:
            repair_prompt = f"""上一次输出未通过结构或引用约束：{first_error}

请只修复 JSON 格式、字段和值，使其符合原任务、JSON Schema 和输入中的可用 ID。
不得增加输入中不存在的事实、论文、方法或数据源。
必须补全可审计 reasoning_trace；logic_chain 每一步都要有唯一 step_id、
非空 evidence_refs、推断类型、结论、置信度和 falsifier，并保留人工决策与下一步核验。

原任务与约束：
{user_prompt[:12000]}

待修复输出：
{first.text[:12000]}"""
            repaired = await gateway.generate(system_prompt, repair_prompt)
            responses.append(repaired)
            try:
                draft = validate_structured_output(repaired.text, prompt.contract)
                validated_content = draft.model_dump(mode="json")
                self._validate_reasoning_trace(validated_content)
                self._validate_domain_references(validated_content, prompt.prompt_id, context)
            except StructuredOutputError as final_error:
                raise StageGenerationOutputError(str(final_error)) from final_error

        content = draft.model_dump(mode="json")
        if stage_key == "problem":
            content["initial_idea"] = project["initial_idea"]
        if stage_key == "analysis":
            plan_stage = next(
                (stage for stage in project.get("stages", []) if stage.get("key") == "identification"),
                {},
            )
            analysis_stage = next(
                (stage for stage in project.get("stages", []) if stage.get("key") == "analysis"),
                {},
            )
            plan = plan_stage.get("content", {})
            current_analysis = analysis_stage.get("content", {})
            content.update(
                {
                    "approved_analysis_plan_revision": plan_stage.get("revision", 0),
                    "approved_analysis_plan_hash": plan_stage.get("content_hash", ""),
                    "do_file": plan.get("stata_do_file", ""),
                    "runner_status": "not_checked",
                    "runs": current_analysis.get("runs", []),
                    "results": current_analysis.get("results", []),
                }
            )
        if stage_key == "delivery":
            evidence_stage = next(
                (stage for stage in project.get("stages", []) if stage.get("key") == "evidence"),
                {},
            )
            literature_stage = next(
                (stage for stage in project.get("stages", []) if stage.get("key") == "literature"),
                {},
            )
            papers = {
                str(item.get("paper_id")): item
                for item in literature_stage.get("content", {}).get("papers", [])
                if isinstance(item, dict) and item.get("paper_id")
            }
            selected_paper_ids = set(content.get("reference_paper_ids", []))
            content.update(
                {
                    "approved_claims": [
                        claim.get("claim_id")
                        for claim in evidence_stage.get("content", {}).get("claims", [])
                        if isinstance(claim, dict)
                        and claim.get("status") not in {"refuted", "withdrawn"}
                    ],
                    "references": [
                        {
                            key: paper.get(key)
                            for key in ("paper_id", "title", "authors", "year", "doi", "url")
                            if paper.get(key) not in (None, "", [])
                        }
                        for paper_id, paper in papers.items()
                        if paper_id in selected_paper_ids
                    ],
                    "source_evidence_revision": evidence_stage.get("revision", 0),
                    "source_evidence_hash": evidence_stage.get("content_hash", ""),
                    "exports": [],
                    "visual_report_path": "",
                    "research_package_path": "",
                }
            )
        content["generation"] = {
            "mode": "model",
            "prompt_id": prompt.prompt_id,
            "prompt_version": prompt.version,
            "model": responses[-1].model,
            "generated_at": datetime.now(UTC).isoformat(),
            "attempts": len(responses),
            "usage": self._merge_usage(responses),
        }
        if orchestration is not None:
            content["generation"]["orchestration"] = orchestration.generation_metadata()
        return content

    @staticmethod
    def _build_context(project: dict[str, Any], stage_key: str) -> dict[str, Any]:
        stages = {stage["key"]: stage for stage in project.get("stages", [])}
        context: dict[str, Any] = {
            "project_id": project["project_id"],
            "title": project["title"],
            "initial_idea": project["initial_idea"],
            "stage": stage_key,
            "current_stage_content": stages.get(stage_key, {}).get("content", {}),
        }
        if stage_key == "literature":
            problem = stages.get("problem", {})
            context["problem_revision"] = problem.get("revision", 0)
            context["problem_content"] = problem.get("content", {})
            current = stages.get("literature", {}).get("content", {})
            if current.get("papers"):
                context["current_stage_content"] = {
                    "topic_summary": current.get("topic_summary", ""),
                    "query_blocks": current.get("query_blocks", []),
                    "inclusion_criteria": current.get("inclusion_criteria", []),
                    "exclusion_criteria": current.get("exclusion_criteria", []),
                    "screening_questions": current.get("screening_questions", []),
                    **StageGenerationService._compact_literature(current),
                }
        if stage_key in {"theory", "design", "data", "identification"}:
            problem = stages.get("problem", {})
            literature = stages.get("literature", {})
            context["problem_content"] = problem.get("content", {})
            context["literature_content"] = StageGenerationService._compact_literature(
                literature.get("content", {})
            )
        if stage_key in {"design", "data"}:
            context["theory_content"] = stages.get("theory", {}).get("content", {})
        if stage_key == "design":
            goal = str(context.get("problem_content", {}).get("objective", ""))
            query = f"{project['title']} {json_text(context.get('theory_content', {}))}"
            context["method_candidates"] = KnowledgeRegistry.method_candidates(goal, query, 10)
        if stage_key == "data":
            design_content = stages.get("design", {}).get("content", {})
            context["design_content"] = design_content
            query = f"{project['title']} {json_text(design_content)}"
            context["data_source_candidates"] = KnowledgeRegistry.data_source_candidates(query, 12)
        if stage_key == "identification":
            design_content = stages.get("design", {}).get("content", {})
            data_content = stages.get("data", {}).get("content", {})
            context["design_content"] = design_content
            context["data_content"] = StageGenerationService._compact_data(data_content)
            method_ids = [
                str(item.get("method_id"))
                for item in design_content.get("method_options", [])
                if isinstance(item, dict) and item.get("method_id")
            ]
            query = f"{project['title']} {json_text(design_content)} {json_text(data_content)}"
            context["formula_candidates"] = KnowledgeRegistry.formula_candidates(query, method_ids, 14)
        if stage_key in {"analysis", "robustness"}:
            plan_stage = stages.get("identification", {})
            context["analysis_plan_revision"] = plan_stage.get("revision", 0)
            context["analysis_plan_hash"] = plan_stage.get("content_hash", "")
            context["analysis_plan_content"] = StageGenerationService._compact_analysis_plan(
                plan_stage.get("content", {})
            )
            context["data_content"] = StageGenerationService._compact_data(
                stages.get("data", {}).get("content", {})
            )
        if stage_key == "analysis":
            current = stages.get("analysis", {}).get("content", {})
            context["current_stage_content"] = {
                "readiness_summary": current.get("readiness_summary", ""),
                "preflight_checks": current.get("preflight_checks", []),
                "result_review_checks": current.get("result_review_checks", []),
                "blocking_issues": current.get("blocking_issues", []),
                "runs": StageGenerationService._compact_runs(current.get("runs", [])),
            }
            context["data_assets"] = StageGenerationService._compact_data_assets(
                project.get("data_assets", [])
            )
        if stage_key in {"data", "identification"}:
            context["data_assets"] = StageGenerationService._compact_data_assets(
                project.get("data_assets", [])
            )
        if stage_key == "robustness":
            context["analysis_runs"] = StageGenerationService._compact_runs(
                stages.get("analysis", {}).get("content", {}).get("runs", [])
            )
        if stage_key in {"evidence", "delivery"}:
            literature = stages.get("literature", {})
            context["literature_content"] = StageGenerationService._compact_literature(
                literature.get("content", {})
            )
            context["analysis_runs"] = StageGenerationService._compact_runs(
                stages.get("analysis", {}).get("content", {}).get("runs", [])
            )
            context["robustness_content"] = stages.get("robustness", {}).get("content", {})
        if stage_key == "evidence":
            context["theory_content"] = stages.get("theory", {}).get("content", {})
            context["design_content"] = stages.get("design", {}).get("content", {})
            context["data_content"] = StageGenerationService._compact_data(
                stages.get("data", {}).get("content", {})
            )
            context["evidence_artifacts"] = StageGenerationService._evidence_artifacts(stages)
        if stage_key == "delivery":
            evidence = stages.get("evidence", {})
            context["evidence_status"] = evidence.get("status", "")
            context["evidence_revision"] = evidence.get("revision", 0)
            context["evidence_hash"] = evidence.get("content_hash", "")
            context["evidence_content"] = evidence.get("content", {})
        return context

    @staticmethod
    def _compact_literature(content: dict[str, Any]) -> dict[str, Any]:
        papers = []
        for item in content.get("papers", [])[:30]:
            if not isinstance(item, dict):
                continue
            papers.append(
                {
                    "paper_id": item.get("paper_id", ""),
                    "title": item.get("title", ""),
                    "authors": item.get("authors", [])[:5],
                    "year": item.get("year", ""),
                    "doi": item.get("doi", ""),
                    "url": item.get("url", ""),
                    "abstract": str(item.get("abstract", ""))[:800],
                }
            )
        return {
            "papers": papers,
            "research_streams": content.get("research_streams", []),
            "syntheses": content.get("syntheses", []),
            "gap_candidates": content.get("gap_candidates", []),
            "coverage_limits": content.get("coverage_limits", []),
        }

    @staticmethod
    def _compact_data(content: dict[str, Any]) -> dict[str, Any]:
        return {
            "data_sources": content.get("data_sources", []),
            "variables": content.get("variables", []),
            "sample_definition": content.get("sample_definition", ""),
            "time_coverage": content.get("time_coverage", ""),
            "join_keys": content.get("join_keys", []),
            "quality_checks": content.get("quality_checks", []),
            "blocking_issues": content.get("blocking_issues", []),
            "unknowns": content.get("unknowns", []),
        }

    @staticmethod
    def _compact_analysis_plan(content: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "design_lane",
            "estimand_or_objective",
            "analysis_sample",
            "unit_of_analysis",
            "variable_roles",
            "model_specifications",
            "diagnostics",
            "analysis_steps",
            "robustness_plan",
            "stopping_conditions",
            "execution_engine",
            "code_language",
            "seed",
            "expected_outputs",
            "unknowns",
        )
        return {key: content.get(key) for key in keys}

    @staticmethod
    def _compact_runs(runs: Any) -> list[dict[str, Any]]:
        compact = []
        for run in runs[:20] if isinstance(runs, list) else []:
            if not isinstance(run, dict):
                continue
            compact.append(
                {
                    "run_id": run.get("run_id", ""),
                    "status": run.get("status", ""),
                    "reason_code": run.get("reason_code", ""),
                    "exit_code": run.get("exit_code"),
                    "do_file_sha256": run.get("do_file_sha256", ""),
                    "structured_results": run.get("structured_results", []),
                    "output_artifacts": run.get("output_artifacts", []),
                }
            )
        return compact

    @staticmethod
    def _compact_data_assets(assets: Any) -> list[dict[str, Any]]:
        compact = []
        for asset in assets[:20] if isinstance(assets, list) else []:
            if not isinstance(asset, dict):
                continue
            metadata = asset.get("metadata", {})
            compact.append(
                {
                    "asset_id": asset.get("asset_id", ""),
                    "original_name": asset.get("original_name", ""),
                    "size_bytes": asset.get("size_bytes", 0),
                    "sha256": asset.get("sha256", ""),
                    "row_count": metadata.get("row_count", 0),
                    "column_count": metadata.get("column_count", 0),
                    "columns": metadata.get("columns", [])[:100],
                }
            )
        return compact

    @staticmethod
    def _evidence_artifacts(stages: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        literature = stages.get("literature", {}).get("content", {})
        for paper in literature.get("papers", [])[:50]:
            if isinstance(paper, dict) and paper.get("paper_id"):
                artifacts.append(
                    {
                        "artifact_id": str(paper["paper_id"]),
                        "kind": "paper",
                        "allowed_evidence_types": ["paper"],
                        "supports_allowed": True,
                        "title": str(paper.get("title", ""))[:300],
                    }
                )
        data = stages.get("data", {}).get("content", {})
        for source in data.get("data_sources", [])[:20]:
            if isinstance(source, dict) and source.get("source_id"):
                artifacts.append(
                    {
                        "artifact_id": str(source["source_id"]),
                        "kind": "data",
                        "allowed_evidence_types": ["data"],
                        "supports_allowed": False,
                        "access_status": source.get("access_status", "unknown"),
                    }
                )
        analysis = stages.get("analysis", {}).get("content", {})
        for run in StageGenerationService._compact_runs(analysis.get("runs", [])):
            run_id = str(run.get("run_id", ""))
            if not run_id:
                continue
            has_results = bool(run.get("structured_results")) and run.get("status") == "succeeded"
            artifacts.append(
                {
                    "artifact_id": run_id,
                    "kind": "run",
                    "run_id": run_id,
                    "status": run.get("status", ""),
                    "allowed_evidence_types": (
                        ["estimate", "proof", "simulation", "experiment", "qualitative_excerpt"]
                        if has_results
                        else ["reviewer_note"]
                    ),
                    "supports_allowed": has_results,
                }
            )
            if has_results:
                for output in run.get("output_artifacts", [])[:30]:
                    path = output.get("path") if isinstance(output, dict) else output
                    if path:
                        artifacts.append(
                            {
                                "artifact_id": str(path),
                                "kind": "run_output",
                                "run_id": run_id,
                                "allowed_evidence_types": ["estimate", "proof", "simulation", "experiment"],
                                "supports_allowed": True,
                            }
                        )
        return artifacts

    @classmethod
    def validate_stage_content(
        cls,
        project: dict[str, Any],
        stage_key: str,
        content: dict[str, Any],
    ) -> None:
        context = cls._build_context(project, stage_key)
        prompt = PromptCatalog.get(stage_key, context)
        if prompt is None:
            raise StageContentValidationError(f"stage '{stage_key}' has no validation contract")
        payload = {key: content[key] for key in prompt.contract.model_fields if key in content}
        try:
            validated = prompt.contract.model_validate(payload).model_dump(mode="json")
            generation = content.get("generation", {})
            is_v2_model_draft = (
                isinstance(generation, dict)
                and str(generation.get("prompt_version", "")).startswith("2.")
            )
            if content.get("reasoning_trace") is not None or is_v2_model_draft:
                cls._validate_reasoning_trace(validated)
            cls._validate_domain_references(validated, prompt.prompt_id, context)
        except (ValidationError, StructuredOutputError) as exc:
            raise StageContentValidationError(str(exc)) from exc

    @staticmethod
    def _validate_reasoning_trace(content: dict[str, Any]) -> None:
        trace = content.get("reasoning_trace")
        if not isinstance(trace, dict):
            raise StructuredOutputError("reasoning_trace is required for Prompt Engineering 2.0 drafts")
        if not str(trace.get("problem_framing", "")).strip():
            raise StructuredOutputError("reasoning_trace.problem_framing must not be empty")

        logic_chain = trace.get("logic_chain")
        if not isinstance(logic_chain, list) or not logic_chain:
            raise StructuredOutputError("reasoning_trace.logic_chain requires at least one auditable step")
        step_ids: set[str] = set()
        for index, step in enumerate(logic_chain, start=1):
            if not isinstance(step, dict):
                raise StructuredOutputError(f"reasoning_trace.logic_chain[{index}] must be an object")
            step_id = str(step.get("step_id", "")).strip()
            if not step_id:
                raise StructuredOutputError(f"reasoning_trace.logic_chain[{index}] has no step_id")
            if step_id in step_ids:
                raise StructuredOutputError(f"duplicate reasoning_trace step_id: {step_id}")
            step_ids.add(step_id)
            evidence_refs = step.get("evidence_refs")
            if not isinstance(evidence_refs, list) or not any(
                str(item).strip() for item in evidence_refs
            ):
                raise StructuredOutputError(
                    f"reasoning_trace step {step_id} requires at least one evidence_ref"
                )
            if not str(step.get("conclusion", "")).strip():
                raise StructuredOutputError(f"reasoning_trace step {step_id} has no conclusion")
            if not str(step.get("falsifier", "")).strip():
                raise StructuredOutputError(f"reasoning_trace step {step_id} has no falsifier")

        human_decisions = trace.get("human_decisions")
        if not isinstance(human_decisions, list) or not any(
            str(item).strip() for item in human_decisions
        ):
            raise StructuredOutputError("reasoning_trace.human_decisions requires at least one item")
        next_verifications = trace.get("next_verifications")
        if not isinstance(next_verifications, list) or not any(
            str(item).strip() for item in next_verifications
        ):
            raise StructuredOutputError("reasoning_trace.next_verifications requires at least one item")

    @staticmethod
    def _validate_domain_references(
        content: dict[str, Any],
        prompt_id: str,
        context: dict[str, Any],
    ) -> None:
        if prompt_id in {"ai4ms.stage.literature-synthesis", "ai4ms.stage.theory"}:
            allowed = {
                str(item.get("paper_id"))
                for item in context.get("literature_content", context.get("current_stage_content", {})).get("papers", [])
                if isinstance(item, dict) and item.get("paper_id")
            }
            referenced = set(StageGenerationService._collect_values(content, "paper_ids"))
            invalid = sorted(referenced - allowed)
            if invalid:
                raise StructuredOutputError(f"output references unknown paper_ids: {invalid[:8]}")
        if prompt_id == "ai4ms.stage.design":
            allowed = {str(item.get("method_id")) for item in context.get("method_candidates", [])}
            referenced = set(StageGenerationService._collect_values(content, "method_id"))
            referenced.add(str(content.get("primary_method_id", "")))
            invalid = sorted(item for item in referenced - allowed if item)
            if invalid:
                raise StructuredOutputError(f"output references methods outside the registry shortlist: {invalid[:8]}")
        if prompt_id == "ai4ms.stage.data":
            allowed = {str(item.get("source_id")) for item in context.get("data_source_candidates", [])}
            referenced = set(StageGenerationService._collect_values(content, "source_id"))
            referenced.update(StageGenerationService._collect_values(content, "source_ids"))
            invalid = sorted(item for item in referenced - allowed if item)
            if invalid:
                raise StructuredOutputError(f"output references data sources outside the registry shortlist: {invalid[:8]}")
        if prompt_id == "ai4ms.stage.identification":
            design = context.get("design_content", {})
            allowed_methods = {
                str(item.get("method_id"))
                for item in design.get("method_options", [])
                if isinstance(item, dict) and item.get("method_id")
            }
            allowed_formulas = {
                str(item.get("formula_id"))
                for item in context.get("formula_candidates", [])
                if isinstance(item, dict) and item.get("formula_id")
            }
            methods = set(StageGenerationService._collect_values(content, "method_id"))
            formulas = set(StageGenerationService._collect_values(content, "formula_id"))
            invalid_methods = sorted(item for item in methods - allowed_methods if item)
            invalid_formulas = sorted(item for item in formulas - allowed_formulas if item)
            if invalid_methods:
                raise StructuredOutputError(f"output references methods outside the approved design: {invalid_methods[:8]}")
            if invalid_formulas:
                raise StructuredOutputError(f"output references formulas outside the registry shortlist: {invalid_formulas[:8]}")
            allowed_specs = {
                str(item.get("specification_id"))
                for item in content.get("model_specifications", [])
                if isinstance(item, dict) and item.get("specification_id")
            }
            linked_specs = set(StageGenerationService._collect_values(content, "specification_ids"))
            invalid_specs = sorted(item for item in linked_specs - allowed_specs if item)
            if invalid_specs:
                raise StructuredOutputError(f"analysis steps reference unknown specification_ids: {invalid_specs[:8]}")
            engine = content.get("execution_engine")
            do_file = str(content.get("stata_do_file") or "")
            if engine == "stata" and not do_file.strip():
                raise StructuredOutputError("execution_engine=stata requires a reviewable stata_do_file")
            if engine != "stata" and do_file.strip():
                raise StructuredOutputError("stata_do_file must be empty when execution_engine is not stata")
            policy_issues = StataPolicyScanner.scan(do_file) if do_file else []
            if policy_issues:
                codes = sorted({str(item.get("code")) for item in policy_issues})
                raise StructuredOutputError(f"stata_do_file violates deterministic policy: {codes}")
        if prompt_id == "ai4ms.stage.analysis":
            expected_engine = context.get("analysis_plan_content", {}).get("execution_engine")
            if content.get("execution_engine") != expected_engine:
                raise StructuredOutputError(
                    f"run preparation engine must match approved analysis plan: {expected_engine}"
                )
        if prompt_id == "ai4ms.stage.robustness":
            plan_specs = {
                str(item.get("specification_id"))
                for item in context.get("analysis_plan_content", {}).get("model_specifications", [])
                if isinstance(item, dict) and item.get("specification_id")
            }
            runs = {
                str(item.get("run_id")): item
                for item in context.get("analysis_runs", [])
                if isinstance(item, dict) and item.get("run_id")
            }
            linked_specs = set(StageGenerationService._collect_values(content, "specification_ids"))
            linked_runs = set(StageGenerationService._collect_values(content, "run_ids"))
            invalid_specs = sorted(item for item in linked_specs - plan_specs if item)
            invalid_runs = sorted(item for item in linked_runs - set(runs) if item)
            if invalid_specs:
                raise StructuredOutputError(f"robustness checks reference unknown specification_ids: {invalid_specs[:8]}")
            if invalid_runs:
                raise StructuredOutputError(f"robustness checks reference unknown run_ids: {invalid_runs[:8]}")
            evidence_statuses = {"passed", "failed", "inconclusive"}
            for check in content.get("robustness_matrix", []):
                if not isinstance(check, dict) or check.get("status") not in evidence_statuses:
                    continue
                referenced = [runs.get(str(run_id), {}) for run_id in check.get("required_run_ids", [])]
                if not referenced or not all(run.get("structured_results") for run in referenced):
                    raise StructuredOutputError(
                        f"robustness check {check.get('check_id', '')} claims a result without structured run evidence"
                    )
        if prompt_id == "ai4ms.stage.evidence":
            StageGenerationService._validate_claim_evidence(content, context)
        if prompt_id == "ai4ms.stage.delivery":
            StageGenerationService._validate_delivery(content, context)

    @staticmethod
    def _validate_claim_evidence(content: dict[str, Any], context: dict[str, Any]) -> None:
        artifact_registry = {
            str(item.get("artifact_id")): item
            for item in context.get("evidence_artifacts", [])
            if isinstance(item, dict) and item.get("artifact_id")
        }
        method_ids = {
            str(item.get("method_id"))
            for item in context.get("design_content", {}).get("method_options", [])
            if isinstance(item, dict) and item.get("method_id")
        }
        robustness = {
            str(item.get("check_id")): item
            for item in context.get("robustness_content", {}).get("robustness_matrix", [])
            if isinstance(item, dict) and item.get("check_id")
        }
        adverse_robustness = {
            check_id
            for check_id, item in robustness.items()
            if item.get("status") in {"failed", "blocked", "inconclusive", "not_run"}
        }
        claim_ids: set[str] = set()
        evidence_registry: dict[str, dict[str, Any]] = {}
        for claim in content.get("claims", []):
            claim_id = str(claim.get("claim_id", ""))
            if claim_id in claim_ids:
                raise StructuredOutputError(f"duplicate claim_id: {claim_id}")
            claim_ids.add(claim_id)
            evidence = claim.get("evidence", [])
            support_items = []
            for item in evidence:
                evidence_id = str(item.get("evidence_id", ""))
                previous = evidence_registry.get(evidence_id)
                if previous is not None and previous != item:
                    raise StructuredOutputError(f"evidence_id {evidence_id} has conflicting records")
                evidence_registry[evidence_id] = item
                artifact_id = str(item.get("artifact_id", ""))
                artifact = artifact_registry.get(artifact_id)
                if artifact is None:
                    raise StructuredOutputError(f"claim {claim_id} references unknown artifact_id: {artifact_id}")
                if item.get("evidence_type") not in artifact.get("allowed_evidence_types", []):
                    raise StructuredOutputError(
                        f"artifact {artifact_id} cannot be used as {item.get('evidence_type')} evidence"
                    )
                if item.get("direction") == "supports":
                    if not artifact.get("supports_allowed"):
                        raise StructuredOutputError(f"artifact {artifact_id} cannot support a scientific claim")
                    support_items.append(item)
                run_id = str(item.get("run_id") or "")
                if run_id and run_id not in {
                    str(run.get("run_id")) for run in context.get("analysis_runs", [])
                }:
                    raise StructuredOutputError(f"evidence {evidence_id} references unknown run_id: {run_id}")
                method_id = str(item.get("method_id") or "")
                if method_id and method_id not in method_ids:
                    raise StructuredOutputError(f"evidence {evidence_id} references unknown method_id: {method_id}")
            local_evidence = {str(item.get("evidence_id")): item for item in evidence}
            for evidence_id in claim.get("counterevidence", []):
                if evidence_id not in local_evidence:
                    raise StructuredOutputError(f"claim {claim_id} references unknown counterevidence: {evidence_id}")
                if local_evidence[evidence_id].get("direction") not in {"contradicts", "qualifies"}:
                    raise StructuredOutputError(f"counterevidence {evidence_id} must contradict or qualify")
            unknown_checks = set(claim.get("robustness_check_ids", [])) - set(robustness)
            if unknown_checks:
                raise StructuredOutputError(f"claim {claim_id} references unknown robustness checks: {sorted(unknown_checks)}")
            if claim.get("status") == "supported" and not support_items:
                raise StructuredOutputError(f"supported claim {claim_id} has no supporting evidence")
            if claim.get("confidence") == "high":
                if (
                    not support_items
                    or adverse_robustness
                    or any(item.get("strength") != "strong" for item in support_items)
                ):
                    raise StructuredOutputError(
                        f"claim {claim_id} cannot be high confidence with adverse robustness or non-strong evidence"
                    )
            if claim.get("claim_type") != "literature_synthesis" and adverse_robustness:
                missing = adverse_robustness - set(claim.get("robustness_check_ids", []))
                if missing:
                    raise StructuredOutputError(
                        f"claim {claim_id} omits adverse robustness checks: {sorted(missing)}"
                    )

        mechanism_ids = {
            str(item.get("mechanism_id"))
            for item in content.get("mechanisms", [])
            if isinstance(item, dict) and item.get("mechanism_id")
        }
        all_evidence_ids = set(evidence_registry)
        for claim in content.get("claims", []):
            unknown = set(claim.get("mechanism_ids", [])) - mechanism_ids
            if unknown:
                raise StructuredOutputError(f"claim {claim.get('claim_id')} references unknown mechanisms: {sorted(unknown)}")
        for section_name in ("mechanisms", "heterogeneity"):
            for item in content.get(section_name, []):
                unknown_claims = set(item.get("claim_ids", [])) - claim_ids
                unknown_evidence = set(item.get("evidence_ids", [])) - all_evidence_ids
                if unknown_claims:
                    raise StructuredOutputError(f"{section_name} references unknown claims: {sorted(unknown_claims)}")
                if unknown_evidence:
                    raise StructuredOutputError(f"{section_name} references unknown evidence: {sorted(unknown_evidence)}")

    @staticmethod
    def _validate_delivery(content: dict[str, Any], context: dict[str, Any]) -> None:
        if context.get("evidence_status") != "approved":
            raise StructuredOutputError("delivery requires a G4-approved evidence stage")
        claims = {
            str(item.get("claim_id")): item
            for item in context.get("evidence_content", {}).get("claims", [])
            if isinstance(item, dict) and item.get("claim_id")
        }
        usable_claims = {
            claim_id: claim
            for claim_id, claim in claims.items()
            if claim.get("status") not in {"refuted", "withdrawn"}
        }
        paper_ids = {
            str(item.get("paper_id"))
            for item in context.get("literature_content", {}).get("papers", [])
            if isinstance(item, dict) and item.get("paper_id")
        }
        for conclusion in content.get("conclusions", []):
            conclusion_id = conclusion.get("conclusion_id", "")
            referenced_claims = set(conclusion.get("claim_ids", []))
            unknown_claims = referenced_claims - set(usable_claims)
            if unknown_claims:
                raise StructuredOutputError(
                    f"conclusion {conclusion_id} references unavailable claims: {sorted(unknown_claims)}"
                )
            allowed_evidence = {
                str(evidence.get("evidence_id"))
                for claim_id in referenced_claims
                for evidence in usable_claims[claim_id].get("evidence", [])
                if isinstance(evidence, dict) and evidence.get("evidence_id")
            }
            unknown_evidence = set(conclusion.get("evidence_ids", [])) - allowed_evidence
            if unknown_evidence:
                raise StructuredOutputError(
                    f"conclusion {conclusion_id} references evidence outside its claims: {sorted(unknown_evidence)}"
                )
            if conclusion.get("status") == "supported" and any(
                usable_claims[claim_id].get("status") != "supported" for claim_id in referenced_claims
            ):
                raise StructuredOutputError(
                    f"conclusion {conclusion_id} cannot be supported by candidate or mixed claims"
                )
        for item in content.get("policy_implications", []):
            unknown = set(item.get("claim_ids", [])) - set(usable_claims)
            if unknown:
                raise StructuredOutputError(f"policy implication references unavailable claims: {sorted(unknown)}")
        all_evidence_ids = {
            str(evidence.get("evidence_id"))
            for claim in usable_claims.values()
            for evidence in claim.get("evidence", [])
            if isinstance(evidence, dict) and evidence.get("evidence_id")
        }
        for section in content.get("outline", []):
            unknown_claims = set(section.get("claim_ids", [])) - set(usable_claims)
            unknown_evidence = set(section.get("evidence_ids", [])) - all_evidence_ids
            if unknown_claims or unknown_evidence:
                raise StructuredOutputError(
                    f"outline section {section.get('section_id')} contains unknown claim/evidence IDs"
                )
        unknown_papers = set(content.get("reference_paper_ids", [])) - paper_ids
        if unknown_papers:
            raise StructuredOutputError(f"delivery references unknown paper_ids: {sorted(unknown_papers)}")

    @staticmethod
    def _collect_values(value: Any, key_suffix: str) -> list[str]:
        found: list[str] = []
        if isinstance(value, dict):
            for key, item in value.items():
                if key == key_suffix or key.endswith(f"_{key_suffix}"):
                    if isinstance(item, list):
                        found.extend(str(entry) for entry in item)
                    elif item:
                        found.append(str(item))
                else:
                    found.extend(StageGenerationService._collect_values(item, key_suffix))
        elif isinstance(value, list):
            for item in value:
                found.extend(StageGenerationService._collect_values(item, key_suffix))
        return found

    @staticmethod
    def _merge_usage(responses: list[InferenceResponse]) -> dict[str, int]:
        keys = ("input_tokens", "output_tokens", "total_tokens", "call_count")
        return {
            key: sum(int(response.usage.get(key, 0) or 0) for response in responses)
            for key in keys
        }


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)[:12000]
