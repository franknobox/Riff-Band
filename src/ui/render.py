"""Rich-based terminal renderer for AOrchestra ShellMessages."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from core.message import (
    ContentPart,
    ErrorMessage,
    OrchestratorDecision,
    OrchestratorThinking,
    PhaseTransition,
    StatusUpdate,
    SubAgentCreated,
    SubAgentResult,
    SubAgentStart,
    SubAgentStepEnd,
    SubAgentStepStart,
    TaskCancelled,
    TaskComplete,
    WorkerCompleted,
    WorkerSpawned,
    WorkerWaitEnd,
    WorkerWaitStart,
)
from ui import theme

# Mapping status → icon
_STATUS_ICONS: Dict[str, str] = {
    "done": f"[{theme.SUCCESS_BOLD}]✓[/]",
    "partial": f"[{theme.WARNING_BOLD}]~[/]",
    "blocked": f"[{theme.ERROR_BOLD}]✗[/]",
    "timeout": f"[{theme.ERROR_BOLD}]⏱[/]",
    "failed": f"[{theme.ERROR_BOLD}]✗[/]",
    "running": f"[{theme.INFO_BOLD}]◎[/]",
    "succeeded": f"[{theme.SUCCESS_BOLD}]✓[/]",
}


class MessageRenderer:
    """Render ShellMessage objects to Rich renderables."""

    def __init__(self, console: Console):
        self._console = console
        self._worker_labels: Dict[str, str] = {}
        self._step_buf = ""       # accumulate text within one step
        self._in_json = False     # suppress JSON blocks

    # ── helpers ───────────────────────────────────────────────────

    def _icon_for(self, status: str) -> str:
        return _STATUS_ICONS.get(status, "[dim]?[/]")

    def _label_for(self, session_id: str) -> str:
        return self._worker_labels.get(session_id, session_id[:8])

    @staticmethod
    def _collapse_text(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @classmethod
    def _short_task_label(cls, label: str, fallback: str = "task") -> str:
        text = cls._collapse_text(label)
        match = re.search(r"\btask[_-]?\d+\b", text, flags=re.IGNORECASE)
        if match:
            return match.group(0).replace("-", "_")
        return text.split(" ", 1)[0] if text else fallback

    @classmethod
    def _task_summary(cls, instruction: str, label: str = "", limit: int = 96) -> str:
        label_text = cls._collapse_text(label)
        label_match = re.match(r"^(task[_-]?\d+)\s+(.+)$", label_text, flags=re.IGNORECASE)
        if label_match:
            summary = label_match.group(2).strip()
            if len(summary) > limit:
                summary = summary[: max(0, limit - 1)].rstrip() + "..."
            return summary

        text = str(instruction or "").strip()
        for marker in ("具体任务:", "具体任务：", "task:", "Task:"):
            if marker in text:
                text = text.split(marker, 1)[1].strip()
                break

        lines: List[str] = []
        skip_prefixes = (
            "任务类型:",
            "任务类型：",
            "期望产出:",
            "期望产出：",
            "完成标准:",
            "完成标准：",
            "context:",
            "Context:",
        )
        for raw in text.splitlines():
            line = raw.strip()
            if not line or any(line.startswith(prefix) for prefix in skip_prefixes):
                continue
            lines.append(line)

        summary = cls._collapse_text(" ".join(lines) if lines else text)
        if label_text and summary.startswith(label_text):
            summary = summary[len(label_text):].strip()
        if len(summary) > limit:
            summary = summary[: max(0, limit - 1)].rstrip() + "..."
        return summary

    @staticmethod
    def _format_cost(cost: float, cost_known: bool = True) -> str:
        return f"${cost:.4f}" if cost_known else "N/A"

    @staticmethod
    def _format_tokens(total: int, input_tokens: int = 0, output_tokens: int = 0) -> str:
        if total <= 0:
            return "0"
        if input_tokens or output_tokens:
            return f"{total:,} (in={input_tokens:,}, out={output_tokens:,})"
        return f"{total:,}"

    # ── per-message renderers ─────────────────────────────────────

    def render(self, msg) -> Optional[RenderableType]:
        """Dispatch to the correct render method."""
        method = getattr(self, f"_render_{type(msg).__name__}", None)
        if method is not None:
            return method(msg)
        return None

    def _render_OrchestratorThinking(self, msg: OrchestratorThinking) -> RenderableType:
        self._step_buf = ""
        self._in_json = False
        return Text.assemble(
            ("  ◌ ", theme.ACCENT),
            (f"[{msg.attempt}/{msg.max_attempts}] ", "dim"),
            ("MainAgent planning...", "bold"),
        )

    def _render_StatusUpdate(self, msg: StatusUpdate) -> RenderableType:
        """Compact status line: phase | tokens."""
        parts = [f"phase={msg.phase}"]
        if msg.input_tokens:
            parts.append(f"in={msg.input_tokens}")
        if msg.output_tokens:
            parts.append(f"out={msg.output_tokens}")
        return Text(f"  ── {' | '.join(parts)} ──", style="dim")

    def _render_OrchestratorDecision(self, msg: OrchestratorDecision) -> RenderableType:
        action = msg.action or "unknown"
        reasoning = msg.reasoning or ""
        lines: List[RenderableType] = [
            Text.assemble(
                ("  ", ""),
                (" → ", theme.ACCENT),
                (action, theme.ACCENT),
            )
        ]
        if reasoning:
            lines.append(Text(reasoning[:200], style="dim italic"))
        return Group(*lines)

    def _render_PhaseTransition(self, msg: PhaseTransition) -> RenderableType:
        return Rule(
            f"[bold]Phase: {msg.from_phase} → {msg.to_phase}[/]",
            style=theme.BORDER,
            align="left",
        )

    def _render_WorkerSpawned(self, msg: WorkerSpawned) -> RenderableType:
        if msg.session_id and msg.label:
            self._worker_labels[msg.session_id] = msg.label
        short_task = (msg.task_instruction or "")[:60]
        return Text.assemble(
            ("  [>] ", theme.ACCENT),
            (f"{msg.label}", "bold"),
            (f"\n      {short_task}" if short_task else "", "dim"),
        )

    def _render_WorkerCompleted(self, msg: WorkerCompleted) -> RenderableType:
        icon = self._icon_for(msg.status)
        label = self._label_for(msg.session_id)
        parts = [f"  {icon} {label} | status={msg.status}"]
        if msg.steps_taken:
            parts.append(f"steps={msg.steps_taken}")
        if msg.cost:
            parts.append(f"cost=${msg.cost:.4f}")
        text = Text(" ".join(parts))
        if msg.issues:
            for issue in msg.issues[:3]:
                text.append(f"\n      [dim]! {issue}[/]")
        return text

    def _render_WorkerWaitStart(self, msg: WorkerWaitStart) -> RenderableType:
        n = len(msg.session_ids) or "all"
        return Text(f"  [wait] Waiting for {n} workers ({msg.timeout_seconds}s)...", style="dim")

    def _render_WorkerWaitEnd(self, msg: WorkerWaitEnd) -> RenderableType:
        return Text(
            f"  [wait] collected={msg.completed} still_running={msg.still_running}",
            style="dim",
        )

    def _render_SubAgentStepStart(self, msg: SubAgentStepStart) -> RenderableType:
        """Reset streaming buffer on new step."""
        self._step_buf = ""
        self._in_json = False
        return None

    def _render_SubAgentCreated(self, msg: SubAgentCreated) -> RenderableType:
        """Show compact agent assembly info."""
        task_label = self._short_task_label(msg.task_label, fallback=msg.agent_id or "task")
        summary = self._task_summary(msg.task_instruction, msg.task_label)
        task_text = f"{task_label}  {summary}" if summary else task_label
        lines: List[RenderableType] = [
            Text.assemble(
                ("  [+] ", theme.ACCENT),
                (f"Agent {msg.agent_id or 'sub'} assembled", "bold"),
            ),
            Text.assemble(
                ("      Task: ", "dim"),
                (task_text, ""),
            ),
        ]
        lines.append(
            Text.assemble(
                ("      Model: ", "dim"),
                (msg.model or "default", ""),
            )
        )
        if msg.tools:
            lines.append(
                Text.assemble(
                    ("      Tools: ", "dim"),
                    (", ".join(msg.tools[:6]), ""),
                )
            )
        return Group(*lines)

    def _render_ContentPart(self, msg: ContentPart) -> RenderableType:
        """Streaming text: show think blocks as dim, suppress JSON."""
        self._step_buf += msg.text
        if not self._in_json:
            if '\n{"action"' in self._step_buf or self._step_buf.lstrip().startswith('{"action"'):
                self._in_json = True
                return None
            return Text(msg.text, style="dim")
        return None

    def _render_SubAgentStart(self, msg: SubAgentStart) -> RenderableType:
        return Text.assemble(
            ("  [sub] ", theme.ACCENT),
            (f"{msg.label} ", "bold"),
            (f"({msg.model})", "dim"),
        )

    def _render_SubAgentStepEnd(self, msg: SubAgentStepEnd) -> RenderableType:
        if not msg.done:
            return None
        label = getattr(msg, "agent_label", "") or ""
        return Text(
            f"  [sub] {label} step {msg.current_step}/{msg.max_steps} → {msg.action_taken} (done)",
            style="dim",
        )

    def _render_SubAgentResult(self, msg: SubAgentResult) -> RenderableType:
        icon = self._icon_for(msg.finish_status)
        parts = [
            f"  {icon} sub done: {msg.label} | status={msg.finish_status}",
            f"steps={msg.steps_taken}",
            f"cost=${msg.cost:.4f}",
        ]
        text = Text(" ".join(parts))
        if msg.finish_message:
            text.append(f"\n      {msg.finish_message[:200]}", style="dim")
        return text

    def _render_TaskComplete(self, msg: TaskComplete) -> RenderableType:
        final = msg.final_result or {}
        result_status = str(final.get("status", "") or "").lower()
        has_result = bool(final)
        if msg.quality_gate_passed:
            icon = f"[{theme.SUCCESS_BOLD}]✓[/]"
            status_text = "PASSED"
            border_style = theme.SUCCESS
        elif has_result and result_status in {"partial", "blocked"}:
            icon = f"[{theme.WARNING_BOLD}]~[/]"
            status_text = result_status.upper()
            border_style = theme.WARNING
        elif has_result:
            icon = f"[{theme.WARNING_BOLD}]![/]"
            status_text = "COMPLETED WITH ISSUES"
            border_style = theme.WARNING
        else:
            icon = f"[{theme.ERROR_BOLD}]✗[/]"
            status_text = "FAILED"
            border_style = theme.ERROR

        table = Table.grid(padding=(0, 2))
        table.add_column(style="dim")
        table.add_column()
        table.add_row("Status", f"{icon} {status_text}")
        table.add_row("Attempts", str(msg.attempts))
        table.add_row("Cost", self._format_cost(msg.total_cost, msg.cost_known))
        table.add_row(
            "Total token",
            self._format_tokens(msg.total_tokens, msg.input_tokens, msg.output_tokens),
        )
        if final.get("report_path"):
            table.add_row("Report", str(final.get("report_path")))
        if final.get("issues"):
            table.add_row("Issues", "; ".join(str(item) for item in list(final.get("issues", []))[:3]))
        if msg.summary:
            table.add_row("Summary", msg.summary[:200])
        return Panel(
            table,
            title="[bold]Task Complete[/]",
            border_style=border_style,
        )

    def _render_TaskCancelled(self, msg: TaskCancelled) -> RenderableType:
        return Panel(
            Text(msg.message, style=theme.MUTED),
            title=f"[{theme.ACCENT}]Cancelled[/]",
            border_style=theme.BORDER,
        )

    def _render_ErrorMessage(self, msg: ErrorMessage) -> RenderableType:
        return Panel(
            Text(f"{msg.error_type}: {msg.message}", style=theme.ERROR),
            border_style=theme.ERROR,
            title=f"[{theme.ERROR_BOLD}]Error[/]",
        )


# ── lightweight renderer (no dependency on rich Console) ──────────

class SimpleRenderer:
    """Text-only renderer that prints directly to stdout (no Rich)."""

    def render(self, msg) -> None:
        method = getattr(self, f"_render_{type(msg).__name__}", None)
        if method is not None:
            method(msg)

    def _render_OrchestratorThinking(self, msg):
        print(f"  [think] MainAgent deciding (attempt {msg.attempt}/{msg.max_attempts})...")

    def _render_StatusUpdate(self, msg):
        parts = [f"phase={msg.phase}"]
        if msg.input_tokens:
            parts.append(f"in={msg.input_tokens}")
        if msg.output_tokens:
            parts.append(f"out={msg.output_tokens}")
        print(f"  -- {' | '.join(parts)} --")

    def _render_OrchestratorDecision(self, msg):
        action = getattr(msg, "action", "") or ""
        reasoning = getattr(msg, "reasoning", "") or ""
        print(f"  [decide] → {action}")
        if reasoning:
            print(f"           {reasoning[:120]}")

    def _render_PhaseTransition(self, msg):
        print(f"  [phase] {msg.from_phase} → {msg.to_phase}")

    def _render_WorkerSpawned(self, msg):
        print(f"  [>] {msg.label} | {msg.model} | {msg.session_id}")

    def _render_WorkerCompleted(self, msg):
        icon = "✓" if msg.status == "done" else "✗"
        print(f"  [{icon}] {msg.label} | status={msg.status} steps={msg.steps_taken} cost=${msg.cost:.4f}")

    def _render_WorkerWaitStart(self, msg):
        print(f"  [wait] waiting for {len(msg.session_ids) or 'all'} workers ({msg.timeout_seconds}s)...")

    def _render_WorkerWaitEnd(self, msg):
        print(f"  [wait] collected={msg.completed} still_running={msg.still_running}")

    def _render_SubAgentCreated(self, msg):
        tools = ", ".join(msg.tools[:4]) if msg.tools else "all"
        task = MessageRenderer._short_task_label(msg.task_label, fallback=msg.agent_id or "task")
        summary = MessageRenderer._task_summary(msg.task_instruction, msg.task_label, limit=72)
        task_text = f"{task}  {summary}" if summary else task
        print(f"  [+] Agent {msg.agent_id or 'sub'} | {task_text} | {msg.model} | {tools}")

    def _render_ContentPart(self, msg):
        pass  # suppress raw LLM tokens in the CLI

    def _render_SubAgentStart(self, msg):
        print(f"  [sub] start: {msg.label} ({msg.model})")

    def _render_SubAgentStepEnd(self, msg):
        if msg.done:
            label = getattr(msg, "agent_label", "") or ""
            print(f"  [sub] {label} step {msg.current_step}/{msg.max_steps} → {msg.action_taken} (done)")

    def _render_SubAgentResult(self, msg):
        icon = "✓" if msg.finish_status == "done" else "✗"
        print(f"  [{icon}] sub done: {msg.label} | status={msg.finish_status} steps={msg.steps_taken} cost=${msg.cost:.4f}")

    def _render_TaskComplete(self, msg):
        icon = "✓" if msg.success else "✗"
        cost = MessageRenderer._format_cost(msg.total_cost, msg.cost_known)
        tokens = MessageRenderer._format_tokens(
            msg.total_tokens,
            msg.input_tokens,
            msg.output_tokens,
        )
        print(
            f"\n  [{icon}] Task complete | quality_gate_passed={msg.quality_gate_passed} "
            f"| attempts={msg.attempts} | Cost: {cost} | Total token: {tokens}"
        )

    def _render_TaskCancelled(self, msg):
        print(f"\n  [!] Cancelled — {msg.message}")

    def _render_ErrorMessage(self, msg):
        print(f"  [!] error: {msg.error_type} — {msg.message}")
