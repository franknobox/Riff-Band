from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from base.engine.logs import logger


class SubAgentProcessManager:
    """Run sub-agent work in an isolated Python subprocess.

    This first-stage manager keeps the public delegation API synchronous while
    moving actual tool execution out of the main-agent process.
    """

    def __init__(self, project_root: Optional[Path] = None) -> None:
        self.project_root = Path(project_root or self._discover_project_root()).resolve()
        self.worker_script = self.project_root / "src" / "workers" / "subagent_worker.py"
        self._running: Dict[str, asyncio.Task] = {}
        self._processes: Dict[str, subprocess.Popen[str]] = {}

    @staticmethod
    def _discover_project_root() -> Path:
        return Path(__file__).resolve().parents[2]

    def run_task(
        self,
        *,
        session_id: str,
        task_instruction: str,
        model: str,
        context: str,
        original_question: str,
        sources_dir: Path,
        output_dir: Path,
        max_subagent_steps: int,
        allowed_tools: Optional[List[str]] = None,
        task_label: str = "",
        parallel_task_index: int = 0,
        profile_name: str = "generic",
        report_filename: str = "task_report.md",
        required_sections: Optional[List[str]] = None,
        min_findings: int = 0,
        timeout_seconds: int = 180,
    ) -> Dict[str, Any]:
        request = {
            "session_id": session_id,
            "task_instruction": task_instruction,
            "model": model,
            "context": context,
            "original_question": original_question,
            "sources_dir": str(sources_dir),
            "output_dir": str(output_dir),
            "max_subagent_steps": max_subagent_steps,
            "allowed_tools": list(allowed_tools or []),
            "task_label": task_label,
            "parallel_task_index": int(parallel_task_index or 0),
            "profile_name": profile_name,
            "report_filename": report_filename,
            "required_sections": list(required_sections or []),
            "min_findings": int(min_findings or 0),
        }

        with tempfile.TemporaryDirectory(prefix="subagent_worker_") as tmp:
            request_path = Path(tmp) / "request.json"
            output_path = Path(tmp) / "result.json"
            request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")

            env = os.environ.copy()
            src_path = str(self.project_root / "src")
            existing_pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = src_path if not existing_pythonpath else src_path + os.pathsep + existing_pythonpath

            command = [sys.executable, str(self.worker_script), str(request_path), str(output_path)]
            timeout = max(1, int(timeout_seconds or 180))
            logger.info(
                f"[SubAgentProcessManager] Start session={session_id} label={task_label} "
                f"model={model} timeout={timeout}s"
            )
            process: subprocess.Popen[str] | None = None
            try:
                process = subprocess.Popen(
                    command,
                    cwd=str(self.project_root),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                self._processes[session_id] = process
                stdout, stderr = process.communicate(timeout=timeout)
                stdout = stdout or ""
                stderr = stderr or ""
                completed = subprocess.CompletedProcess(
                    command,
                    process.returncode,
                    stdout,
                    stderr,
                )
            except subprocess.TimeoutExpired as exc:
                if process is not None and process.poll() is None:
                    process.kill()
                    stdout, stderr = process.communicate()
                else:
                    stdout = exc.stdout or ""
                    stderr = exc.stderr or ""
                logger.info(
                    f"[SubAgentProcessManager] Timeout session={session_id} "
                    f"label={task_label} after {timeout}s"
                )
                return {
                    "done": False,
                    "steps_taken": 0,
                    "cost": 0.0,
                    "finish_result": {
                        "status": "blocked",
                        "message": f"Sub-agent process timed out after {timeout} seconds.",
                        "completed": [],
                        "issues": ["subagent_process_timeout"],
                        "result": "",
                    },
                    "trace_summary": "",
                    "session_id": session_id,
                    "worker_state": "timeout",
                    "worker_process": {
                        "exit_code": "timeout",
                        "stdout": (stdout or "")[-4000:] if isinstance(stdout, str) else "",
                        "stderr": (stderr or "")[-4000:] if isinstance(stderr, str) else "",
                        "timeout_seconds": timeout,
                    },
                }
            finally:
                self._processes.pop(session_id, None)

            if output_path.exists():
                try:
                    payload = json.loads(output_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    payload = {
                        "done": False,
                        "steps_taken": 0,
                        "cost": 0.0,
                        "finish_result": {
                            "status": "blocked",
                            "message": f"Sub-agent worker returned invalid JSON: {exc}",
                            "completed": [],
                            "issues": [str(exc)],
                            "result": "",
                        },
                    }
            else:
                payload = {
                    "done": False,
                    "steps_taken": 0,
                    "cost": 0.0,
                    "finish_result": {
                        "status": "blocked",
                        "message": "Sub-agent worker did not produce a result file.",
                        "completed": [],
                        "issues": [
                            f"exit_code={completed.returncode}",
                            completed.stderr.strip(),
                        ],
                        "result": completed.stdout.strip(),
                    },
                }

            payload.setdefault("worker_process", {})
            payload["worker_process"].update(
                {
                    "exit_code": completed.returncode,
                    "stdout": (completed.stdout or "")[-4000:],
                    "stderr": (completed.stderr or "")[-4000:],
                    "timeout_seconds": timeout,
                }
            )
            finish_result = payload.get("finish_result", {}) or {}
            status = finish_result.get("status", "")
            message = str(finish_result.get("message", "") or "")
            issues = finish_result.get("issues", []) or []
            issue_part = f" issues={issues}" if issues else ""
            logger.info(
                f"[SubAgentProcessManager] Done session={session_id} label={task_label} "
                f"exit={completed.returncode} status={status} "
                f"message={message[:300]}{issue_part}"
            )
            return payload

    def spawn_task(self, **kwargs: Any) -> Dict[str, Any]:
        session_id = str(kwargs.get("session_id", "")).strip()
        if not session_id:
            raise ValueError("session_id is required to spawn a sub-agent process")
        if session_id in self._running and not self._running[session_id].done():
            raise RuntimeError(f"Sub-agent session is already running: {session_id}")

        task = asyncio.create_task(asyncio.to_thread(self.run_task, **kwargs))
        self._running[session_id] = task
        return {"session_id": session_id, "state": "running"}

    def is_running(self, session_id: str) -> bool:
        task = self._running.get(session_id)
        return bool(task and not task.done())

    def cancel(self, session_id: str) -> bool:
        cancelled = False
        task = self._running.get(session_id)
        if task is not None and not task.done():
            task.cancel()
            cancelled = True
        process = self._processes.get(session_id)
        if process is not None and process.poll() is None:
            process.kill()
            cancelled = True
        return cancelled

    def cancel_all(self) -> int:
        count = 0
        for session_id in list(self._running.keys()):
            if self.cancel(session_id):
                count += 1
        for session_id in list(self._processes.keys()):
            if self.cancel(session_id):
                count += 1
        return count

    def collect_result(self, session_id: str) -> Optional[Dict[str, Any]]:
        task = self._running.get(session_id)
        if task is None or not task.done():
            return None
        self._running.pop(session_id, None)
        try:
            return task.result()
        except Exception as exc:
            return {
                "done": False,
                "steps_taken": 0,
                "cost": 0.0,
                "finish_result": {
                    "status": "blocked",
                    "message": f"Sub-agent background task failed: {exc}",
                    "completed": [],
                    "issues": [repr(exc)],
                    "result": "",
                },
                "trace_summary": "",
                "session_id": session_id,
                "worker_state": "failed",
            }

    async def wait_for(
        self,
        session_ids: Optional[List[str]] = None,
        timeout_seconds: float = 0,
    ) -> List[str]:
        ids = [str(item).strip() for item in (session_ids or self._running.keys()) if str(item).strip()]
        tasks = [self._running[item] for item in ids if item in self._running]
        if tasks and timeout_seconds > 0:
            await asyncio.wait(tasks, timeout=timeout_seconds)
        return [item for item in ids if item in self._running and self._running[item].done()]
