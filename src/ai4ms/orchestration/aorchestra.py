from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4

from ai4ms.inference.gateway import configured_model_name, configured_model_names
from project.build_project import build_agent_project


AORCHESTRA_PAPER = "AOrchestra: Automating Sub-Agent Creation for Agentic Orchestration"
AO_STAGE_KEYS = frozenset({"problem", "literature", "robustness", "evidence"})


@dataclass(frozen=True)
class OrchestrationResult:
    run_id: str
    stage_key: str
    status: str
    summary: str
    report: str
    report_path: str
    subagent_runs: int
    attempts: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    total_cost: float
    cost_known: bool

    def prompt_context(self) -> dict[str, Any]:
        return {
            "runtime": "AOrchestra",
            "paper": AORCHESTRA_PAPER,
            "run_id": self.run_id,
            "status": self.status,
            "summary": self.summary,
            "subagent_runs": self.subagent_runs,
            "analysis_report": self.report[:18000],
        }

    def generation_metadata(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("report")
        data["runtime"] = "AOrchestra"
        data["paper"] = AORCHESTRA_PAPER
        return data


class StageOrchestrator(Protocol):
    async def analyze(
        self,
        project: dict[str, Any],
        stage_key: str,
        instruction: str,
        context: dict[str, Any],
    ) -> OrchestrationResult: ...


class AOrchestraStageService:
    """Read-only AOrchestra adapter for selected AI4MS reasoning stages."""

    _DISCOVERY_TOOLS = [
        "list_sources",
        "search_sources",
        "read_source",
        "read_sources",
        "web_search",
        "web_fetch",
        "read_url",
        "openalex_search",
        "arxiv_search",
        "semantic_scholar_search",
        "crossref_lookup",
        "dblp_lookup",
        "novelty_check",
        "record_finding",
        "read_findings",
        "synthesize_findings",
        "write_scratchpad_note",
        "read_scratchpad",
        "write_report_section",
        "verify_artifacts",
        "citation_audit",
    ]
    _AUDIT_TOOLS = [
        "list_sources",
        "search_sources",
        "read_source",
        "read_sources",
        "record_finding",
        "read_findings",
        "synthesize_findings",
        "write_scratchpad_note",
        "read_scratchpad",
        "write_report_section",
        "verify_artifacts",
    ]

    def __init__(
        self,
        projects_dir: str | Path,
        *,
        project_builder: Callable[..., Any] = build_agent_project,
        model_name_factory: Callable[[], str] = configured_model_name,
        model_names_factory: Callable[[str | None], tuple[str, ...]] = configured_model_names,
    ) -> None:
        self.projects_dir = Path(projects_dir)
        self.project_builder = project_builder
        self.model_name_factory = model_name_factory
        self.model_names_factory = model_names_factory

    async def analyze(
        self,
        project: dict[str, Any],
        stage_key: str,
        instruction: str,
        context: dict[str, Any],
    ) -> OrchestrationResult:
        if stage_key not in AO_STAGE_KEYS:
            raise ValueError(f"AOrchestra is not enabled for stage '{stage_key}'")

        model = self.model_name_factory().strip()
        if not model:
            raise RuntimeError("AOrchestra requires AI4MS_MODEL or AUTOENV_OPENAI_MODELS")
        model_pool = list(self.model_names_factory(model)) or [model]

        project_id = str(project["project_id"])
        run_id = f"ao_{stage_key}_{uuid4().hex[:12]}"
        project_dir = self.projects_dir / project_id
        run_dir = project_dir / "agent-runs" / run_id
        sources_dir = run_dir / "sources"
        sources_dir.mkdir(parents=True, exist_ok=False)

        context_path = sources_dir / "stage_context.json"
        context_path.write_text(
            json.dumps(
                {
                    "project_id": project_id,
                    "title": project.get("title", ""),
                    "initial_idea": project.get("initial_idea", ""),
                    "stage_key": stage_key,
                    "researcher_instruction": instruction,
                    "stage_context": context,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        allowed_tools = (
            self._DISCOVERY_TOOLS if stage_key in {"problem", "literature"} else self._AUDIT_TOOLS
        )
        runtime = self.project_builder(
            main_model=model,
            sub_models=model_pool,
            brief_text=self._brief(stage_key, instruction, context),
            sources_dir=sources_dir,
            output_dir=run_dir,
            max_attempts=self._int_setting("AI4MS_AO_MAX_ATTEMPTS", 2, 2, 10),
            max_subagent_steps=self._int_setting("AI4MS_AO_MAX_SUBAGENT_STEPS", 7, 3, 20),
            max_parallel_subtasks=self._int_setting("AI4MS_AO_MAX_PARALLEL", 3, 2, 5),
            subagent_process_timeout_seconds=self._int_setting(
                "AI4MS_AO_TIMEOUT_SECONDS", 150, 30, 600
            ),
            profile_name=f"ai4ms-{stage_key}",
            report_filename="stage_analysis.md",
            required_sections=["阶段编排结论"],
            min_findings=0,
            runtime_metadata={
                "ai4ms_stage_key": stage_key,
                "allowed_worker_tools": allowed_tools,
                "default_worker_tools": allowed_tools,
                "parallel_forbidden_tools": ["write_report_section"],
                "task_goal": "形成供阶段结构化生成器使用的只读研究分析，不作批准决定。",
                "workflow_hints": [
                    "至少创建两个职责不同的 SubAgent，并优先并行执行独立任务。",
                    "所有结论必须区分输入事实、推断、反证和未知。",
                    "不得声称已批准资产，不得修改 AI4MS 数据库或正式阶段资产。",
                ],
                "completion_requirements": [
                    "主报告包含 ## 阶段编排结论。",
                    "综合支持证据、反向证据、边界和仍需人工决定的问题。",
                ],
            },
        )

        terminal: Any = None
        sessions: set[str] = set()
        async for event in runtime.stream():
            session_id = str(getattr(event, "session_id", "") or "")
            if session_id:
                sessions.add(session_id)
            if event.__class__.__name__ == "TaskComplete":
                terminal = event

        report_file = run_dir / "stage_analysis.md"
        report = report_file.read_text(encoding="utf-8").strip() if report_file.exists() else ""
        summary = str(getattr(terminal, "summary", "") or "").strip()
        if not report:
            report = summary
        if not report:
            raise RuntimeError(f"AOrchestra run '{run_id}' produced no usable analysis")

        success = bool(getattr(terminal, "success", False))
        result = OrchestrationResult(
            run_id=run_id,
            stage_key=stage_key,
            status="complete" if success else "partial",
            summary=summary or report[:1000],
            report=report,
            report_path=str(report_file.relative_to(project_dir)).replace("\\", "/"),
            subagent_runs=len(sessions),
            attempts=int(getattr(terminal, "attempts", 0) or 0),
            input_tokens=int(getattr(terminal, "input_tokens", 0) or 0),
            output_tokens=int(getattr(terminal, "output_tokens", 0) or 0),
            total_tokens=int(getattr(terminal, "total_tokens", 0) or 0),
            total_cost=float(getattr(terminal, "total_cost", 0.0) or 0.0),
            cost_known=bool(getattr(terminal, "cost_known", True)),
        )
        (run_dir / "orchestration.json").write_text(
            json.dumps(
                {
                    **result.generation_metadata(),
                    "created_at": datetime.now(UTC).isoformat(),
                    "allowed_worker_tools": allowed_tools,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return result

    @staticmethod
    def _int_setting(name: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(os.getenv(name, str(default)))
        except ValueError as exc:
            raise RuntimeError(f"{name} must be an integer") from exc
        return min(max(value, minimum), maximum)

    @staticmethod
    def _brief(
        stage_key: str,
        instruction: str,
        context: dict[str, Any],
    ) -> str:
        tasks = {
            "problem": (
                "并行委派概念与边界澄清、相邻术语/已有研究侦察、候选空白反向检索。"
                "输出只能把空白写成候选，不得宣称绝对原创。"
            ),
            "literature": (
                "并行委派检索策略覆盖审查、争议与反向证据查找、已有论文材料综合。"
                "若 stage_context 已含 paper_id，引用必须保留这些 ID；外部线索只能作为待纳入候选。"
            ),
            "robustness": (
                "只读取 stage_context，分别委派规格/样本/口径审查、安慰剂与证伪审查、"
                "失败和负结果解释审查。不得联网，不得运行代码，不得把 planned/blocked 写成 passed。"
            ),
            "evidence": (
                "只读取 stage_context，分别委派 Claim-Evidence 映射审计、反证与竞争解释审计、"
                "过度主张和适用边界审计。不得联网，不得创造论文、run、数值或 evidence ID。"
            ),
        }
        extra = str(instruction or "").strip() or "无额外要求"
        context_preview = json.dumps(context, ensure_ascii=False, indent=2)
        if len(context_preview) > 12000:
            context_preview = context_preview[:12000] + "\n... [上下文已截断]"
        return (
            f"[用户任务]\nAI4MS 阶段: {stage_key}\n"
            f"{tasks[stage_key]}\n"
            "源文件工具的根目录已经是本次运行的 sources_dir；读取根内的 stage_context.json "
            "作为正式输入，不要添加 sources/ 前缀。至少创建两个职责不同的 SubAgent；"
            "研究后由独立写作 SubAgent 将综合结果写入 stage_analysis.md，包含标题 ## 阶段编排结论；"
            "再执行验证。最终结果只供结构化阶段生成器参考，不能批准或直接修改正式资产。\n"
            f"研究者额外要求: {extra}\n"
            "正式上下文摘要（与 stage_context.json 内容一致）：\n"
            f"{context_preview}"
        )
