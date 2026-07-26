from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from pydantic import ValidationError

from config import AgentConfig
from research import ResearchRequest, run_research


JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"
ERROR_CODE_CANCELLED = -32000


@dataclass
class MCPResearchJob:
    task_id: str
    request: ResearchRequest
    cancel_event: asyncio.Event
    task: asyncio.Task | None = None
    status: str = "running"
    result: dict[str, Any] | None = None
    error: str = ""
    cancel_requested: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    progress: list[str] = field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "task_id": self.task_id,
            "status": self.status,
            "topic": self.request.topic,
            "mode": self.request.mode,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "cancel_requested": self.cancel_requested,
            "progress": self.progress[-20:],
        }
        if self.result is not None:
            payload["result"] = self.result
        if self.error:
            payload["error"] = self.error
        return payload


class RiffBandMCPServer:
    """Minimal stdio MCP server for Riff Band.

    The server intentionally avoids an SDK dependency for now. It implements the
    small JSON-RPC surface needed by MCP clients to discover and call tools.
    """

    def __init__(self, config_path: str | Path = "aorchestra.yaml"):
        load_dotenv()
        self.config_path = Path(config_path)
        self.config = AgentConfig.load(self.config_path)
        self._jobs: dict[str, MCPResearchJob] = {}
        self._current_task_id: str | None = None
        self._cancel_grace_seconds = 1.0

    @staticmethod
    def _success(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
        error: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": error}

    @staticmethod
    def _text_content(text: str) -> list[dict[str, str]]:
        return [{"type": "text", "text": text}]

    def _tool_result(
        self,
        request_id: Any,
        payload: dict[str, Any],
        *,
        is_error: bool = False,
    ) -> dict[str, Any]:
        return self._success(
            request_id,
            {
                "content": self._text_content(
                    json.dumps(payload, ensure_ascii=False, indent=2)
                ),
                "structuredContent": payload,
                "isError": is_error,
            },
        )

    def _emit_progress(self, message: str) -> None:
        """Emit a progress notification on stdout for MCP clients."""
        notification = {
            "jsonrpc": JSONRPC_VERSION,
            "method": "notifications/progress",
            "params": {"message": message},
        }
        sys.stdout.write(json.dumps(notification, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def _tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "research",
                "description": (
                    "Run Riff Band fixed research pipeline for a topic. "
                    "Supports two modes: academic (9-step literature review, "
                    "outputs paper.tex + references.bib) and visual "
                    "(10-step general research, outputs report_visual.html "
                    "with ECharts, TOC, dark/light toggle)."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Research topic or question.",
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["academic", "visual"],
                            "default": "academic",
                        },
                        "depth": {
                            "type": "string",
                            "enum": ["quick", "standard", "deep"],
                            "default": "standard",
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["markdown", "latex", "html", "json"],
                            "default": "latex",
                        },
                        "sources": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                        "constraints": {
                            "type": "string",
                            "default": "",
                        },
                    },
                    "required": ["topic"],
                },
            },
            {
                "name": "research_status",
                "description": "Get status and result for a running or finished research task.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "Task id returned by the research tool.",
                        },
                    },
                },
            },
            {
                "name": "cancel_research",
                "description": "Cancel the currently running research task.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "Optional task id. Defaults to the latest running task.",
                        },
                    },
                },
            },
        ]

    async def handle_request(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = str(message.get("method", ""))
        request_id = message.get("id")
        params = message.get("params") or {}

        # Notifications do not require responses.
        if request_id is None and method in {"notifications/initialized", "initialized"}:
            return None

        if method == "initialize":
            return self._success(
                request_id,
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "riff-band", "version": "0.1.0"},
                },
            )

        if method == "ping":
            return self._success(request_id, {})

        if method == "tools/list":
            return self._success(request_id, {"tools": self._tool_definitions()})

        if method == "tools/call":
            return await self._handle_tool_call(request_id, params)

        if method == "resources/list":
            return self._success(request_id, {"resources": []})

        if method == "prompts/list":
            return self._success(request_id, {"prompts": []})

        return self._error(request_id, -32601, f"Method not found: {method}")

    async def _handle_tool_call(self, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("name", ""))
        arguments = params.get("arguments") or {}

        if name == "cancel_research":
            return self._handle_cancel(request_id, arguments)

        if name == "research_status":
            return self._handle_status(request_id, arguments)

        if name != "research":
            return self._error(request_id, -32602, f"Unknown tool: {name}")
        if not isinstance(arguments, dict):
            return self._error(request_id, -32602, "Tool arguments must be an object.")

        try:
            request = ResearchRequest(
                topic=arguments.get("topic", ""),
                mode=arguments.get("mode", "academic"),
                depth=arguments.get("depth", "standard"),
                output_format=arguments.get("output_format", "latex"),
                sources=list(arguments.get("sources") or []),
                constraints=str(arguments.get("constraints", "") or ""),
                trigger="mcp",
                metadata={
                    "mcp_tool": name,
                    "config_path": str(self.config_path),
                },
            )
        except (TypeError, ValidationError, ValueError) as exc:
            return self._success(
                request_id,
                {
                    "content": self._text_content(f"Invalid research request: {exc}"),
                    "isError": True,
                },
            )

        job = self._start_research_job(request)
        return self._tool_result(request_id, job.payload(), is_error=False)

    def _start_research_job(self, request: ResearchRequest) -> MCPResearchJob:
        task_id = f"research_{uuid4().hex[:12]}"
        job = MCPResearchJob(
            task_id=task_id,
            request=request,
            cancel_event=asyncio.Event(),
        )
        self._jobs[task_id] = job
        self._current_task_id = task_id
        job.task = asyncio.create_task(self._run_research_job(job), name=task_id)
        self._emit_job_progress(job, f"Research started: {request.topic!r} mode={request.mode}")
        return job

    async def _run_research_job(self, job: MCPResearchJob) -> None:
        try:
            result = await run_research(
                job.request,
                self.config,
                progress_callback=lambda message: self._emit_job_progress(job, message),
                cancel_event=job.cancel_event,
            )
            job.result = result.model_dump()
            job.status = "cancelled" if job.cancel_requested else result.status
        except asyncio.CancelledError:
            job.status = "cancelled"
            job.error = "Research cancelled"
            self._emit_job_progress(job, "Research cancelled by client")
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            self._emit_job_progress(job, f"Research failed: {exc}")
        finally:
            job.touch()
            if self._current_task_id == job.task_id:
                self._current_task_id = None

    def _emit_job_progress(self, job: MCPResearchJob, message: str) -> None:
        job.progress.append(message)
        job.touch()
        self._emit_progress(message)

    def _handle_status(self, request_id: Any, arguments: dict[str, Any]) -> dict[str, Any]:
        task_id = str(arguments.get("task_id", "") or "").strip()
        if not task_id:
            task_id = self._current_task_id or self._latest_task_id()
        job = self._jobs.get(task_id)
        if job is None:
            return self._tool_result(
                request_id,
                {"task_id": task_id, "status": "unknown", "error": "Unknown research task"},
                is_error=True,
            )
        return self._tool_result(request_id, job.payload(), is_error=job.status in {"failed", "blocked"})

    def _handle_cancel(self, request_id: Any, arguments: dict[str, Any]) -> dict[str, Any]:
        task_id = str(arguments.get("task_id", "") or "").strip()
        if not task_id:
            task_id = self._current_task_id or self._latest_running_task_id()
        job = self._jobs.get(task_id)
        if job is None or job.status != "running":
            return self._tool_result(
                request_id,
                {
                    "task_id": task_id,
                    "cancelled": False,
                    "reason": "No running research",
                },
            )

        job.cancel_requested = True
        job.cancel_event.set()
        job.touch()
        asyncio.create_task(self._force_cancel_after_grace(job.task_id))
        return self._tool_result(
            request_id,
            {
                "task_id": job.task_id,
                "cancelled": True,
                "status": job.status,
            },
        )

    async def _force_cancel_after_grace(self, task_id: str) -> None:
        await asyncio.sleep(self._cancel_grace_seconds)
        job = self._jobs.get(task_id)
        if job is None or job.status != "running" or job.task is None or job.task.done():
            return
        job.task.cancel()

    def _latest_running_task_id(self) -> str | None:
        for task_id, job in reversed(self._jobs.items()):
            if job.status == "running":
                return task_id
        return None

    def _latest_task_id(self) -> str | None:
        if not self._jobs:
            return None
        return next(reversed(self._jobs))

    async def serve_stdio(self) -> int:
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                response = self._error(None, -32700, "Parse error", str(exc))
            else:
                if not isinstance(message, dict):
                    response = self._error(None, -32600, "Invalid Request")
                else:
                    response = await self.handle_request(message)
            if response is None:
                continue
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        return 0


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Riff Band MCP stdio server")
    parser.add_argument("--config", default="aorchestra.yaml", help="Path to config YAML")
    args = parser.parse_args(argv)

    server = RiffBandMCPServer(args.config)
    return await server.serve_stdio()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
else:
    def _entry():
        raise SystemExit(asyncio.run(main()))
