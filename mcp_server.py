"""Compatibility entry point for the Riff Band MCP stdio server."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_PATH = REPO_ROOT / "src"
MODULE_PATH = SRC_PATH / "mcp_server.py"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

spec = importlib.util.spec_from_file_location("_riffband_mcp_server", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Failed to load MCP server module from {MODULE_PATH}")

_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = _module
spec.loader.exec_module(_module)

RiffBandMCPServer = _module.RiffBandMCPServer
main = _module.main
_entry = _module._entry


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
