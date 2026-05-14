from __future__ import annotations

import unittest
from pathlib import Path

from config import AgentConfig
from agents.main_agent import MainAgent
from research import pipeline as pipeline_module
from research.artifacts import append_jsonl, export_latex
from research import ResearchRequest, run_research
from research.prompts import ResearchMainPromptBuilder, ResearchSubPromptBuilder
from research.steps import RESEARCH_STEPS


class _FakeProject:
    def __init__(self, main_prompt_builder=None, sub_prompt_builder=None):
        self.main_prompt_builder = main_prompt_builder
        self.sub_prompt_builder = sub_prompt_builder

    async def stream(self):
        if False:
            yield None


class TestResearchMode(unittest.IsolatedAsyncioTestCase):
    def test_request_requires_topic(self):
        with self.assertRaises(ValueError):
            ResearchRequest(topic="")

    async def test_run_research_returns_pipeline_scaffold_without_llm_config(self):
        cfg = AgentConfig(
            main_model="test-model",
            sub_models=["test-model"],
            sources_dir=Path("workspace/sources"),
            workspace_dir=Path("workspace"),
        )
        request = ResearchRequest(topic="Zimbabwe economic history", trigger="cli")

        result = await run_research(request, cfg)

        self.assertEqual(result.status, "partial")
        self.assertIn("partial artifacts", result.summary)
        self.assertEqual(result.metadata["topic"], request.topic)
        self.assertEqual(result.metadata["trigger"], "cli")
        self.assertEqual(len(result.steps), 9)
        self.assertEqual(result.metadata["output_format"], "latex")
        self.assertTrue(result.report_path.endswith("paper.tex"))
        self.assertTrue(any(item.type == "bibtex" for item in result.artifacts))
        self.assertTrue(result.metadata["manifest_path"])
        self.assertFalse(result.metadata["agent_execution"])

    async def test_research_pipeline_uses_research_prompt_builders(self):
        from research import pipeline as pipeline_module

        captured = {}

        def fake_has_llm_config(self):
            return True

        def fake_build_agent_project(**kwargs):
            captured["multi_main"] = kwargs.get("main_prompt_builder")
            captured["multi_sub"] = kwargs.get("sub_prompt_builder")
            captured.setdefault("multi_required_sections", []).append(kwargs.get("required_sections"))
            captured.setdefault("multi_runtime_metadata", []).append(kwargs.get("runtime_metadata"))
            return _FakeProject()

        def fake_build_single_agent_project(**kwargs):
            captured["single_sub"] = kwargs.get("sub_prompt_builder")
            captured.setdefault("single_required_sections", []).append(kwargs.get("required_sections"))
            captured.setdefault("single_runtime_metadata", []).append(kwargs.get("runtime_metadata"))
            return _FakeProject()

        old_has_llm_config = pipeline_module.ResearchPipeline._has_llm_config
        old_build_agent_project = pipeline_module.build_agent_project
        old_build_single_agent_project = pipeline_module.build_single_agent_project
        try:
            pipeline_module.ResearchPipeline._has_llm_config = fake_has_llm_config
            pipeline_module.build_agent_project = fake_build_agent_project
            pipeline_module.build_single_agent_project = fake_build_single_agent_project

            cfg = AgentConfig(
                main_model="test-model",
                sub_models=["test-model"],
                sources_dir=Path("workspace/sources"),
                workspace_dir=Path("workspace"),
            )
            result = await run_research(ResearchRequest(topic="review task", trigger="cli"), cfg)
        finally:
            pipeline_module.ResearchPipeline._has_llm_config = old_has_llm_config
            pipeline_module.build_agent_project = old_build_agent_project
            pipeline_module.build_single_agent_project = old_build_single_agent_project

        self.assertEqual(result.metadata["agent_execution"], True)
        self.assertIs(captured["multi_main"], ResearchMainPromptBuilder)
        self.assertIs(captured["multi_sub"], ResearchSubPromptBuilder)
        self.assertIs(captured["single_sub"], ResearchSubPromptBuilder)
        self.assertEqual(captured["single_required_sections"][0], [])
        for sections in captured["multi_required_sections"] + captured["single_required_sections"][1:]:
            self.assertEqual(len(sections), 1)
        for metadata in captured["multi_runtime_metadata"] + captured["single_runtime_metadata"]:
            self.assertEqual(metadata["research_completion_scope"], "current_step_only")
            if metadata["current_step_requires_report_section"]:
                self.assertIn(metadata["current_step_expected_section"], metadata["all_required_sections"])
            else:
                self.assertNotIn(metadata["current_step_expected_section"], metadata["all_required_sections"])
            self.assertFalse(metadata["require_flow_integrity"])
            self.assertFalse(metadata["require_verification_passed"])
            self.assertIn("material_digest", metadata)
            self.assertIn("material_ready", metadata)

    def test_material_readiness_blocks_downstream_steps_without_upstream_artifacts(self):
        cfg = AgentConfig(
            main_model="test-model",
            sub_models=["test-model"],
            sources_dir=Path("workspace/sources"),
            workspace_dir=Path("workspace"),
        )
        pipeline = pipeline_module.ResearchPipeline(ResearchRequest(topic="RIS ISAC", trigger="cli"), cfg)
        steps = {step.key: step for step in RESEARCH_STEPS}

        debate_readiness = pipeline._assess_material_readiness(steps["claim_debate"])
        self.assertTrue(debate_readiness.blocking)
        self.assertIn("claims.jsonl is empty", " ".join(debate_readiness.issues))

        append_jsonl(
            pipeline.artifacts.findings,
            {"finding": "RIS supports ISAC sensing", "source_url": "https://example.org"},
        )
        append_jsonl(
            pipeline.artifacts.claims,
            {"claim": "RIS can improve ISAC coverage", "source_urls": ["https://example.org"]},
        )

        debate_readiness = pipeline._assess_material_readiness(steps["claim_debate"])
        self.assertFalse(debate_readiness.blocking)

        draft_readiness = pipeline._assess_material_readiness(steps["section_draft"])
        self.assertTrue(draft_readiness.blocking)
        self.assertIn("outline.md", " ".join(draft_readiness.issues))

    def test_latex_export_creates_tex_and_bib_with_citations(self):
        root = Path("workspace") / "test_latex_export"
        root.mkdir(parents=True, exist_ok=True)
        markdown = root / "research_report.md"
        papers = root / "papers.jsonl"
        tex = root / "paper.tex"
        bib = root / "references.bib"
        markdown.write_text(
            "# Report\n\n## Literature Synthesis\n\nClaim https://example.org/paper\n",
            encoding="utf-8",
        )
        append_jsonl(
            papers,
            {
                "title": "A Relevant Paper",
                "authors": ["Ada Lovelace"],
                "year": "2024",
                "venue": "Journal",
                "source_url": "https://example.org/paper",
            },
        )

        export_latex(markdown, tex, "Topic", papers_path=papers, bib_path=bib)

        self.assertIn("\\cite{", tex.read_text(encoding="utf-8"))
        self.assertIn("\\bibliography{references}", tex.read_text(encoding="utf-8"))
        self.assertIn("@article", bib.read_text(encoding="utf-8"))

    def test_research_step_mode_does_not_use_report_phase_machine(self):
        agent = MainAgent()
        agent.meta = {
            "profile_name": "research_mode",
            "research_completion_scope": "current_step_only",
        }

        self.assertEqual(agent._current_phase(), "research_step")
        self.assertEqual(agent._next_required_intent(), "execute_current_step")
        self.assertIn("delegate_task", agent._allowed_actions_for_phase())
        self.assertNotIn("complete_task", agent._allowed_actions_for_phase())

        agent.task_entries = [
            {
                "profile": "general_research",
                "status": "done",
                "worker_state": "done",
                "session_id": "s1",
            }
        ]
        self.assertEqual(agent._next_required_intent(), "complete_current_step")
        self.assertIn("complete_task", agent._allowed_actions_for_phase())
        self.assertEqual(agent._blocked_by_phase("complete_task", {}), "")

        orchestration = agent._quality_gate_orchestration()
        self.assertFalse(orchestration["require_flow_integrity"])
        self.assertFalse(orchestration["require_verification_passed"])

    def test_research_step_mode_blocks_complete_until_min_findings(self):
        agent = MainAgent()
        agent.meta = {
            "profile_name": "research_mode",
            "research_completion_scope": "current_step_only",
            "min_findings": 2,
        }
        agent.task_entries = [
            {
                "profile": "general_research",
                "status": "done",
                "worker_state": "done",
                "session_id": "s1",
            }
        ]

        blocked = agent._blocked_by_phase("complete_task", {})

        self.assertIn("below min_findings", blocked)

    def test_report_mode_keeps_original_phase_machine(self):
        agent = MainAgent()
        agent.meta = {"profile_name": "generic"}

        self.assertEqual(agent._current_phase(), "research")
        self.assertEqual(agent._next_required_intent(), "finish_research")
        self.assertIn("delegate_tasks", agent._allowed_actions_for_phase())

    def test_literature_search_starts_single_batch_search_plan(self):
        agent = MainAgent()
        agent.instruction = "[研究主题]\n研究智能反射面在通信感知一体化系统中的赋能\n"
        agent.sub_models = ["worker-model"]
        agent.meta = {
            "profile_name": "research_mode",
            "research_completion_scope": "current_step_only",
            "research_step_key": "literature_search",
            "step_min_papers": 30,
            "min_findings": 8,
            "max_parallel_subtasks": 4,
        }

        self.assertTrue(agent._should_start_literature_parallel_search())
        params = agent._literature_search_task_params()

        self.assertIn("batch_literature_search", params["tools"])
        self.assertIn("read_papers", params["tools"])
        self.assertNotIn("semantic_scholar_search", params["tools"])
        self.assertIn("立即记录", params["task_instruction"])
        self.assertIn('"reconfigurable intelligent surface"', params["context"])

    def test_literature_search_uses_step1_scratchpad_terms_when_available(self):
        root = Path("workspace") / "test_search_plan"
        scratchpad = root / "scratchpad" / "shared.md"
        scratchpad.parent.mkdir(parents=True, exist_ok=True)
        scratchpad.write_text(
            "\n".join(
                [
                    "## 研究问题拆解",
                    "中文关键词: 通信感知一体化, 智能反射面",
                    "英文关键词: integrated sensing and communication, reconfigurable intelligent surface",
                    "检索式:",
                    "- RIS ISAC beamforming",
                    "- RIS assisted vehicular sensing",
                    "- Intelligent Reflecting Surface in Integrated Sensing and Communication",
                ]
            ),
            encoding="utf-8",
        )
        agent = MainAgent()
        agent.instruction = "[研究主题]\n测试主题\n"
        agent.sub_models = ["worker-model"]
        agent.meta = {
            "profile_name": "research_mode",
            "research_completion_scope": "current_step_only",
            "research_step_key": "literature_search",
            "step_min_papers": 30,
            "min_findings": 8,
            "max_parallel_subtasks": 4,
            "scratchpad_path": str(scratchpad),
        }

        params = agent._literature_search_task_params()
        context = params["context"]

        self.assertIn("integrated sensing and communication", context)
        self.assertIn("RIS ISAC beamforming", agent._extract_search_terms_from_scratchpad())
        self.assertIn('"RIS" "ISAC"', context)

    def test_step3_prompt_samples_paper_notes_instead_of_injecting_all(self):
        cfg = AgentConfig(
            main_model="test-model",
            sub_models=["test-model"],
            sources_dir=Path("workspace/sources"),
            workspace_dir=Path("workspace"),
        )
        pipeline = pipeline_module.ResearchPipeline(
            ResearchRequest(topic="RIS ISAC", trigger="internal"),
            cfg,
        )
        for index in range(30):
            append_jsonl(
                pipeline.artifacts.papers,
                {
                    "title": f"Paper {index}",
                    "source_url": f"https://example.org/paper/{index}",
                    "abstract": "A" * 1200,
                },
            )
        for index in range(12):
            append_jsonl(
                pipeline.artifacts.findings,
                {
                    "finding": f"Finding {index}",
                    "source_url": f"https://example.org/paper/{index}",
                },
            )
        for index in range(200):
            append_jsonl(
                pipeline.artifacts.paper_notes,
                {
                    "title": f"Paper Note {index}",
                    "problem": "P" * 1000,
                    "method": "M" * 1000,
                    "main_findings": "F" * 1000,
                    "limitations": "L" * 1000,
                    "evidence_source": "abstract",
                },
            )

        step = next(item for item in RESEARCH_STEPS if item.key == "knowledge_synthesis")
        readiness = pipeline._assess_material_readiness(step)
        brief = pipeline._build_step_brief(step, pipeline.skills.load_text(step.skill), readiness)
        meta = pipeline._step_runtime_metadata(step, readiness)
        meta.update(
            {
                "required_sections": [step.expected_section],
                "report_path": str(pipeline.artifacts.report_md),
                "findings_path": str(pipeline.artifacts.findings),
                "scratchpad_path": str(pipeline.artifacts.scratchpad),
                "papers_path": str(pipeline.artifacts.papers),
                "paper_notes_path": str(pipeline.artifacts.paper_notes),
                "claims_path": str(pipeline.artifacts.claims),
                "debate_log_path": str(pipeline.artifacts.debate_log),
                "outline_path": str(pipeline.artifacts.outline),
                "review_path": str(pipeline.artifacts.review),
            }
        )
        prompt = ResearchMainPromptBuilder.build_prompt(
            instruction=brief,
            meta=meta,
            prior_context="",
            attempt_index=1,
            max_attempts=6,
            sub_models=["test-model"],
            subtask_history="",
            tools=[],
        )

        self.assertEqual(readiness.digest["paper_notes"]["count"], 200)
        self.assertEqual(len(readiness.digest["paper_notes"]["sample"]), 5)
        self.assertIn("Paper Note 0", prompt)
        self.assertNotIn("Paper Note 199", prompt)
        self.assertLess(len(prompt), 40000)


if __name__ == "__main__":
    unittest.main()
