from __future__ import annotations

import asyncio
from pathlib import Path

from ai4ms.orchestration import AOrchestraStageService


class _WorkerCompleted:
    session_id = "worker_1"


class TaskComplete:
    success = True
    summary = "完成阶段审查"
    attempts = 4
    input_tokens = 10
    output_tokens = 20
    total_tokens = 30
    total_cost = 0.0
    cost_known = False


class _FakeRuntime:
    async def stream(self):
        yield _WorkerCompleted()
        yield TaskComplete()


def _project() -> dict:
    return {
        "project_id": "prj_orchestration",
        "title": "测试课题",
        "initial_idea": "测试研究问题",
        "stages": [],
    }


def test_aorchestra_adapter_isolates_artifacts_and_limits_audit_tools(tmp_path):
    captured = {}

    def builder(**kwargs):
        captured.update(kwargs)
        output_dir = Path(kwargs["output_dir"])
        (output_dir / "stage_analysis.md").write_text(
            "## 阶段编排结论\n保留负结果并降低主张强度。",
            encoding="utf-8",
        )
        return _FakeRuntime()

    service = AOrchestraStageService(
        tmp_path / "projects",
        project_builder=builder,
        model_name_factory=lambda: "test-model",
        model_names_factory=lambda _primary: ("test-model", "fallback-model"),
    )
    result = asyncio.run(
        service.analyze(_project(), "robustness", "审查失败项", {"analysis_runs": []})
    )

    allowed = captured["runtime_metadata"]["allowed_worker_tools"]
    assert "read_source" in allowed
    assert "web_search" not in allowed
    assert "write_report_section" in allowed
    assert captured["max_parallel_subtasks"] >= 2
    assert captured["sub_models"] == ["test-model", "fallback-model"]
    assert result.subagent_runs == 1
    assert result.status == "complete"
    project_dir = tmp_path / "projects" / "prj_orchestration"
    assert (project_dir / result.report_path).is_file()
    assert (project_dir / "agent-runs" / result.run_id / "orchestration.json").is_file()
