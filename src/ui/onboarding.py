"""First-run onboarding wizard for Riff Band."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text
from ui import theme


YAML_TEMPLATE = """\
# AOrchestra Agent 运行配置

main_model: {model}
mode: {mode}                       # single | multi | auto
profile_name: generic

sub_models:
  - {model}

sources_dir: workspace/sources
workspace_dir: {workspace}         # 工作区根目录 (output, sessions, sources)
max_attempts: 6
max_subagent_steps: 12
subagent_process_timeout_seconds: 300
"""

ENV_TEMPLATE = """\
# AOrchestra 环境配置
# LLM API key 通过环境变量配置

AUTOENV_OPENAI_API_KEY={api_key}
AUTOENV_OPENAI_BASE_URL={base_url}
AUTOENV_OPENAI_MODELS={model}

# 联网搜索 (可选) — https://serper.dev 免费注册
# SERPER_API_KEY=your_serper_api_key_here
SERPER_BASE_URL=https://google.serper.dev/search
"""


def run_onboarding(config_path: Path, env_path: Path) -> bool:
    """Run the first-run wizard.  Returns True if config was created."""
    console = Console()

    # ── banner ───────────────────────────────────────────────────
    console.print()
    console.print(
        Panel(
            Text.assemble(
                ("Welcome to ", "bold"),
                (theme.APP_NAME, theme.BRAND),
                ("\n\n", ""),
                ("Looks like this is your first run.\n", "dim"),
                ("Let's set things up in a few steps.", "dim"),
            ),
            border_style=theme.BORDER,
            title="[bold]Setup Wizard[/]",
        )
    )
    console.print()

    # ── step 1 — model ───────────────────────────────────────────
    console.print("[bold]Step 1/3[/] — LLM Model")
    console.print("[dim]Riff Band supports any OpenAI-compatible API.[/]")

    model = Prompt.ask(
        "  Model name",
        default="MiniMax-M2.7",
    )
    base_url = Prompt.ask(
        "  API Base URL",
        default="https://api.minimax.chat/v1",
    )
    api_key = Prompt.ask(
        "  API Key",
        password=True,
    )

    console.print()

    # ── step 2 — workspace ──────────────────────────────────────
    console.print("[bold]Step 2/3[/] — Workspace")
    console.print("[dim]Where outputs, sessions, and sources are stored.[/]")

    workspace = Prompt.ask(
        "  Workspace directory",
        default="workspace",
    )
    console.print()

    # ── step 3 — mode ───────────────────────────────────────────
    console.print("[bold]Step 3/3[/] — Default Mode")
    console.print("[dim]How should tasks be handled by default?[/]")
    console.print(f"  [{theme.ACCENT}]single[/]  — lightweight, one agent, low latency")
    console.print(f"  [{theme.ACCENT}]multi[/]   — orchestrated, parallel sub-agents")
    console.print(f"  [{theme.ACCENT}]auto[/]    — auto-detect based on task complexity [dim](recommended)[/]")

    mode = Prompt.ask(
        "  Default mode",
        choices=["single", "multi", "auto"],
        default="auto",
    )
    console.print()

    # ── confirm & write ──────────────────────────────────────────
    console.print(
        Panel(
            Text.assemble(
                ("Model:     ", "dim"), (f"{model}\n", ""),
                ("Base URL:  ", "dim"), (f"{base_url}\n", ""),
                ("Key:       ", "dim"), ("****\n", theme.MUTED),
                ("Workspace: ", "dim"), (f"{workspace}\n", ""),
                ("Mode:      ", "dim"), (f"{mode}\n", ""),
            ),
            title="[bold]Summary[/]",
            border_style=theme.BORDER,
        )
    )

    if not Confirm.ask("  Write configuration?", default=True):
        console.print("[dim]Setup cancelled. Run again to configure.[/]")
        return False

    # Write aorchestra.yaml
    config_path.write_text(
        YAML_TEMPLATE.format(
            model=model,
            mode=mode,
            workspace=workspace,
        ),
        encoding="utf-8",
    )

    # Write .env
    env_path.write_text(
        ENV_TEMPLATE.format(
            api_key=api_key,
            base_url=base_url,
            model=model,
        ),
        encoding="utf-8",
    )

    console.print()
    console.print(
        Panel(
            Text.assemble(
                (f"[{theme.SUCCESS_BOLD}]✓[/] Config saved to ", ""),
                (str(config_path), "bold"),
                ("\n", ""),
                (f"[{theme.SUCCESS_BOLD}]✓[/] API key saved to ", ""),
                (str(env_path), "bold"),
                ("\n\n", ""),
                ("Run [bold]python shell.py --config "),
                (str(config_path), theme.ACCENT),
                ("[/] to start.", "bold"),
            ),
            border_style=theme.BORDER,
            title="[bold]Ready[/]",
        )
    )
    return True
