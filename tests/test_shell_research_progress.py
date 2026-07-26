from __future__ import annotations

from pathlib import Path

from rich.console import Console

from research import ResearchRequest
from ui.shell import AOrchestraShell


def _make_config(path: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                "main_model: test-model",
                "mode: auto",
                "profile_name: generic",
                "sub_models:",
                "  - test-model",
                "sources_dir: workspace/sources",
                "workspace_dir: workspace",
                "max_attempts: 1",
                "max_subagent_steps: 1",
                "subagent_process_timeout_seconds: 1",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _make_shell(tmp_path: Path) -> tuple[AOrchestraShell, Console]:
    shell = AOrchestraShell(_make_config(tmp_path / "aorchestra.yaml"))
    console = Console(record=True, color_system=None, width=120)
    shell._console = console
    return shell, console


def test_research_progress_hides_raw_metadata_and_shows_thinking(tmp_path: Path):
    shell, console = _make_shell(tmp_path)
    request = ResearchRequest(
        topic="2026年AI行业趋势",
        mode="visual",
        depth="deep",
        output_format="html",
        trigger="cli",
    )

    shell._render_research_progress(
        "Research run start topic='2026年AI行业趋势' mode=visual steps=10 "
        "agent_execution=True run_dir=C:\\Users\\11761\\workspace\\research\\run",
        request,
    )
    shell._render_research_progress(
        "Step 1/10 start key=decompose_topic title='Step 1: Topic Decomposition' "
        "executor=single-agent expected_section='研究问题拆解' min_findings=0 "
        "min_papers=0 material_ready=True blocking=False issues=[]",
        request,
    )

    output = console.export_text()
    assert "[research]" in output
    assert "2026年AI行业趋势 started" in output
    assert "think..." in output
    assert "run_dir=" not in output
    assert "expected_section" not in output
    assert "material_ready" not in output


def test_research_progress_renders_step_result_compactly(tmp_path: Path):
    shell, console = _make_shell(tmp_path)
    request = ResearchRequest(topic="test", trigger="cli")

    shell._render_research_progress(
        "Step 2/10 finished key=information_search status=partial issues=1",
        request,
    )

    output = console.export_text()
    assert "[partial]" in output
    assert "2/10 Information Search" in output
    assert "issues=1" in output
