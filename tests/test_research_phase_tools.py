from __future__ import annotations

import asyncio
import json
import shutil
import unittest
from pathlib import Path

from project.tools import (
    BatchClaimDebateTool,
    BatchKnowledgeSynthesisTool,
    BatchPaperEnrichmentTool,
    BatchClaimGenerationTool,
    BuildResearchOutlineTool,
    LiteratureScreenTool,
    ReadClaimDebateLogTool,
    ReadPaperCardsTool,
    ReadPapersTool,
    ReadResearchClaimsTool,
    ReadResearchOutlineTool,
    ReadResearchReportTool,
    ReadSynthesisDigestTool,
    RecordClaimDebateTool,
    RecordPaperTool,
    RecordResearchClaimTool,
    ReviewResearchReportTool,
    SynthesizeFindingsTool,
)


class TestResearchPhaseTools(unittest.TestCase):
    def setUp(self):
        self.root = Path("workspace") / "test_research_phase_tools"
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_paper_record_and_read(self):
        papers = self.root / "papers.jsonl"
        record = RecordPaperTool(papers_path=papers)
        read = ReadPapersTool(papers_path=papers)

        result = asyncio.run(
            record(
                title="Evidence Paper",
                authors=["Ada"],
                year="2024",
                source_url="https://example.org/paper",
                relevance="core source",
            )
        )
        self.assertTrue(result["success"])

        output = asyncio.run(read(query="Evidence"))
        rows = json.loads(output["output"])["papers"]
        self.assertEqual(rows[0]["title"], "Evidence Paper")

        fallback_output = asyncio.run(read(query="NoExactPhrase", limit=1))
        fallback_payload = json.loads(fallback_output["output"])
        self.assertEqual(fallback_payload["total_count"], 1)
        self.assertTrue(fallback_payload["fallback_used"])
        self.assertEqual(fallback_payload["papers"][0]["title"], "Evidence Paper")

    def test_batch_paper_enrichment_writes_top_relevant_notes(self):
        papers = self.root / "papers.jsonl"
        notes = self.root / "paper_notes.jsonl"
        cards = self.root / "paper_cards.jsonl"
        papers.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "title": "RIS Assisted Integrated Sensing and Communication",
                            "year": "2024",
                            "source_url": "https://example.org/ris-isac",
                            "abstract": "This paper proposes a beamforming optimization framework for reconfigurable intelligent surface assisted integrated sensing and communication systems. The method studies sensing and communication tradeoffs.",
                            "relevance": "query=RIS ISAC",
                        }
                    ),
                    json.dumps(
                        {
                            "title": "Generic Wireless Paper",
                            "year": "2018",
                            "source_url": "https://example.org/wireless",
                            "abstract": "This paper studies a generic wireless communication system.",
                            "relevance": "query=wireless",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        result = asyncio.run(
            BatchPaperEnrichmentTool(papers_path=papers, paper_notes_path=notes, paper_cards_path=cards)(
                topic="RIS-assisted ISAC",
                priority_terms=["reconfigurable intelligent surface", "integrated sensing and communication"],
                limit=1,
            )
        )
        self.assertTrue(result["success"])
        rows = [json.loads(line) for line in notes.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertIn("RIS Assisted", rows[0]["title"])
        self.assertEqual(rows[0]["evidence_source"], "abstract")
        card_rows = [json.loads(line) for line in cards.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(card_rows), 1)
        self.assertIn("key_result", card_rows[0])
        read_cards = asyncio.run(ReadPaperCardsTool(paper_cards_path=cards)(query="NoExactPhrase", limit=1))
        read_payload = json.loads(read_cards["output"])
        self.assertTrue(read_payload["fallback_used"])
        self.assertEqual(read_payload["count"], 1)

    def test_literature_screen_selects_candidates(self):
        candidates = self.root / "candidates.jsonl"
        shortlist = self.root / "shortlist.jsonl"
        papers = self.root / "papers.jsonl"
        candidates.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "title": "RIS ISAC Candidate",
                            "year": "2024",
                            "source_url": "https://example.org/ris-isac",
                            "abstract": "Reconfigurable intelligent surface integrated sensing and communication beamforming.",
                            "doi": "10.1/ris",
                            "candidate_backend": "openalex",
                        }
                    ),
                    json.dumps(
                        {
                            "title": "Unrelated Candidate",
                            "year": "2020",
                            "source_url": "https://example.org/other",
                            "abstract": "A generic unrelated paper.",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        result = asyncio.run(
            LiteratureScreenTool(
                candidates_path=candidates,
                shortlist_path=shortlist,
                papers_path=papers,
            )(
                topic="RIS ISAC",
                priority_terms=["reconfigurable intelligent surface", "integrated sensing and communication"],
                target_papers=1,
            )
        )

        self.assertTrue(result["success"])
        selected = [json.loads(line) for line in papers.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["title"], "RIS ISAC Candidate")
        self.assertEqual(selected[0]["screening_decision"], "include")

    def test_batch_claim_generation_writes_multiple_claims(self):
        notes = self.root / "paper_notes.jsonl"
        findings = self.root / "findings.jsonl"
        claims = self.root / "claims.jsonl"
        notes.write_text(
            json.dumps(
                {
                    "title": "RIS ISAC Paper",
                    "main_findings": "RIS-assisted ISAC studies optimize beamforming and sensing tradeoffs.",
                    "source_url": "https://example.org/ris-isac",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        findings.write_text(
            json.dumps(
                {
                    "finding": "RIS can support ISAC scenarios.",
                    "source_url": "https://example.org/ris-isac",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        result = asyncio.run(
            BatchClaimGenerationTool(
                paper_notes_path=notes,
                findings_path=findings,
                claims_path=claims,
                report_path=self.root / "research_report.md",
            )(topic="RIS ISAC", target_claims=4)
        )
        self.assertTrue(result["success"])
        rows = [json.loads(line) for line in claims.read_text(encoding="utf-8").splitlines()]
        self.assertGreaterEqual(len(rows), 4)
        self.assertTrue(all(row["source_urls"] for row in rows))
        report_text = (self.root / "research_report.md").read_text(encoding="utf-8")
        self.assertIn("## 研究空白、未来方向与可检验问题", report_text)

        fallback = asyncio.run(ReadResearchClaimsTool(claims_path=claims)(query="NoExactClaimPhrase", limit=2))
        fallback_payload = json.loads(fallback["output"])
        self.assertEqual(fallback_payload["total_count"], len(rows))
        self.assertTrue(fallback_payload["fallback_used"])
        self.assertEqual(fallback_payload["count"], 2)

    def test_batch_knowledge_synthesis_writes_digest_and_cross_paper_findings(self):
        cards = self.root / "paper_cards.jsonl"
        notes = self.root / "paper_notes.jsonl"
        findings = self.root / "findings.jsonl"
        digest = self.root / "synthesis_digest.json"
        report = self.root / "research_report.md"
        cards.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "title": "RIS ISAC Beamforming",
                            "source_url": "https://example.org/beamforming",
                            "method": "beamforming optimization",
                            "key_result": "Jointly studies sensing and communication tradeoffs.",
                            "limitations": "Abstract-level evidence only.",
                            "evidence_level": "abstract",
                            "screening_score": 20,
                        }
                    ),
                    json.dumps(
                        {
                            "title": "RIS ISAC Channel Estimation",
                            "source_url": "https://example.org/channel",
                            "method": "CSI and channel estimation",
                            "key_result": "Studies sensing accuracy and CSI overhead.",
                            "limitations": "Deployment assumptions remain unclear.",
                            "evidence_level": "abstract",
                            "screening_score": 18,
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        result = asyncio.run(
            BatchKnowledgeSynthesisTool(
                paper_cards_path=cards,
                paper_notes_path=notes,
                findings_path=findings,
                synthesis_digest_path=digest,
                report_path=report,
            )(topic="RIS ISAC")
        )
        self.assertTrue(result["success"])
        payload = json.loads(digest.read_text(encoding="utf-8"))
        self.assertGreaterEqual(payload["cluster_count"], 1)
        self.assertTrue(payload["research_gaps"])
        finding_rows = [json.loads(line) for line in findings.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(any("cross_paper_synthesis" in row.get("tags", []) for row in finding_rows))
        read_digest = asyncio.run(ReadSynthesisDigestTool(synthesis_digest_path=digest)())
        self.assertIn("research_gaps", json.loads(read_digest["output"])["content"])

    def test_synthesis_claim_debate_outline_and_review_artifacts(self):
        scratchpad = self.root / "scratchpad" / "shared.md"
        claims = self.root / "claims.jsonl"
        debate = self.root / "debate_log.md"
        outline = self.root / "outline.md"
        report = self.root / "research_report.md"
        findings = self.root / "findings.jsonl"
        review = self.root / "review_report.md"

        asyncio.run(
            SynthesizeFindingsTool(scratchpad_path=scratchpad)(
                themes=["Theme A"],
                consensus=["Agreement"],
                disagreements=["Dispute"],
                gaps=["Gap"],
            )
        )
        self.assertIn("Theme A", scratchpad.read_text(encoding="utf-8"))

        asyncio.run(
            RecordResearchClaimTool(claims_path=claims)(
                claim="Claim A",
                claim_type="gap",
                evidence_basis="Finding A",
                source_urls=["https://example.org/source"],
                priority="high",
            )
        )
        read_claims = asyncio.run(ReadResearchClaimsTool(claims_path=claims)(query="Claim A"))
        self.assertEqual(json.loads(read_claims["output"])["count"], 1)

        asyncio.run(
            RecordClaimDebateTool(debate_log_path=debate)(
                claim="Claim A",
                decision="keep",
                rationale="Well supported",
                priority="high",
            )
        )
        self.assertIn("Decision: keep", debate.read_text(encoding="utf-8"))
        read_debate = asyncio.run(ReadClaimDebateLogTool(debate_log_path=debate)())
        self.assertIn("Claim A", json.loads(read_debate["output"])["content"])

        batch_debate = asyncio.run(
            BatchClaimDebateTool(
                claims_path=claims,
                findings_path=findings,
                debate_log_path=debate,
                report_path=report,
            )(limit=4)
        )
        self.assertTrue(batch_debate["success"])
        self.assertIn("Decision:", debate.read_text(encoding="utf-8"))
        self.assertIn("## 观点辩论与优先级评估", report.read_text(encoding="utf-8"))

        asyncio.run(
            BuildResearchOutlineTool(outline_path=outline)(
                title="Outline",
                sections=["Background", "Synthesis"],
                claim_evidence_map=["Claim A -> https://example.org/source"],
            )
        )
        self.assertIn("Claim-Evidence Map", outline.read_text(encoding="utf-8"))
        read_outline = asyncio.run(ReadResearchOutlineTool(outline_path=outline)())
        self.assertIn("Claim-Evidence Map", json.loads(read_outline["output"])["content"])

        report.write_text("# Report\n\n## Evidence\n\nClaim https://example.org/source\n", encoding="utf-8")
        read_report = asyncio.run(ReadResearchReportTool(report_path=report)())
        self.assertIn("## Evidence", json.loads(read_report["output"])["content"])
        findings.write_text(json.dumps({"finding": "Claim", "source_url": "https://example.org/source"}) + "\n", encoding="utf-8")
        review_result = asyncio.run(
            ReviewResearchReportTool(
                report_path=report,
                findings_path=findings,
                claims_path=claims,
                review_path=review,
            )(required_sections=["Evidence"], recommendation="accept")
        )
        self.assertTrue(review_result["success"])
        self.assertIn("Recommendation: accept", review.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
