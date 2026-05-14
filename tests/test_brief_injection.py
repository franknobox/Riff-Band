from __future__ import annotations

import unittest

from project.build_project import _default_worker_tools


class TestBriefInjection(unittest.TestCase):
    def test_default_worker_tools_are_general_purpose(self):
        tools = _default_worker_tools()
        self.assertIn("read_source", tools)
        self.assertIn("record_finding", tools)
        self.assertIn("write_report_section", tools)
        self.assertIn("verify_artifacts", tools)
        self.assertNotIn("read_brief", tools)


if __name__ == "__main__":
    unittest.main()
