from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp

from ai4ms.runners.bundle import (
    create_request_archive,
    load_and_validate_result_bundle,
    safe_extract_archive,
)


def discover_remote_stata_profile() -> dict[str, Any] | None:
    base_url = os.environ.get("AI4MS_STATA_RUNNER_URL", "").strip().rstrip("/")
    if not base_url:
        return None
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return _unavailable_profile("Stata Local Runner URL 无效")
    request = urllib.request.Request(
        f"{base_url}/v1/status",
        headers={"X-AI4MS-Runner-Token": _runner_token()},
    )
    try:
        with urllib.request.urlopen(request, timeout=2.5) as response:
            profile = json.loads(response.read().decode("utf-8"))
        profile["transport"] = "http_local_runner"
        return profile
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return _unavailable_profile(
                "Stata Local Runner 令牌不一致；请确保工作台与本机 Runner 使用相同 token"
            )
        if exc.code == 503:
            return _unavailable_profile(
                "Stata Local Runner 尚未配置 token；请先运行本机安装脚本"
            )
        return _unavailable_profile(
            f"Stata Local Runner 返回 HTTP {exc.code}"
        )
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return _unavailable_profile(
            f"无法连接研究者本机 Stata Local Runner：{type(exc).__name__}"
        )


class RemoteStataAdapter:
    async def cancel(self, run_id: str) -> bool:
        base_url = os.environ.get("AI4MS_STATA_RUNNER_URL", "").strip().rstrip("/")
        if not base_url:
            return False
        timeout = aiohttp.ClientTimeout(total=10, connect=5)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{base_url}/v1/runs/{run_id}/cancel",
                    headers={"X-AI4MS-Runner-Token": _runner_token()},
                ) as response:
                    return response.status in {200, 202}
        except (aiohttp.ClientError, TimeoutError):
            return False

    async def execute(
        self,
        _profile: dict[str, Any],
        do_file_path: Path,
        project_dir: Path,
        run_id: str,
        input_path: Path,
        output_dir: Path,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        base_url = os.environ.get("AI4MS_STATA_RUNNER_URL", "").strip().rstrip("/")
        if not base_url:
            raise RuntimeError("AI4MS_STATA_RUNNER_URL is not configured")
        archive_path = output_dir / ".run_bundle.request.zip"
        response_path = output_dir / ".result_bundle.response.zip"
        extract_dir = output_dir / ".remote_result"
        package_manifest = create_request_archive(output_dir, input_path, archive_path)
        timeout = aiohttp.ClientTimeout(total=timeout_seconds + 30, connect=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                with archive_path.open("rb") as payload:
                    async with session.post(
                        f"{base_url}/v1/runs",
                        data=payload,
                        headers={
                            "Content-Type": "application/zip",
                            "X-AI4MS-Runner-Token": _runner_token(),
                        },
                    ) as response:
                        if response.status >= 400:
                            detail = (await response.text())[:500]
                            raise RuntimeError(
                                f"Local Runner returned HTTP {response.status}: {detail}"
                            )
                        with response_path.open("wb") as output:
                            async for chunk in response.content.iter_chunked(1024 * 1024):
                                output.write(chunk)
            extract_dir.mkdir(parents=True, exist_ok=False)
            safe_extract_archive(response_path, extract_dir)
            bundle = load_and_validate_result_bundle(
                extract_dir / "result_bundle.json",
                run_id=run_id,
                input_sha256=_request_value(output_dir, "input_sha256"),
                do_file_sha256=_request_value(output_dir, "do_file_sha256"),
                signing_token=_runner_token(),
                require_signature=True,
            )
            for path in extract_dir.rglob("*"):
                if path.is_file():
                    relative = path.relative_to(extract_dir)
                    destination = output_dir / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, destination)
            return {
                "status": bundle["status"],
                "reason_code": bundle["reason_code"],
                "exit_code": bundle["exit_code"],
                "started_at": bundle["started_at"],
                "finished_at": bundle["finished_at"],
                "duration_seconds": bundle["duration_seconds"],
                "data_signature": bundle["data_signature"],
                "structured_results": bundle["structured_results"],
                "result_bundle": bundle,
                "package_manifest": package_manifest,
            }
        finally:
            archive_path.unlink(missing_ok=True)
            response_path.unlink(missing_ok=True)
            if extract_dir.exists():
                shutil.rmtree(extract_dir, ignore_errors=True)


def _request_value(output_dir: Path, key: str) -> str:
    payload = json.loads((output_dir / "run_request.json").read_text(encoding="utf-8"))
    return str(payload[key])


def _runner_token() -> str:
    return os.environ.get("AI4MS_STATA_RUNNER_TOKEN", "").strip()


def _unavailable_profile(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "engine": "stata",
        "mode": "batch",
        "transport": "http_local_runner",
        "executable_name": "",
        "version": "unknown",
        "edition": "unknown",
        "os": "host",
        "locale": "unknown",
        "license_mode": "user_byol",
        "license_confirmed": False,
        "max_concurrency": 1,
        "reason": reason,
    }
