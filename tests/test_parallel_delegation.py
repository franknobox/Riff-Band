from __future__ import annotations

import asyncio
import unittest

from agents.main_agent import MainOrchestratorAgent
from orchestration_tools.delegate import DelegateTasksTool


class TestParallelDelegation(unittest.TestCase):
    def test_main_agent_applies_parallel_defaults(self):
        agent = MainOrchestratorAgent(
            sub_models=["m1"],
            meta={
                "max_parallel_subtasks": 3,
                "default_worker_tools": [
                    "search_sources",
                    "read_sources",
                    "record_finding",
                    "write_report_section",
                    "verify_artifacts",
                ],
                "parallel_forbidden_tools": ["write_report_section"],
            },
        )
        params = agent._apply_delegate_tasks_defaults(
            {
                "tasks": [
                    {"task_instruction": "collect market data"},
                    {"task_instruction": "collect policy signals", "tools": ["search_sources", "write_report_section"]},
                ]
            }
        )
        self.assertEqual(params["max_concurrency"], 3)
        self.assertEqual(params["tasks"][0]["model"], "m1")
        self.assertIn("verify_artifacts", params["tasks"][0]["tools"])
        self.assertNotIn("write_report_section", params["tasks"][0]["tools"])
        self.assertNotIn("write_report_section", params["tasks"][1]["tools"])

    def test_delegate_tasks_rejects_parallel_write_report(self):
        tool = DelegateTasksTool(env=None, models=["m1"], subagent_factory=None)
        result = asyncio.run(
            tool(
                tasks=[
                    {
                        "task_instruction": "parallel drafting",
                        "model": "m1",
                        "tools": ["write_report_section"],
                    }
                ],
                max_concurrency=3,
            )
        )
        self.assertFalse(result["success"])
        self.assertIn("forbidden tool write_report_section", result["message"])


if __name__ == "__main__":
    unittest.main()
