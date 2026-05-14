from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from research.artifacts import ResearchArtifacts, read_jsonl
from research.steps import ResearchStep, required_report_sections


@dataclass(frozen=True)
class GateResult:
    passed: bool
    issues: list[str] = field(default_factory=list)
    stats: dict[str, int | bool | str] = field(default_factory=dict)


class ResearchGatekeeper:
    """Programmatic quality gates for research-mode steps and final output."""

    def __init__(self, artifacts: ResearchArtifacts):
        self.artifacts = artifacts

    def check_step(self, step: ResearchStep) -> GateResult:
        issues: list[str] = []
        report_text = self._read_text(self.artifacts.report_md)
        scratchpad_text = self._read_text(self.artifacts.scratchpad)
        findings_count = len(read_jsonl(self.artifacts.findings))
        papers_count = len(read_jsonl(self.artifacts.papers))
        paper_notes_count = len(read_jsonl(self.artifacts.paper_notes))
        paper_cards_count = len(read_jsonl(self.artifacts.paper_cards))
        synthesis_digest_chars = len(self._read_text(self.artifacts.synthesis_digest))

        if not report_text and not scratchpad_text:
            issues.append("step produced neither report content nor scratchpad notes")
        if step.report_required:
            if step.expected_section and f"## {step.expected_section}" not in report_text:
                issues.append(f"missing report section: {step.expected_section}")
        elif step.expected_section and f"## {step.expected_section}" not in scratchpad_text:
            issues.append(f"missing scratchpad plan section: {step.expected_section}")
        if step.min_findings and findings_count < step.min_findings:
            issues.append(f"findings count {findings_count} < step minimum {step.min_findings}")
        if getattr(step, "min_papers", 0) and papers_count < step.min_papers:
            issues.append(f"papers count {papers_count} < step minimum {step.min_papers}")
        if step.key == "paper_enrichment":
            if papers_count and paper_notes_count == 0:
                issues.append("paper_enrichment produced no paper_notes.jsonl records")
            if papers_count and paper_cards_count == 0:
                issues.append("paper_enrichment produced no paper_cards.jsonl records")
            elif step.min_papers and paper_notes_count < min(step.min_papers, papers_count):
                issues.append(
                    f"paper_notes count {paper_notes_count} < expected enrichment minimum {min(step.min_papers, papers_count)}"
                )
        if step.key == "knowledge_synthesis" and synthesis_digest_chars == 0:
            issues.append("knowledge_synthesis produced no synthesis_digest.json content")

        return GateResult(
            passed=not issues,
            issues=issues,
            stats={
                "report_exists": self.artifacts.report_md.exists(),
                "scratchpad_exists": self.artifacts.scratchpad.exists(),
                "findings_count": findings_count,
                "papers_count": papers_count,
                "paper_notes_count": paper_notes_count,
                "paper_cards_count": paper_cards_count,
                "synthesis_digest_chars": synthesis_digest_chars,
                "report_chars": len(report_text),
                "scratchpad_chars": len(scratchpad_text),
            },
        )

    def check_final(self, min_findings: int, output_format: str, min_papers: int = 0) -> GateResult:
        issues: list[str] = []
        report_text = self._read_text(self.artifacts.report_md)
        tex_text = self._read_text(self.artifacts.paper_tex)
        bib_text = self._read_text(self.artifacts.references_bib)
        findings = read_jsonl(self.artifacts.findings)
        papers = read_jsonl(self.artifacts.papers)

        if not report_text.strip():
            issues.append("canonical markdown report is missing or empty")
        else:
            missing = [
                section
                for section in required_report_sections()
                if f"## {section}" not in report_text
            ]
            if missing:
                issues.append(f"missing required research sections: {missing}")
            if not re.search(r"https?://", report_text):
                issues.append("report does not include explicit source links")

        if len(findings) < min_findings:
            issues.append(f"findings count {len(findings)} < min_findings {min_findings}")
        if len(papers) < min_papers:
            issues.append(f"papers count {len(papers)} < min_papers {min_papers}")

        if output_format == "latex":
            if not tex_text.strip():
                issues.append("LaTeX paper.tex was not generated or is empty")
            else:
                required_latex = [
                    r"\begin{abstract}",
                    r"\section",
                    r"\bibliography{references}",
                ]
                missing_latex = [item for item in required_latex if item not in tex_text]
                if missing_latex:
                    issues.append(f"LaTeX draft is missing required elements: {missing_latex}")
                if not re.search(r"\\cite\{[^}]+\}|\\url\{https?://", tex_text):
                    issues.append("LaTeX draft does not include citations or source URLs")
            if not bib_text.strip():
                issues.append("references.bib was not generated or is empty")
            elif bib_text.count("@") < min_papers:
                issues.append(f"references.bib has {bib_text.count('@')} entries; minimum is {min_papers}")
        if output_format == "html" and not self.artifacts.report_html.exists():
            issues.append("HTML export was not generated")

        return GateResult(
            passed=not issues,
            issues=issues,
            stats={
                "findings_count": len(findings),
                "papers_count": len(papers),
                "report_chars": len(report_text),
                "tex_chars": len(tex_text),
                "bib_entries": bib_text.count("@"),
                "output_format": output_format,
            },
        )

    @staticmethod
    def _read_text(path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")
