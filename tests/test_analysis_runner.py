from __future__ import annotations

import asyncio
import json
import os

import pytest

from ai4ms.runners.service import AnalysisRunnerService
from ai4ms.runners.stata import StataBatchAdapter, StataPolicyScanner, sha256_file
from ai4ms.services.models import AnalysisRunRequest


SAFE_DO_FILE = """version 18.0
set more off
set varabbrev off
args project_dir run_id input_dta output_dir
use `"`input_dta'"', clear
set seed 20260721
summarize outcome treatment
"""


def _project(status: str = "approved", binding_hash: str = "hash_plan") -> dict:
    return {
        "project_id": "prj_runner",
        "stages": [
            {
                "key": "identification",
                "status": status,
                "revision": 3,
                "content_hash": "hash_plan",
                "content": {
                    "execution_engine": "stata",
                    "stata_do_file": SAFE_DO_FILE,
                    "seed": 20260721,
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
                    "approved_analysis_plan_hash": binding_hash,
                    "do_file": SAFE_DO_FILE,
                    "runs": [],
                },
            },
        ],
    }


def _profile(available: bool = True) -> dict:
    return {
        "available": available,
        "engine": "stata",
        "mode": "batch",
        "executable": "fake-stata",
        "executable_name": "fake-stata",
        "version": "19",
        "edition": "MP",
        "license_mode": "user_byol",
        "license_confirmed": available,
        "max_concurrency": 1,
        "reason": "" if available else "not found",
    }


def test_stata_policy_blocks_external_process_install_network_and_traversal():
    issues = StataPolicyScanner.scan(
        "version 18\nshell whoami\nssc install reghdfe\ncopy https://example.com/x x\nuse ../secret.dta\nsave `\"`input_dta'\"', replace"
    )

    assert {item["code"] for item in issues} == {
        "external_process",
        "dynamic_install",
        "network_access",
        "parent_traversal",
        "overwrite_input",
    }


def test_stata_policy_blocks_prefixed_shell_early_exit_and_delimiter_changes():
    issues = StataPolicyScanner.scan(
        "version 18\ncapture noisily shell whoami\nexit 0\n#delimit ;\n"
    )

    assert {item["code"] for item in issues} == {
        "external_process",
        "early_exit",
        "delimiter_change",
    }


def test_stata_structure_requires_runner_bound_input():
    issues = StataPolicyScanner.required_structure_issues(
        "version 18\nset more off\nuse \"input/panel.dta\", clear\n"
    )

    assert {item["code"] for item in issues} == {
        "missing_runner_args",
        "missing_bound_input",
    }


def test_preflight_reports_no_runner_without_leaking_executable_path(tmp_path):
    project_dir = tmp_path / "prj_runner"
    project_dir.mkdir()
    (project_dir / "input.dta").write_bytes(b"fixture")
    service = AnalysisRunnerService(profile_factory=lambda: _profile(False))

    result = service.preflight(
        _project(), project_dir, AnalysisRunRequest(input_artifact_path="input.dta")
    )

    assert result["status"] == "blocked"
    assert result["reason_code"] == "no_runner"
    assert result["checks"]["gate_passed"] is True
    assert "executable" not in result["runner_profile"]


def test_preflight_blocks_unapproved_gate_stale_binding_and_path_traversal(tmp_path):
    project_dir = tmp_path / "prj_runner"
    project_dir.mkdir()
    service = AnalysisRunnerService(profile_factory=lambda: _profile())

    gate = service.preflight(
        _project(status="needs_review"),
        project_dir,
        AnalysisRunRequest(input_artifact_path="../outside.dta"),
    )
    stale = service.preflight(
        _project(binding_hash="old_hash"),
        project_dir,
        AnalysisRunRequest(input_artifact_path="../outside.dta"),
    )

    assert gate["reason_code"] == "gate_not_approved"
    assert stale["reason_code"] == "stale_plan_binding"
    assert any(item["code"] == "invalid_input" for item in stale["issues"])


def test_preflight_resolves_registered_asset_and_checks_hash_and_columns(tmp_path):
    project_dir = tmp_path / "prj_runner"
    data_dir = project_dir / "artifacts" / "data" / "data_bbbbbbbbbbbb"
    data_dir.mkdir(parents=True)
    input_path = data_dir / "panel.dta"
    input_path.write_bytes(b"registered stata fixture")
    project = _project()
    project["data_assets"] = [
        {
            "asset_id": "data_bbbbbbbbbbbb",
            "stored_path": "artifacts/data/data_bbbbbbbbbbbb/panel.dta",
            "sha256": sha256_file(input_path),
            "metadata": {
                "columns": [
                    {"name": "outcome"},
                    {"name": "treatment"},
                ]
            },
        }
    ]
    service = AnalysisRunnerService(profile_factory=lambda: _profile())

    ready = service.preflight(
        project,
        project_dir,
        AnalysisRunRequest(input_asset_id="data_bbbbbbbbbbbb"),
    )
    assert ready["status"] == "ready"
    assert ready["input_asset_id"] == "data_bbbbbbbbbbbb"
    assert ready["checks"]["asset_hash_passed"] is True
    assert ready["missing_variables"] == []

    input_path.write_bytes(b"tampered")
    tampered = service.preflight(
        project,
        project_dir,
        AnalysisRunRequest(input_asset_id="data_bbbbbbbbbbbb"),
    )
    assert tampered["status"] == "blocked"
    assert tampered["reason_code"] == "asset_hash_mismatch"

    input_path.write_bytes(b"registered stata fixture")
    project["data_assets"][0]["metadata"]["columns"] = [{"name": "outcome"}]
    missing = service.preflight(
        project,
        project_dir,
        AnalysisRunRequest(input_asset_id="data_bbbbbbbbbbbb"),
    )
    assert missing["status"] == "blocked"
    assert missing["reason_code"] == "missing_required_variables"


class _FakeAdapter:
    async def execute(self, _profile, _do_file, _project_dir, _run_id, _input, output_dir, _timeout):
        (output_dir / "structured_results.csv").write_text(
            "result_id,kind,specification_id,term,label,estimate,std_error,statistic,p_value,ci_lower,ci_upper,sample_size,status,unit\n"
            "RES_1,estimate,main,treatment,baseline,0.2,0.05,4,0.001,0.102,0.298,100,observed,\n",
            encoding="utf-8",
        )
        (output_dir / "data_signature.txt").write_text("signature-test\n", encoding="utf-8")
        return {
            "status": "succeeded",
            "reason_code": "completed",
            "exit_code": 0,
            "started_at": "2026-07-21T00:00:00+00:00",
            "finished_at": "2026-07-21T00:00:01+00:00",
            "duration_seconds": 1.0,
        }


def test_submit_writes_immutable_manifest_and_output_hashes(tmp_path):
    project_dir = tmp_path / "prj_runner"
    project_dir.mkdir()
    (project_dir / "input.dta").write_bytes(b"fixture")
    service = AnalysisRunnerService(
        adapter=_FakeAdapter(), profile_factory=lambda: _profile()
    )

    run = asyncio.run(
        service.submit(
            _project(),
            project_dir,
            AnalysisRunRequest(input_artifact_path="input.dta", timeout_seconds=30),
        )
    )

    assert run["status"] == "succeeded"
    assert run["analysis_plan_hash"] == "hash_plan"
    assert run["input_artifacts"][0]["sha256"]
    assert run["structured_results"][0]["term"] == "treatment"
    assert run["structured_results"][0]["estimate"] == 0.2
    assert run["data_signature"] == "signature-test"
    assert any(item["path"].endswith("structured_results.csv") and len(item["sha256"]) == 64 for item in run["output_artifacts"])
    manifest = project_dir / run["manifest_path"]
    assert json.loads(manifest.read_text(encoding="utf-8"))["run_id"] == run["run_id"]


@pytest.mark.skipif(os.name == "nt", reason="uses a POSIX fake Stata executable")
def test_stata_batch_adapter_enforces_timeout_and_writes_process_logs(tmp_path):
    executable = tmp_path / "fake-stata"
    executable.write_text("#!/bin/sh\nsleep 5\n", encoding="utf-8")
    executable.chmod(0o755)
    do_file = tmp_path / "entrypoint.do"
    do_file.write_text("version 18.0\n", encoding="utf-8")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    input_path = tmp_path / "input.dta"
    input_path.write_bytes(b"fixture")

    result = asyncio.run(
        StataBatchAdapter().execute(
            {"executable": str(executable)},
            do_file,
            tmp_path,
            "run_timeout",
            input_path,
            output_dir,
            0.05,
        )
    )

    assert result["status"] == "failed"
    assert result["reason_code"] == "timeout"
    assert result["duration_seconds"] < 2
    assert (output_dir / "runner.stdout.log").is_file()
    assert (output_dir / "runner.stderr.log").is_file()
