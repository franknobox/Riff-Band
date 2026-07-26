from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from agents.main_agent import MainOrchestratorAgent
from orchestration_tools.delegate import DelegateTasksTool
from orchestration_tools.worker_process import SubAgentProcessManager


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

    def test_worker_process_replaces_undecodable_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worker = root / "fake_worker.py"
            worker.write_text(
                "\n".join(
                    [
                        "import json, sys",
                        "request_path, output_path = sys.argv[1], sys.argv[2]",
                        "sys.stdout.buffer.write(b'prefix-\\xff-\\xfe-suffix')",
                        "payload = {",
                        "  'done': True,",
                        "  'steps_taken': 1,",
                        "  'cost': 0.0,",
                        "  'finish_result': {'status': 'done', 'message': 'ok', 'completed': [], 'issues': [], 'result': 'ok'},",
                        "}",
                        "open(output_path, 'w', encoding='utf-8').write(json.dumps(payload))",
                    ]
                ),
                encoding="utf-8",
            )
            manager = SubAgentProcessManager(project_root=root)
            manager.worker_script = worker

            result = manager.run_task(
                session_id="s1",
                task_instruction="task",
                model="m1",
                context="",
                original_question="q",
                sources_dir=root,
                output_dir=root,
                max_subagent_steps=1,
                timeout_seconds=5,
            )

            self.assertTrue(result["done"])
            self.assertEqual(result["finish_result"]["status"], "done")
            self.assertIn("prefix-", result["worker_process"]["stdout"])


if __name__ == "__main__":
    unittest.main()
