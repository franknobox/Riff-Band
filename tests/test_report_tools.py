from __future__ import annotations

import asyncio
import shutil
import unittest
from pathlib import Path

from project.tools.report_tools import WriteReportSectionTool


class TestReportTools(unittest.TestCase):
    def setUp(self):
        self.root = Path("workspace") / "test_report_tools"
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_write_report_section_strips_duplicate_heading(self):
        report = self.root / "report.md"
        tool = WriteReportSectionTool(report_path=report)

        asyncio.run(
            tool(
                section_title="知识综合与研究空白",
                content="## 知识综合与研究空白\n\n正文内容",
            )
        )

        text = report.read_text(encoding="utf-8")
        self.assertEqual(text.count("## 知识综合与研究空白"), 1)
        self.assertIn("正文内容", text)


if __name__ == "__main__":
    unittest.main()
