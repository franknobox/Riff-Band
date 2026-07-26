from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from base.engine.logs import logger
from config import AgentConfig
from core.message import (
    ErrorMessage,
    OrchestratorDecision,
    OrchestratorThinking,
    PhaseTransition,
    SubAgentResult,
    SubAgentStart,
    SubAgentStepEnd,
    SubAgentStepStart,
    TaskComplete,
    WorkerCompleted,
    WorkerSpawned,
    WorkerWaitEnd,
    WorkerWaitStart,
)
from project import build_project_by_mode


def _read_task_from_terminal() -> str:
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

    print("请输入任务内容，输入空行表示结束:")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _render_message(msg) -> None:
    """Simple text renderer for streaming messages."""
    if isinstance(msg, OrchestratorThinking):
        print(f"  [think] MainAgent 正在规划 (attempt {msg.attempt}/{msg.max_attempts})...")

    elif isinstance(msg, OrchestratorDecision):
        action = msg.action or "unknown"
        reasoning = msg.reasoning or ""
        print(f"  [decide] → {action}")
        if reasoning:
            print(f"           reason: {reasoning[:120]}")

    elif isinstance(msg, PhaseTransition):
        print(f"  [phase] {msg.from_phase} → {msg.to_phase}")

    elif isinstance(msg, WorkerSpawned):
        print(f"  [>] worker spawned: {msg.label} | {msg.model} | {msg.session_id}")

    elif isinstance(msg, WorkerCompleted):
        icon = "✓" if msg.status == "done" else "✗"
        print(f"  [{icon}] worker done: {msg.label} | status={msg.status} "
              f"| steps={msg.steps_taken} | cost=${msg.cost:.4f}")

    elif isinstance(msg, WorkerWaitStart):
        print(f"  [wait] 等待 {len(msg.session_ids) or 'all'} workers ({msg.timeout_seconds}s timeout)...")

    elif isinstance(msg, WorkerWaitEnd):
        print(f"  [wait] collected={msg.completed} still_running={msg.still_running}")

    elif isinstance(msg, SubAgentStart):
        print(f"  [sub] start: {msg.label} ({msg.model})")

    elif isinstance(msg, SubAgentStepStart):
        pass  # too noisy

    elif isinstance(msg, SubAgentStepEnd):
        if msg.done:
            print(f"  [sub] {msg.label} step {msg.current_step}/{msg.max_steps} "
                  f"→ {msg.action_taken} (done)")

    elif isinstance(msg, SubAgentResult):
        icon = "✓" if msg.finish_status == "done" else "✗"
        print(f"  [{icon}] sub done: {msg.label} | status={msg.finish_status} "
              f"| steps={msg.steps_taken} | cost=${msg.cost:.4f}")

    elif isinstance(msg, TaskComplete):
        icon = "✓" if msg.success else "✗"
        print(f"\n  [{icon}] Task complete | quality_gate_passed={msg.quality_gate_passed} "
              f"| attempts={msg.attempts} | cost=${msg.total_cost:.4f}")

    elif isinstance(msg, ErrorMessage):
        print(f"  [!] error: {msg.error_type} — {msg.message}")


def _print_final_result(final_result: dict) -> None:
    """Print a concise, user-facing completion summary."""
    summary = str(final_result.get("executive_summary", "") or "Task completed.").strip()
    status = str(final_result.get("status", "") or "").strip()
    confidence = str(final_result.get("confidence", "") or "").strip()
    quality_gate_passed = bool(final_result.get("quality_gate_passed", False))

    print("任务已完成。")
    print(f"质量门: {'通过' if quality_gate_passed else '未通过'}")
    if status or confidence:
        detail = " | ".join(
            item
            for item in [
                f"status={status}" if status else "",
                f"confidence={confidence}" if confidence else "",
            ]
            if item
        )
        print(detail)
    if summary:
        print(f"摘要: {summary}")

    artifacts = [item for item in list(final_result.get("artifacts", []) or []) if isinstance(item, dict)]
    report_path = str(final_result.get("report_path", "") or "").strip()
    findings_path = str(final_result.get("findings_path", "") or "").strip()

    print("产物:")
    printed_paths: set[str] = set()
    for artifact in artifacts:
        path = str(artifact.get("path", "") or "").strip()
        if not path or path in printed_paths:
            continue
        printed_paths.add(path)
        artifact_type = str(artifact.get("type", "file") or "file")
        description = str(artifact.get("description", "") or "").strip()
        suffix = f" - {description}" if description else ""
        print(f"- {artifact_type}: {path}{suffix}")
    for label, path in [("report", report_path), ("findings", findings_path)]:
        if path and path not in printed_paths:
            printed_paths.add(path)
            print(f"- {label}: {path}")

    open_issues = list(final_result.get("open_issues", []) or [])
    issues = list(final_result.get("issues", []) or [])
    if open_issues or issues:
        print("问题:")
        for issue in [*open_issues, *issues][:8]:
            print(f"- {issue}")


async def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Run the general-purpose agent workflow")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--stream", action="store_true", help="Use streaming message output")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("AOrchestra Agent Runtime")
    logger.info("=" * 60)

    cfg = AgentConfig.load(args.config)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cfg.timestamp = timestamp

    task_input = _read_task_from_terminal()
    if not task_input:
        raise ValueError("终端输入内容为空，请提供任务内容。")

    output_dir = (Path("workspace") / "output").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("任务已从终端输入加载")
    logger.info(f"报告输出目录: {output_dir}")

    profile_name = cfg.profile_name
    project, decision = await build_project_by_mode(
        mode=cfg.mode,
        main_model=cfg.main_model,
        sub_models=cfg.sub_models,
        brief_text=task_input,
        sources_dir=cfg.sources_dir,
        output_dir=output_dir,
        max_attempts=cfg.max_attempts,
        max_subagent_steps=cfg.max_subagent_steps,
        max_parallel_subtasks=cfg.max_parallel_subtasks,
        subagent_process_timeout_seconds=cfg.subagent_process_timeout_seconds,
        profile_name=profile_name,
    )
    print(
        f"Mode routing => selected={decision.mode} "
        f"source={decision.source} reason={decision.reason}"
    )
    print(f"Runtime profile => {profile_name}")
    print()

    if args.stream:
        async for msg in project.stream():
            _render_message(msg)
    else:
        result = await project.run()
        final_result = result.get("final_result")
        if final_result is None:
            print("Task finished without a passing final result. Check logs for quality gate issues.")
        else:
            _print_final_result(final_result)

    return 0


if __name__ == "__main__":
    raise sys.exit(asyncio.run(main()))
