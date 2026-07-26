from __future__ import annotations

import json
import asyncio
import io
import sys
from pathlib import Path

import mcp_server
from mcp_server import RiffBandMCPServer
from research import ResearchResult


def _write_config(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "main_model: test-model",
                "sub_models:",
                "  - test-model",
                "sources_dir: workspace/sources",
                "workspace_dir: workspace",
                "mode: auto",
                "profile_name: generic",
            ]
        ),
        encoding="utf-8",
    )


def test_mcp_initialize_and_list_tools(tmp_path):
    config_path = tmp_path / "aorchestra.yaml"
    _write_config(config_path)
    server = RiffBandMCPServer(config_path)

    init_response = asyncio.run(
        server.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
    )
    assert init_response["result"]["capabilities"]["tools"] == {}

    tools_response = asyncio.run(
        server.handle_request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
    )
    tools = tools_response["result"]["tools"]
    tool_names = [tool["name"] for tool in tools]
    assert "research" in tool_names
    assert "cancel_research" in tool_names
    assert tools[0]["inputSchema"]["required"] == ["topic"]


async def _await_mcp_job(server: RiffBandMCPServer, task_id: str) -> dict:
    for _ in range(20):
        response = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 30,
                "method": "tools/call",
                "params": {
                    "name": "research_status",
                    "arguments": {"task_id": task_id},
                },
            }
        )
        payload = response["result"]["structuredContent"]
        if payload["status"] != "running":
            return payload
        await asyncio.sleep(0.01)
    raise AssertionError(f"MCP research job did not finish: {task_id}")


def test_mcp_research_tool_starts_background_job_and_status_returns_result(tmp_path):
    config_path = tmp_path / "aorchestra.yaml"
    _write_config(config_path)
    server = RiffBandMCPServer(config_path)

    async def run_case():
        response = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "research",
                    "arguments": {
                        "topic": "low altitude economy in the Greater Bay Area",
                        "depth": "quick",
                    },
                },
            }
        )

        result = response["result"]
        assert result["isError"] is False
        payload = result["structuredContent"]
        assert payload["status"] == "running"
        assert payload["task_id"]

        final_payload = await _await_mcp_job(server, payload["task_id"])
        assert final_payload["status"] in {"done", "partial"}
        research_result = final_payload["result"]
        assert research_result["metadata"]["trigger"] == "mcp"
        assert research_result["metadata"]["topic"] == "low altitude economy in the Greater Bay Area"
        assert research_result["status"] == "partial"

    asyncio.run(run_case())


def test_mcp_research_visual_mode(tmp_path):
    config_path = tmp_path / "aorchestra.yaml"
    _write_config(config_path)
    server = RiffBandMCPServer(config_path)

    async def run_case():
        response = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "research",
                    "arguments": {
                        "topic": "AI trends 2026",
                        "mode": "visual",
                        "depth": "quick",
                        "output_format": "html",
                    },
                },
            }
        )

        result = response["result"]
        assert result["isError"] is False
        payload = result["structuredContent"]
        assert payload["status"] == "running"
        final_payload = await _await_mcp_job(server, payload["task_id"])
        research_result = final_payload["result"]
        assert research_result["metadata"]["mode"] == "visual"
        artifact_paths = [a["path"] for a in research_result["artifacts"]]
        assert any("_visual.html" in p for p in artifact_paths)

    asyncio.run(run_case())


def test_mcp_research_tool_returns_before_long_job_finishes(tmp_path, monkeypatch):
    config_path = tmp_path / "aorchestra.yaml"
    _write_config(config_path)
    server = RiffBandMCPServer(config_path)

    async def slow_research(request, config, progress_callback=None, cancel_event=None):
        await asyncio.sleep(1)
        return ResearchResult(status="partial", metadata={"topic": request.topic})

    target_module = getattr(mcp_server, "_module", mcp_server)
    monkeypatch.setattr(target_module, "run_research", slow_research)

    async def run_case():
        response = await asyncio.wait_for(
            server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 40,
                    "method": "tools/call",
                    "params": {
                        "name": "research",
                        "arguments": {"topic": "slow topic"},
                    },
                }
            ),
            timeout=0.1,
        )
        payload = response["result"]["structuredContent"]
        assert payload["status"] == "running"
        assert payload["task_id"]

        cancel_response = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 41,
                "method": "tools/call",
                "params": {
                    "name": "cancel_research",
                    "arguments": {"task_id": payload["task_id"]},
                },
            }
        )
        assert cancel_response["result"]["structuredContent"]["cancelled"] is True

    asyncio.run(run_case())


def test_mcp_cancel_research_sets_cancel_event(tmp_path, monkeypatch):
    config_path = tmp_path / "aorchestra.yaml"
    _write_config(config_path)
    server = RiffBandMCPServer(config_path)

    async def cancellable_research(request, config, progress_callback=None, cancel_event=None):
        assert cancel_event is not None
        await asyncio.wait_for(cancel_event.wait(), timeout=1)
        return ResearchResult(status="partial", summary="cancel observed")

    target_module = getattr(mcp_server, "_module", mcp_server)
    monkeypatch.setattr(target_module, "run_research", cancellable_research)

    async def run_case():
        start = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 42,
                "method": "tools/call",
                "params": {
                    "name": "research",
                    "arguments": {"topic": "cancellable topic"},
                },
            }
        )
        task_id = start["result"]["structuredContent"]["task_id"]
        cancel = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 43,
                "method": "tools/call",
                "params": {
                    "name": "cancel_research",
                    "arguments": {"task_id": task_id},
                },
            }
        )
        assert cancel["result"]["structuredContent"]["cancelled"] is True

        final_payload = await _await_mcp_job(server, task_id)
        assert final_payload["status"] == "cancelled"

    asyncio.run(run_case())


def test_mcp_cancel_research_idle(tmp_path):
    config_path = tmp_path / "aorchestra.yaml"
    _write_config(config_path)
    server = RiffBandMCPServer(config_path)

    response = asyncio.run(
        server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "cancel_research",
                    "arguments": {},
                },
            }
        )
    )

    result = response["result"]["structuredContent"]
    assert result["cancelled"] is False
    assert "No running research" in result["reason"]


def test_mcp_progress_notification_format():
    server = RiffBandMCPServer.__new__(RiffBandMCPServer)

    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        server._emit_progress("test progress message")
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue().strip()
    notification = json.loads(output)
    assert notification["jsonrpc"] == "2.0"
    assert "id" not in notification  # notifications have no id
    assert notification["method"] == "notifications/progress"
    assert notification["params"]["message"] == "test progress message"


def test_mcp_tool_description_includes_visual():
    config_path = Path("dummy.yaml")
    server = RiffBandMCPServer.__new__(RiffBandMCPServer)

    # Mock _tool_definitions by calling it on a bare instance
    # Since _tool_definitions doesn't use self attributes, we can call it
    tools = server._tool_definitions()
    research_tool = [t for t in tools if t["name"] == "research"][0]
    desc = research_tool["description"]
    assert "visual" in desc.lower()
    assert "report_visual.html" in desc


def test_mcp_research_invalid_mode_rejected(tmp_path):
    config_path = tmp_path / "aorchestra.yaml"
    _write_config(config_path)
    server = RiffBandMCPServer(config_path)

    response = asyncio.run(
        server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "research",
                    "arguments": {
                        "topic": "test",
                        "mode": "invalid_mode",
                    },
                },
            }
        )
    )

    assert response["result"]["isError"] is True


def test_mcp_error_on_empty_topic(tmp_path):
    config_path = tmp_path / "aorchestra.yaml"
    _write_config(config_path)
    server = RiffBandMCPServer(config_path)

    response = asyncio.run(
        server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "research",
                    "arguments": {
                        "mode": "academic",
                    },
                },
            }
        )
    )

    assert response["result"]["isError"] is True
