from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path

from research.artifacts import ResearchArtifacts
from research.gates import ResearchGatekeeper
from research.schema import ResearchRequest
from research.steps import RESEARCH_STEPS


class TestResearchGatekeeper(unittest.TestCase):
    def _make_tmp_dir(self) -> Path:
        root = Path("workspace") / "test_tmp"
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"case_{uuid.uuid4().hex}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _setup_artifacts(self, td: Path) -> ResearchArtifacts:
        request = ResearchRequest(topic="Test Topic")
        return ResearchArtifacts.create(td, request)

    def test_gate_step_missing_section_fails(self):
        td = self._make_tmp_dir()
        try:
            artifacts = self._setup_artifacts(td)
            gate = ResearchGatekeeper(artifacts)

            # literature_search step requires "文献检索与证据表" section
            step = RESEARCH_STEPS[1]
            self.assertEqual(step.key, "literature_search")

            result = gate.check_step(step)
            self.assertFalse(result.passed)
            self.assertTrue(any("missing report section" in issue for issue in result.issues))
            self.assertIn("findings_count", result.stats)
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_gate_step_min_findings_fails(self):
        td = self._make_tmp_dir()
        try:
            artifacts = self._setup_artifacts(td)
            gate = ResearchGatekeeper(artifacts)

            # Write report section but not enough findings
            artifacts.report_md.write_text("## 文献检索与证据表\n\nok\n", encoding="utf-8")
            step = RESEARCH_STEPS[1]
            result = gate.check_step(step)

            self.assertFalse(result.passed)
            self.assertTrue(any("findings count" in issue for issue in result.issues))
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_gate_step_passes_with_content(self):
        td = self._make_tmp_dir()
        try:
            artifacts = self._setup_artifacts(td)
            gate = ResearchGatekeeper(artifacts)

            # Use knowledge_synthesis step (no min_papers requirement)
            step = RESEARCH_STEPS[3]
            self.assertEqual(step.key, "knowledge_synthesis")

            # Write report section and enough findings
            artifacts.report_md.write_text(f"## {step.expected_section}\n\nok https://example.com\n", encoding="utf-8")
            for i in range(10):
                artifacts.findings.write_text(
                    (artifacts.findings.read_text(encoding="utf-8") if artifacts.findings.exists() else "")
                    + json.dumps({"finding": f"f{i}", "source_url": "https://example.com"}) + "\n",
                    encoding="utf-8",
                )
            # synthesis_digest is now checked for knowledge_synthesis
            artifacts.synthesis_digest.write_text('{"synthesis": "test content"}', encoding="utf-8")
            result = gate.check_step(step)
            self.assertTrue(result.passed, f"Issues: {result.issues}")
            self.assertEqual(result.issues, [])
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_gate_final_missing_report_fails(self):
        td = self._make_tmp_dir()
        try:
            artifacts = self._setup_artifacts(td)
            gate = ResearchGatekeeper(artifacts)

            result = gate.check_final(min_findings=5, output_format="markdown")
            self.assertFalse(result.passed)
            self.assertTrue(any("canonical markdown report is missing" in issue for issue in result.issues))
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_gate_final_latex_missing_elements_fails(self):
        td = self._make_tmp_dir()
        try:
            artifacts = self._setup_artifacts(td)
            gate = ResearchGatekeeper(artifacts)

            # Write a minimal markdown report with required sections and source links
            sections = "\n\n".join(f"## {s}\n\nok https://example.com" for s in [
                "文献检索与证据表",
                "论文阅读笔记与结构化抽取",
                "知识综合与研究空白",
                "研究空白、未来方向与可检验问题",
                "观点辩论与优先级评估",
                "结构化论文大纲",
                "LaTeX文献综述正文",
                "多视角审稿意见",
            ])
            artifacts.report_md.write_text(f"# Report\n\n{sections}\n", encoding="utf-8")

            # Add enough findings and papers
            for i in range(5):
                artifacts.findings.write_text(
                    (artifacts.findings.read_text(encoding="utf-8") if artifacts.findings.exists() else "")
                    + json.dumps({"finding": f"f{i}"}) + "\n",
                    encoding="utf-8",
                )

            result = gate.check_final(min_findings=5, output_format="latex", min_papers=3)
            self.assertFalse(result.passed)
            # LaTeX file is missing
            self.assertTrue(any("LaTeX paper.tex was not generated" in issue for issue in result.issues))
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_gate_final_latex_passes(self):
        td = self._make_tmp_dir()
        try:
            artifacts = self._setup_artifacts(td)
            gate = ResearchGatekeeper(artifacts)

            sections = "\n\n".join(f"## {s}\n\nok https://example.com" for s in [
                "文献检索与证据表",
                "论文阅读笔记与结构化抽取",
                "知识综合与研究空白",
                "研究空白、未来方向与可检验问题",
                "观点辩论与优先级评估",
                "结构化论文大纲",
                "LaTeX文献综述正文",
                "多视角审稿意见",
            ])
            artifacts.report_md.write_text(f"# Report\n\n{sections}\n", encoding="utf-8")

            for i in range(5):
                artifacts.findings.write_text(
                    (artifacts.findings.read_text(encoding="utf-8") if artifacts.findings.exists() else "")
                    + json.dumps({"finding": f"f{i}"}) + "\n",
                    encoding="utf-8",
                )

            # Add papers to satisfy min_papers
            artifacts.papers.write_text(
                json.dumps({"title": "Demo Paper", "authors": ["Alice"], "year": "2024", "source_url": "https://example.com"}) + "\n",
                encoding="utf-8",
            )

            # Generate valid LaTeX and BibTeX
            artifacts.paper_tex.write_text(
                r"\documentclass{article}\n\begin{document}\n\begin{abstract}\nAbstract\n\end{abstract}\n\section{Intro}\n\cite{key} \url{https://example.com}\n\bibliographystyle{plain}\n\bibliography{references}\n\end{document}",
                encoding="utf-8",
            )
            artifacts.references_bib.write_text(
                "@article{key, title={Title}, author={Author}, year={2024}}\n",
                encoding="utf-8",
            )

            result = gate.check_final(min_findings=5, output_format="latex", min_papers=1)
            self.assertTrue(result.passed)
            self.assertEqual(result.issues, [])
        finally:
            shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
