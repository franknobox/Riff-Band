from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ShellMessage:
    """Base message for agent-UI streaming communication."""

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ── Orchestrator lifecycle ─────────────────────────────────────────────


@dataclass
class OrchestratorThinking(ShellMessage):
    """MainAgent is sending a prompt to the LLM."""

    attempt: int = 0
    max_attempts: int = 0


@dataclass
class OrchestratorDecision(ShellMessage):
    """MainAgent has received an LLM response and chosen an action."""

    action: str = ""
    reasoning: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""


# ── Streaming content ───────────────────────────────────────────────────


@dataclass
class ContentPart(ShellMessage):
    """A chunk of streaming text from the LLM."""

    text: str = ""
    content_type: str = "text"  # text | tool_call


# ── Sub-agent lifecycle (in-process) ───────────────────────────────────


@dataclass
class SubAgentCreated(ShellMessage):
    """A sub-agent has been assembled with its (I, C, T, M) four-tuple."""

    agent_id: str = ""
    model: str = ""
    tools: List[str] = field(default_factory=list)
    task_instruction: str = ""
    task_label: str = ""
    context: str = ""


@dataclass
class SubAgentStepStart(ShellMessage):
    """A sub-agent is about to execute a step."""

    agent_label: str = ""
    current_step: int = 0
    max_steps: int = 0


@dataclass
class SubAgentStepEnd(ShellMessage):
    """A sub-agent has completed a step."""

    agent_label: str = ""
    action_taken: str = ""
    current_step: int = 0
    max_steps: int = 0
    done: bool = False
    info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SubAgentStart(ShellMessage):
    """A sub-agent is starting execution."""

    label: str = ""
    task_instruction: str = ""
    model: str = ""
    max_steps: int = 0


@dataclass
class SubAgentResult(ShellMessage):
    """A sub-agent has finished execution."""

    label: str = ""
    model: str = ""
    steps_taken: int = 0
    done: bool = False
    cost: float = 0.0
    finish_status: str = ""
    finish_message: str = ""
    finish_issues: List[str] = field(default_factory=list)


# ── Worker subprocess lifecycle ────────────────────────────────────────


@dataclass
class WorkerSpawned(ShellMessage):
    """A worker subprocess has been launched."""

    session_id: str = ""
    label: str = ""
    model: str = ""
    task_instruction: str = ""


@dataclass
class WorkerCompleted(ShellMessage):
    """A worker subprocess has finished."""

    session_id: str = ""
    label: str = ""
    exit_code: int = 0
    status: str = ""
    steps_taken: int = 0
    cost: float = 0.0
    message: str = ""
    issues: List[str] = field(default_factory=list)


# ── Worker session management ──────────────────────────────────────────


@dataclass
class WorkerWaitStart(ShellMessage):
    """Orchestrator is waiting for worker sessions to complete."""

    session_ids: List[str] = field(default_factory=list)
    timeout_seconds: float = 0


@dataclass
class WorkerWaitEnd(ShellMessage):
    """Orchestrator has finished waiting for workers."""

    completed: int = 0
    still_running: int = 0
    results: List[Dict[str, Any]] = field(default_factory=list)


# ── Phase transitions ──────────────────────────────────────────────────


@dataclass
class PhaseTransition(ShellMessage):
    """The orchestrator has moved to a different phase."""

    from_phase: str = ""
    to_phase: str = ""
    guidance: str = ""


# ── Terminal states ────────────────────────────────────────────────────


@dataclass
class TaskComplete(ShellMessage):
    """The orchestration task has finished."""

    success: bool = False
    quality_gate_passed: bool = False
    attempts: int = 0
    total_cost: float = 0.0
    cost_known: bool = True
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    summary: str = ""
    final_result: Optional[Dict[str, Any]] = None


@dataclass
class ErrorMessage(ShellMessage):
    """An error occurred during execution."""

    error_type: str = ""
    message: str = ""
    recoverable: bool = False
    details: Optional[Dict[str, Any]] = None


# ── Status updates ──────────────────────────────────────────────────────


@dataclass
class StatusUpdate(ShellMessage):
    """Periodic status snapshot during execution."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    phase: str = ""
    elapsed: str = ""


# ── Cancellation ────────────────────────────────────────────────────────


@dataclass
class TaskCancelled(ShellMessage):
    """The current task was cancelled by the user."""

    message: str = "Task cancelled by user."
    attempts: int = 0
