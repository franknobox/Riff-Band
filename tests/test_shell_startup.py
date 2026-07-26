from __future__ import annotations

from pathlib import Path

from ui.shell import AOrchestraShell


class _FakeConsole:
    is_terminal = True

    def __init__(self) -> None:
        self.clear_calls = 0

    def clear(self) -> None:
        self.clear_calls += 1


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


def test_shell_clears_interactive_terminal_on_startup(tmp_path: Path):
    shell = AOrchestraShell(_make_config(tmp_path / "aorchestra.yaml"))
    fake_console = _FakeConsole()
    shell._console = fake_console

    shell._clear_startup_screen()

    assert fake_console.clear_calls == 1


def test_shell_startup_clear_can_be_disabled(tmp_path: Path, monkeypatch):
    shell = AOrchestraShell(_make_config(tmp_path / "aorchestra.yaml"))
    fake_console = _FakeConsole()
    shell._console = fake_console
    monkeypatch.setenv("RIFFBAND_NO_CLEAR", "1")

    shell._clear_startup_screen()

    assert fake_console.clear_calls == 0
