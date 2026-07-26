from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from ai4ms.runners.bundle import (
    load_and_validate_result_bundle,
    parse_result_bundle,
    write_run_contract_files,
)
from ai4ms.runners.contracts import RunBundleRequest
from ai4ms.runners.remote import RemoteStataAdapter, discover_remote_stata_profile
from ai4ms.runners.stata import (
    StataBatchAdapter,
    StataPolicyScanner,
    discover_stata_profile,
    sha256_file,
)
from ai4ms.services.models import AnalysisRunRequest


class AnalysisRunnerService:
    def __init__(
        self,
        adapter: StataBatchAdapter | None = None,
        profile_factory: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.adapter = adapter or (
            RemoteStataAdapter()
            if os.environ.get("AI4MS_STATA_RUNNER_URL", "").strip()
            else StataBatchAdapter()
        )
        self.profile_factory = profile_factory or self._discover_profile

    def status(self) -> dict[str, Any]:
        profile = self.profile_factory()
        return self._public_profile(profile)

    def preflight(
        self,
        project: dict[str, Any],
        project_dir: Path,
        request: AnalysisRunRequest,
    ) -> dict[str, Any]:
        stages = {stage["key"]: stage for stage in project.get("stages", [])}
        plan_stage = stages.get("identification", {})
        analysis_stage = stages.get("analysis", {})
        plan = plan_stage.get("content", {})
        analysis = analysis_stage.get("content", {})
        do_file = str(analysis.get("do_file") or plan.get("stata_do_file") or "")
        profile = self.profile_factory()
        policy_issues = StataPolicyScanner.scan(do_file)
        structure_issues = StataPolicyScanner.required_structure_issues(do_file) if do_file else []

        gate_passed = plan_stage.get("status") == "approved"
        binding_passed = (
            not analysis.get("approved_analysis_plan_hash")
            or (
                analysis.get("approved_analysis_plan_hash") == plan_stage.get("content_hash")
                and analysis.get("approved_analysis_plan_revision") == plan_stage.get("revision")
            )
        )
        engine_passed = plan.get("execution_engine") == "stata"
        input_path, input_issue, input_asset = self._resolve_input(
            project, project_dir, request
        )
        variable_names = [
            str(item.get("source_variable"))
            for item in plan.get("variable_roles", [])
            if isinstance(item, dict) and item.get("source_variable")
        ]
        metadata_columns = {
            str(item.get("name"))
            for item in (input_asset or {}).get("metadata", {}).get("columns", [])
            if isinstance(item, dict) and item.get("name")
        }
        missing_variables = sorted(
            name for name in variable_names if metadata_columns and name not in metadata_columns
        )
        variable_mapping_passed = bool(variable_names) and not missing_variables
        asset_hash_passed = bool(input_path) and (
            input_asset is None
            or sha256_file(input_path) == str(input_asset.get("sha256") or "")
        )

        checks = {
            "gate_passed": gate_passed,
            "binding_passed": binding_passed,
            "engine_passed": engine_passed,
            "policy_passed": not policy_issues and not structure_issues and bool(do_file),
            "input_passed": input_path is not None,
            "asset_hash_passed": asset_hash_passed,
            "variable_mapping_passed": variable_mapping_passed,
            "runner_passed": bool(profile.get("available")),
            "license_passed": bool(profile.get("available") and profile.get("license_confirmed")),
        }
        issues: list[dict[str, Any]] = [*policy_issues, *structure_issues]
        simple_issues = (
            (not gate_passed, "gate_not_approved", "S5/G3 分析计划尚未由人工批准"),
            (not binding_passed, "stale_plan_binding", "S6 绑定的分析计划 revision 或 hash 已过期"),
            (not engine_passed, "unsupported_engine", "当前 Runner 只支持 execution_engine=stata"),
            (not do_file, "missing_do_file", "已批准 S5 计划没有可运行的 Stata do-file"),
            (not profile.get("available"), "no_runner", "未发现配置或 PATH 可用的 Stata BYOL Runner"),
            (profile.get("available") and not profile.get("license_confirmed"), "license_not_confirmed", "Runner 管理员尚未确认 Stata 许可可用"),
            (bool(input_issue), "invalid_input", input_issue),
            (
                bool(missing_variables),
                "missing_required_variables",
                f"数据文件缺少 S5 所需变量：{', '.join(missing_variables[:20])}",
            ),
            (
                not variable_names,
                "missing_variable_mapping",
                "S5 未提供变量映射",
            ),
            (
                bool(input_path) and not asset_hash_passed,
                "asset_hash_mismatch",
                "数据文件当前 SHA-256 与项目资产登记值不一致",
            ),
        )
        issues.extend(
            {"code": code, "line": 0, "message": message, "excerpt": ""}
            for condition, code, message in simple_issues
            if condition
        )
        reason_priority = (
            "gate_not_approved",
            "stale_plan_binding",
            "external_process",
            "dynamic_install",
            "embedded_runtime",
            "early_exit",
            "delimiter_change",
            "network_access",
            "parent_traversal",
            "absolute_windows_path",
            "absolute_posix_path",
            "unc_path",
            "destructive_delete",
            "overwrite_input",
            "missing_version",
            "missing_more_off",
            "missing_runner_args",
            "missing_bound_input",
            "unsupported_engine",
            "missing_do_file",
            "no_runner",
            "license_not_confirmed",
            "invalid_input",
            "asset_hash_mismatch",
            "missing_required_variables",
            "missing_variable_mapping",
        )
        issue_codes = {item["code"] for item in issues}
        reason_code = next((code for code in reason_priority if code in issue_codes), "ready")
        return {
            "status": "ready" if all(checks.values()) else "blocked",
            "reason_code": reason_code,
            "checked_at": datetime.now(UTC).isoformat(),
            "analysis_plan_revision": plan_stage.get("revision", 0),
            "analysis_plan_hash": plan_stage.get("content_hash", ""),
            "do_file_sha256": self._sha256_text(do_file),
            "runner_profile": self._public_profile(profile),
            "input_asset_id": request.input_asset_id,
            "input_artifact_path": (
                str(input_asset.get("stored_path"))
                if input_asset
                else request.input_artifact_path
            ),
            "input_metadata": (input_asset or {}).get("metadata", {}),
            "input_sha256": (input_asset or {}).get("sha256", ""),
            "required_variables": variable_names,
            "missing_variables": missing_variables,
            "checks": checks,
            "issues": issues,
        }

    async def submit(
        self,
        project: dict[str, Any],
        project_dir: Path,
        request: AnalysisRunRequest,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        preflight = self.preflight(project, project_dir, request)
        run_id = run_id or f"run_{uuid4().hex[:12]}"
        run_dir = project_dir / "artifacts" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        stages = {stage["key"]: stage for stage in project.get("stages", [])}
        plan = stages.get("identification", {}).get("content", {})
        analysis = stages.get("analysis", {}).get("content", {})
        do_file = str(analysis.get("do_file") or plan.get("stata_do_file") or "")
        do_file_path = run_dir / "analysis.do"
        do_file_path.write_bytes(do_file.encode("utf-8"))
        (run_dir / "preflight.json").write_text(
            json.dumps(preflight, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        run: dict[str, Any] = {
            "run_id": run_id,
            "status": "blocked",
            "reason_code": preflight["reason_code"],
            "requested_at": datetime.now(UTC).isoformat(),
            "requested_by": request.requested_by,
            "analysis_plan_revision": preflight["analysis_plan_revision"],
            "analysis_plan_hash": preflight["analysis_plan_hash"],
            "do_file_sha256": preflight["do_file_sha256"],
            "input_asset_id": request.input_asset_id,
            "input_artifact_path": request.input_artifact_path,
            "parameters": request.parameters,
            "seed": request.seed if request.seed is not None else plan.get("seed"),
            "runner_profile": preflight["runner_profile"],
            "preflight": preflight,
            "exit_code": None,
            "input_artifacts": [],
            "package_manifest": [],
            "output_artifacts": [],
            "structured_results": [],
            "logs": [],
            "data_signature": "",
            "manifest_path": f"artifacts/runs/{run_id}/manifest.json",
        }
        if preflight["status"] == "ready":
            input_path, _issue, input_asset = self._resolve_input(
                project, project_dir, request
            )
            input_sha256 = sha256_file(input_path)
            run["input_artifact_path"] = input_path.relative_to(project_dir).as_posix()
            run["input_artifacts"] = [
                {
                    "path": input_path.relative_to(project_dir).as_posix(),
                    "size": input_path.stat().st_size,
                    "sha256": input_sha256,
                    "asset_id": (input_asset or {}).get("asset_id", ""),
                }
            ]
            bundle_request = RunBundleRequest(
                run_id=run_id,
                project_id=str(project.get("project_id") or ""),
                input_sha256=input_sha256,
                do_file_sha256=preflight["do_file_sha256"],
                timeout_seconds=request.timeout_seconds,
                analysis_plan_revision=int(preflight["analysis_plan_revision"]),
                analysis_plan_hash=str(preflight["analysis_plan_hash"]),
                seed=run["seed"],
                parameters=request.parameters,
            )
            write_run_contract_files(
                run_dir,
                bundle_request,
                signing_token=os.environ.get("AI4MS_STATA_RUNNER_TOKEN", "").strip(),
            )
            try:
                execution = await self.adapter.execute(
                    self.profile_factory(),
                    run_dir / "entrypoint.do",
                    project_dir,
                    run_id,
                    input_path,
                    run_dir,
                    request.timeout_seconds,
                )
                run.update(execution)
                result_bundle_path = run_dir / "result_bundle.json"
                result_bundle = (
                    load_and_validate_result_bundle(
                        result_bundle_path,
                        run_id=run_id,
                        input_sha256=input_sha256,
                        do_file_sha256=preflight["do_file_sha256"],
                        signing_token=os.environ.get(
                            "AI4MS_STATA_RUNNER_TOKEN", ""
                        ).strip(),
                        require_signature=(
                            preflight["runner_profile"].get("transport")
                            == "http_local_runner"
                        ),
                        reject_undeclared=False,
                    )
                    if result_bundle_path.is_file()
                    else parse_result_bundle(
                        run_dir,
                        run_id=run_id,
                        input_sha256=input_sha256,
                        do_file_sha256=preflight["do_file_sha256"],
                        execution=execution,
                        runner_profile=self.profile_factory(),
                    )
                )
                run.update(
                    {
                        "status": result_bundle["status"],
                        "reason_code": result_bundle["reason_code"],
                        "exit_code": result_bundle["exit_code"],
                        "structured_results": result_bundle["structured_results"],
                        "data_signature": result_bundle["data_signature"],
                        "logs": result_bundle["logs"],
                        "result_bundle": result_bundle,
                    }
                )
            except asyncio.CancelledError:
                run.update(
                    {
                        "status": "canceled",
                        "reason_code": "user_canceled",
                        "finished_at": datetime.now(UTC).isoformat(),
                    }
                )
            except Exception as exc:
                run.update(
                    {
                        "status": "failed",
                        "reason_code": "runner_or_result_bundle_error",
                        "runner_error": f"{type(exc).__name__}: {str(exc)[:300]}",
                        "finished_at": datetime.now(UTC).isoformat(),
                    }
                )
            run["output_artifacts"] = self._collect_artifacts(project_dir, run_dir)

        manifest = run_dir / "manifest.json"
        manifest.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
        return run

    async def cancel(self, run_id: str) -> bool:
        cancel = getattr(self.adapter, "cancel", None)
        if not callable(cancel):
            return False
        return bool(await cancel(run_id))

    @staticmethod
    def _resolve_input(
        project: dict[str, Any],
        project_dir: Path,
        request: AnalysisRunRequest,
    ) -> tuple[Path | None, str, dict[str, Any] | None]:
        asset: dict[str, Any] | None = None
        if request.input_asset_id:
            asset = next(
                (
                    item
                    for item in project.get("data_assets", [])
                    if item.get("asset_id") == request.input_asset_id
                ),
                None,
            )
            if asset is None:
                return None, "项目中不存在指定的数据资产", None
        raw = str(
            (asset or {}).get("stored_path") or request.input_artifact_path or ""
        ).strip()
        if not raw:
            return None, "未配置项目内只读 .dta 输入文件", asset
        relative = Path(raw)
        if relative.is_absolute() or ".." in relative.parts:
            return None, "输入路径必须是项目目录内的相对路径", asset
        root = project_dir.resolve()
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return None, "输入路径越出项目目录", asset
        if target.suffix.lower() != ".dta":
            return None, "Stata Runner 输入必须是 .dta 文件", asset
        if not target.is_file():
            return None, "项目内输入文件不存在", asset
        return target, "", asset

    @staticmethod
    def _sha256_text(value: str) -> str:
        import hashlib

        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _public_profile(profile: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "available",
            "engine",
            "mode",
            "transport",
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
        return {key: profile.get(key) for key in keys}

    @staticmethod
    def _discover_profile() -> dict[str, Any]:
        return discover_remote_stata_profile() or discover_stata_profile()

    @staticmethod
    def _collect_artifacts(project_dir: Path, run_dir: Path) -> list[dict[str, Any]]:
        artifacts = []
        for path in sorted(run_dir.rglob("*")):
            if not path.is_file() or path.name == "manifest.json":
                continue
            artifacts.append(
                {
                    "path": path.relative_to(project_dir).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        return artifacts
