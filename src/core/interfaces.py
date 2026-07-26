from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Tuple


Action = Dict[str, Any]
Observation = Dict[str, Any]


@dataclass
class TaskContext:
    """Task description passed to agents and environments."""

    task_id: str
    instruction: str
    action_space: str
    max_steps: int
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepRecord:
    """Single agent-environment interaction step."""

    observation: Observation
    action: Action
    reward: float
    raw_response: str
    done: bool
    info: Dict[str, Any]
    raw_input: Optional[str] = None


@dataclass
class RunResult:
    """Structured execution result for a single agent run."""

    model: str
    total_reward: float
    steps: int
    done: bool
    trace: List[StepRecord]
    cost: float
    input_tokens: int = 0
    output_tokens: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class ToolLike(Protocol):
    """Minimal tool interface used by the orchestration layer."""

    name: str
    description: str
    parameters: Dict[str, Any]

    async def __call__(self, **kwargs) -> Dict[str, Any]:
        ...


class AgentEnvironment(Protocol):
    """Generic environment protocol without benchmark dependencies."""

    def get_task_context(self) -> TaskContext:
        ...

    def reset(self) -> Observation:
        ...

    async def step(self, action: Action) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        ...


class MainPromptBuilder(Protocol):
    """Prompt builder used by the main orchestrator agent."""

    @staticmethod
    def build_prompt(
        instruction: str,
        meta: Dict[str, Any],
        prior_context: str,
        attempt_index: int,
        max_attempts: int,
        sub_models: List[str],
        subtask_history: str = "",
        tools: Optional[List[Any]] = None,
    ) -> str:
        ...


class SubPromptBuilder(Protocol):
    """Prompt builder used by a delegated sub-agent."""

    @staticmethod
    def build_prompt(
        task_instruction: str,
        context: str,
        original_question: str,
        action_space: str,
        observation: Any,
        memory: str,
        current_step: int,
        max_steps: int,
    ) -> str:
        ...
