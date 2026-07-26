from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ai4ms.db import ProjectStore


class DataAssetError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class DataAssetService:
    def __init__(self, store: ProjectStore, projects_dir: Path):
        self.store = store
        self.projects_dir = projects_dir
        self.max_upload_bytes = max(
            1,
            int(os.environ.get("AI4MS_MAX_DATA_UPLOAD_BYTES", str(1024 * 1024 * 1024))),
        )

    async def upload(
        self,
        project_id: str,
        filename: str,
        media_type: str,
        read: Callable[[int], Awaitable[bytes]],
    ) -> dict[str, Any]:
        safe_name = self._safe_filename(filename)
        if Path(safe_name).suffix.lower() != ".dta":
            raise DataAssetError("unsupported_data_format", "当前只接受 Stata .dta 数据文件")

        asset_id = f"data_{uuid4().hex[:12]}"
        asset_dir = self.projects_dir / project_id / "artifacts" / "data" / asset_id
        asset_dir.mkdir(parents=True, exist_ok=False)
        target = asset_dir / safe_name
        temporary = asset_dir / f".{safe_name}.uploading"
        digest = hashlib.sha256()
        size = 0
        try:
            with temporary.open("xb") as handle:
                while chunk := await read(1024 * 1024):
                    size += len(chunk)
                    if size > self.max_upload_bytes:
                        raise DataAssetError(
                            "data_file_too_large",
                            f"数据文件超过上传上限 {self.max_upload_bytes} bytes",
                        )
                    digest.update(chunk)
                    handle.write(chunk)
            if size == 0:
                raise DataAssetError("empty_data_file", "上传的数据文件为空")
            temporary.replace(target)
            metadata = self.read_stata_metadata(target)
            relative_path = target.relative_to(self.projects_dir / project_id).as_posix()
            return self.store.create_data_asset(
                project_id=project_id,
                asset_id=asset_id,
                original_name=safe_name,
                stored_path=relative_path,
                media_type=media_type or "application/octet-stream",
                size_bytes=size,
                sha256=digest.hexdigest(),
                metadata=metadata,
            )
        except Exception:
            temporary.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            try:
                asset_dir.rmdir()
            except OSError:
                pass
            raise

    @staticmethod
    def read_stata_metadata(path: Path) -> dict[str, Any]:
        try:
            from pandas.io.stata import StataReader

            with StataReader(path, convert_dates=False, convert_categoricals=False) as reader:
                reader._ensure_open()
                variable_labels = reader.variable_labels()
                names = list(reader._varlist)
                storage_types = list(reader._typlist)
                display_formats = list(reader._fmtlist)
                value_label_names = list(reader._lbllist)
                columns = [
                    {
                        "name": name,
                        "label": str(variable_labels.get(name, "")),
                        "storage_type": str(storage_types[index]) if index < len(storage_types) else "",
                        "display_format": str(display_formats[index]) if index < len(display_formats) else "",
                        "value_label": str(value_label_names[index]) if index < len(value_label_names) else "",
                    }
                    for index, name in enumerate(names)
                ]
                timestamp = getattr(reader, "_time_stamp", None)
                return {
                    "format": "stata_dta",
                    "format_version": str(getattr(reader, "_format_version", "unknown")),
                    "data_label": str(getattr(reader, "data_label", "") or ""),
                    "time_stamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp or ""),
                    "row_count": int(reader._nobs),
                    "column_count": int(reader._nvar),
                    "columns": columns,
                    "parsed_at": datetime.now(UTC).isoformat(),
                }
        except DataAssetError:
            raise
        except Exception as exc:
            raise DataAssetError(
                "invalid_stata_file",
                f"无法读取 Stata 数据元信息：{type(exc).__name__}: {str(exc)[:240]}",
            ) from exc

    @staticmethod
    def _safe_filename(filename: str) -> str:
        name = Path(str(filename or "").strip()).name
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
        if not name:
            raise DataAssetError("invalid_filename", "数据文件名无效")
        if len(name) > 180:
            stem = Path(name).stem[:160]
            name = f"{stem}{Path(name).suffix[:20]}"
        return name
