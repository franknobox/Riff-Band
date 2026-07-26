from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
import shutil
import uuid

from agents.main_agent import MainOrchestratorAgent
from core.interfaces import TaskContext
from project.tools import RecordFindingTool, WriteReportSectionTool
from orchestration_tools.complete_task import CompleteTaskTool
from orchestration_tools.delegate import ScopedEnvironment


class DummyEnv:
    def __init__(self):
        self.max_steps = 5
        self.calls = []

    def get_task_context(self) -> TaskContext:
        return TaskContext(
            task_id="t1",
            instruction="demo",
            action_space=(
                "Available actions:\n\n"
                "### read_source\nDescription: read\nParameters: {}\n\n"
                "### web_search\nDescription: search\nParameters: {}\n\n"
                "### record_finding\nDescription: record\nParameters: {}\n\n"
                "### finish\nDescription: done\nParameters: {}"
            ),
            max_steps=5,
            meta_data={},
        )

    async def reset(self, seed=None):
        return {"current_step": 0}

    async def step(self, action):
        self.calls.append(action)
        return {"ok": True}, 0.0, False, {}


class TestStandardFlows(unittest.TestCase):
    def _make_tmp_dir(self) -> Path:
        root = Path("workspace") / "test_tmp"
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"case_{uuid.uuid4().hex}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def test_record_finding_dedup_and_fields(self):
        td = self._make_tmp_dir()
        try:
            path = td / "findings.jsonl"
            tool = RecordFindingTool(findings_path=path)

            result1 = asyncio.run(
                tool(
                    city="Shenzhen",
                    industry="AI",
                    finding="Strong AI ecosystem",
                    evidence="Official policy doc",
                    source_url="https://example.com/doc",
                    source_title="Policy",
                    published_at="2026-04-01",
                    quote="AI support increased",
                    confidence="high",
                )
            )
            self.assertTrue(result1["success"])

            result2 = asyncio.run(
                tool(
                    city="Shenzhen",
                    industry="AI",
                    finding="Strong AI ecosystem",
                    evidence="Official policy doc",
                    source_url="https://example.com/doc",
                    source_title="Policy",
                    published_at="2026-04-01",
                    quote="AI support increased",
                    confidence="high",
                )
            )
            self.assertTrue(result2["success"])
            self.assertIn("Skipped duplicate", result2["output"])

            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(rows), 1)
            self.assertIn("dedup_key", rows[0])
            self.assertIn("source_url", rows[0])
            self.assertEqual(rows[0]["confidence"], "high")
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_write_report_section_default_header(self):
        td = self._make_tmp_dir()
        try:
            path = td / "report.md"
            tool = WriteReportSectionTool(report_path=path)

            asyncio.run(tool(section_title="Executive Summary", content="Summary content"))
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# Task Analysis Report"))
            self.assertIn("## Executive Summary", text)
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_complete_task_quality_gate(self):
        td = self._make_tmp_dir()
        try:
            report_path = td / "report.md"
            report_path.write_text(
                "# Title\n\n"
                "## Executive Summary\n\nok https://example.com\n\n"
                "## Policy Drivers and Constraints\n\nok\n\n"
                "## City and Industry Comparison\n\nok\n\n"
                "## Investment Opportunities and Risks\n\nok\n",
                encoding="utf-8",
            )
            findings_path = td / "findings.jsonl"
            rows = []
            for i in range(5):
                rows.append(
                    {
                        "city": "Shenzhen",
                        "industry": "AI",
                        "finding": f"f{i}",
                        "evidence": "e",
                        "source_url": "https://example.com",
                        "dedup_key": f"k{i}",
                    }
                )
            findings_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

            tool = CompleteTaskTool()
            ok = asyncio.run(
                tool(
                    executive_summary="done",
                    report_path=str(report_path),
                    confidence="medium",
                    findings_path=str(findings_path),
                    required_sections=[
                        "Executive Summary",
                        "Policy Drivers and Constraints",
                        "City and Industry Comparison",
                        "Investment Opportunities and Risks",
                    ],
                    min_findings=5,
                )
            )
            self.assertTrue(ok["quality_gate_passed"])
            self.assertTrue(ok["done"])

            fail = asyncio.run(
                tool(
                    executive_summary="",
                    report_path=str(report_path),
                    confidence="bad",
                    findings_path=str(findings_path),
                    required_sections=["Non Existing Section"],
                    min_findings=10,
                )
            )
            self.assertFalse(fail["quality_gate_passed"])
            self.assertFalse(fail["done"])
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_complete_task_research_step_skips_report_gate(self):
        tool = CompleteTaskTool()

        result = asyncio.run(
            tool(
                executive_summary="current research step finished",
                confidence="medium",
                status="done",
                report_path="missing.md",
                findings_path="missing.jsonl",
                required_sections=["Only This Step"],
                min_findings=99,
                orchestration={"research_step_mode": True},
            )
        )

        self.assertTrue(result["quality_gate_passed"])
        self.assertTrue(result["step_gate_deferred"])

    def test_scoped_environment_blocks_disallowed_tools(self):
        env = DummyEnv()
        scoped = ScopedEnvironment(base_env=env, allowed_tools={"readsource"}, max_steps=5)

        ctx = scoped.get_task_context()
        self.assertIn("### read_source", ctx.action_space)
        self.assertNotIn("### web_search", ctx.action_space)

        asyncio.run(scoped.reset())
        obs, _, done, info = asyncio.run(scoped.step({"action": "web_search", "params": {}}))
        self.assertFalse(obs["success"])
        self.assertFalse(done)
        self.assertEqual(info["error"], "forbidden_tool")
        self.assertEqual(len(env.calls), 0)

    def test_main_agent_delegate_defaults(self):
        agent = MainOrchestratorAgent(sub_models=["m1"], meta={
            "default_worker_tools": ["read_source", "record_finding"],
        })
        params = agent._apply_delegate_defaults({"task_instruction": "Analyze policy constraints", "context": ""})
        self.assertEqual(params["model"], "m1")
        self.assertEqual(params["tools"], ["read_source", "record_finding"])

    def test_main_agent_cannot_expand_worker_tool_allowlist(self):
        agent = MainOrchestratorAgent(sub_models=["m1"], meta={
            "default_worker_tools": ["read_source"],
            "allowed_worker_tools": ["read_source", "read_sources"],
        })

        params = agent._apply_delegate_defaults({
            "task_instruction": "Audit existing evidence",
            "context": "",
            "tools": ["read_source", "web_search", "write_report_section"],
        })

        self.assertEqual(params["tools"], ["read_source"])


if __name__ == "__main__":
    unittest.main()
