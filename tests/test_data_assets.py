from __future__ import annotations

import hashlib
from io import BytesIO

import pandas as pd
from fastapi.testclient import TestClient

from ai4ms.api.app import create_app


def _stata_bytes() -> bytes:
    buffer = BytesIO()
    pd.DataFrame(
        {
            "firm_id": [1, 1, 2],
            "year": [2022, 2023, 2023],
            "outcome": [1.2, 1.5, 2.0],
            "treatment": [0, 1, 1],
        }
    ).to_stata(
        buffer,
        write_index=False,
        version=118,
        data_label="AI4MS upload fixture",
        variable_labels={"outcome": "Innovation outcome"},
    )
    return buffer.getvalue()


def test_upload_registers_stata_asset_hash_and_metadata(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = client.post(
        "/api/v1/projects",
        json={"title": "Data asset", "initial_idea": "Inspect a Stata dataset"},
    ).json()
    payload = _stata_bytes()

    uploaded = client.post(
        f"/api/v1/projects/{project['project_id']}/assets/data",
        files={"file": ("panel.dta", payload, "application/x-stata")},
    )

    assert uploaded.status_code == 201, uploaded.text
    asset = uploaded.json()
    assert asset["asset_id"].startswith("data_")
    assert asset["sha256"] == hashlib.sha256(payload).hexdigest()
    assert asset["size_bytes"] == len(payload)
    assert asset["metadata"]["row_count"] == 3
    assert asset["metadata"]["column_count"] == 4
    assert {item["name"] for item in asset["metadata"]["columns"]} == {
        "firm_id",
        "year",
        "outcome",
        "treatment",
    }

    hydrated = client.get(f"/api/v1/projects/{project['project_id']}").json()
    assert hydrated["data_assets"][0]["asset_id"] == asset["asset_id"]
    listed = client.get(
        f"/api/v1/projects/{project['project_id']}/assets/data"
    ).json()["items"]
    assert listed == hydrated["data_assets"]


def test_upload_rejects_non_stata_file(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = client.post(
        "/api/v1/projects",
        json={"title": "Data asset", "initial_idea": "Reject non-Stata data"},
    ).json()
    response = client.post(
        f"/api/v1/projects/{project['project_id']}/assets/data",
        files={"file": ("notes.csv", b"a,b\n1,2\n", "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_data_format"
