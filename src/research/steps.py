from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ResearchStepKind = Literal[
    "decompose_topic",
    "literature_search",
    "paper_enrichment",
    "knowledge_synthesis",
    "claim_generation",
    "claim_debate",
    "outline_build",
    "section_draft",
    "multi_agent_review",
]


@dataclass(frozen=True)
class ResearchStep:
    key: ResearchStepKind
    title: str
    skill: str
    expected_section: str
    min_findings: int = 0
    min_papers: int = 0
    parallel_hint: bool = False
    report_required: bool = True


RESEARCH_STEPS: tuple[ResearchStep, ...] = (
    ResearchStep(
        key="decompose_topic",
        title="Step 1: Topic Decomposition",
        skill="decompose-topic",
        expected_section="研究问题拆解",
        report_required=False,
    ),
    ResearchStep(
        key="literature_search",
        title="Step 2: Literature Search",
        skill="literature-search",
        expected_section="文献检索与证据表",
        min_findings=0,
        min_papers=30,
        parallel_hint=True,
    ),
    ResearchStep(
        key="paper_enrichment",
        title="Step 2.5: Paper Enrichment",
        skill="paper-enrichment",
        expected_section="论文阅读笔记与结构化抽取",
        min_papers=30,
        parallel_hint=True,
    ),
    ResearchStep(
        key="knowledge_synthesis",
        title="Step 3: Knowledge Synthesis",
        skill="knowledge-synthesis",
        expected_section="知识综合与研究空白",
        min_findings=0,
        parallel_hint=True,
    ),
    ResearchStep(
        key="claim_generation",
        title="Step 4: Claim Generation",
        skill="claim-generation",
        expected_section="研究空白、未来方向与可检验问题",
        min_findings=0,
        parallel_hint=True,
    ),
    ResearchStep(
        key="claim_debate",
        title="Step 5: Claim Debate",
        skill="claim-debate",
        expected_section="观点辩论与优先级评估",
        parallel_hint=True,
    ),
    ResearchStep(
        key="outline_build",
        title="Step 6: Outline Build",
        skill="outline-build",
        expected_section="结构化论文大纲",
    ),
    ResearchStep(
        key="section_draft",
        title="Step 7: Section Draft",
        skill="section-draft",
        expected_section="LaTeX文献综述正文",
    ),
    ResearchStep(
        key="multi_agent_review",
        title="Step 8: Multi-Agent Review",
        skill="multi-agent-review",
        expected_section="多视角审稿意见",
        parallel_hint=True,
    ),
)


def required_report_sections() -> list[str]:
    return [step.expected_section for step in RESEARCH_STEPS if step.report_required]
