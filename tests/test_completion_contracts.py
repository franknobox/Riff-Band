from __future__ import annotations

import hashlib
import json

from fastapi.testclient import TestClient

from ai4ms.api.app import create_app


def _create_project(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/projects",
        json={
            "title": "AI adoption and operations",
            "initial_idea": "How does AI adoption change operating performance?",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_diagnostic_registry_is_versioned_and_contains_all_36_rules(tmp_path):
    client = TestClient(create_app(tmp_path))

    response = client.get("/api/v1/knowledge/diagnostics?limit=100")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1.0"
    assert payload["registry_version"] == "2026.07.1"
    assert payload["authority"] == "ai4ms-backend"
    assert payload["count"] == payload["total"] == 36
    assert [item["id"] for item in payload["items"]] == [
        f"D{index:02d}" for index in range(1, 37)
    ]
    assert response.headers["x-ai4ms-registry-version"] == "2026.07.1"
    assert "diagnostics-2026.07.1" in response.headers["etag"]

    filtered = client.get(
        "/api/v1/knowledge/diagnostics",
        params={"family": "因果识别", "level": "阻塞"},
    )
    assert filtered.status_code == 200
    assert 0 < filtered.json()["count"] < 36
    assert all(
        item["family"] == "因果识别" and item["level"] == "阻塞"
        for item in filtered.json()["items"]
    )

    detail = client.get("/api/v1/knowledge/diagnostics/d36")
    assert detail.status_code == 200
    assert detail.json()["item"]["id"] == "D36"


def test_interface_theme_profile_persists_while_allowing_local_first_ui(tmp_path):
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/v1/profile").json()["interface_theme"] == "graphite"

    updated = client.patch(
        "/api/v1/profile",
        json={"interface_theme": "blueprint"},
    )
    assert updated.status_code == 200
    assert updated.json()["interface_theme"] == "blueprint"

    invalid = client.patch(
        "/api/v1/profile",
        json={"interface_theme": "neon"},
    )
    assert invalid.status_code == 422

    restarted = TestClient(create_app(tmp_path))
    assert restarted.get("/api/v1/profile").json()["interface_theme"] == "blueprint"


def test_asset_section_patch_creates_revision_and_rejects_stale_writes(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)
    project_id = project["project_id"]
    revision = project["stages"][0]["revision"]

    saved = client.patch(
        f"/api/v1/projects/{project_id}/stages/problem/asset-sections/section-1",
        json={
            "title": "研究问题与边界",
            "content": "研究对象为平台企业；时间范围由研究者确认。",
            "expected_revision": revision,
            "change_reason": "Edit asset drilldown",
        },
    )
    assert saved.status_code == 200
    stage = saved.json()["stages"][0]
    assert stage["revision"] == revision + 1
    assert stage["content"]["_asset_version"]["schema_version"] == "1.0"
    assert (
        stage["content"]["_asset_version"]["sections"]["section-1"]["content"]
        == "研究对象为平台企业；时间范围由研究者确认。"
    )

    stale = client.patch(
        f"/api/v1/projects/{project_id}/stages/problem/asset-sections/section-2",
        json={
            "title": "理论机制",
            "content": "stale overwrite",
            "expected_revision": revision,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "revision_conflict"

    revisions = client.get(
        f"/api/v1/projects/{project_id}/stages/problem/revisions"
    ).json()["items"]
    assert [item["revision"] for item in revisions[:2]] == [
        revision + 1,
        revision,
    ]

    restarted = TestClient(create_app(tmp_path))
    persisted = restarted.get(f"/api/v1/projects/{project_id}").json()["stages"][0]
    assert (
        persisted["content"]["_asset_version"]["sections"]["section-1"]["title"]
        == "研究问题与边界"
    )


def test_analysis_log_download_rechecks_declared_artifact_hash(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)
    project_id = project["project_id"]
    run_id = "run_log_contract"
    project_dir = client.app.state.project_service.projects_dir / project_id
    run_dir = project_dir / "artifacts" / "runs" / run_id
    run_dir.mkdir(parents=True)
    log_path = run_dir / "analysis.log"
    log_path.write_bytes(b"verified Stata log\n")
    digest = hashlib.sha256(log_path.read_bytes()).hexdigest()
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "succeeded",
                "reason_code": "completed",
                "output_artifacts": [
                    {
                        "path": f"artifacts/runs/{run_id}/analysis.log",
                        "size": log_path.stat().st_size,
                        "sha256": digest,
                    }
                ],
                "logs": ["analysis.log"],
            }
        ),
        encoding="utf-8",
    )
    job_dir = project_dir / "artifacts" / "jobs"
    job_dir.mkdir(parents=True)
    (job_dir / f"{run_id}.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "project_id": project_id,
                "status": "succeeded",
                "reason_code": "completed",
                "created_at": "2026-07-25T00:00:00+00:00",
                "started_at": "2026-07-25T00:00:00+00:00",
                "finished_at": "2026-07-25T00:00:01+00:00",
                "timeout_seconds": 30,
                "cancel_requested": False,
                "parent_run_id": "",
                "request": {},
                "run_manifest_path": f"artifacts/runs/{run_id}/manifest.json",
            }
        ),
        encoding="utf-8",
    )

    downloaded = client.get(
        f"/api/v1/projects/{project_id}/stages/analysis/runs/{run_id}/artifacts/analysis.log"
    )
    assert downloaded.status_code == 200
    assert downloaded.text == "verified Stata log\n"

    log_path.write_bytes(b"tampered\n")
    rejected = client.get(
        f"/api/v1/projects/{project_id}/stages/analysis/runs/{run_id}/artifacts/analysis.log"
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "analysis_job_conflict"
