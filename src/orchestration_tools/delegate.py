from __future__ import annotations

import asyncio
import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from pydantic import Field

from base.agent.base_action import BaseAction
from base.engine.async_llm import LLMsConfig, create_llm_instance
from base.engine.logs import LogLevel, logger
from core.interfaces import Action, Observation, TaskContext
from core.runner import AgentRunner
from core.trace import summarize_trace_for_decision
from orchestration_tools.worker_process import SubAgentProcessManager


def _normalize_tool_name(name: str) -> str:
    normalized = name.lower().strip().replace("_", "")
    if normalized.endswith("action"):
        normalized = normalized[:-6]
    return normalized


def _normalize_context(context: Any) -> str:
    if context is None:
        return ""
    if isinstance(context, str):
        return context
    if isinstance(context, (dict, list)):
        try:
            return json.dumps(context, ensure_ascii=False, indent=2)
        except TypeError:
            return str(context)
    return str(context)


def _normalize_tools_input(tools: Any) -> List[str]:
    if not tools:
        return []
    if isinstance(tools, str):
        return [item.strip() for item in re.split(r"[,;\s]+", tools) if item.strip()]
    if isinstance(tools, (list, tuple, set)):
        return [str(item).strip() for item in tools if str(item).strip()]
    return [str(tools).strip()]


def _format_trace(trace) -> str:
    return summarize_trace_for_decision(trace)


def _summarize_finish_result(finish_result: Dict[str, Any]) -> str:
    if not finish_result:
        return "No finish result recorded."
    return json.dumps(
        {
            "status": finish_result.get("status", ""),
            "message": finish_result.get("message", ""),
            "completed": finish_result.get("completed", []),
            "issues": finish_result.get("issues", []),
            "result": finish_result.get("result", ""),
        },
        ensure_ascii=False,
        indent=2,
    )


def _session_public_view(session: Dict[str, Any], include_trace: bool = False) -> Dict[str, Any]:
    rounds = list(session.get("rounds", []) or [])
    latest = rounds[-1] if rounds else {}
    view: Dict[str, Any] = {
        "session_id": session.get("session_id", ""),
        "state": session.get("state", "active"),
        "task_instruction": session.get("task_instruction", ""),
        "model": session.get("model", ""),
        "tools": session.get("tools", []),
        "rounds": len(rounds),
        "latest_finish_result": session.get("latest_finish_result", {}),
        "latest_steps_taken": latest.get("steps_taken", 0),
        "created_as_parallel_worker": bool(session.get("parallel_worker", False)),
        "isolated_findings_path": session.get("isolated_findings_path", ""),
    }
    if include_trace:
        view["history"] = rounds
        memory_text = ""
        agent = session.get("agent")
        if agent is not None and getattr(agent, "memory", None) is not None:
            memory_text = agent.memory.as_text()
        view["memory"] = memory_text
    return view


def agent_label(task_instruction: str, task_index: int | None = None) -> str:
    """Generate a human-friendly label without truncating the task title."""
    index_part = f"task_{task_index}" if task_index is not None else "task"
    text = str(task_instruction or "").strip()
    if not text:
        return index_part
    for prefix in ("具体任务:", "具体任务："):
        if prefix in text:
            first_line = text.split(prefix, 1)[1].strip().split("\n")[0].strip()
            if first_line:
                return f"{index_part} {first_line}"

    # Try "具体任务:" or "具体任务：" first
    for prefix in ("具体任务:", "具体任务：", "task:", "Task:"):
        if prefix in text:
            rest = text.split(prefix, 1)[1].strip()
            first_line = rest.split("\n")[0].strip()
            if first_line:
                return f"{index_part} {first_line}"
            break

    # Fall back to first meaningful line, stripped of common prefixes
    first_line = text.split("\n")[0].strip()
    for p in ("任务类型:", "期望产出:", "完成标准:"):
        first_line = first_line.replace(p, "").strip()
    return f"{index_part} {first_line}" if first_line else index_part


def _filter_action_space(action_space: str, allowed_tools: Set[str]) -> str:
    if not allowed_tools:
        return action_space

    blocks = re.split(r"\n(?=### )", action_space)
    filtered_blocks: List[str] = []
    for block in blocks:
        if block.startswith("Available actions"):
            filtered_blocks.append(block.rstrip())
            continue
        match = re.match(r"### (\w+)", block)
        if not match:
            continue
        block_tool = match.group(1)
        if _normalize_tool_name(block_tool) in allowed_tools or block_tool == "finish":
            filtered_blocks.append(block.rstrip())

    return "\n\n".join(filtered_blocks)


@dataclass
class ScopedEnvironment:
    """Execution wrapper that enforces tool-level permissions for one delegated run."""

    base_env: Any
    allowed_tools: Set[str]
    max_steps: int
    _local_steps: int = 0

    def get_task_context(self) -> TaskContext:
        base_ctx = self.base_env.get_task_context()
        filtered_action_space = _filter_action_space(base_ctx.action_space, self.allowed_tools)
        meta = dict(base_ctx.meta_data or {})
        meta["allowed_tools"] = sorted(self.allowed_tools)
        return TaskContext(
            task_id=base_ctx.task_id,
            instruction=base_ctx.instruction,
            action_space=filtered_action_space,
            max_steps=base_ctx.max_steps,
            meta_data=meta,
        )

    async def reset(self, seed: int | None = None) -> Observation:
        self._local_steps = 0
        try:
            obs = await self.base_env.reset(seed=seed)
        except TypeError:
            obs = await self.base_env.reset()
        if isinstance(obs, dict):
            obs = dict(obs)
            obs["allowed_tools"] = sorted(self.allowed_tools)
        return obs

    async def step(self, action: Action) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        self._local_steps += 1
        action_name = str(action.get("action", ""))
        normalized = _normalize_tool_name(action_name)
        if action_name != "finish" and normalized not in self.allowed_tools:
            done = self._local_steps >= self.max_steps
            obs: Observation = {
                "action": action_name,
                "success": False,
                "error": (
                    f"Tool '{action_name}' 在当前分配的任务中不被允许 "
                    f"Allowed tools: {sorted(self.allowed_tools)} and finish."
                ),
                "current_step": self._local_steps,
                "max_steps": self.max_steps,
            }
            info: Dict[str, Any] = {"error": "forbidden_tool"}
            return obs, 0.0, done, info
        return await self.base_env.step(action)


class _DelegateBase(BaseAction):
    env: Any = Field(default=None, exclude=True)
    models: List[str] = Field(default_factory=list)
    subagent_factory: Optional[Callable[..., Any]] = Field(default=None, exclude=True)
    runner: AgentRunner = Field(default_factory=AgentRunner, exclude=True)
    session_store: Dict[str, Dict[str, Any]] = Field(default_factory=dict, exclude=True)
    process_manager: SubAgentProcessManager = Field(default_factory=SubAgentProcessManager, exclude=True)


    def _resolve_allowed_tools(self, requested_tools: Any) -> Optional[List[str]]:
        normalized_tools = _normalize_tools_input(requested_tools)
        if not normalized_tools:
            return None
        env_tools = getattr(self.env, "tools", {})
        env_names = list(env_tools.keys()) if isinstance(env_tools, dict) else []
        env_normalized = {_normalize_tool_name(item): item for item in env_names}
        resolved: List[str] = []
        for raw in normalized_tools:
            canonical = env_normalized.get(_normalize_tool_name(str(raw)))
            if canonical:
                resolved.append(canonical)
        deduped = sorted(set(resolved))
        return deduped or None

    def _build_session_context(self, session: Dict[str, Any], extra_context: Any = "") -> str:
        parts: List[str] = []
        existing_context = str(session.get("context", "")).strip()
        if existing_context:
            parts.append("[Original session context]")
            parts.append(existing_context)

        rounds = session.get("rounds", []) or []
        if rounds:
            last_round = rounds[-1]
            parts.append("[Latest delegated run summary]")
            parts.append(_summarize_finish_result(last_round.get("finish_result", {})))
            trace_summary = str(last_round.get("trace_summary", "")).strip()
            if trace_summary:
                parts.append("[Latest trace summary]")
                parts.append(trace_summary)

        user_context = _normalize_context(extra_context).strip()
        if user_context:
            parts.append("[Continuation request]")
            parts.append(user_context)
        return "\n\n".join(parts).strip()

    def _store_session_round(
        self,
        session_id: str,
        task_instruction: str,
        model: str,
        context: Any,
        tools: Optional[List[str]],
        result_schema: Optional[Dict[str, Any]],
        result_payload: Dict[str, Any],
        agent: Any = None,
        env: Any = None,
        parallel_worker: bool = False,
    ) -> Dict[str, Any]:
        session = self.session_store.get(session_id) or {
            "session_id": session_id,
            "state": "active",
            "task_instruction": task_instruction,
            "model": model,
            "context": _normalize_context(context),
            "tools": _normalize_tools_input(tools),
            "result_schema": result_schema,
            "rounds": [],
            "agent": agent,
            "env": env,
            "parallel_worker": parallel_worker,
        }
        session["task_instruction"] = task_instruction or session.get("task_instruction", "")
        session["model"] = model or session.get("model", "")
        if context is not None and not str(session.get("context", "")).strip():
            session["context"] = _normalize_context(context)
        if context is not None:
            session["last_context"] = _normalize_context(context)
        if tools is not None:
            session["tools"] = _normalize_tools_input(tools)
        if result_schema is not None:
            session["result_schema"] = result_schema
        if agent is not None:
            session["agent"] = agent
        if env is not None:
            session["env"] = env
        if parallel_worker:
            session["parallel_worker"] = True
        session["rounds"].append(
            {
                "finish_result": result_payload.get("finish_result", {}),
                "trace_summary": result_payload.get("trace_summary", ""),
                "steps_taken": result_payload.get("steps_taken", 0),
                "allowed_tools": result_payload.get("allowed_tools", []),
            }
        )
        session["latest_finish_result"] = result_payload.get("finish_result", {})
        session["state"] = session.get("state", "active") or "active"
        self.session_store[session_id] = session
        return session

    def _store_running_session(
        self,
        session_id: str,
        task_instruction: str,
        model: str,
        context: Any,
        tools: Optional[List[str]],
        result_schema: Optional[Dict[str, Any]],
        env: Any = None,
        parallel_worker: bool = False,
        isolated_findings_path: str = "",
    ) -> Dict[str, Any]:
        session = self.session_store.get(session_id) or {
            "session_id": session_id,
            "rounds": [],
        }
        session.update(
            {
                "state": "running",
                "task_instruction": task_instruction,
                "model": model,
                "context": _normalize_context(context),
                "last_context": _normalize_context(context),
                "tools": _normalize_tools_input(tools),
                "result_schema": result_schema,
                "env": env,
                "parallel_worker": parallel_worker,
                "isolated_findings_path": isolated_findings_path,
            }
        )
        self.session_store[session_id] = session
        return session

    def _finalize_session_result(self, session_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        session = self.session_store.get(session_id) or {}
        result_schema = session.get("result_schema")
        finish_result = dict(result.get("finish_result", {}) or {})
        schema_error = self._validate_result_schema(finish_result.get("result"), result_schema)
        if schema_error:
            finish_result = dict(finish_result)
            finish_result["status"] = "failed"
            issues = list(finish_result.get("issues", []) or [])
            issues.append(schema_error)
            finish_result["issues"] = issues
            finish_result["message"] = (finish_result.get("message") or "").strip() or "Delegated output failed schema validation."
            result["finish_result"] = finish_result

        status = str(finish_result.get("status", "") or result.get("worker_state", "finished"))
        result["schema_validation_error"] = schema_error
        result["session_id"] = session_id
        result["task_instruction"] = str(session.get("task_instruction", result.get("task_instruction", "")))
        result["model"] = str(session.get("model", result.get("model", "")))
        result["worker_state"] = status
        updated = self._store_session_round(
            session_id=session_id,
            task_instruction=str(session.get("task_instruction", result.get("task_instruction", ""))),
            model=str(session.get("model", result.get("model", ""))),
            context=session.get("last_context", session.get("context", "")),
            tools=result.get("allowed_tools") or session.get("tools"),
            result_schema=result_schema,
            result_payload=result,
            env=session.get("env"),
            parallel_worker=bool(session.get("parallel_worker", False)),
        )
        updated["state"] = status or "finished"
        if session.get("isolated_findings_path"):
            updated["isolated_findings_path"] = session.get("isolated_findings_path")
            result["isolated_findings_path"] = session.get("isolated_findings_path")
        result["session_rounds"] = len(updated.get("rounds", []))
        return result

    def _collect_finished_sessions(self, session_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        ids = session_ids or list(self.session_store.keys())
        results: List[Dict[str, Any]] = []
        for session_id in ids:
            result = self.process_manager.collect_result(str(session_id))
            if result is None:
                continue
            results.append(self._finalize_session_result(str(session_id), result))
        return results

    def _get_or_create_worker_agent(
        self,
        session_id: str,
        task_instruction: str,
        model: str,
        context: str,
        run_env: Any,
        allowed_tools: Optional[List[str]],
        label: str,
    ) -> Any:
        session = self.session_store.get(session_id)
        if session and session.get("state") == "closed":
            raise RuntimeError(f"Worker session is closed: {session_id}")

        agent = session.get("agent") if session else None
        if agent is None:
            llm = create_llm_instance(LLMsConfig.default().get(model))
            agent = self.subagent_factory(
                llm=llm,
                task_instruction=task_instruction,
                context=context,
                original_question=run_env.get_task_context().instruction,
                allowed_tools=allowed_tools,
                task_label=label,
                preserve_memory_on_reset=True,
            )
        else:
            agent.task_instruction = task_instruction
            agent.context = context
            agent.allowed_tools = allowed_tools
            agent.task_label = label
            agent.preserve_memory_on_reset = True
            if not getattr(agent, "original_question", ""):
                agent.original_question = run_env.get_task_context().instruction
        return agent

    def _validate_result_schema(self, result_payload: Any, result_schema: Optional[Dict[str, Any]]) -> str:
        if not result_schema:
            return ""
        try:
            import jsonschema  # type: ignore
        except ImportError:
            return "jsonschema is not installed; cannot validate delegated result_schema"

        to_validate = result_payload
        if isinstance(to_validate, str):
            raw = to_validate.strip()
            if raw.startswith("{") or raw.startswith("["):
                try:
                    to_validate = json.loads(raw)
                except json.JSONDecodeError:
                    return "result_schema provided but finish_result.result is not valid JSON text"
        try:
            jsonschema.validate(to_validate, result_schema)
            return ""
        except Exception as exc:
            return f"result_schema validation failed: {exc}"


    # deepcopy为每个并行子任务创建一个环境副本，确保输出文件路径隔离，并返回副本环境和对应的findings文件路径
    def _create_isolated_env(self, task_index: int, run_id: str) -> Tuple[Any, Path]:
        try:
            env_clone = copy.deepcopy(self.env)
        except Exception as exc:
            raise RuntimeError(f"Failed to clone environment for parallel task {task_index}: {exc}") from exc

        base_output = Path(getattr(self.env, "output_dir", Path("workspace/output")))
        display_index = max(1, int(task_index or 1))
        task_output_dir = base_output / "parallel_runs" / run_id / f"task_{display_index}"
        task_output_dir.mkdir(parents=True, exist_ok=True)

        if hasattr(env_clone, "output_dir"):
            env_clone.output_dir = task_output_dir

        if hasattr(env_clone, "meta_data") and isinstance(env_clone.meta_data, dict):
            env_clone.meta_data = dict(env_clone.meta_data)
            env_clone.meta_data["output_dir"] = str(task_output_dir)
            report_name = Path(str(env_clone.meta_data.get("report_path", "task_report.md"))).name
            env_clone.meta_data["report_path"] = str(task_output_dir / report_name)
            env_clone.meta_data["findings_path"] = str(task_output_dir / "findings.jsonl")
            env_clone.meta_data["scratchpad_path"] = str(task_output_dir / "scratchpad" / "shared.md")
            env_clone.meta_data["parallel_task_index"] = display_index

        tools_map = getattr(env_clone, "tools", {})
        if isinstance(tools_map, dict):
            for tool in tools_map.values():
                if hasattr(tool, "report_path"):
                    report_name = Path(str(getattr(tool, "report_path", "task_report.md"))).name
                    tool.report_path = task_output_dir / report_name
                if hasattr(tool, "findings_path"):
                    tool.findings_path = task_output_dir / "findings.jsonl"
                if hasattr(tool, "scratchpad_path"):
                    tool.scratchpad_path = task_output_dir / "scratchpad" / "shared.md"
                if hasattr(tool, "default_report_path"):
                    report_name = Path(str(getattr(tool, "default_report_path", "task_report.md"))).name
                    tool.default_report_path = task_output_dir / report_name
                if hasattr(tool, "default_findings_path"):
                    tool.default_findings_path = task_output_dir / "findings.jsonl"
                if hasattr(tool, "default_scratchpad_path"):
                    tool.default_scratchpad_path = task_output_dir / "scratchpad" / "shared.md"

        return env_clone, (task_output_dir / "findings.jsonl")

    def _merge_findings_files(self, isolated_findings: List[Path]) -> Dict[str, Any]:
        base_findings = Path(
            getattr(self.env, "meta_data", {}).get(
                "findings_path",
                str(Path(getattr(self.env, "output_dir", Path("workspace/output"))) / "findings.jsonl"),
            )
        )
        base_findings.parent.mkdir(parents=True, exist_ok=True)

        existing_keys: Set[str] = set()
        merged_count = 0
        if base_findings.exists():
            for line in base_findings.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = str(row.get("dedup_key", "")).strip()
                if key:
                    existing_keys.add(key)

        with base_findings.open("a", encoding="utf-8") as out:
            for file in isolated_findings:
                if not file.exists():
                    continue
                for line in file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    key = str(row.get("dedup_key", "")).strip()
                    if key and key in existing_keys:
                        continue
                    if key:
                        existing_keys.add(key)
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    merged_count += 1

        return {"merged_findings": merged_count, "target_findings_path": str(base_findings)}

    def _merge_scratchpad_files(self, isolated_scratchpads: List[Path]) -> Dict[str, Any]:
        base_scratchpad = Path(
            getattr(self.env, "meta_data", {}).get(
                "scratchpad_path",
                str(Path(getattr(self.env, "output_dir", Path("workspace/output"))) / "scratchpad" / "shared.md"),
            )
        )
        base_scratchpad.parent.mkdir(parents=True, exist_ok=True)

        existing = base_scratchpad.read_text(encoding="utf-8").strip() if base_scratchpad.exists() else "# Shared Scratchpad"
        seen_blocks: Set[str] = {existing}
        merged_count = 0
        blocks = [existing.rstrip()]
        for file in isolated_scratchpads:
            if not file.exists():
                continue
            text = file.read_text(encoding="utf-8").strip()
            if not text:
                continue
            normalized = re.sub(r"\s+", " ", text)
            if normalized in seen_blocks:
                continue
            seen_blocks.add(normalized)
            merged_count += 1
            blocks.append(f"## Parallel scratchpad: {file.parent.parent.name}\n\n{text}")

        if merged_count:
            base_scratchpad.write_text("\n\n".join(blocks).rstrip() + "\n", encoding="utf-8")
        elif not base_scratchpad.exists():
            base_scratchpad.write_text(existing.rstrip() + "\n", encoding="utf-8")

        return {"merged_scratchpads": merged_count, "target_scratchpad_path": str(base_scratchpad)}

    def _prepare_process_run(
        self,
        task_instruction: str,
        model: str,
        context: Any = "",
        tools: Optional[List[str]] = None,
        env_override: Any = None,
        task_index: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if model not in self.models:
            raise ValueError(f"Invalid model: {model}")
        session = self.session_store.get(session_id or "")
        run_env = env_override or (session.get("env") if session and session.get("env") is not None else self.env)
        if run_env is None:
            raise ValueError("Delegate tools require an execution environment")

        normalized_context = _normalize_context(context)
        allowed_tools = self._resolve_allowed_tools(tools)
        label = agent_label(task_instruction, task_index)
        meta = getattr(run_env, "meta_data", {}) or {}
        report_path = Path(str(meta.get("report_path", "")))
        report_filename = report_path.name if str(report_path).strip() else "task_report.md"
        output_dir = Path(getattr(run_env, "output_dir", Path("workspace/output")))
        sources_dir = Path(getattr(run_env, "sources_dir", Path("workspace/sources")))
        original_question = run_env.get_task_context().instruction
        if hasattr(run_env, "meta_data") and isinstance(run_env.meta_data, dict):
            run_env.meta_data["task_label"] = label
            run_env.meta_data["worker_session_id"] = session_id or ""
            if task_index is not None:
                run_env.meta_data["parallel_task_index"] = int(task_index)
        return {
            "run_env": run_env,
            "allowed_tools": allowed_tools,
            "label": label,
            "process_kwargs": {
                "session_id": session_id or "",
                "task_instruction": task_instruction,
                "model": model,
                "context": normalized_context,
                "original_question": original_question,
                "sources_dir": sources_dir,
                "output_dir": output_dir,
                "max_subagent_steps": int(getattr(run_env, "max_steps", 10) or 10),
                "allowed_tools": allowed_tools,
                "task_label": label,
                "parallel_task_index": int(task_index or meta.get("parallel_task_index", 0) or 0),
                "profile_name": str(meta.get("profile_name", "generic") or "generic"),
                "report_filename": report_filename,
                "required_sections": list(meta.get("required_sections", []) or []),
                "min_findings": int(meta.get("min_findings", 0) or 0),
                "timeout_seconds": int(meta.get("subagent_process_timeout_seconds", 180) or 180),
            },
        }

    async def _spawn_single(
        self,
        task_instruction: str,
        model: str,
        context: Any = "",
        tools: Optional[List[str]] = None,
        result_schema: Optional[Dict[str, Any]] = None,
        env_override: Any = None,
        task_index: Optional[int] = None,
        session_id: Optional[str] = None,
        parallel_worker: bool = False,
        isolated_findings_path: str = "",
    ) -> Dict[str, Any]:
        prepared = self._prepare_process_run(
            task_instruction=task_instruction,
            model=model,
            context=context,
            tools=tools,
            env_override=env_override,
            task_index=task_index,
            session_id=session_id,
        )
        allowed_tools = prepared["allowed_tools"]
        label = prepared["label"]
        logger.log_to_file(
            LogLevel.INFO,
            (
                f"[Delegate] Spawn {label} | model={model} | tools={allowed_tools or []} | "
                f"task_instruction={task_instruction}"
            ),
        )
        self.process_manager.spawn_task(**prepared["process_kwargs"])
        session = self._store_running_session(
            session_id=session_id or "",
            task_instruction=task_instruction,
            model=model,
            context=context,
            tools=allowed_tools or tools,
            result_schema=result_schema,
            env=prepared["run_env"],
            parallel_worker=parallel_worker,
            isolated_findings_path=isolated_findings_path,
        )
        return {
            "success": True,
            "session_id": session_id or "",
            "session_rounds": len(session.get("rounds", [])),
            "worker_state": "running",
            "finish_result": {
                "status": "running",
                "message": "Sub-agent session started and is running in the background.",
                "completed": [],
                "issues": [],
                "result": "",
            },
            "steps_taken": 0,
            "done": False,
            "allowed_tools": allowed_tools or [],
            "trace_summary": "",
        }

    async def _run_single(
        self,
        task_instruction: str,
        model: str,
        context: Any = "",
        tools: Optional[List[str]] = None,
        result_schema: Optional[Dict[str, Any]] = None,
        env_override: Any = None,
        task_index: Optional[int] = None,
        session_id: Optional[str] = None,
        reuse_worker: bool = True,
    ) -> Dict[str, Any]:
        session = self.session_store.get(session_id or "")
        try:
            prepared = self._prepare_process_run(
                task_instruction=task_instruction,
                model=model,
                context=context,
                tools=tools,
                env_override=env_override,
                task_index=task_index,
                session_id=session_id,
            )
        except ValueError as exc:
            return {"error": str(exc), "steps_taken": 0, "done": False}

        allowed_tools = prepared["allowed_tools"]
        label = prepared["label"]
        logger.log_to_file(
            LogLevel.INFO,
            (
                f"[Delegate] Start {label} | model={model} | tools={allowed_tools or []} | "
                f"task_instruction={task_instruction}"
            ),
        )
        result = await asyncio.to_thread(self.process_manager.run_task, **prepared["process_kwargs"])
        result = self._finalize_session_result(session_id or "", result)
        logger.log_to_file(
            LogLevel.INFO,
            (
                f"[Delegate] Done {label} | steps={result.get('steps_taken', 0)} | "
                f"done={result.get('done', False)} | "
                f"status={(result.get('finish_result', {}) or {}).get('status', '')}"
            ),
        )
        return {
            "model": model,
            "steps_taken": result.get("steps_taken", 0),
            "done": result.get("done", False),
            "cost": result.get("cost", 0.0),
            "input_tokens": int(result.get("input_tokens", 0) or 0),
            "output_tokens": int(result.get("output_tokens", 0) or 0),
            "allowed_tools": allowed_tools or [],
            "finish_result": result.get("finish_result", {}),
            "schema_validation_error": result.get("schema_validation_error", ""),
            "trace_summary": result.get("trace_summary", ""),
            "session_id": session_id or "",
            "worker_reused": bool(session_id and session),
            "worker_state": result.get("worker_state", "finished"),
            "_env": prepared["run_env"],
            "worker_process": result.get("worker_process", {}),
        }


class DelegateTaskTool(_DelegateBase):
    """Delegate one focused subtask to a sub-agent."""

    name: str = "delegate_task"
    description: str = "Delegate a focused analysis subtask to a sub-agent"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "task_instruction": {"type": "string"},
                "context": {"type": "string"},
                "model": {"type": "string"},
                "tools": {"type": "array", "items": {"type": "string"}},
                "result_schema": {"type": "object"},
            },
            "required": ["task_instruction", "model"],
            "additionalProperties": False,
        }
    )

    async def __call__(
        self,
        task_instruction: str,
        model: str,
        context: Any = "",
        tools: Optional[List[str]] = None,
        result_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        session_id = uuid4().hex[:12]  # 生成一个短的唯一session_id
        return await self._spawn_single(
            task_instruction=task_instruction,
            model=model,
            context=context,
            tools=tools,
            result_schema=result_schema,
            env_override=None,
            session_id=session_id,
        )


class ContinueTaskTool(_DelegateBase):
    """Continue a previously delegated session with retained context."""

    name: str = "continue_task"
    description: str = "Continue an existing delegated sub-agent session using its prior result and trace"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "task_instruction": {"type": "string"},
                "context": {"type": "string"},
                "model": {"type": "string"},
                "tools": {"type": "array", "items": {"type": "string"}},
                "result_schema": {"type": "object"},
            },
            "required": ["session_id", "task_instruction"],
            "additionalProperties": False,
        }
    )

    async def __call__(
        self,
        session_id: str,
        task_instruction: str,
        context: Any = "",
        model: str = "",
        tools: Optional[List[str]] = None,
        result_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        session = self.session_store.get(session_id)
        if not session:
            return {"success": False, "message": f"Unknown session_id: {session_id}"}
        if session.get("state") == "running":
            return {"success": False, "message": f"Worker session is still running: {session_id}"}
        if session.get("state") == "closed":
            return {"success": False, "message": f"Worker session is closed: {session_id}"}

        chosen_model = str(model or session.get("model", "")).strip()
        chosen_tools = tools if tools is not None else session.get("tools")
        chosen_schema = result_schema if result_schema is not None else session.get("result_schema")
        merged_context = self._build_session_context(session, extra_context=context)
        result = await self._run_single(
            task_instruction=task_instruction,
            model=chosen_model,
            context=merged_context,
            tools=chosen_tools,
            result_schema=chosen_schema,
            env_override=None,
            session_id=session_id,
        )
        updated = self._store_session_round(
            session_id=session_id,
            task_instruction=task_instruction,
            model=chosen_model,
            context=merged_context,
            tools=result.get("allowed_tools") or chosen_tools,
            result_schema=chosen_schema,
            result_payload=result,
            agent=result.get("_agent"),
            env=result.get("_env"),
        )
        result["session_id"] = session_id
        result["session_rounds"] = len(updated.get("rounds", []))
        result.pop("_agent", None)
        result.pop("_env", None)
        return result


class ListWorkerSessionsTool(_DelegateBase):
    """List long-lived delegated worker sessions."""

    name: str = "list_worker_sessions"
    description: str = "List active and closed long-lived worker sessions"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "include_closed": {"type": "boolean", "default": False},
            },
            "additionalProperties": False,
        }
    )

    async def __call__(self, include_closed: bool = False) -> Dict[str, Any]:
        self._collect_finished_sessions()
        sessions = []
        for session in self.session_store.values():
            if not include_closed and session.get("state") == "closed":
                continue
            sessions.append(_session_public_view(session, include_trace=False))
        return {"success": True, "sessions": sessions, "count": len(sessions)}


class InspectWorkerSessionTool(_DelegateBase):
    """Inspect one long-lived worker session."""

    name: str = "inspect_worker_session"
    description: str = "Inspect a worker session including memory and round history"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "include_trace": {"type": "boolean", "default": True},
            },
            "required": ["session_id"],
            "additionalProperties": False,
        }
    )

    async def __call__(self, session_id: str, include_trace: bool = True) -> Dict[str, Any]:
        self._collect_finished_sessions([str(session_id).strip()])
        session = self.session_store.get(str(session_id).strip())
        if not session:
            return {"success": False, "message": f"Unknown session_id: {session_id}"}
        return {"success": True, "session": _session_public_view(session, include_trace=include_trace)}


class CloseWorkerSessionTool(_DelegateBase):
    """Close a long-lived worker session so it cannot be continued."""

    name: str = "close_worker_session"
    description: str = "Close a worker session and release its retained agent object"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["session_id"],
            "additionalProperties": False,
        }
    )

    async def __call__(self, session_id: str, reason: str = "") -> Dict[str, Any]:
        key = str(session_id).strip()
        session = self.session_store.get(key)
        if not session:
            return {"success": False, "message": f"Unknown session_id: {session_id}"}
        session["state"] = "closed"
        session["close_reason"] = str(reason or "").strip()
        session["agent"] = None
        return {"success": True, "output": f"Closed worker session {key}.", "session_id": key}


class WaitWorkerSessionsTool(_DelegateBase):
    """Wait for running sub-agent sessions and collect completed results."""

    name: str = "wait_worker_sessions"
    description: str = "Wait for running sub-agent sessions and collect completed results"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "session_ids": {"type": "array", "items": {"type": "string"}},
                "timeout_seconds": {"type": "number", "default": 10},
            },
            "additionalProperties": False,
        }
    )

    async def __call__(
        self,
        session_ids: Optional[List[str]] = None,
        timeout_seconds: float = 10,
    ) -> Dict[str, Any]:
        ids = [str(item).strip() for item in (session_ids or []) if str(item).strip()]
        if not ids:
            ids = [
                session_id
                for session_id, session in self.session_store.items()
                if session.get("state") == "running"
            ]
        done_ids = await self.process_manager.wait_for(ids, timeout_seconds=float(timeout_seconds or 0))
        results = self._collect_finished_sessions(done_ids)
        for item in results:
            finish = item.get("finish_result", {}) or {}
            issues = finish.get("issues", []) or []
            issue_part = f" issues={issues}" if issues else ""
            logger.info(
                "[WaitWorkerSessions] Collected "
                f"session={item.get('session_id', '')} "
                f"status={finish.get('status', '')} "
                f"message={str(finish.get('message', '') or '')[:300]}"
                f"{issue_part}"
            )

        isolated = [
            Path(str(item.get("isolated_findings_path", "")))
            for item in results
            if str(item.get("isolated_findings_path", "")).strip()
        ]
        merge_info = self._merge_findings_files(isolated) if isolated else {}
        isolated_scratchpads = [
            path.parent / "scratchpad" / "shared.md"
            for path in isolated
        ]
        scratchpad_merge_info = self._merge_scratchpad_files(isolated_scratchpads) if isolated_scratchpads else {}
        running_ids = [
            session_id
            for session_id in ids
            if self.session_store.get(session_id, {}).get("state") == "running"
        ]
        return {
            "success": True,
            "results": results,
            "done_session_ids": [item.get("session_id", "") for item in results],
            "running_session_ids": running_ids,
            "count": len(results),
            "summary": {
                "waited_for": ids,
                "completed": len(results),
                "still_running": len(running_ids),
                **merge_info,
                **scratchpad_merge_info,
            },
        }


class DelegateTasksTool(_DelegateBase):
    """Delegate multiple focused subtasks and run them concurrently."""

    name: str = "delegate_tasks"
    description: str = "Delegate multiple independent subtasks to sub-agents in parallel"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task_instruction": {"type": "string"},
                            "context": {"type": "string"},
                            "model": {"type": "string"},
                            "tools": {"type": "array", "items": {"type": "string"}},
                            "result_schema": {"type": "object"},
                        },
                        "required": ["task_instruction", "model"],
                    },
                },
                "max_concurrency": {"type": "integer", "default": 3},
            },
            "required": ["tasks"],
            "additionalProperties": False,
        }
    )

    async def __call__(self, tasks: List[Dict[str, Any]], max_concurrency: int = 3) -> Dict[str, Any]:
        if not tasks:
            return {"success": False, "message": "tasks cannot be empty", "results": []}

        # Hard rule: writing report sections is forbidden in parallel phase.
        for idx, task in enumerate(tasks):
            task_tools = _normalize_tools_input(task.get("tools"))
            if any(_normalize_tool_name(item) == _normalize_tool_name("write_report_section") for item in task_tools):
                return {
                    "success": False,
                    "message": f"Task[{idx}] includes forbidden tool write_report_section in parallel mode.",
                    "results": [],
                }

        limit = max(1, int(max_concurrency or 3))
        semaphore = asyncio.Semaphore(limit)
        run_id = uuid4().hex
        isolated_files: List[Path] = []
        logger.log_to_file(
            LogLevel.INFO,
            f"[DelegateTasks] run_id={run_id} max_concurrency={limit} total_tasks={len(tasks)}",
        )

        prepared_tasks: List[Dict[str, Any]] = []
        for item in tasks:
            prepared = dict(item)
            prepared["session_id"] = uuid4().hex[:12]
            prepared_tasks.append(prepared)

        async def _run_with_session(idx: int, task: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                isolated_env, isolated_findings = self._create_isolated_env(idx + 1, run_id)
                result = await self._spawn_single(
                    task_instruction=str(task.get("task_instruction", "")),
                    model=str(task.get("model", "")),
                    context=task.get("context", ""),
                    tools=task.get("tools"),
                    result_schema=task.get("result_schema"),
                    env_override=isolated_env,
                    task_index=idx + 1,
                    session_id=str(task.get("session_id", "")),
                    parallel_worker=True,
                    isolated_findings_path=str(isolated_findings),
                )
                result["task_index"] = idx + 1
                result["task_instruction"] = str(task.get("task_instruction", ""))
                result["isolated_findings_path"] = str(isolated_findings)
                isolated_files.append(isolated_findings)
                return result

        all_results = await asyncio.gather(*[_run_with_session(i, t) for i, t in enumerate(prepared_tasks)])

        summary = {
            "total": len(all_results),
            "running_count": sum(1 for item in all_results if item.get("worker_state") == "running"),
            "done_count": 0,
            "partial_count": 0,
            "blocked_count": 0,
            "total_steps": 0,
            "total_cost": 0.0,
            "max_concurrency": limit,
        }
        return {"success": True, "results": all_results, "summary": summary}
