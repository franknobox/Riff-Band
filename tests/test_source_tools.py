from __future__ import annotations

import asyncio
import json
import shutil
import unittest
import uuid
from pathlib import Path

from project.tools import ReadSourcesTool, SearchSourcesTool


class TestSourceTools(unittest.TestCase):
    def _make_tmp_sources(self) -> Path:
        root = Path("workspace") / "test_tmp"
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"sources_{uuid.uuid4().hex}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def test_search_sources_hits_relevant_files(self):
        src = self._make_tmp_sources()
        try:
            (src / "policy.txt").write_text("Shenzhen policy support for AI and semiconductors.", encoding="utf-8")
            (src / "finance.txt").write_text("Quarterly revenue and margin updates.", encoding="utf-8")
            tool = SearchSourcesTool(sources_dir=src)

            result = asyncio.run(tool(query="Shenzhen AI policy", top_k=3))
            self.assertTrue(result["success"])
            items = json.loads(result["output"])
            self.assertGreaterEqual(len(items), 1)
            self.assertEqual(items[0]["path"], "policy.txt")
        finally:
            shutil.rmtree(src, ignore_errors=True)

    def test_read_sources_batch(self):
        src = self._make_tmp_sources()
        try:
            (src / "a.md").write_text("alpha", encoding="utf-8")
            (src / "b.md").write_text("beta", encoding="utf-8")
            tool = ReadSourcesTool(sources_dir=src)
            result = asyncio.run(tool(paths=["a.md", "b.md", "missing.md"]))
            self.assertTrue(result["success"])
            items = json.loads(result["output"])
            self.assertEqual(len(items), 3)
            ok = [i for i in items if i["success"]]
            bad = [i for i in items if not i["success"]]
            self.assertEqual(len(ok), 2)
            self.assertEqual(len(bad), 1)
        finally:
            shutil.rmtree(src, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
