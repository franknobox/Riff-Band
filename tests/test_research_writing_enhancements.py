from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from ai4ms.api.app import create_app
from ai4ms.delivery import AcademicOutputQualityService
from ai4ms.services.stage_generation import (
    StageContentValidationError,
    StageGenerationService,
)
from test_delivery_export import _project as delivery_project
from test_workbench_api import (
    _FakeLiteratureSearch,
    _approve,
    _create_project,
    _valid_gate_content,
)


def _problem_candidates() -> list[dict]:
    shared = {
        "unit_of_analysis": "企业",
        "candidate_contribution": "theory",
        "evidence_refs": ["project.initial_idea"],
        "feasibility_status": "conditional",
        "data_needs": ["企业层 AI 采用与创新数据"],
    }
    return [
        {
            **shared,
            "question_id": "RQ1",
            "statement": "企业采用 AI 与创新结果之间存在什么关系？",
            "question_type": "explain",
            "management_decision": "企业是否以及如何配置 AI 投资",
            "outcome_or_objective": "解释创新结果差异",
            "falsifier": "相同情境的既有研究已充分回答该问题。",
        },
        {
            **shared,
            "question_id": "RQ2",
            "statement": "哪些组织条件改变 AI 采用与企业创新的关系？",
            "question_type": "explore",
            "management_decision": "企业在何种组织条件下配置 AI",
            "outcome_or_objective": "识别关系的组织边界",
            "falsifier": "关键组织条件无法可靠测量。",
        },
    ]


def test_problem_selection_is_human_bound_and_stale_selection_blocks_g0(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)
    project_id = project["project_id"]
    content = _valid_gate_content(project, "problem")
    content.update(
        {
            "question_candidates": _problem_candidates(),
            "problem_diagnostics": [
                {
                    "diagnostic_id": "PD1",
                    "dimension": "unit_alignment",
                    "status": "warning",
                    "finding": "采用行为与创新结果可能处于不同组织层级。",
                    "evidence_refs": ["project.initial_idea"],
                    "required_action": "确认变量和研究单位的层级一致性。",
                }
            ],
            "selection_tradeoffs": ["RQ1 更聚焦；RQ2 数据需求更高。"],
        }
    )
    saved = client.put(
        f"/api/v1/projects/{project_id}/stages/problem",
        json={"content": content, "change_reason": "Generate candidate questions"},
    )
    revision = saved.json()["stages"][0]["revision"]

    selected = client.post(
        f"/api/v1/projects/{project_id}/stages/problem/question-selection",
        json={
            "selected_question_id": "RQ1",
            "rationale": "问题边界更聚焦且与当前数据可行性更一致。",
            "expected_revision": revision,
            "actor_type": "human",
        },
    )
    assert selected.status_code == 200
    selected_stage = selected.json()["stages"][0]
    assert selected_stage["content"]["question_selection"]["selected_by"] == "human"
    assert len(
        selected_stage["content"]["question_selection"]["candidate_fingerprint"]
    ) == 64

    changed_content = deepcopy(selected_stage["content"])
    changed_content["question_candidates"][0]["statement"] += "（修改后）"
    changed = client.put(
        f"/api/v1/projects/{project_id}/stages/problem",
        json={"content": changed_content, "change_reason": "Change candidate meaning"},
    ).json()
    changed_stage = changed["stages"][0]
    workspace = {
        **changed_stage["content"].get("_workspace", {}),
        "human_confirmed": True,
    }
    confirmed = client.patch(
        f"/api/v1/projects/{project_id}/stages/problem/workspace",
        json={
            "workspace": workspace,
            "expected_revision": changed_stage["revision"],
            "change_reason": "Confirm edited draft",
        },
    )
    assert confirmed.status_code == 200
    decision = client.post(
        f"/api/v1/projects/{project_id}/stages/problem/decisions",
        json={"decision": "approve", "reason": "Reviewed", "actor_type": "human"},
    )
    assert decision.status_code == 409
    assert "明确选择" in decision.json()["error"]["message"]


def test_literature_plan_review_screening_and_coverage_are_revisioned(tmp_path):
    client = TestClient(
        create_app(tmp_path, literature_search=_FakeLiteratureSearch())
    )
    project = _create_project(client)
    project_id = project["project_id"]
    _approve(client, project_id, "problem")
    planned = client.put(
        f"/api/v1/projects/{project_id}/stages/literature",
        json={
            "content": {"query_blocks": [{"query_en": "AI adoption"}]},
            "change_reason": "Prepare search plan",
        },
    ).json()

    blocked = client.post(
        f"/api/v1/projects/{project_id}/stages/literature/search",
        json={"backends": ["openalex"]},
    )
    assert blocked.status_code == 409
    assert "批准当前 query plan" in blocked.json()["error"]["message"]

    revision = planned["stages"][1]["revision"]
    reviewed = client.post(
        f"/api/v1/projects/{project_id}/stages/literature/plan-review",
        json={
            "decision": "approve",
            "reason": "检索范围、数据库和查询式已人工检查。",
            "expected_revision": revision,
            "actor_type": "human",
        },
    )
    assert reviewed.status_code == 200
    searched = client.post(
        f"/api/v1/projects/{project_id}/stages/literature/search",
        json={"backends": ["openalex"]},
    )
    assert searched.status_code == 200
    searched_stage = searched.json()["stages"][1]
    assert searched_stage["content"]["search_runs"][-1]["query_origin"] == "human_approved_plan"
    assert searched_stage["content"]["coverage_audit"]["screening"]["unreviewed"] == 1

    unsupported_level = client.patch(
        f"/api/v1/projects/{project_id}/stages/literature/papers/paper_a/screening",
        json={
            "decision": "include",
            "reason": "当前只返回元数据，不能把证据等级升级为全文。",
            "evidence_level": "full_text",
            "expected_revision": searched_stage["revision"],
            "actor_type": "human",
        },
    )
    assert unsupported_level.status_code == 409
    assert "cannot mark it as full_text" in unsupported_level.json()["error"]["message"]

    screened = client.patch(
        f"/api/v1/projects/{project_id}/stages/literature/papers/paper_a/screening",
        json={
            "decision": "include",
            "reason": "题名与研究问题相关，保留进入摘要级提取。",
            "evidence_level": "metadata",
            "expected_revision": searched_stage["revision"],
            "actor_type": "human",
        },
    )
    assert screened.status_code == 200
    content = screened.json()["stages"][1]["content"]
    assert content["screening_decisions"][0]["decided_by"] == "human"
    assert content["coverage_audit"]["screening"]["include"] == 1
    assert content["coverage_audit"]["screening"]["unreviewed"] == 0
    assert content["paper_evidence_cards"] == []


def _enriched_delivery_project() -> dict:
    project = deepcopy(delivery_project())
    delivery = project["stages"][-1]["content"]
    delivery.update(
        {
            "document_profile": {
                "document_type": "management_research_article",
                "research_paradigm": "empirical_quantitative",
                "audience": "管理科学研究者",
                "language": "zh-CN",
                "citation_style": "gbt7714_numeric",
                "journal_or_institution_requirements": [],
                "common_method_bias_applicability": "not_applicable",
            },
            "abstract": "本文基于已批准的文献综合主张形成受证据范围约束的研究报告。",
            "keywords": ["人工智能采用", "企业创新"],
            "manuscript_sections": [
                {
                    "section_id": "SEC1",
                    "title": "研究问题",
                    "purpose": "说明研究边界。",
                    "body_markdown": "本节界定研究问题与适用边界。",
                    "claim_ids": [],
                    "evidence_ids": [],
                    "citation_paper_ids": [],
                    "citation_evidence_ids": [],
                    "content_status": "draft",
                    "unresolved_items": [],
                },
                {
                    "section_id": "SEC2",
                    "title": "证据",
                    "purpose": "展示可追溯证据。",
                    "body_markdown": "现有论文与已审核数据研究支持有限关系判断 [paper:paper_a] [claim:C1] [evidence:EV1]。",
                    "claim_ids": ["C1"],
                    "evidence_ids": ["EV1"],
                    "citation_paper_ids": ["paper_a"],
                    "citation_evidence_ids": ["EVLIB_A", "EVLIB_DATA"],
                    "content_status": "draft",
                    "unresolved_items": [],
                },
                {
                    "section_id": "SEC3",
                    "title": "结论",
                    "purpose": "形成有限结论。",
                    "body_markdown": "结论不超过当前证据强度 [paper:paper_a] [claim:C1] [evidence:EV1]。",
                    "claim_ids": ["C1"],
                    "evidence_ids": ["EV1"],
                    "citation_paper_ids": ["paper_a"],
                    "citation_evidence_ids": ["EVLIB_A"],
                    "content_status": "draft",
                    "unresolved_items": [],
                },
            ],
            "logic_closure": [
                {
                    "link_id": "LC1",
                    "research_question_refs": ["AI 采用是否影响企业创新？"],
                    "method_or_design_refs": ["文献综合"],
                    "claim_ids": ["C1"],
                    "conclusion_ids": ["CON1"],
                    "closure_status": "closed",
                    "missing_link": "",
                }
            ],
            "author_self_review": [],
        }
    )
    return project


def test_academic_output_quality_is_ready_and_inline_sources_are_hard_validated():
    project = _enriched_delivery_project()
    quality = AcademicOutputQualityService.audit(project)

    assert quality["status"] == "ready"
    assert quality["counts"] == {
        "must_fix": 0,
        "should_improve": 0,
        "note": 0,
    }
    assert quality["traceability"]["cited_paper_ids"] == ["paper_a"]

    delivery = project["stages"][-1]["content"]
    delivery["manuscript_sections"][1]["body_markdown"] += " [paper:paper_unknown]"
    with pytest.raises(
        StageContentValidationError,
        match="unknown inline paper marker",
    ):
        StageGenerationService.validate_stage_content(project, "delivery", delivery)
