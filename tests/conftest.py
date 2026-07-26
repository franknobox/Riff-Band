from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest


def pytest_configure() -> None:
    test_log_dir = Path(tempfile.gettempdir()) / "riffband-test-logs"
    test_log_dir.mkdir(parents=True, exist_ok=True)
    import os
    os.environ.setdefault("RIFFBAND_LOG_DIR", str(test_log_dir))

    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    src_str = str(src_path)
    if src_path.exists() and src_str not in sys.path:
        sys.path.insert(0, src_str)


@pytest.fixture(autouse=True)
def isolate_test_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep test-created workspace artifacts out of the repository workspace."""
    monkeypatch.chdir(tmp_path)
