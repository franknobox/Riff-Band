from __future__ import annotations

import asyncio
import hashlib
import os
import platform
import re
import signal
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


LICENSE_MODES = {"user_byol", "institution_network", "institution_compute_server"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_stata_profile() -> dict[str, Any]:
    configured = os.environ.get("AI4MS_STATA_EXECUTABLE", "").strip()
    executable = ""
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            executable = str(candidate.resolve())
    if not executable:
        names = (
            "StataMP-64.exe",
            "StataSE-64.exe",
            "StataBE-64.exe",
            "StataMP.exe",
            "StataSE.exe",
            "Stata.exe",
            "stata-mp",
            "stata-se",
            "stata",
        )
        executable = next((found for name in names if (found := shutil.which(name))), "")

    basename = Path(executable).name.lower() if executable else ""
    edition = "MP" if "mp" in basename else "SE" if "se" in basename else "BE" if "be" in basename else "unknown"
    license_mode = os.environ.get("AI4MS_STATA_LICENSE_MODE", "user_byol").strip()
    if license_mode not in LICENSE_MODES:
        license_mode = "user_byol"
    license_confirmed = os.environ.get("AI4MS_STATA_LICENSE_CONFIRMED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return {
        "available": bool(executable),
        "engine": "stata",
        "mode": "batch",
        "transport": "local_process",
        "executable": executable,
        "executable_name": Path(executable).name if executable else "",
        "version": os.environ.get("AI4MS_STATA_VERSION", "unknown").strip() or "unknown",
        "edition": edition,
        "os": platform.system(),
        "locale": os.environ.get("AI4MS_STATA_LOCALE", "unknown").strip() or "unknown",
        "license_mode": license_mode,
        "license_confirmed": license_confirmed,
        "max_concurrency": max(1, int(os.environ.get("AI4MS_STATA_MAX_CONCURRENCY", "1") or 1)),
        "reason": "" if executable else "No configured or PATH-discoverable Stata executable was found.",
    }


class StataPolicyScanner:
    _rules = (
        ("external_process", re.compile(r"^\s*(?:shell|winexec)\b|^\s*!", re.I), "禁止启动 shell 或外部进程"),
        ("dynamic_install", re.compile(r"^\s*(?:ssc|net)\s+install\b|^\s*update\s+all\b", re.I), "禁止动态安装或更新 ado"),
        ("embedded_runtime", re.compile(r"^\s*(?:python|python:|java|javacall|plugin)\b", re.I), "禁止未批准的 Python、Java 或插件"),
        ("early_exit", re.compile(r"^\s*exit\b", re.I), "禁止提前退出并绕过 Result Bundle 生成"),
        ("delimiter_change", re.compile(r"^\s*#delimit\b", re.I), "禁止改变命令分隔符并绕过逐行策略检查"),
        ("network_access", re.compile(r"https?://|ftp://", re.I), "禁止任意网络访问"),
        ("parent_traversal", re.compile(r"(?:^|[\s\"'\\/])\.\.(?:[\\/]|$)"), "禁止父目录穿越"),
        ("absolute_windows_path", re.compile(r"(?:^|[\s\"'])[A-Za-z]:[\\/]"), "禁止硬编码 Windows 绝对路径"),
        ("absolute_posix_path", re.compile(r"(?:^|[\s=])[\"']/[^\"']+"), "禁止硬编码 POSIX 绝对路径"),
        ("unc_path", re.compile(r"\\\\[^\\\s]+\\"), "禁止 UNC 网络路径"),
        ("destructive_delete", re.compile(r"^\s*(?:erase|rm|rmdir)\b", re.I), "禁止删除文件或目录"),
        ("overwrite_input", re.compile(r"^\s*(?:save|export|outsheet|copy)\b.*input_dta.*\breplace\b", re.I), "禁止覆盖只读输入数据"),
    )

    @classmethod
    def scan(cls, do_file: str) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        for line_number, line in enumerate(str(do_file or "").splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("*") or stripped.startswith("//"):
                continue
            normalized = re.sub(
                r"^\s*(?:(?:capture|cap|quietly|qui|noisily|noi)\s+)+",
                "",
                line,
                flags=re.I,
            )
            for code, pattern, message in cls._rules:
                if pattern.search(normalized):
                    issues.append(
                        {
                            "code": code,
                            "line": line_number,
                            "message": message,
                            "excerpt": stripped[:200],
                        }
                    )
        return issues

    @staticmethod
    def required_structure_issues(do_file: str) -> list[dict[str, Any]]:
        text = str(do_file or "")
        checks = (
            ("missing_version", r"(?im)^\s*version\s+\d", "do-file 必须固定 Stata version"),
            ("missing_more_off", r"(?im)^\s*set\s+more\s+off\b", "do-file 必须设置 set more off"),
            (
                "missing_runner_args",
                r"(?im)^\s*args\b[^\r\n]*\binput_dta\b[^\r\n]*\boutput_dir\b",
                "do-file 必须接收 Runner 的 input_dta 和 output_dir 参数",
            ),
            (
                "missing_bound_input",
                r"(?im)^\s*(?:capture\s+|cap\s+|quietly\s+|qui\s+|noisily\s+|noi\s+)*use\b[^\r\n]*\binput_dta\b",
                "do-file 必须从 Runner 绑定的 input_dta 读取数据",
            ),
        )
        return [
            {"code": code, "line": 0, "message": message, "excerpt": ""}
            for code, pattern, message in checks
            if not re.search(pattern, text)
        ]


class StataBatchAdapter:
    def __init__(self) -> None:
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._cancel_requested: set[str] = set()

    async def cancel(self, run_id: str) -> bool:
        self._cancel_requested.add(run_id)
        process = self._processes.get(run_id)
        if process is None or process.returncode is not None:
            return False
        _kill_process_tree(process)
        return True

    async def execute(
        self,
        profile: dict[str, Any],
        do_file_path: Path,
        project_dir: Path,
        run_id: str,
        input_path: Path,
        output_dir: Path,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        executable = str(profile["executable"])
        if os.name == "nt":
            command = [executable, "/e", "do", str(do_file_path), str(project_dir), run_id, str(input_path), str(output_dir)]
        else:
            command = [executable, "-b", "do", str(do_file_path), str(project_dir), run_id, str(input_path), str(output_dir)]

        started_at = datetime.now(UTC)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(do_file_path.parent),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=os.name != "nt",
        )
        self._processes[run_id] = process
        timed_out = False
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
        except TimeoutError:
            timed_out = True
            _kill_process_tree(process)
            stdout, stderr = await process.communicate()
        finally:
            self._processes.pop(run_id, None)
        finished_at = datetime.now(UTC)
        canceled = run_id in self._cancel_requested
        self._cancel_requested.discard(run_id)
        (output_dir / "runner.stdout.log").write_bytes(stdout)
        (output_dir / "runner.stderr.log").write_bytes(stderr)
        return {
            "status": "canceled" if canceled else "failed" if timed_out or process.returncode else "succeeded",
            "reason_code": "user_canceled" if canceled else "timeout" if timed_out else "nonzero_exit" if process.returncode else "completed",
            "exit_code": process.returncode,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        }


def _kill_process_tree(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    if os.name == "nt":
        process.kill()
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
