from __future__ import annotations

import asyncio
import inspect
from datetime import datetime
from typing import AsyncGenerator, List, Optional

from base.engine.logs import LogLevel, logger
from core.interfaces import AgentEnvironment, RunResult, StepRecord
from core.message import (
    ContentPart,
    ErrorMessage,
    ShellMessage,
    SubAgentResult,
    SubAgentStart,
    SubAgentStepEnd,
    SubAgentStepStart,
    TaskCancelled,
)


class AgentRunner:
    """Generic agent-environment loop with streaming support."""

    step_timeout: Optional[float] = 600.0
    _last_result: Optional[RunResult] = None

    # ── public API ─────────────────────────────────────────────────

    async def run(self, agent, env: AgentEnvironment) -> RunResult:
        """Run agent to completion (backward-compatible)."""
        result = None
        async for _ in self.stream(agent, env):
            pass
        return self._last_result

    async def stream(
        self,
        agent,
        env: AgentEnvironment,
        cancel_event: Optional["asyncio.Event"] = None,
    ) -> AsyncGenerator[ShellMessage, None]:
        """Run agent, yielding ShellMessage events at each step.

        If *cancel_event* is set, the loop stops at the next checkpoint
        and yields a :class:`TaskCancelled` message.
        """
        start_time = datetime.now().isoformat()
        self._last_result = None

        info = env.get_task_context()
        agent.reset(info)

        reset_result = env.reset()
        obs = await reset_result if inspect.isawaitable(reset_result) else reset_result

        label = getattr(agent, "task_label", "") or ""
        model = getattr(agent, "llm", None)
        model_name = getattr(model, "model_name", "") if model else ""

        yield SubAgentStart(
            label=label,
            task_instruction=getattr(agent, "task_instruction", "") or "",
            model=model_name or "",
            max_steps=info.max_steps,
        )

        history: List[StepRecord] = []
        total_reward = 0.0

        for idx in range(info.max_steps):
            if cancel_event is not None and cancel_event.is_set():
                yield TaskCancelled(
                    message=f"Cancelled at step {idx + 1}/{info.max_steps}",
                    attempts=idx + 1,
                )
                break

            yield SubAgentStepStart(
                agent_label=label,
                current_step=idx + 1,
                max_steps=info.max_steps,
            )

            logger.log_to_file(LogLevel.INFO, f"[AgentRunner] Observation: {obs}")
            try:
                if hasattr(agent, "stream_step"):
                    # Streaming path: yield ContentPart chunks, extract final result
                    action = None
                    raw_response = ""
                    raw_input = None
                    step_gen = agent.stream_step(
                        observation=obs,
                        history=history,
                        current_step=idx + 1,
                        max_steps=info.max_steps,
                    )
                    async for item in step_gen:
                        if isinstance(item, tuple) and len(item) >= 2:
                            # Final result: (action, raw_response, raw_input?)
                            action = item[0]
                            raw_response = item[1]
                            raw_input = item[2] if len(item) > 2 else None
                        elif isinstance(item, ContentPart):
                            yield item
                    if action is None:
                        raise ValueError("stream_step did not yield a final result")
                elif self.step_timeout:
                    step_result = await asyncio.wait_for(
                        agent.step(
                            observation=obs,
                            history=history,
                            current_step=idx + 1,
                            max_steps=info.max_steps,
                        ),
                        timeout=self.step_timeout,
                    )
                else:
                    step_result = await agent.step(
                        observation=obs,
                        history=history,
                        current_step=idx + 1,
                        max_steps=info.max_steps,
                    )
            except asyncio.TimeoutError:
                record = StepRecord(
                    observation=obs,
                    action={"action": "timeout", "params": {}},
                    reward=0.0,
                    raw_response="step timeout",
                    done=True,
                    info={"error": "step_timeout"},
                )
                history.append(record)
                yield ErrorMessage(
                    error_type="step_timeout",
                    message=f"Step {idx + 1} timed out after {self.step_timeout}s",
                )
                break

            if not hasattr(agent, "stream_step"):
                if len(step_result) == 3:
                    action, raw_response, raw_input = step_result
                elif len(step_result) == 2:
                    action, raw_response = step_result
                    raw_input = None
                else:
                    raise ValueError(f"Unsupported step return shape: {len(step_result)}")

            obs_next, reward, done, step_info = await env.step(action)
            step_info = dict(step_info or {})
            step_info["last_action_result"] = obs_next
            history.append(
                StepRecord(
                    observation=obs,
                    action=action,
                    reward=reward,
                    raw_response=raw_response,
                    done=done,
                    info=step_info,
                    raw_input=raw_input,
                )
            )
            total_reward += reward

            yield SubAgentStepEnd(
                agent_label=label,
                action_taken=action.get("action", ""),
                current_step=idx + 1,
                max_steps=info.max_steps,
                done=done,
                info=step_info,
            )

            obs = obs_next
            if done:
                break

        end_time = datetime.now().isoformat()
        usage = agent.llm.get_usage_summary() if getattr(agent, "llm", None) else {}

        finish_result = {}
        if history:
            finish_result = (
                history[-1].info.get("finish_result", {})
                if history[-1].info.get("finished")
                else {}
            )

        result = RunResult(
            model=usage.get("model", ""),
            total_reward=total_reward,
            steps=len(history),
            done=history[-1].done if history else False,
            trace=history,
            cost=usage.get("total_cost", 0.0),
            input_tokens=usage.get("total_input_tokens", 0),
            output_tokens=usage.get("total_output_tokens", 0),
            start_time=start_time,
            end_time=end_time,
        )
        self._last_result = result

        yield SubAgentResult(
            label=label,
            model=model_name or "",
            steps_taken=len(history),
            done=result.done,
            cost=result.cost,
            finish_status=finish_result.get("status", ""),
            finish_message=finish_result.get("message", ""),
            finish_issues=list(finish_result.get("issues", []) or []),
        )
