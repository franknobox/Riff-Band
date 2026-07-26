from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ai4ms.runners.service import AnalysisRunnerService
from ai4ms.services.models import AnalysisRunRequest


ACTIVE_JOB_STATUSES = {"queued", "running", "canceling"}
TERMINAL_JOB_STATUSES = {"succeeded", "failed", "canceled", "interrupted"}
_RUN_ID = re.compile(r"^run_[0-9A-Za-z_-]+$")


class AnalysisJobNotFoundError(LookupError):
    pass


class AnalysisRunBlockedError(RuntimeError):
    def __init__(self, preflight: dict[str, Any]):
        self.preflight = preflight
        super().__init__(f"analysis preflight blocked: {preflight.get('reason_code', 'blocked')}")


class AnalysisJobConflictError(RuntimeError):
    pass


class AnalysisJobService:
    def __init__(
        self,
        projects_dir: Path,
        runner: AnalysisRunnerService,
        project_loader: Callable[[str], dict[str, Any]],
        run_recorder: Callable[[str, dict[str, Any]], dict[str, Any]],
    ) -> None:
        self.projects_dir = projects_dir
        self.runner = runner
        self.project_loader = project_loader
        self.run_recorder = run_recorder
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._project_locks: dict[str, asyncio.Lock] = {}
        self._execution_slots = asyncio.Semaphore(
            max(
                1,
                int(
                    os.environ.get(
                        "AI4MS_ANALYSIS_MAX_CONCURRENCY",
                        os.environ.get("AI4MS_STATA_MAX_CONCURRENCY", "1"),
                    )
                    or 1
                ),
            )
        )

    async def submit(
        self,
        project_id: str,
        request: AnalysisRunRequest,
        *,
        parent_run_id: str = "",
    ) -> dict[str, Any]:
        project = self.project_loader(project_id)
        project_dir = self.projects_dir / project_id
        preflight = self.runner.preflight(project, project_dir, request)
        if preflight.get("status") != "ready":
            raise AnalysisRunBlockedError(preflight)

        run_id = f"run_{uuid4().hex[:12]}"
        now = _now()
        job = {
            "run_id": run_id,
            "project_id": project_id,
            "status": "queued",
            "reason_code": "queued",
            "created_at": now,
            "started_at": "",
            "finished_at": "",
            "timeout_seconds": request.timeout_seconds,
            "cancel_requested": False,
            "parent_run_id": parent_run_id,
            "request": request.model_dump(mode="json"),
            "run_manifest_path": f"artifacts/runs/{run_id}/manifest.json",
        }
        self._save(job)
        task = asyncio.create_task(
            self._execute(job, project, request),
            name=f"analysis:{project_id}:{run_id}",
        )
        self._tasks[run_id] = task
        task.add_done_callback(lambda _task, key=run_id: self._tasks.pop(key, None))
        return dict(job)

    def list(self, project_id: str) -> list[dict[str, Any]]:
        self.project_loader(project_id)
        job_dir = self._job_dir(project_id)
        if not job_dir.exists():
            return []
        jobs = [self._load(path) for path in job_dir.glob("run_*.json")]
        return sorted(jobs, key=lambda item: item.get("created_at", ""), reverse=True)

    def get(self, project_id: str, run_id: str) -> dict[str, Any]:
        self.project_loader(project_id)
        path = self._job_path(project_id, run_id)
        if not path.is_file():
            raise AnalysisJobNotFoundError(run_id)
        job = self._load(path)
        if job.get("status") in ACTIVE_JOB_STATUSES and run_id not in self._tasks:
            job.update(
                {
                    "status": "interrupted",
                    "reason_code": "backend_restarted",
                    "finished_at": _now(),
                }
            )
            self._save(job)
        return job

    def result(self, project_id: str, run_id: str) -> dict[str, Any]:
        job = self.get(project_id, run_id)
        manifest = self.projects_dir / project_id / str(job["run_manifest_path"])
        if not manifest.is_file():
            raise AnalysisJobConflictError("run result is not available")
        return self._load(manifest)

    async def cancel(self, project_id: str, run_id: str) -> dict[str, Any]:
        job = self.get(project_id, run_id)
        if job["status"] in TERMINAL_JOB_STATUSES:
            return job
        job.update(
            {
                "status": "canceling",
                "reason_code": "cancel_requested",
                "cancel_requested": True,
            }
        )
        self._save(job)
        handled = await self.runner.cancel(run_id)
        task = self._tasks.get(run_id)
        if not handled and task is not None:
            task.cancel()
        return self.get(project_id, run_id)

    async def rerun(
        self,
        project_id: str,
        run_id: str,
        *,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        previous = self.get(project_id, run_id)
        if previous["status"] not in TERMINAL_JOB_STATUSES:
            raise AnalysisJobConflictError("an active run cannot be rerun")
        request_payload = dict(previous["request"])
        if timeout_seconds is not None:
            request_payload["timeout_seconds"] = timeout_seconds
        return await self.submit(
            project_id,
            AnalysisRunRequest.model_validate(request_payload),
            parent_run_id=run_id,
        )

    async def _execute(
        self,
        job: dict[str, Any],
        project: dict[str, Any],
        request: AnalysisRunRequest,
    ) -> None:
        run_id = str(job["run_id"])
        project_id = str(job["project_id"])
        try:
            async with self._execution_slots:
                job.update(
                    {
                        "status": "running",
                        "reason_code": "running",
                        "started_at": _now(),
                    }
                )
                self._save(job)
                run = await self.runner.submit(
                    project,
                    self.projects_dir / project_id,
                    request,
                    run_id=run_id,
                )
                await self._record_run(project_id, run, job)
                job.update(
                    {
                        "status": _job_status(run.get("status")),
                        "reason_code": str(
                            run.get("reason_code") or "runner_error"
                        ),
                        "finished_at": str(run.get("finished_at") or _now()),
                    }
                )
        except asyncio.CancelledError:
            run = self._fallback_run(job, "canceled", "user_canceled")
            self._write_manifest(project_id, run)
            await self._record_run(project_id, run, job)
            job.update(
                {
                    "status": "canceled",
                    "reason_code": "user_canceled",
                    "finished_at": _now(),
                }
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc)[:400]}"
            run = self._fallback_run(
                job,
                "failed",
                "background_job_error",
                error=error,
            )
            self._write_manifest(project_id, run)
            await self._record_run(project_id, run, job)
            job.update(
                {
                    "status": "failed",
                    "reason_code": "background_job_error",
                    "finished_at": _now(),
                    "error": error,
                }
            )
        finally:
            self._save(job)

    def _job_dir(self, project_id: str) -> Path:
        return self.projects_dir / project_id / "artifacts" / "jobs"

    def _job_path(self, project_id: str, run_id: str) -> Path:
        if not _RUN_ID.fullmatch(run_id):
            raise AnalysisJobNotFoundError(run_id)
        return self._job_dir(project_id) / f"{run_id}.json"

    def _save(self, job: dict[str, Any]) -> None:
        path = self._job_path(str(job["project_id"]), str(job["run_id"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(job, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, path)

    async def _record_run(
        self,
        project_id: str,
        run: dict[str, Any],
        job: dict[str, Any],
    ) -> None:
        try:
            async with self._project_locks.setdefault(project_id, asyncio.Lock()):
                self.run_recorder(project_id, run)
        except Exception as exc:
            job["record_error"] = f"{type(exc).__name__}: {str(exc)[:400]}"

    def _write_manifest(self, project_id: str, run: dict[str, Any]) -> None:
        path = self.projects_dir / project_id / str(run["manifest_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(run, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _fallback_run(
        job: dict[str, Any],
        status: str,
        reason_code: str,
        *,
        error: str = "",
    ) -> dict[str, Any]:
        request = job["request"]
        return {
            "run_id": job["run_id"],
            "status": status,
            "reason_code": reason_code,
            "exit_code": None,
            "requested_at": job["created_at"],
            "requested_by": request["requested_by"],
            "finished_at": _now(),
            "input_asset_id": request["input_asset_id"],
            "input_artifact_path": request["input_artifact_path"],
            "parameters": request["parameters"],
            "seed": request["seed"],
            "data_signature": "",
            "structured_results": [],
            "output_artifacts": [],
            "logs": [],
            "runner_error": error,
            "manifest_path": job["run_manifest_path"],
        }

    @staticmethod
    def _load(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))


def _job_status(run_status: Any) -> str:
    status = str(run_status or "failed")
    return status if status in {"succeeded", "failed", "canceled"} else "failed"


def _now() -> str:
    return datetime.now(UTC).isoformat()
