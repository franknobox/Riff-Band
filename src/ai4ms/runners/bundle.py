from __future__ import annotations

import csv
import hashlib
import hmac
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

from ai4ms.runners.contracts import ResultBundle, RunBundleRequest, StructuredResult
from ai4ms.runners.stata import sha256_file


RESULT_ARTIFACT_SUFFIXES = {
    ".json",
    ".csv",
    ".xlsx",
    ".xls",
    ".tex",
    ".png",
    ".svg",
    ".pdf",
    ".gph",
    ".log",
    ".smcl",
    ".txt",
}


ENTRYPOINT_DO = r"""version 18.0
set more off
args project_dir run_id input_dta output_dir

capture log close _all
log using "`output_dir'/analysis.log", text replace name(ai4ms)
capture noisily do "analysis.do" "`project_dir'" "`run_id'" "`input_dta'" "`output_dir'"
local analysis_rc = _rc
local contract_rc = 0
if `analysis_rc' == 0 {
    capture noisily do "result_contract.do" "`project_dir'" "`run_id'" "`input_dta'" "`output_dir'"
    local contract_rc = _rc
}
capture log close ai4ms

if `analysis_rc' != 0 {
    exit `analysis_rc'
}
if `contract_rc' != 0 {
    exit `contract_rc'
}
exit 0
"""


RESULT_CONTRACT_DO = r"""version 18.0
set more off
args project_dir run_id input_dta output_dir

capture noisily datasignature
local ai4ms_signature ""
if _rc == 0 {
    local ai4ms_signature "`r(datasignature)'"
}
tempname signature_file
file open `signature_file' using "`output_dir'/data_signature.txt", write text replace
file write `signature_file' `"`ai4ms_signature'"' _n
file close `signature_file'

capture confirm matrix e(b)
if _rc != 0 {
    display as error "AI4MS result contract requires the final approved estimation result in e(b)."
    exit 459
}
capture confirm matrix e(V)
if _rc != 0 {
    display as error "AI4MS result contract requires e(V) for uncertainty reporting."
    exit 459
}

matrix __ai4ms_b = e(b)
matrix __ai4ms_v = e(V)
local ai4ms_terms : colfullnames __ai4ms_b
local ai4ms_k = colsof(__ai4ms_b)
local ai4ms_cmdline `"`e(cmdline)'"'
scalar __ai4ms_n = .
scalar __ai4ms_df = .
capture scalar __ai4ms_n = e(N)
capture scalar __ai4ms_df = e(df_r)

tempname result_post
tempfile result_data
postfile `result_post' str32 result_id str16 kind str64 specification_id str244 term ///
    str244 label double estimate std_error statistic p_value ci_lower ci_upper ///
    long sample_size str16 status str32 unit using `result_data', replace

forvalues ai4ms_i = 1/`ai4ms_k' {
    local ai4ms_term : word `ai4ms_i' of `ai4ms_terms'
    scalar __ai4ms_estimate = __ai4ms_b[1, `ai4ms_i']
    scalar __ai4ms_se = sqrt(__ai4ms_v[`ai4ms_i', `ai4ms_i'])
    scalar __ai4ms_stat = cond(__ai4ms_se > 0, __ai4ms_estimate / __ai4ms_se, .)
    scalar __ai4ms_p = cond(missing(__ai4ms_stat), ., ///
        cond(missing(__ai4ms_df), 2 * normal(-abs(__ai4ms_stat)), ///
        2 * ttail(__ai4ms_df, abs(__ai4ms_stat))))
    scalar __ai4ms_critical = cond(missing(__ai4ms_df), invnormal(.975), invttail(__ai4ms_df, .025))
    scalar __ai4ms_low = __ai4ms_estimate - __ai4ms_critical * __ai4ms_se
    scalar __ai4ms_high = __ai4ms_estimate + __ai4ms_critical * __ai4ms_se
    local ai4ms_result_id "RES_`ai4ms_i'"
    post `result_post' ("`ai4ms_result_id'") ("estimate") ("main") ///
        ("`ai4ms_term'") (`"`ai4ms_cmdline'"') (__ai4ms_estimate) (__ai4ms_se) ///
        (__ai4ms_stat) (__ai4ms_p) (__ai4ms_low) (__ai4ms_high) ///
        (__ai4ms_n) ("observed") ("")
}
postclose `result_post'

preserve
use `result_data', clear
export delimited using "`output_dir'/structured_results.csv", replace quote
restore
"""


def write_run_contract_files(
    run_dir: Path,
    request: RunBundleRequest,
    *,
    signing_token: str = "",
) -> RunBundleRequest:
    if signing_token:
        request = request.model_copy(
            update={"bundle_signature": _signature(request, signing_token)}
        )
    (run_dir / "entrypoint.do").write_text(ENTRYPOINT_DO, encoding="utf-8")
    (run_dir / "result_contract.do").write_text(RESULT_CONTRACT_DO, encoding="utf-8")
    (run_dir / "run_request.json").write_text(
        request.model_dump_json(indent=2), encoding="utf-8"
    )
    return request


def create_request_archive(run_dir: Path, input_path: Path, archive_path: Path) -> list[str]:
    names = ["run_request.json", "analysis.do", "entrypoint.do", "result_contract.do"]
    with zipfile.ZipFile(archive_path, "w", allowZip64=True) as archive:
        for name in names:
            archive.write(run_dir / name, name, compress_type=zipfile.ZIP_DEFLATED)
        archive.write(input_path, "input.dta", compress_type=zipfile.ZIP_STORED)
    return [*names, "input.dta"]


def safe_extract_archive(
    archive_path: Path,
    destination: Path,
    *,
    max_files: int = 256,
    max_uncompressed_bytes: int = 4 * 1024 * 1024 * 1024,
) -> list[Path]:
    destination = destination.resolve()
    extracted: list[Path] = []
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        if len(infos) > max_files:
            raise ValueError("run bundle contains too many files")
        if sum(item.file_size for item in infos) > max_uncompressed_bytes:
            raise ValueError("run bundle exceeds the uncompressed size limit")
        for item in infos:
            if item.is_dir():
                continue
            relative = Path(item.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("run bundle contains an unsafe path")
            target = (destination / relative).resolve()
            try:
                target.relative_to(destination)
            except ValueError as exc:
                raise ValueError("run bundle path escapes destination") from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            extracted.append(target)
    return extracted


def parse_result_bundle(
    output_dir: Path,
    *,
    run_id: str,
    input_sha256: str,
    do_file_sha256: str,
    execution: dict[str, Any],
    runner_profile: dict[str, Any],
    signing_token: str = "",
) -> dict[str, Any]:
    warnings: list[str] = []
    results_path = output_dir / "structured_results.csv"
    structured_results = _parse_structured_results(results_path) if results_path.is_file() else []
    status = str(execution.get("status") or "failed")
    reason_code = str(execution.get("reason_code") or "runner_error")
    if status == "succeeded" and not structured_results:
        status = "failed"
        reason_code = "missing_structured_results"
        warnings.append("运行退出码为 0，但未产生符合契约的 structured_results.csv")

    signature_path = output_dir / "data_signature.txt"
    data_signature = (
        signature_path.read_text(encoding="utf-8", errors="replace").strip()[:2000]
        if signature_path.is_file()
        else ""
    )
    if status == "succeeded" and not data_signature:
        warnings.append("未回收 Stata datasignature；文件 SHA-256 仍保留")

    files = [
        path
        for path in output_dir.rglob("*")
        if path.is_file()
        and path.name != "result_bundle.json"
        and path.suffix.lower() in RESULT_ARTIFACT_SUFFIXES
    ]
    tables = sorted(
        path.relative_to(output_dir).as_posix()
        for path in files
        if path.suffix.lower() in {".csv", ".xlsx", ".xls", ".tex"}
    )
    figures = sorted(
        path.relative_to(output_dir).as_posix()
        for path in files
        if path.suffix.lower() in {".png", ".svg", ".pdf", ".gph"}
    )
    logs = sorted(
        path.relative_to(output_dir).as_posix()
        for path in files
        if path.suffix.lower() in {".log", ".smcl"}
    )
    public_runner = {
        key: runner_profile.get(key)
        for key in (
            "engine",
            "mode",
            "transport",
            "executable_name",
            "version",
            "edition",
            "os",
            "locale",
            "license_mode",
        )
        if runner_profile.get(key) is not None
    }
    bundle = ResultBundle(
        run_id=run_id,
        status=status,
        reason_code=reason_code,
        exit_code=execution.get("exit_code"),
        started_at=str(execution.get("started_at") or ""),
        finished_at=str(execution.get("finished_at") or ""),
        duration_seconds=execution.get("duration_seconds"),
        input_sha256=input_sha256,
        do_file_sha256=do_file_sha256,
        data_signature=data_signature,
        runner=public_runner,
        structured_results=structured_results,
        tables=tables,
        figures=figures,
        logs=logs,
        artifacts=[
            {
                "path": path.relative_to(output_dir).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in sorted(files)
        ],
        warnings=warnings,
    )
    if signing_token:
        bundle = bundle.model_copy(
            update={"bundle_signature": _signature(bundle, signing_token)}
        )
    result = bundle.model_dump(mode="json")
    (output_dir / "result_bundle.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def load_and_validate_result_bundle(
    path: Path,
    *,
    run_id: str,
    input_sha256: str,
    do_file_sha256: str,
    signing_token: str = "",
    require_signature: bool = False,
    reject_undeclared: bool = True,
) -> dict[str, Any]:
    bundle = ResultBundle.model_validate_json(path.read_text(encoding="utf-8"))
    if bundle.run_id != run_id:
        raise ValueError("result bundle run_id does not match request")
    if bundle.input_sha256 != input_sha256:
        raise ValueError("result bundle input hash does not match request")
    if bundle.do_file_sha256 != do_file_sha256:
        raise ValueError("result bundle do-file hash does not match request")
    if require_signature and not bundle.bundle_signature:
        raise ValueError("result bundle signature is missing")
    if signing_token and bundle.bundle_signature:
        expected = _signature(bundle, signing_token)
        if not hmac.compare_digest(bundle.bundle_signature, expected):
            raise ValueError("result bundle signature is invalid")
    root = path.parent.resolve()
    declared_paths = set()
    for artifact in bundle.artifacts:
        relative = Path(artifact.path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("result bundle contains an unsafe artifact path")
        artifact_path = (root / relative).resolve()
        try:
            artifact_path.relative_to(root)
        except ValueError as exc:
            raise ValueError("result bundle artifact escapes result directory") from exc
        if not artifact_path.is_file():
            raise ValueError(f"result bundle artifact is missing: {artifact.path}")
        if artifact_path.stat().st_size != artifact.size:
            raise ValueError(f"result bundle artifact size mismatch: {artifact.path}")
        if sha256_file(artifact_path) != artifact.sha256:
            raise ValueError(f"result bundle artifact hash mismatch: {artifact.path}")
        declared_paths.add(artifact.path)
    returned_paths = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item.name != path.name
    }
    if reject_undeclared and returned_paths - declared_paths:
        raise ValueError("result bundle contains undeclared files")
    return bundle.model_dump(mode="json")


def verify_run_request_signature(request: RunBundleRequest, signing_token: str) -> bool:
    if not request.bundle_signature or not signing_token:
        return False
    return hmac.compare_digest(
        request.bundle_signature,
        _signature(request, signing_token),
    )


def _parse_structured_results(path: Path) -> list[StructuredResult]:
    results: list[StructuredResult] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle), start=1):
            result_id = str(row.get("result_id") or f"RES_{index}").strip()
            results.append(
                StructuredResult(
                    result_id=result_id,
                    kind=str(row.get("kind") or "estimate").strip(),
                    specification_id=str(row.get("specification_id") or "").strip(),
                    term=str(row.get("term") or "").strip(),
                    label=str(row.get("label") or "").strip(),
                    estimate=_number(row.get("estimate")),
                    std_error=_number(row.get("std_error")),
                    statistic=_number(row.get("statistic")),
                    p_value=_number(row.get("p_value")),
                    ci_lower=_number(row.get("ci_lower")),
                    ci_upper=_number(row.get("ci_upper")),
                    sample_size=_integer(row.get("sample_size")),
                    status=str(row.get("status") or "observed").strip(),
                    unit=str(row.get("unit") or "").strip(),
                    source_file=path.name,
                )
            )
    return results


def _number(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text == ".":
        return None
    return float(text)


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _signature(model: RunBundleRequest | ResultBundle, signing_token: str) -> str:
    payload = model.model_dump(mode="json", exclude={"bundle_signature"})
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hmac.new(signing_token.encode("utf-8"), canonical, hashlib.sha256).hexdigest()


def output_file_manifest(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]
