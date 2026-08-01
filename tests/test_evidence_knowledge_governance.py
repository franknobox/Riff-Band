from __future__ import annotations

from fastapi.testclient import TestClient

from ai4ms.api.app import create_app
from test_workbench_api import _approve, _create_project


class _FakeResearchService:
    async def research(
        self,
        project_id: str,
        stage_key: str,
        query: str,
        mode: str,
    ) -> dict:
        assert project_id
        assert stage_key == "literature"
        assert mode == "on"
        return {
            "search_id": "web_governance_test",
            "status": "complete",
            "mode": "on",
            "searched": True,
            "searched_at": "2026-07-26T00:00:00+00:00",
            "queries": [query],
            "citations": [
                {
                    "citation_id": "SRC1",
                    "title": "Human-reviewed management science source",
                    "url": "https://example.org/source-1",
                    "domain": "example.org",
                    "snippet": "A candidate source found by an agent.",
                    "excerpt": "The source describes a management-science method.",
                    "provider": "test-search",
                    "source_type": "academic",
                    "is_official": False,
                    "paper_id": "paper_governance",
                    "retrieved_at": "2026-07-26T00:00:00+00:00",
                }
            ],
            "source_runs": [
                {
                    "provider": "test-search",
                    "success": True,
                    "record_count": 1,
                    "error": "",
                }
            ],
            "snapshot_path": "artifacts/web/web_governance_test.json",
        }


def _literature_stage(project: dict) -> dict:
    return next(
        stage for stage in project["stages"] if stage["key"] == "literature"
    )


def test_agent_evidence_candidate_requires_human_approval_and_is_revisioned(
    tmp_path,
):
    client = TestClient(
        create_app(tmp_path, research_service=_FakeResearchService())
    )
    project = _create_project(client)
    project_id = project["project_id"]
    project = _approve(client, project_id, "problem")
    literature = _literature_stage(project)

    discovered = client.post(
        f"/api/v1/projects/{project_id}/evidence-candidates/discover",
        json={
            "query": "AI adoption and innovation evidence",
            "candidate_type": "literature",
            "expected_revision": literature["revision"],
            "limit": 4,
            "actor_type": "agent",
        },
    )
    assert discovered.status_code == 200
    discovered_project = discovered.json()
    literature = _literature_stage(discovered_project)
    candidate = literature["content"]["evidence_candidates"][0]
    assert candidate["status"] == "pending"
    assert literature["content"]["evidence_library"] == []
    assert (
        literature["content"]["evidence_discovery_runs"][-1]["ai_report"][
            "schema_version"
        ]
        == "ai4ms.ai-report.v1"
    )

    approved = client.patch(
        (
            f"/api/v1/projects/{project_id}/evidence-candidates/"
            f"{candidate['candidate_id']}/review"
        ),
        json={
            "decision": "approve",
            "reason": "研究者核对了题名、来源链接和摘要证据等级。",
            "expected_revision": literature["revision"],
            "evidence_level": "abstract",
            "edits": {
                "title": "Verified management science paper",
                "authors": ["Researcher A"],
                "year": 2025,
            },
            "actor_type": "human",
        },
    )
    assert approved.status_code == 200
    literature = _literature_stage(approved.json())
    record = literature["content"]["evidence_library"][0]
    assert record["evidence_id"].startswith("EVLIB_")
    assert record["approved_by"] == "human"
    assert record["title"] == "Verified management science paper"
    assert len(record["content_hash"]) == 64

    patched = client.patch(
        (
            f"/api/v1/projects/{project_id}/evidence-library/"
            f"{record['evidence_id']}"
        ),
        json={
            "edits": {
                "summary": "人工补充的证据概括。",
                "locator": "Section 3, Table 2",
            },
            "reason": "补充可复核的证据定位。",
            "expected_revision": literature["revision"],
            "actor_type": "human",
        },
    )
    assert patched.status_code == 200
    updated_record = _literature_stage(patched.json())["content"][
        "evidence_library"
    ][0]
    assert updated_record["revision"] == 2
    assert updated_record["summary"] == "人工补充的证据概括。"
    assert updated_record["audit_trail"][-1]["action"] == "human_edit"


def test_knowledge_candidates_and_manual_records_are_human_governed(tmp_path):
    client = TestClient(
        create_app(tmp_path, research_service=_FakeResearchService())
    )
    discovered = client.post(
        "/api/v1/knowledge/candidates/discover",
        json={
            "kind": "method",
            "query": "management science causal method",
            "limit": 3,
            "actor_type": "agent",
        },
    )
    assert discovered.status_code == 200
    payload = discovered.json()
    assert payload["ai_report"]["schema_version"] == "ai4ms.ai-report.v1"
    candidate = payload["items"][0]
    assert candidate["status"] == "pending"

    approved_content = {
        **candidate["proposed_content"],
        "name": "Human-verified causal workflow",
        "family": "因果识别",
        "goal": "估计管理干预对企业结果的影响",
        "assumptions": "可辩护的识别假设",
        "diagnostics": "趋势、重叠与失败规则检查",
        "failure": "关键识别假设失败时退出因果解释",
    }
    approved = client.patch(
        f"/api/v1/knowledge/candidates/{candidate['candidate_id']}/review",
        json={
            "decision": "approve",
            "reason": "研究者已核对方法定义和原始来源。",
            "expected_revision": candidate["revision"],
            "edits": approved_content,
            "actor_type": "human",
        },
    )
    assert approved.status_code == 200
    record = approved.json()["record"]
    assert record["record_id"].startswith("MUSR_")
    assert record["revision"] == 1
    reviewed_candidate = approved.json()["candidate"]

    reapproved = client.patch(
        (
            "/api/v1/knowledge/candidates/"
            f"{candidate['candidate_id']}/review"
        ),
        json={
            "decision": "approve",
            "reason": "研究者再次核对并补充安慰剂诊断。",
            "expected_revision": reviewed_candidate["revision"],
            "edits": {
                "diagnostics": "趋势、重叠、安慰剂与敏感性检查",
            },
            "actor_type": "human",
        },
    )
    assert reapproved.status_code == 200
    assert reapproved.json()["record"]["record_id"] == record["record_id"]
    assert reapproved.json()["record"]["revision"] == 2
    record = reapproved.json()["record"]

    listed = client.get("/api/v1/knowledge/records?kind=method")
    assert listed.status_code == 200
    assert [item["record_id"] for item in listed.json()["items"]] == [
        record["record_id"]
    ]

    changed_content = {
        **record["content"],
        "diagnostics": "趋势、重叠、安慰剂与敏感性检查",
    }
    patched = client.patch(
        f"/api/v1/knowledge/records/{record['record_id']}",
        json={
            "content": changed_content,
            "reason": "人工补充安慰剂诊断。",
            "expected_revision": 2,
            "actor_type": "human",
        },
    )
    assert patched.status_code == 200
    assert patched.json()["revision"] == 3

    conflict = client.patch(
        f"/api/v1/knowledge/records/{record['record_id']}",
        json={
            "content": changed_content,
            "reason": "使用过期 revision 的修改。",
            "expected_revision": 2,
            "actor_type": "human",
        },
    )
    assert conflict.status_code == 409

    manual_formula = client.post(
        "/api/v1/knowledge/records",
        json={
            "kind": "formula",
            "content": {
                "name": "人工核验的固定效应公式",
                "category": "面板模型",
                "latex": "Y_{it}=beta D_{it}+alpha_i+lambda_t+epsilon_{it}",
                "use_when": "企业年度面板且需要控制双向固定效应",
                "notation": "i 表示企业，t 表示年份",
                "assumptions": "严格外生或有边界的条件外生",
                "diagnostics": "组内变异和聚类层级",
                "packages": "Stata reghdfe",
                "warning": "不能自动消除随时间变化的遗漏混杂",
                "source_urls": ["https://example.org/fixed-effects"],
            },
            "reason": "研究者根据原始方法资料人工创建。",
            "actor_type": "human",
        },
    )
    assert manual_formula.status_code == 201
    assert manual_formula.json()["record_id"].startswith("FUSR_")

    builtin_collision = client.post(
        "/api/v1/knowledge/records",
        json={
            "kind": "formula",
            "content": {
                **manual_formula.json()["content"],
                "formula_id": "F01",
                "name": "不得覆盖内置公式",
            },
            "reason": "验证自定义记录不能覆盖内置注册表。",
            "actor_type": "human",
        },
    )
    assert builtin_collision.status_code == 409
