from __future__ import annotations

import json
import sqlite3
import time

from fastapi.testclient import TestClient

from ai4ms.api.app import create_app
from ai4ms.services.stage_generation import StageGenerationService


class _FakeStageGeneration:
    async def generate(self, project: dict, stage_key: str, instruction: str = "") -> dict:
        return {
            "initial_idea": project["initial_idea"],
            "research_object": "platform firms",
            "generation": {
                "mode": "model",
                "prompt_id": f"test.{stage_key}",
                "prompt_version": "test",
                "model": "fake-model",
                "instruction": instruction,
            },
        }


class _FakeLiteratureSearch:
    async def search(self, project_id: str, stage_content: dict, request) -> dict:
        assert project_id
        assert stage_content["query_blocks"]
        return {
            "search_id": "search_api_test",
            "searched_at": "2026-07-21T00:00:00+00:00",
            "status": "complete",
            "queries": ["AI adoption"],
            "backends": list(request.backends),
            "counts": {"identified": 2, "deduplicated": 1},
            "papers": [{"paper_id": "paper_a", "title": "Paper A"}],
            "source_runs": [{"backend": "openalex", "success": True, "record_count": 1}],
            "snapshot_path": "artifacts/literature/search_api_test.json",
        }


class _FakeAnalysisRunner:
    def status(self) -> dict:
        return {
            "available": True,
            "engine": "stata",
            "mode": "batch",
            "executable_name": "fake-stata",
            "version": "19",
            "edition": "MP",
            "license_mode": "user_byol",
            "license_confirmed": True,
            "max_concurrency": 1,
            "reason": "",
        }

    def preflight(self, project: dict, project_dir, request) -> dict:
        return {
            "status": "ready",
            "reason_code": "ready",
            "analysis_plan_revision": next(stage for stage in project["stages"] if stage["key"] == "identification")["revision"],
            "input_artifact_path": request.input_artifact_path,
            "checks": {"gate_passed": True},
            "issues": [],
        }

    async def submit(self, project: dict, project_dir, request, run_id: str | None = None) -> dict:
        resolved_run_id = run_id or "run_api_test"
        run = {
            "run_id": resolved_run_id,
            "status": "succeeded",
            "reason_code": "completed",
            "requested_by": request.requested_by,
            "analysis_plan_revision": next(stage for stage in project["stages"] if stage["key"] == "identification")["revision"],
            "analysis_plan_hash": "plan_hash",
            "do_file_sha256": "a" * 64,
            "runner_profile": self.status(),
            "preflight": self.preflight(project, project_dir, request),
            "exit_code": 0,
            "data_signature": "test-signature",
            "structured_results": [],
            "output_artifacts": [{"path": "artifacts/runs/run_api_test/results.csv", "sha256": "b" * 64}],
            "manifest_path": f"artifacts/runs/{resolved_run_id}/manifest.json",
        }
        manifest = project_dir / run["manifest_path"]
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(run), encoding="utf-8")
        return run

    async def cancel(self, _run_id: str) -> bool:
        return False


def _create_project(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/projects",
        json={
            "title": "AI adoption and firm innovation",
            "initial_idea": "How does AI adoption affect firm innovation?",
        },
    )
    assert response.status_code == 201
    return response.json()


def _approve(client: TestClient, project_id: str, stage_key: str) -> dict:
    project = client.get(f"/api/v1/projects/{project_id}").json()
    current = next(stage for stage in project["stages"] if stage["key"] == stage_key)
    current_content = current.get("content", {})
    content = _valid_gate_content(project, stage_key)
    content.update(
        {
            key: value
            for key, value in current_content.items()
            if key not in content or value not in ("", [], {}, None)
        }
    )
    updated = client.put(
        f"/api/v1/projects/{project_id}/stages/{stage_key}",
        json={"content": content, "change_reason": "Prepare valid gate fixture"},
    )
    assert updated.status_code == 200
    updated_project = updated.json()
    updated_stage = next(
        stage for stage in updated_project["stages"] if stage["key"] == stage_key
    )
    workspace = {
        **updated_stage.get("content", {}).get("_workspace", {}),
        "human_confirmed": True,
    }
    confirmed = client.patch(
        f"/api/v1/projects/{project_id}/stages/{stage_key}/workspace",
        json={
            "workspace": workspace,
            "expected_revision": updated_stage["revision"],
            "change_reason": "Persist human confirmation for gate fixture",
        },
    )
    assert confirmed.status_code == 200
    response = client.post(
        f"/api/v1/projects/{project_id}/stages/{stage_key}/decisions",
        json={"decision": "approve", "reason": "Reviewed", "actor_type": "human"},
    )
    assert response.status_code == 200
    return response.json()


def _valid_evidence_content() -> dict:
    return {
        "claims": [
            {
                "claim_id": "C1",
                "claim_text": "现有论文元数据支持 AI 采用与创新关系的候选文献综合判断。",
                "claim_type": "literature_synthesis",
                "status": "supported",
                "confidence": "medium",
                "scope": {"population_or_system": "企业", "time": "论文覆盖期", "geography": "论文覆盖地区", "boundary_conditions": ["仅为文献综合"]},
                "evidence": [{"evidence_id": "EV1", "evidence_type": "paper", "artifact_id": "paper_a", "locator": "title and metadata", "direction": "supports", "strength": "moderate"}],
                "assumptions": [],
                "counterevidence": [],
                "uncertainty_note": "尚无本地模型结果，不能作因果判断。",
                "robustness_check_ids": [],
                "mechanism_ids": [],
            }
        ],
        "mechanisms": [],
        "heterogeneity": [],
        "limitations": ["当前仅有论文元数据证据。"],
        "interpretation": "结论只覆盖文献综合，不包含本地因果估计。",
        "unknowns": ["本地估计结果"],
    }


def _valid_delivery_content() -> dict:
    return {
        "title": "AI 采用与企业创新研究报告",
        "executive_summary": "现有论文元数据支持候选关系判断，但尚无本地模型结果，因此不能形成因果结论。",
        "conclusions": [{"conclusion_id": "CON1", "statement": "当前只能形成 AI 采用与创新关系的有限文献综合结论。", "claim_ids": ["C1"], "evidence_ids": ["EV1"], "status": "supported", "scope_note": "限于现有论文覆盖范围。"}],
        "policy_implications": [{"implication_id": "POL1", "statement": "企业可继续评估 AI 采用，但应先验证数据和实际效果。", "audience": "企业管理者", "claim_ids": ["C1"], "conditions": ["完成本地数据验证"], "risk_note": "不能把文献关系直接解释为因果收益。"}],
        "outline": [
            {"section_id": "SEC1", "title": "研究问题", "purpose": "说明问题和范围。", "claim_ids": [], "evidence_ids": []},
            {"section_id": "SEC2", "title": "证据", "purpose": "展示可追溯文献证据。", "claim_ids": ["C1"], "evidence_ids": ["EV1"]},
            {"section_id": "SEC3", "title": "结论", "purpose": "给出有限结论和披露。", "claim_ids": ["C1"], "evidence_ids": ["EV1"]},
        ],
        "approved_claims": ["C1"],
        "reference_paper_ids": ["paper_a"],
        "references": [{"paper_id": "paper_a", "title": "Paper A", "authors": ["Li"]}],
        "limitations": ["没有本地模型结果。"],
        "reproducibility_notes": ["结论保留 claim_id 和 evidence_id。"],
        "disclosure": "报告为 AI 辅助草稿，最终内容由研究者审批。",
        "release_notes": "首次交付。",
        "unknowns": ["本地估计结果"],
        "exports": [],
        "visual_report_path": "",
        "research_package_path": "",
    }


def _valid_gate_content(project: dict, stage_key: str) -> dict:
    if stage_key == "problem":
        return {
            "initial_idea": project["initial_idea"],
            "research_object": "采用 AI 的企业",
            "problem_boundary": "研究企业采用 AI 与创新结果之间的关系，不预设因果成立。",
            "objective": "explain",
            "units": ["企业"],
            "geography": ["待确认"],
            "time_window": "待确认",
            "concepts": [{"label": "AI 采用", "terms": ["AI adoption"], "exclude_terms": []}],
            "questions": ["企业采用 AI 与创新结果之间存在什么关系？"],
            "candidate_gaps": [],
            "counter_searches": ["AI adoption firm innovation existing evidence"],
            "unknowns": ["数据可得性"],
        }
    if stage_key == "literature":
        return {
            "topic_summary": "企业 AI 采用与创新结果研究",
            "query_blocks": [
                {"label": "核心关系", "terms": ["AI adoption", "innovation"], "exclude_terms": [], "query_zh": "人工智能采用 企业创新", "query_en": "AI adoption AND firm innovation", "purpose": "定位核心研究"},
                {"label": "反向证据", "terms": ["AI adoption", "null effect"], "exclude_terms": [], "query_zh": "人工智能采用 创新 无显著影响", "query_en": "AI adoption AND innovation AND null effect", "purpose": "检查反证"},
            ],
            "databases": ["openalex", "crossref"],
            "languages": ["zh", "en"],
            "inclusion_criteria": ["主题与企业 AI 采用或创新有关"],
            "exclusion_criteria": ["没有可追溯元数据"],
            "screening_questions": ["研究对象和结论边界是否明确？"],
            "counter_searches": ["AI adoption innovation contradictory evidence"],
            "papers": [{"paper_id": "paper_a", "title": "Paper A", "authors": ["Li"], "year": 2025}],
            "search_runs": [{"search_id": "search_fixture", "status": "complete"}],
            "research_streams": [{"stream_id": "stream_core", "name": "核心关系", "description": "讨论企业 AI 采用与创新结果的研究。", "paper_ids": ["paper_a"], "naming_evidence": "当前论文题名和元数据。"}],
            "syntheses": [{"statement": "当前论文元数据提示该关系值得进一步验证。", "status": "limited", "supporting_paper_ids": ["paper_a"], "opposing_paper_ids": [], "qualifiers": ["仅有元数据"]}],
            "gap_candidates": [],
            "recommended_next_steps": ["补充全文与反向证据"],
            "unknowns": ["全文结论"],
            "coverage_limits": ["当前测试仅保留一条论文元数据"],
        }
    if stage_key == "theory":
        return {
            "theoretical_lenses": [{"name": "组织信息处理理论", "relevance": "解释信息处理能力与创新活动的关系。", "limits": ["不能单独确认因果方向"], "supporting_paper_ids": ["paper_a"]}],
            "constructs": [
                {"name": "AI 采用", "definition": "企业部署并使用 AI 的程度。", "role": "antecedent", "measurement_unknowns": ["口径待定"]},
                {"name": "企业创新", "definition": "企业形成创新成果的表现。", "role": "outcome", "measurement_unknowns": ["指标待定"]},
            ],
            "mechanisms": [{"name": "信息处理机制", "chain": ["AI 采用改变信息处理", "信息处理影响创新"], "boundary_conditions": ["组织吸收能力"], "supporting_paper_ids": ["paper_a"], "evidence_status": "limited"}],
            "research_questions": ["AI 采用如何通过信息处理影响企业创新？"],
            "competing_explanations": [{"explanation": "创新能力强的企业更早采用 AI。", "distinguishing_observation": "采用前创新趋势可区分反向因果。"}],
            "falsifiable_propositions": [{"proposition_id": "H1", "statement": "AI 采用与企业创新存在可检验关系。", "falsification": "在可比样本中没有观察到该关系。"}],
            "contribution_boundary": "只提出待检验机制，不把相关性写成因果事实。",
            "unknowns": ["构念测量方式"],
        }

    context = StageGenerationService._build_context(project, stage_key)
    if stage_key == "design":
        method_ids = [item["method_id"] for item in context["method_candidates"][:2]]
        return {
            "design_lane": "empirical_causal",
            "research_question": "AI 采用如何影响企业创新结果？",
            "unit_of_analysis": "企业-年",
            "estimand_or_objective": "估计 AI 采用与企业创新之间的平均关系。",
            "method_options": [
                {"method_id": method_ids[0], "role": "primary", "rationale": "与企业面板研究目标相匹配。", "fit_conditions": ["存在企业年度数据"], "risks": ["选择偏差"]},
                {"method_id": method_ids[1], "role": "alternative", "rationale": "用于检查主方法的依赖。", "fit_conditions": ["满足替代方法假设"], "risks": ["假设可能不成立"]},
            ],
            "primary_method_id": method_ids[0],
            "assumptions": [{"assumption_id": "A1", "category": "identification", "statement": "关键混杂因素得到适当处理。", "testability": "partially_testable", "planned_check": "检查处理前趋势和可观测平衡。"}],
            "falsification": ["执行安慰剂检验"],
            "threats_to_validity": ["选择偏差"],
            "stopping_conditions": ["关键识别假设明显不成立"],
            "unknowns": ["面板长度"],
        }
    if stage_key == "data":
        source_id = context["data_source_candidates"][0]["source_id"]
        return {
            "data_sources": [{"source_id": source_id, "role": "candidate", "access_status": "unknown", "license_status": "unknown", "rationale": "候选数据源可能覆盖企业与创新字段。", "required_fields": ["企业标识", "年份"], "risks": ["访问状态未知"]}],
            "variables": [
                {"name": "AI 采用", "role": "treatment", "construct": "企业 AI 采用", "operationalization": "按可得字段构建。", "unit": "企业-年", "source_ids": [source_id], "missing_data_plan": "报告缺失机制后处理。"},
                {"name": "创新结果", "role": "outcome", "construct": "企业创新", "operationalization": "按创新字段构建。", "unit": "企业-年", "source_ids": [source_id], "missing_data_plan": "报告缺失比例并做敏感性分析。"},
            ],
            "sample_definition": "具有企业标识、年份和关键变量的企业年度样本。",
            "time_coverage": "取决于实际数据可得年份",
            "join_keys": ["企业标识", "年份"],
            "pii_class": "unknown",
            "privacy_risks": ["字段分类待确认"],
            "ethics_checks": ["确认授权和数据最小化"],
            "quality_checks": ["主键唯一性", "缺失与异常值"],
            "blocking_issues": ["访问权限待确认"],
            "unknowns": ["许可条款"],
        }
    if stage_key == "identification":
        method_id = context["design_content"]["method_options"][0]["method_id"]
        return {
            "design_lane": "empirical_causal",
            "estimand_or_objective": "估计 AI 采用与企业创新结果之间的平均关系。",
            "analysis_sample": "满足企业标识、年份和主变量要求的企业年度样本。",
            "unit_of_analysis": "企业-年",
            "variable_roles": [
                {"name": "创新结果", "role": "outcome", "source_variable": "innovation", "transformation": "none", "rationale": "对应结果构念。"},
                {"name": "AI 采用", "role": "treatment", "source_variable": "ai_adoption", "transformation": "none", "rationale": "对应核心处理变量。"},
            ],
            "model_specifications": [{"specification_id": "SPEC1", "label": "主模型", "role": "primary", "method_id": method_id, "formula_id": None, "equation_or_objective": "innovation = beta * ai_adoption + controls", "outcome_or_target": ["innovation"], "predictors_or_decisions": ["ai_adoption"], "fixed_effects": [], "uncertainty_or_standard_errors": "稳健标准误", "weights": "none", "sample_restrictions": []}],
            "diagnostics": [{"diagnostic_id": "DIAG1", "target": "识别假设", "procedure": "检查趋势和样本结构。", "pass_condition": "没有发现明显违背。", "failure_action": "停止因果解释。"}],
            "analysis_steps": [
                {"step_id": "STEP1", "purpose": "检查数据", "inputs": ["input"], "operation": "检查变量和主键。", "outputs": ["audit"], "linked_specification_ids": []},
                {"step_id": "STEP2", "purpose": "估计主模型", "inputs": ["sample"], "operation": "执行冻结规格。", "outputs": ["results"], "linked_specification_ids": ["SPEC1"]},
            ],
            "missing_data_plan": "先报告缺失机制再处理。",
            "multiplicity_plan": "区分主要与次要结果。",
            "robustness_plan": ["替代指标", "替代样本"],
            "stopping_conditions": ["关键变量不存在"],
            "execution_engine": "manual",
            "code_language": "manual review",
            "stata_do_file": "",
            "seed": None,
            "expected_outputs": ["数据审计", "主结果"],
            "reproducibility_requirements": ["保存输入输出 hash"],
            "unknowns": ["数据是否满足要求"],
        }
    if stage_key == "analysis":
        return {
            "execution_engine": "manual",
            "readiness_summary": "分析计划已冻结，仍需完成输入与运行条件检查。",
            "expected_outputs": ["数据审计", "主结果"],
            "preflight_checks": ["检查输入文件", "检查计划 revision"],
            "result_review_checks": ["检查失败诊断", "检查结果完整性"],
            "blocking_issues": ["测试流程不执行真实分析"],
            "unknowns": ["实际运行结果"],
        }
    if stage_key == "robustness":
        return {
            "robustness_matrix": [
                {"check_id": "ROB1", "category": "alternative_measure", "rationale": "检查口径依赖。", "specification": "替换创新指标。", "linked_specification_ids": [], "required_run_ids": [], "status": "planned", "result_summary": "", "implication": "完成前不提升结论强度。"},
                {"check_id": "ROB2", "category": "placebo", "rationale": "检查虚假关系。", "specification": "执行安慰剂检验。", "linked_specification_ids": [], "required_run_ids": [], "status": "planned", "result_summary": "", "implication": "失败时降低解释强度。"},
            ],
            "failed_checks": [],
            "interpretation_limits": ["尚无真实运行结果"],
            "next_runs": ["执行计划中的稳健性分支"],
            "reproducibility_report": "当前只完成计划审查，尚未形成数值复现结论。",
            "unknowns": ["实际运行结果"],
        }
    if stage_key == "evidence":
        return _valid_evidence_content()
    if stage_key == "delivery":
        return _valid_delivery_content()
    raise AssertionError(f"missing gate fixture for {stage_key}")


def test_health_meta_and_web_assets(tmp_path):
    client = TestClient(create_app(tmp_path))

    assert client.get("/healthz").json()["status"] == "ok"
    stages = client.get("/api/v1/meta/stages").json()["items"]
    assert [stage["position"] for stage in stages] == list(range(1, 11))
    assert [stage["code"] for stage in stages] == [f"S{index}" for index in range(10)]
    assert stages[-1]["artifact_type"] == "ResearchPackage"
    profile = client.get("/api/v1/meta/domain-profile").json()
    assert profile["key"] == "management_science"
    assert profile["name"] == "管理科学"
    inference = client.get("/api/v1/meta/inference")
    assert inference.status_code == 200
    assert set(inference.json()) == {"configured", "model", "reason"}
    assert "api_key" not in inference.text.lower()
    assert client.get("/openapi.json").json()["info"]["title"] == "AI4MS 科研工作台 API"

    page = client.get("/")
    if client.app.state.web_root is None:
        assert page.status_code == 503
    else:
        assert page.status_code == 200
        assert "AI4MS" in page.text
        assert "/_next/static/" in page.text
        assert client.get("/favicon.svg").status_code == 200
        assert client.get("/ai4ms-user-guide.html").status_code == 200


def test_project_stage_gate_and_revision_flow(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)
    project_id = project["project_id"]

    assert project["current_stage"] == "problem"
    assert project["stages"][0]["revision"] == 1
    assert project["stages"][1]["status"] == "not_started"
    assert project["stages"][0]["content_hash"]

    locked = client.post(
        f"/api/v1/projects/{project_id}/stages/literature/draft",
        json={"instruction": ""},
    )
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "stage_locked"

    project = _approve(client, project_id, "problem")
    assert project["current_stage"] == "literature"
    assert project["stages"][1]["status"] == "in_progress"

    drafted = client.post(
        f"/api/v1/projects/{project_id}/stages/literature/draft",
        json={"instruction": "Build query blocks"},
    )
    assert drafted.status_code == 200
    project = drafted.json()
    literature = project["stages"][1]
    assert literature["revision"] == 1
    assert literature["content"]["draft_source"] == "structure_template"
    assert literature["status"] == "needs_review"

    invalid_actor = client.post(
        f"/api/v1/projects/{project_id}/stages/literature/decisions",
        json={"decision": "approve", "actor_type": "agent"},
    )
    assert invalid_actor.status_code == 422


def test_gate_rejects_invalid_stage_asset(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)

    response = client.post(
        f"/api/v1/projects/{project['project_id']}/stages/problem/decisions",
        json={"decision": "approve", "reason": "Reviewed", "actor_type": "human"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_stage_content"


def test_gate_requires_saved_confirmation_for_the_current_revision(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)
    project_id = project["project_id"]
    problem = project["stages"][0]
    valid_content = _valid_gate_content(project, "problem")

    prepared = client.put(
        f"/api/v1/projects/{project_id}/stages/problem",
        json={"content": valid_content, "change_reason": "Prepare valid problem"},
    )
    assert prepared.status_code == 200
    prepared_stage = prepared.json()["stages"][0]
    assert prepared_stage["readiness"]["percent"] == 50
    assert prepared_stage["readiness"]["checks"] == {
        "artifact_saved": True,
        "contract_valid": True,
        "human_confirmed": False,
        "approved": False,
    }
    assert prepared_stage["readiness"]["can_submit"] is False

    missing_confirmation = client.post(
        f"/api/v1/projects/{project_id}/stages/problem/decisions",
        json={"decision": "approve", "reason": "Reviewed", "actor_type": "human"},
    )
    assert missing_confirmation.status_code == 409
    assert "人工确认尚未保存" in missing_confirmation.json()["error"]["message"]

    confirmed = client.patch(
        f"/api/v1/projects/{project_id}/stages/problem/workspace",
        json={
            "workspace": {"human_confirmed": True},
            "expected_revision": prepared_stage["revision"],
            "change_reason": "Confirm current problem revision",
        },
    )
    assert confirmed.status_code == 200
    confirmed_stage = confirmed.json()["stages"][0]
    assert confirmed_stage["content"]["_workspace"]["human_confirmed"] is True
    assert confirmed_stage["readiness"]["percent"] == 75
    assert confirmed_stage["readiness"]["can_submit"] is True
    assert confirmed_stage["readiness"]["missing"] == ["提交并通过人工审批"]

    approved = client.post(
        f"/api/v1/projects/{project_id}/stages/problem/decisions",
        json={"decision": "approve", "reason": "Reviewed", "actor_type": "human"},
    )
    assert approved.status_code == 200
    approved_stage = approved.json()["stages"][0]
    assert approved_stage["readiness"]["percent"] == 100
    assert approved_stage["readiness"]["missing"] == []

    changed_content = dict(confirmed_stage["content"])
    changed_content["problem_boundary"] = "修改后的研究边界"
    changed = client.put(
        f"/api/v1/projects/{project_id}/stages/problem",
        json={"content": changed_content, "change_reason": "Change canonical content"},
    )
    assert changed.status_code == 200
    assert changed.json()["stages"][0]["content"]["_workspace"]["human_confirmed"] is False

    stale_confirmation = client.post(
        f"/api/v1/projects/{project_id}/stages/problem/decisions",
        json={"decision": "approve", "reason": "Reviewed", "actor_type": "human"},
    )
    assert stale_confirmation.status_code == 409


def test_stage_revision_history_can_restore_an_exact_draft(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)
    project_id = project["project_id"]

    first_content = {
        **_valid_gate_content(project, "problem"),
        "draft_marker": "first",
    }
    first = client.put(
        f"/api/v1/projects/{project_id}/stages/problem",
        json={"content": first_content, "change_reason": "First draft"},
    )
    assert first.status_code == 200
    first_stage = first.json()["stages"][0]

    confirmed = client.patch(
        f"/api/v1/projects/{project_id}/stages/problem/workspace",
        json={
            "workspace": {
                "summary": "第一版人工说明",
                "human_confirmed": True,
                "sync_history": ["保存第一版"],
            },
            "expected_revision": first_stage["revision"],
            "change_reason": "Confirm first draft",
        },
    )
    confirmed_stage = confirmed.json()["stages"][0]
    source_revision = confirmed_stage["revision"]

    second_content = dict(confirmed_stage["content"])
    second_content["draft_marker"] = "second"
    second = client.put(
        f"/api/v1/projects/{project_id}/stages/problem",
        json={"content": second_content, "change_reason": "Second draft"},
    )
    second_stage = second.json()["stages"][0]
    assert second_stage["content"]["_workspace"]["human_confirmed"] is False

    revisions = client.get(
        f"/api/v1/projects/{project_id}/stages/problem/revisions"
    )
    assert revisions.status_code == 200
    revision_numbers = [item["revision"] for item in revisions.json()["items"]]
    assert revision_numbers == sorted(revision_numbers, reverse=True)
    assert source_revision in revision_numbers

    restored = client.post(
        f"/api/v1/projects/{project_id}/stages/problem/restore",
        json={
            "revision": source_revision,
            "expected_revision": second_stage["revision"],
            "change_reason": "Restore first draft",
        },
    )
    assert restored.status_code == 200
    restored_stage = restored.json()["stages"][0]
    assert restored_stage["revision"] == second_stage["revision"] + 1
    assert restored_stage["content"]["draft_marker"] == "first"
    assert restored_stage["content"]["_workspace"]["summary"] == "第一版人工说明"
    assert restored_stage["content"]["_workspace"]["human_confirmed"] is False
    assert "恢复" in restored_stage["content"]["_workspace"]["sync_history"][0]


def test_model_draft_is_saved_as_an_agent_revision(tmp_path):
    client = TestClient(create_app(tmp_path, stage_generation=_FakeStageGeneration()))
    project = _create_project(client)

    response = client.post(
        f"/api/v1/projects/{project['project_id']}/stages/problem/draft",
        json={"instruction": "clarify the unit", "generation_mode": "model"},
    )

    assert response.status_code == 200
    stage = response.json()["stages"][0]
    assert stage["revision"] == 2
    assert stage["author_type"] == "agent"
    assert stage["content"]["generation"]["model"] == "fake-model"
    assert stage["content"]["generation"]["instruction"] == "clarify the unit"


def test_literature_search_endpoint_saves_papers_and_run_metadata(tmp_path):
    client = TestClient(create_app(tmp_path, literature_search=_FakeLiteratureSearch()))
    project = _create_project(client)
    project_id = project["project_id"]
    _approve(client, project_id, "problem")
    client.put(
        f"/api/v1/projects/{project_id}/stages/literature",
        json={
            "content": {"query_blocks": [{"query_en": "AI adoption"}]},
            "change_reason": "search plan",
        },
    )

    response = client.post(
        f"/api/v1/projects/{project_id}/stages/literature/search",
        json={"backends": ["openalex"]},
    )

    assert response.status_code == 200
    stage = response.json()["stages"][1]
    assert stage["author_type"] == "agent"
    assert stage["content"]["papers"][0]["paper_id"] == "paper_a"
    assert stage["content"]["search_runs"][0]["snapshot_path"].endswith("search_api_test.json")


def test_knowledge_registry_endpoints_expose_compact_candidates(tmp_path):
    client = TestClient(create_app(tmp_path))

    methods = client.get("/api/v1/knowledge/methods?goal=causal&limit=4").json()["items"]
    sources = client.get("/api/v1/knowledge/data-sources?q=企业专利&limit=5").json()["items"]
    formulas = client.get("/api/v1/knowledge/formulas?q=双重差分&method_id=M06&limit=4").json()["items"]

    assert len(methods) == 4
    assert all(item["method_id"].startswith("M") for item in methods)
    assert len(sources) == 5
    assert all(item["source_id"].startswith("D") for item in sources)
    assert len(formulas) == 4
    assert all("formula_id" in item for item in formulas)


def test_analysis_runner_api_preflight_and_run_revision(tmp_path):
    client = TestClient(create_app(tmp_path, analysis_runner=_FakeAnalysisRunner()))
    project = _create_project(client)
    project_id = project["project_id"]

    locked = client.post(
        f"/api/v1/projects/{project_id}/stages/analysis/preflight",
        json={"input_artifact_path": "input.dta"},
    )
    assert locked.status_code == 409

    for index, stage_key in enumerate(("problem", "literature", "theory", "design", "data", "identification")):
        if index:
            drafted = client.post(
                f"/api/v1/projects/{project_id}/stages/{stage_key}/draft",
                json={"generation_mode": "template"},
            )
            assert drafted.status_code == 200
        project = _approve(client, project_id, stage_key)

    runner = client.get("/api/v1/runners/stata")
    assert runner.status_code == 200
    assert runner.json()["available"] is True

    preflight = client.post(
        f"/api/v1/projects/{project_id}/stages/analysis/preflight",
        json={"input_artifact_path": "input.dta"},
    )
    assert preflight.status_code == 200
    assert preflight.json()["status"] == "ready"

    submitted = client.post(
        f"/api/v1/projects/{project_id}/stages/analysis/runs",
        json={"input_artifact_path": "input.dta"},
    )
    assert submitted.status_code == 202
    job = submitted.json()
    deadline = time.time() + 2
    while job["status"] in {"queued", "running", "canceling"} and time.time() < deadline:
        time.sleep(0.01)
        job = client.get(
            f"/api/v1/projects/{project_id}/stages/analysis/runs/{job['run_id']}"
        ).json()
    assert job["status"] == "succeeded"
    listed = client.get(
        f"/api/v1/projects/{project_id}/stages/analysis/runs"
    ).json()["items"]
    assert listed[0]["run_id"] == job["run_id"]
    result = client.get(
        f"/api/v1/projects/{project_id}/stages/analysis/runs/{job['run_id']}/result"
    )
    assert result.status_code == 200
    stage = client.get(f"/api/v1/projects/{project_id}").json()["stages"][6]
    assert stage["revision"] == 1
    assert stage["content"]["runs"][0]["run_id"] == job["run_id"]
    assert stage["content"]["results"][0]["status"] == "succeeded"


def test_upstream_change_invalidates_downstream_and_persists(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)
    project_id = project["project_id"]
    project = _approve(client, project_id, "problem")

    drafted = client.post(
        f"/api/v1/projects/{project_id}/stages/literature/draft",
        json={"instruction": ""},
    )
    assert drafted.status_code == 200
    project = _approve(client, project_id, "literature")
    assert project["stages"][1]["status"] == "approved"
    assert project["stages"][2]["status"] == "in_progress"

    changed = client.put(
        f"/api/v1/projects/{project_id}/stages/problem",
        json={
            "content": {"research_object": "platform firms", "questions": ["What changes?"]},
            "change_reason": "Narrowed research object",
            "author_type": "human",
        },
    )
    assert changed.status_code == 200
    project = changed.json()
    assert project["current_stage"] == "problem"
    assert project["stages"][0]["revision"] == 4
    assert project["stages"][1]["status"] == "needs_review"
    assert project["stages"][2]["status"] == "not_started"
    assert len(project["approvals"]) == 2

    restarted = TestClient(create_app(tmp_path))
    persisted = restarted.get(f"/api/v1/projects/{project_id}")
    assert persisted.status_code == 200
    assert persisted.json()["stages"][0]["content"]["research_object"] == "platform firms"


def test_validation_and_missing_resources(tmp_path):
    client = TestClient(create_app(tmp_path))

    assert client.post("/api/v1/projects", json={"title": "", "initial_idea": "x"}).status_code == 422
    missing = client.get("/api/v1/projects/prj_missing")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "project_not_found"

    project = _create_project(client)
    unknown_stage = client.get(f"/api/v1/projects/{project['project_id']}/stages/unknown")
    assert unknown_stage.status_code == 404
    assert unknown_stage.json()["error"]["code"] == "stage_not_found"


def test_stage_workspace_update_preserves_canonical_content_and_detects_conflicts(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)
    project_id = project["project_id"]
    problem = project["stages"][0]
    canonical_content = dict(problem["content"])

    payload = {
        "workspace": {
            "title": "问题识别工作资产",
            "summary": "围绕当前研究问题形成可审阅说明。",
            "objective": "明确研究问题与边界。",
            "content": "研究者编辑的说明正文。",
            "scope": "平台企业。",
            "evidence_note": "文献证据待补充。",
            "decision": "保留当前问题。",
            "risk": "数据不可得时收缩范围。",
            "handoff": "交付给文献检索阶段。",
            "human_confirmed": True,
            "sync_history": ["研究者保存"],
        },
        "expected_revision": problem["revision"],
        "change_reason": "Save workspace notes",
    }
    saved = client.patch(
        f"/api/v1/projects/{project_id}/stages/problem/workspace",
        json=payload,
    )

    assert saved.status_code == 200
    updated_stage = saved.json()["stages"][0]
    assert updated_stage["revision"] == problem["revision"] + 1
    for key, value in canonical_content.items():
        assert updated_stage["content"][key] == value
    assert updated_stage["content"]["_workspace"]["evidence_note"] == "文献证据待补充。"

    conflict = client.patch(
        f"/api/v1/projects/{project_id}/stages/problem/workspace",
        json=payload,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "revision_conflict"

    invalid = dict(payload)
    invalid["expected_revision"] = updated_stage["revision"]
    invalid["workspace"] = {**payload["workspace"], "papers": []}
    response = client.patch(
        f"/api/v1/projects/{project_id}/stages/problem/workspace",
        json=invalid,
    )
    assert response.status_code == 422

    renamed = client.patch(
        f"/api/v1/projects/{project_id}",
        json={
            "title": "平台企业 AI 采用研究",
            "initial_idea": "平台企业采用 AI 后如何改变创新行为？",
        },
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "平台企业 AI 采用研究"
    assert renamed.json()["initial_idea"] == "平台企业采用 AI 后如何改变创新行为？"


def test_complete_s0_to_s9_flow(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)
    project_id = project["project_id"]
    stage_keys = [stage["key"] for stage in project["stages"]]

    for index, stage_key in enumerate(stage_keys[:8]):
        if index > 0:
            drafted = client.post(
                f"/api/v1/projects/{project_id}/stages/{stage_key}/draft",
                json={"instruction": f"Create {stage_key} structure"},
            )
            assert drafted.status_code == 200
            assert drafted.json()["stages"][index]["revision"] == 1
        if stage_key == "literature":
            current = client.get(f"/api/v1/projects/{project_id}/stages/literature").json()["content"]
            current["papers"] = [{"paper_id": "paper_a", "title": "Paper A", "authors": ["Li"], "year": 2025}]
            saved = client.put(
                f"/api/v1/projects/{project_id}/stages/literature",
                json={"content": current, "change_reason": "Add traceable paper"},
            )
            assert saved.status_code == 200
        project = _approve(client, project_id, stage_key)

    evidence = client.put(
        f"/api/v1/projects/{project_id}/stages/evidence",
        json={"content": _valid_evidence_content(), "change_reason": "Build Claim-Evidence graph"},
    )
    assert evidence.status_code == 200
    project = _approve(client, project_id, "evidence")

    delivery = client.put(
        f"/api/v1/projects/{project_id}/stages/delivery",
        json={"content": _valid_delivery_content(), "change_reason": "Prepare delivery"},
    )
    assert delivery.status_code == 200
    exported = client.post(f"/api/v1/projects/{project_id}/stages/delivery/export")
    assert exported.status_code == 200
    export_record = exported.json()["stages"][9]["content"]["exports"][-1]
    report = client.get(f"/api/v1/projects/{project_id}/exports/{export_record['export_id']}/report")
    package = client.get(f"/api/v1/projects/{project_id}/exports/{export_record['export_id']}/package")
    assert report.status_code == 200
    assert "Claim-Evidence" in report.text
    assert report.headers["content-disposition"].startswith("inline")
    assert package.status_code == 200
    assert package.headers["content-type"] == "application/zip"
    project = _approve(client, project_id, "delivery")

    assert project["status"] == "completed"
    assert project["current_stage"] == "delivery"
    assert project["progress"] == {"approved": 10, "total": 10}
    assert all(stage["status"] == "approved" for stage in project["stages"])


def test_legacy_nine_stage_database_is_migrated_without_losing_revisions(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)
    project_id = project["project_id"]
    db_path = tmp_path / "ai4ms.db"

    with sqlite3.connect(db_path) as conn:
        renames = (
            ("analysis", "run"),
            ("identification", "analysis"),
            ("theory", "topic"),
            ("problem", "idea"),
        )
        for new_key, old_key in renames:
            conn.execute(
                "UPDATE stage_revisions SET stage_key = ? WHERE project_id = ? AND stage_key = ?",
                (old_key, project_id, new_key),
            )
            conn.execute(
                "UPDATE approval_events SET stage_key = ? WHERE project_id = ? AND stage_key = ?",
                (old_key, project_id, new_key),
            )
            conn.execute(
                "UPDATE stage_states SET stage_key = ? WHERE project_id = ? AND stage_key = ?",
                (old_key, project_id, new_key),
            )
        conn.execute(
            "DELETE FROM stage_states WHERE project_id = ? AND stage_key = 'robustness'",
            (project_id,),
        )
        conn.execute(
            "UPDATE projects SET current_stage = 'idea' WHERE project_id = ?",
            (project_id,),
        )

    migrated = TestClient(create_app(tmp_path)).get(f"/api/v1/projects/{project_id}")
    assert migrated.status_code == 200
    payload = migrated.json()
    assert payload["current_stage"] == "problem"
    assert [stage["key"] for stage in payload["stages"]] == [
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
    ]
    assert payload["stages"][0]["revision"] == 1
    assert payload["stages"][0]["content"]["initial_idea"]
    assert payload["stages"][7]["revision"] == 0
