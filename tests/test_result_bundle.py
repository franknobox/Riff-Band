from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

import uvicorn
import pytest
from fastapi.testclient import TestClient

from ai4ms.runners.bundle import (
    create_request_archive,
    load_and_validate_result_bundle,
    parse_result_bundle,
    verify_run_request_signature,
    write_run_contract_files,
)
from ai4ms.runners.contracts import RunBundleRequest
from ai4ms.runners.local_app import create_local_runner_app
from ai4ms.runners.remote import RemoteStataAdapter
from ai4ms.runners.service import AnalysisRunnerService
from ai4ms.runners.stata import sha256_file
from ai4ms.services.models import AnalysisRunRequest


RESULTS_CSV = (
    "result_id,kind,specification_id,term,label,estimate,std_error,statistic,p_value,"
    "ci_lower,ci_upper,sample_size,status,unit\n"
    "RES_1,estimate,main,treatment,approved model,0.2,0.05,4,0.001,0.102,0.298,100,observed,\n"
)


class _FakeStata:
    async def execute(self, _profile, _entrypoint, _project_dir, _run_id, _input, output_dir, _timeout):
        (output_dir / "structured_results.csv").write_text(RESULTS_CSV, encoding="utf-8")
        (output_dir / "data_signature.txt").write_text("stata-signature\n", encoding="utf-8")
        (output_dir / "analysis.log").write_text("fake Stata run\n", encoding="utf-8")
        (output_dir / "coefficient.png").write_bytes(b"png")
        return {
            "status": "succeeded",
            "reason_code": "completed",
            "exit_code": 0,
            "started_at": "2026-07-24T00:00:00+00:00",
            "finished_at": "2026-07-24T00:00:01+00:00",
            "duration_seconds": 1.0,
        }


class _CancelableStata:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release: asyncio.Event | None = None

    async def execute(self, _profile, _entrypoint, _project_dir, _run_id, _input, _output_dir, _timeout):
        self.release = asyncio.Event()
        self.started.set()
        await self.release.wait()
        return {
            "status": "canceled",
            "reason_code": "user_canceled",
            "exit_code": None,
            "started_at": "2026-07-24T00:00:00+00:00",
            "finished_at": "2026-07-24T00:00:01+00:00",
            "duration_seconds": 1.0,
        }

    async def cancel(self, _run_id: str) -> bool:
        if self.release is None:
            return False
        self.release.set()
        return True


def _profile():
    return {
        "available": True,
        "engine": "stata",
        "mode": "batch",
        "executable": "fake-stata",
        "executable_name": "fake-stata",
        "version": "19",
        "edition": "MP",
        "os": "Windows",
        "locale": "zh_CN",
        "license_mode": "user_byol",
        "license_confirmed": True,
        "max_concurrency": 1,
        "reason": "",
    }


def test_result_bundle_parser_produces_structured_results(tmp_path):
    (tmp_path / "structured_results.csv").write_text(RESULTS_CSV, encoding="utf-8")
    (tmp_path / "data_signature.txt").write_text("sig\n", encoding="utf-8")
    result = parse_result_bundle(
        tmp_path,
        run_id="run_parser",
        input_sha256="a" * 64,
        do_file_sha256="b" * 64,
        execution={
            "status": "succeeded",
            "reason_code": "completed",
            "exit_code": 0,
            "duration_seconds": 0.2,
        },
        runner_profile=_profile(),
        signing_token="result-secret",
    )

    assert result["status"] == "succeeded"
    assert result["data_signature"] == "sig"
    assert result["structured_results"][0]["estimate"] == 0.2
    assert json.loads((tmp_path / "result_bundle.json").read_text(encoding="utf-8"))[
        "run_id"
    ] == "run_parser"
    load_and_validate_result_bundle(
        tmp_path / "result_bundle.json",
        run_id="run_parser",
        input_sha256="a" * 64,
        do_file_sha256="b" * 64,
        signing_token="result-secret",
        require_signature=True,
    )

    (tmp_path / "structured_results.csv").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="(size|hash) mismatch"):
        load_and_validate_result_bundle(
            tmp_path / "result_bundle.json",
            run_id="run_parser",
            input_sha256="a" * 64,
            do_file_sha256="b" * 64,
            signing_token="result-secret",
            require_signature=True,
        )


def test_run_bundle_hmac_detects_manifest_tampering(tmp_path):
    request = RunBundleRequest(
        run_id="run_signature",
        project_id="prj_signature",
        input_sha256="a" * 64,
        do_file_sha256="b" * 64,
        timeout_seconds=30,
        analysis_plan_revision=1,
        analysis_plan_hash="plan-hash",
    )
    signed = write_run_contract_files(
        tmp_path, request, signing_token="shared-secret"
    )

    assert verify_run_request_signature(signed, "shared-secret") is True
    tampered = signed.model_copy(update={"timeout_seconds": 120})
    assert verify_run_request_signature(tampered, "shared-secret") is False


def test_local_runner_accepts_signed_request_and_returns_result_bundle(tmp_path):
    bundle_dir = tmp_path / "request"
    bundle_dir.mkdir()
    input_path = bundle_dir / "fixture.dta"
    input_path.write_bytes(b"stata fixture")
    do_file = "version 18.0\nset more off\nargs project_dir run_id input_dta output_dir\nuse `\"`input_dta'\"', clear\nreg outcome treatment\n"
    (bundle_dir / "analysis.do").write_text(do_file, encoding="utf-8")
    request = RunBundleRequest(
        run_id="run_local_test",
        project_id="prj_local",
        input_sha256=sha256_file(input_path),
        do_file_sha256=sha256_file(bundle_dir / "analysis.do"),
        timeout_seconds=30,
        analysis_plan_revision=3,
        analysis_plan_hash="plan-hash",
    )
    write_run_contract_files(bundle_dir, request, signing_token="test-token")
    archive_path = tmp_path / "request.zip"
    create_request_archive(bundle_dir, input_path, archive_path)
    app = create_local_runner_app(
        adapter=_FakeStata(),
        profile_factory=_profile,
        data_dir=tmp_path / "runner",
        token="test-token",
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/runs",
            content=archive_path.read_bytes(),
            headers={
                "Content-Type": "application/zip",
                "X-AI4MS-Runner-Token": "test-token",
            },
        )

    assert response.status_code == 200, response.text
    result_zip = tmp_path / "result.zip"
    result_zip.write_bytes(response.content)
    with zipfile.ZipFile(result_zip) as archive:
        manifest = json.loads(archive.read("result_bundle.json"))
        assert "structured_results.csv" in archive.namelist()
        assert "coefficient.png" in archive.namelist()
    assert manifest["status"] == "succeeded"
    assert manifest["structured_results"][0]["term"] == "treatment"


def test_workbench_remote_adapter_round_trips_through_local_runner(tmp_path, monkeypatch):
    local_app = create_local_runner_app(
        adapter=_FakeStata(),
        profile_factory=_profile,
        data_dir=tmp_path / "local-runner",
        token="roundtrip-token",
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(local_app, host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 5
    while not server.started and time.time() < deadline:
        time.sleep(0.02)
    assert server.started

    project_dir = tmp_path / "project"
    data_dir = project_dir / "artifacts" / "data" / "data_aaaaaaaaaaaa"
    data_dir.mkdir(parents=True)
    input_path = data_dir / "panel.dta"
    input_path.write_bytes(b"stata fixture")
    do_file = (
        "version 18.0\nset more off\nargs project_dir run_id input_dta output_dir\n"
        "use `\"`input_dta'\"', clear\nreg outcome treatment\n"
    )
    project = {
        "project_id": "prj_remote",
        "data_assets": [
            {
                "asset_id": "data_aaaaaaaaaaaa",
                "stored_path": "artifacts/data/data_aaaaaaaaaaaa/panel.dta",
                "sha256": sha256_file(input_path),
                "metadata": {
                    "columns": [
                        {"name": "outcome"},
                        {"name": "treatment"},
                    ]
                },
            }
        ],
        "stages": [
            {
                "key": "identification",
                "status": "approved",
                "revision": 3,
                "content_hash": "plan-hash",
                "content": {
                    "execution_engine": "stata",
                    "stata_do_file": do_file,
                    "variable_roles": [
                        {"source_variable": "outcome"},
                        {"source_variable": "treatment"},
                    ],
                },
            },
            {
                "key": "analysis",
                "status": "in_progress",
                "revision": 1,
                "content": {
                    "approved_analysis_plan_revision": 3,
                    "approved_analysis_plan_hash": "plan-hash",
                    "do_file": do_file,
                },
            },
        ],
    }
    monkeypatch.setenv("AI4MS_STATA_RUNNER_URL", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("AI4MS_STATA_RUNNER_TOKEN", "roundtrip-token")
    try:
        service = AnalysisRunnerService()
        assert service.status()["available"] is True
        run = asyncio.run(
            service.submit(
                project,
                project_dir,
                AnalysisRunRequest(input_asset_id="data_aaaaaaaaaaaa", timeout_seconds=30),
            )
        )
    finally:
        server.should_exit = True
        thread.join(timeout=5)

    assert run["status"] == "succeeded"
    assert run["runner_profile"]["transport"] == "http_local_runner"
    assert run["structured_results"][0]["term"] == "treatment"
    assert run["data_signature"] == "stata-signature"


def test_remote_cancel_reaches_active_local_runner(tmp_path, monkeypatch):
    bundle_dir = tmp_path / "request"
    bundle_dir.mkdir()
    input_path = bundle_dir / "fixture.dta"
    input_path.write_bytes(b"stata fixture")
    do_file = (
        "version 18.0\nset more off\nargs project_dir run_id input_dta output_dir\n"
        "use `\"`input_dta'\"', clear\nreg outcome treatment\n"
    )
    analysis_path = bundle_dir / "analysis.do"
    analysis_path.write_text(do_file, encoding="utf-8")
    request = RunBundleRequest(
        run_id="run_cancel_test",
        project_id="prj_cancel",
        input_sha256=sha256_file(input_path),
        do_file_sha256=sha256_file(analysis_path),
        timeout_seconds=30,
        analysis_plan_revision=1,
        analysis_plan_hash="plan-hash",
    )
    write_run_contract_files(bundle_dir, request, signing_token="cancel-token")
    archive_path = tmp_path / "request.zip"
    create_request_archive(bundle_dir, input_path, archive_path)

    adapter = _CancelableStata()
    local_app = create_local_runner_app(
        adapter=adapter,
        profile_factory=_profile,
        data_dir=tmp_path / "local-runner",
        token="cancel-token",
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(local_app, host="127.0.0.1", port=port, log_level="error")
    )
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    deadline = time.time() + 5
    while not server.started and time.time() < deadline:
        time.sleep(0.02)
    assert server.started

    response_body: dict[str, bytes] = {}

    def submit_bundle() -> None:
        http_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/runs",
            data=archive_path.read_bytes(),
            headers={
                "Content-Type": "application/zip",
                "X-AI4MS-Runner-Token": "cancel-token",
            },
            method="POST",
        )
        with urllib.request.urlopen(http_request, timeout=10) as response:
            response_body["content"] = response.read()

    submit_thread = threading.Thread(target=submit_bundle)
    submit_thread.start()
    try:
        assert adapter.started.wait(timeout=5)
        monkeypatch.setenv("AI4MS_STATA_RUNNER_URL", f"http://127.0.0.1:{port}")
        monkeypatch.setenv("AI4MS_STATA_RUNNER_TOKEN", "cancel-token")
        assert asyncio.run(RemoteStataAdapter().cancel("run_cancel_test")) is True
        submit_thread.join(timeout=10)
        assert not submit_thread.is_alive()
    finally:
        server.should_exit = True
        server_thread.join(timeout=5)

    result_zip = tmp_path / "canceled.zip"
    result_zip.write_bytes(response_body["content"])
    with zipfile.ZipFile(result_zip) as archive:
        manifest = json.loads(archive.read("result_bundle.json"))
    assert manifest["status"] == "canceled"
    assert manifest["reason_code"] == "user_canceled"
