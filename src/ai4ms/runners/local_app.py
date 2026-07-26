from __future__ import annotations

import asyncio
import hmac
import json
import os
import shutil
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from ai4ms.runners.bundle import (
    RESULT_ARTIFACT_SUFFIXES,
    parse_result_bundle,
    safe_extract_archive,
    verify_run_request_signature,
)
from ai4ms.runners.contracts import RunBundleRequest
from ai4ms.runners.stata import (
    StataBatchAdapter,
    StataPolicyScanner,
    discover_stata_profile,
    sha256_file,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env", override=False)
load_dotenv(REPO_ROOT / ".env.stata-runner.local", override=True)


def create_local_runner_app(
    *,
    adapter: StataBatchAdapter | None = None,
    profile_factory: Callable[[], dict[str, Any]] | None = None,
    data_dir: str | Path | None = None,
    token: str | None = None,
) -> FastAPI:
    resolved_dir = Path(
        data_dir
        or os.environ.get("AI4MS_LOCAL_RUNNER_DATA_DIR", "")
        or Path(tempfile.gettempdir()) / "ai4ms-stata-runner"
    )
    resolved_dir.mkdir(parents=True, exist_ok=True)
    expected_token = (
        token if token is not None else os.environ.get("AI4MS_STATA_RUNNER_TOKEN", "").strip()
    )
    runner_adapter = adapter or StataBatchAdapter()
    get_profile = profile_factory or discover_stata_profile
    max_concurrency = max(
        1, int(os.environ.get("AI4MS_STATA_MAX_CONCURRENCY", "1") or 1)
    )
    semaphore = asyncio.Semaphore(max_concurrency)
    canceled_runs: set[str] = set()
    max_request_bytes = max(
        1,
        int(os.environ.get("AI4MS_LOCAL_RUNNER_MAX_BUNDLE_BYTES", str(2 * 1024**3))),
    )

    app = FastAPI(
        title="AI4MS Stata Local Runner",
        version="1.0.0",
        description="研究者本机自带许可的 Stata 批处理连接器。",
    )

    def authorize(request: Request) -> None:
        supplied = request.headers.get("X-AI4MS-Runner-Token", "")
        if not expected_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI4MS_STATA_RUNNER_TOKEN is not configured",
            )
        if not hmac.compare_digest(supplied, expected_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid local runner token",
            )

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "service": "ai4ms-stata-local-runner"}

    @app.get("/v1/status")
    async def runner_status(request: Request):
        authorize(request)
        return _public_profile(get_profile())

    @app.post("/v1/runs/{run_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
    async def cancel_run(run_id: str, request: Request):
        authorize(request)
        if not run_id.startswith("run_") or len(run_id) > 100:
            raise HTTPException(status_code=404, detail="run is not active")
        canceled_runs.add(run_id)
        cancel = getattr(runner_adapter, "cancel", None)
        if callable(cancel):
            await cancel(run_id)
        return {"run_id": run_id, "status": "canceling"}

    @app.post("/v1/runs")
    async def execute_run(request: Request, background: BackgroundTasks):
        authorize(request)
        profile = get_profile()
        if not profile.get("available"):
            raise HTTPException(status_code=409, detail="no licensed Stata executable was found")
        if not profile.get("license_confirmed"):
            raise HTTPException(status_code=409, detail="Stata license availability is not confirmed")

        work_dir = Path(tempfile.mkdtemp(prefix="run_", dir=resolved_dir))
        request_zip = work_dir / "request.zip"
        bundle_dir = work_dir / "bundle"
        output_dir = work_dir / "output"
        response_zip = work_dir / "result.zip"
        size = 0
        try:
            with request_zip.open("xb") as handle:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > max_request_bytes:
                        raise HTTPException(status_code=413, detail="run bundle is too large")
                    handle.write(chunk)
            bundle_dir.mkdir()
            safe_extract_archive(
                request_zip,
                bundle_dir,
                max_uncompressed_bytes=max_request_bytes * 2,
            )
            run_request = RunBundleRequest.model_validate_json(
                (bundle_dir / "run_request.json").read_text(encoding="utf-8")
            )
            if not verify_run_request_signature(run_request, expected_token):
                raise HTTPException(status_code=409, detail="run bundle signature is invalid")
            analysis_path = bundle_dir / "analysis.do"
            entrypoint_path = bundle_dir / "entrypoint.do"
            input_path = bundle_dir / "input.dta"
            if sha256_file(analysis_path) != run_request.do_file_sha256:
                raise HTTPException(status_code=409, detail="do-file hash mismatch")
            if sha256_file(input_path) != run_request.input_sha256:
                raise HTTPException(status_code=409, detail="input data hash mismatch")
            issues = [
                *StataPolicyScanner.scan(analysis_path.read_text(encoding="utf-8")),
                *StataPolicyScanner.required_structure_issues(
                    analysis_path.read_text(encoding="utf-8")
                ),
            ]
            if issues:
                raise HTTPException(
                    status_code=409,
                    detail={"message": "do-file policy rejected the run bundle", "issues": issues},
                )

            output_dir.mkdir()
            try:
                async with semaphore:
                    if run_request.run_id in canceled_runs:
                        execution = _canceled_execution()
                    else:
                        execution = await runner_adapter.execute(
                            profile,
                            entrypoint_path,
                            bundle_dir,
                            run_request.run_id,
                            input_path,
                            output_dir,
                            run_request.timeout_seconds,
                        )
            finally:
                canceled_runs.discard(run_request.run_id)
            parse_result_bundle(
                output_dir,
                run_id=run_request.run_id,
                input_sha256=run_request.input_sha256,
                do_file_sha256=run_request.do_file_sha256,
                execution=execution,
                runner_profile=profile,
                signing_token=expected_token,
            )
            _write_response_archive(output_dir, response_zip)
            background.add_task(shutil.rmtree, work_dir, True)
            return FileResponse(
                response_zip,
                media_type="application/zip",
                filename=f"{run_request.run_id}-result-bundle.zip",
                background=background,
            )
        except HTTPException:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise
        except Exception as exc:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise HTTPException(
                status_code=422,
                detail=f"invalid run bundle: {type(exc).__name__}: {str(exc)[:400]}",
            ) from exc

    return app


def _canceled_execution() -> dict[str, Any]:
    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat()
    return {
        "status": "canceled",
        "reason_code": "user_canceled",
        "exit_code": None,
        "started_at": now,
        "finished_at": now,
        "duration_seconds": 0,
    }


def _write_response_archive(output_dir: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for path in sorted(output_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in RESULT_ARTIFACT_SUFFIXES:
                archive.write(path, path.relative_to(output_dir).as_posix())


def _public_profile(profile: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "available",
        "engine",
        "mode",
        "executable_name",
        "version",
        "edition",
        "os",
        "locale",
        "license_mode",
        "license_confirmed",
        "max_concurrency",
        "reason",
    )
    result = {key: profile.get(key) for key in keys}
    result["transport"] = "local_process"
    return result


app = create_local_runner_app()


def _entry() -> None:
    import uvicorn

    host = os.environ.get("AI4MS_LOCAL_RUNNER_HOST", "127.0.0.1")
    port = int(os.environ.get("AI4MS_LOCAL_RUNNER_PORT", "8765"))
    uvicorn.run("ai4ms.runners.local_app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    _entry()
