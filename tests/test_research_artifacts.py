from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from research.artifacts import (
    ResearchArtifacts,
    append_jsonl,
    ensure_text_artifact,
    export_bibtex,
    export_html,
    export_latex,
    read_jsonl,
)
from research.schema import ResearchRequest


class TestResearchArtifacts(unittest.TestCase):
    def _make_tmp_dir(self) -> Path:
        root = Path("workspace") / "test_tmp"
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"case_{uuid.uuid4().hex}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def test_artifacts_create_directory_structure(self):
        td = self._make_tmp_dir()
        try:
            request = ResearchRequest(topic="Test Topic")
            artifacts = ResearchArtifacts.create(td, request)
            self.assertTrue(artifacts.run_dir.exists())
            self.assertTrue(artifacts.scratchpad.parent.exists())
            self.assertTrue(artifacts.report_md.name.endswith("research_report.md"))
            self.assertTrue(artifacts.paper_tex.name.endswith("_paper.tex"))
            self.assertTrue(artifacts.references_bib.name.endswith("_references.bib"))
            self.assertTrue(artifacts.report_html.name.endswith("_report.html"))
            self.assertTrue(artifacts.paper_tex.parent.name == "output")
            self.assertTrue(artifacts.report_md.parent.name.startswith("202"))
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_artifacts_create_paths_are_unique_within_same_second(self):
        td = self._make_tmp_dir()
        try:
            class FixedDateTime:
                @classmethod
                def now(cls):
                    return cls()

                def strftime(self, fmt: str) -> str:
                    return "20260515_120000"

            request = ResearchRequest(topic="Same Topic")
            with patch("research.artifacts.datetime", FixedDateTime):
                first = ResearchArtifacts.create(td, request)
                second = ResearchArtifacts.create(td, request)

            self.assertNotEqual(first.run_dir, second.run_dir)
            self.assertNotEqual(first.paper_tex, second.paper_tex)
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_artifacts_to_artifacts_by_format(self):
        td = self._make_tmp_dir()
        try:
            request = ResearchRequest(topic="Test Topic")
            artifacts = ResearchArtifacts.create(td, request)

            md_items = artifacts.to_artifacts("markdown")
            types_md = {item.type for item in md_items}
            self.assertIn("report", types_md)
            self.assertNotIn("latex", types_md)
            self.assertNotIn("html", types_md)

            latex_items = artifacts.to_artifacts("latex")
            types_latex = {item.type for item in latex_items}
            self.assertIn("latex", types_latex)
            self.assertIn("bibtex", types_latex)

            html_items = artifacts.to_artifacts("html")
            types_html = {item.type for item in html_items}
            self.assertIn("html", types_html)
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_export_latex_generates_tex_and_bib(self):
        td = self._make_tmp_dir()
        try:
            report_md = td / "report.md"
            report_md.write_text("# Title\n\n## Section\n\nContent with https://example.com.\n", encoding="utf-8")
            tex_path = td / "out.tex"
            bib_path = td / "refs.bib"
            papers = [
                {"title": "Demo Paper", "authors": ["Alice Smith"], "year": "2024", "venue": "Demo Conf", "source_url": "https://example.com"},
            ]

            export_latex(report_md, tex_path, "Test Title", papers_path=None, bib_path=bib_path)

            self.assertTrue(tex_path.exists())
            tex_text = tex_path.read_text(encoding="utf-8")
            self.assertIn(r"\documentclass{article}", tex_text)
            self.assertIn(r"\begin{abstract}", tex_text)
            self.assertIn(r"\section{Section}", tex_text)

            # bib_path not passed, so no bibliography line when no url_to_key mapping
            # Re-run with bib_path and papers to get citations
            export_latex(report_md, tex_path, "Test Title", papers_path=None, bib_path=bib_path)
            # Since papers_path is None, bib entries won't be generated via export_bibtex
            # Let's test export_bibtex directly
            url_to_key = export_bibtex(papers, bib_path)
            self.assertTrue(bib_path.exists())
            bib_text = bib_path.read_text(encoding="utf-8")
            self.assertIn("@article{", bib_text)
            self.assertIn("Demo Paper", bib_text)
            self.assertEqual(url_to_key.get("https://example.com"), "Smith2024DemoPaper")
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_export_html_generates_html(self):
        td = self._make_tmp_dir()
        try:
            report_md = td / "report.md"
            report_md.write_text("# Title\n\n## Section\n\nSome paragraph.\n\n- bullet item\n", encoding="utf-8")
            html_path = td / "out.html"

            export_html(report_md, html_path, "Test Title")

            self.assertTrue(html_path.exists())
            html_text = html_path.read_text(encoding="utf-8")
            self.assertIn("<!doctype html>", html_text)
            self.assertIn("<h1>Title</h1>", html_text)
            self.assertIn("<h2>Section</h2>", html_text)
            self.assertIn("<p>Some paragraph.</p>", html_text)
            self.assertIn('class="bullet"', html_text)
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_append_and_read_jsonl(self):
        td = self._make_tmp_dir()
        try:
            path = td / "data.jsonl"
            append_jsonl(path, {"key": "a"})
            append_jsonl(path, {"key": "b"})
            rows = read_jsonl(path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["key"], "a")
            self.assertEqual(rows[1]["key"], "b")

            # read non-existent returns empty
            self.assertEqual(read_jsonl(td / "nonexistent.jsonl"), [])
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_ensure_text_artifact_idempotent(self):
        td = self._make_tmp_dir()
        try:
            path = td / "note.md"
            ensure_text_artifact(path, "Title", "body content")
            self.assertEqual(path.read_text(encoding="utf-8"), "# Title\n\nbody content\n")

            # second call should not overwrite existing content
            ensure_text_artifact(path, "Other", "other body")
            self.assertEqual(path.read_text(encoding="utf-8"), "# Title\n\nbody content\n")
        finally:
            shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
