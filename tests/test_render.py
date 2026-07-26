"""Integration test: verify rendering pipeline works end-to-end."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))  # for config.py

from rich.console import Console
from core.message import (
    ErrorMessage,
    OrchestratorDecision,
    OrchestratorThinking,
    PhaseTransition,
    SubAgentResult,
    SubAgentStart,
    TaskCancelled,
    TaskComplete,
    WorkerCompleted,
    WorkerSpawned,
    WorkerWaitEnd,
    WorkerWaitStart,
)
from ui.render import MessageRenderer


def test_all_message_types_render():
    console = Console(force_terminal=True, width=120)
    renderer = MessageRenderer(console)

    messages = [
        OrchestratorThinking(attempt=1, max_attempts=6),
        OrchestratorDecision(action="delegate_task", reasoning="Need to collect policy data"),
        PhaseTransition(from_phase="research", to_phase="synthesis"),
        WorkerSpawned(session_id="abc123", label="research_0", model="m1",
                      task_instruction="Research policy landscape"),
        WorkerCompleted(session_id="abc123", label="research_0", status="done",
                        steps_taken=5, cost=0.0123, message="Completed policy research",
                        issues=[]),
        WorkerCompleted(session_id="def456", label="research_1", status="partial",
                        steps_taken=3, cost=0.0056,
                        message="Missing competitor data",
                        issues=["no web access", "sources empty"]),
        WorkerWaitStart(session_ids=["abc123", "def456"], timeout_seconds=30),
        WorkerWaitEnd(completed=2, still_running=0),
        SubAgentStart(label="synthesis", model="m2"),
        SubAgentResult(label="synthesis", model="m2", steps_taken=2, done=True,
                       cost=0.003, finish_status="done",
                       finish_message="Report written"),
        TaskComplete(success=True, quality_gate_passed=True, attempts=3,
                     total_cost=0.0209, cost_known=False,
                     total_tokens=1234, input_tokens=1000, output_tokens=234,
                     summary="All sections done",
                     final_result={"executive_summary": "Task completed successfully"}),
        ErrorMessage(error_type="step_timeout", message="Step 3 timed out after 600s"),
        TaskCancelled(message="Cancelled by user.", attempts=2),
    ]

    for msg in messages:
        result = renderer.render(msg)
        assert result is not None, f"Render returned None for {type(msg).__name__}"
        print(f"  [{type(msg).__name__:25s}] → {type(result).__name__}")

    print("\nAll message types render successfully.")


if __name__ == "__main__":
    test_all_message_types_render()
