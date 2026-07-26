from __future__ import annotations

import json
from itertools import count
from pathlib import Path
from typing import Any, Dict, List, Tuple

from base.agent.base_action import BaseAction
from base.engine.logs import logger
from core.interfaces import Action, Observation, TaskContext


ACTION_SPACE_TEMPLATE = """
### finish
描述：向主Agent汇报结果。当分配的子任务完成或受阻时使用。
参数：{"status": "done|partial|blocked", "message": "<你完成了什么>", "completed": ["<产出项>"], "issues": ["<缺口>"], "result": "<可选简短结果>"}

[重要说明]
- 完整任务简报已注入上下文，使用工具访问本地文件、联网搜索、记录结论并产出结果。
- 若无本地资料且无法联网搜索，立即以 partial 状态结束并说明缺口。
- 子任务完成或无法继续时，使用 finish 结束。

动作格式：{"action": "<动作名称>", "params": {...}}
""".strip()

_TASK_CONTEXT_COUNTER = count(1)


class TaskExecutionEnvironment:
    """Expose task context and execute delegated tool calls."""

    def __init__(
        self,
        brief_text: str,
        sources_dir: Path,
        output_dir: Path,
        tools: List[BaseAction],
        max_steps: int = 12,
        meta_data: Dict[str, Any] | None = None,
    ):
        self.brief_text = brief_text
        self.sources_dir = sources_dir
        self.output_dir = output_dir
        self.tools: Dict[str, BaseAction] = {tool.name: tool for tool in tools}
        self.max_steps = max_steps
        self.task_id = f"task_context_{next(_TASK_CONTEXT_COUNTER)}"
        self.meta_data = {
            "sources_dir": str(sources_dir),
            "output_dir": str(output_dir),
            **(meta_data or {}),
        }
        self._steps = 0
        self._done = False

    def _source_files(self) -> List[str]:
        if not self.sources_dir.exists():
            return []
        return sorted(
            str(path.relative_to(self.sources_dir))
            for path in self.sources_dir.rglob("*")
            if path.is_file()
        )

    def _build_instruction(self) -> str:
        search_enabled = self.meta_data.get("search_enabled", False)
        search_text = "已启用" if search_enabled else "未启用"
        return f"[用户任务]\n{self.brief_text}\n\n[联网搜索]\n{search_text}"

    def _log_label(self) -> str:
        label = str(self.meta_data.get("task_label", "") or "").strip()
        session_id = str(self.meta_data.get("worker_session_id", "") or "").strip()
        if label and session_id:
            return f"{label} session={session_id}"
        if label:
            return label
        if session_id:
            return f"{self.task_id} session={session_id}"
        return self.task_id

    def _build_action_space(self) -> str:
        if not self.tools:
            tool_block = "无可用工具"
        else:
            parts = ["可用操作:"]
            for tool in self.tools.values():
                params = getattr(tool, "parameters", {}) or {}
                parts.append(
                    f"### {tool.name}\n"
                    f"描述: {tool.description}\n"
                    f"参数: {json.dumps(params, ensure_ascii=False)}"
                )
            tool_block = "\n\n".join(parts)
        return tool_block + "\n\n" + ACTION_SPACE_TEMPLATE

    
    def get_task_context(self) -> TaskContext:
        return TaskContext(
            task_id=self.task_id,
            instruction=self._build_instruction(),
            action_space=self._build_action_space(),  # 把tools渲染成action_space
            max_steps=self.max_steps,
            meta_data=self.meta_data,
        )

    async def reset(self, seed: int | None = None) -> Observation:
        self._steps = 0
        self._done = False
        source_files = self._source_files()
        source_count = len(source_files)
        search_enabled = bool(self.meta_data.get("search_enabled", False))
        return {
            "message": "分析环境已就绪。请查阅简报、检查资料并执行步骤。",
            "profile_name": str(self.meta_data.get("profile_name", "generic")),
            "current_step": 0,
            "max_steps": self.max_steps,
            "report_path": str(self.meta_data.get("report_path", str(self.output_dir / "task_report.md"))),
            "findings_path": str(self.output_dir / "findings.jsonl"),
            "source_count": source_count,
            "search_enabled": search_enabled,
        }

    async def step(self, action: Action) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        if self._done:
            raise RuntimeError("环境已结束，请先调用 reset() 重置环境。")

        self._steps += 1
        action_type = action.get("action", "")
        params = action.get("params", {})

        if action_type == "finish":
            return self._handle_finish(params)

        return await self._handle_tool(action_type, params)

    def _handle_finish(self, params: Dict[str, Any]) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        finish_result = {
            "status": params.get("status", "done"),
            "message": params.get("message", ""),
            "completed": params.get("completed", []),
            "issues": params.get("issues", []),
            "result": params.get("result", ""),
        }
        self._done = True
        return (
            {
                "message": "进度已汇报给MainAgent",
                "current_step": self._steps,
                "finish_result": finish_result,
            },
            1.0 if finish_result["status"] == "done" else 0.5,
            True,
            {"finished": True, "finish_result": finish_result},
        )

    async def _handle_tool(self, action_type: str, params: Dict[str, Any]) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        tool = self.tools.get(action_type)
        if tool is None:
            return self._handle_unknown_action(action_type)

        try:
            result = await tool(**params)
            success = result.get("success", False)
            observation = {
                "action": action_type,
                "success": success,
                "output": result.get("output") if success else None,
                "error": result.get("message") if not success else None,
                "current_step": self._steps,
                "max_steps": self.max_steps,
            }
            if result.get("backend"):
                observation["backend"] = result.get("backend")
            logger.info(
                f"[TaskExecutionEnvironment] {self._log_label()} "
                f"step {self._steps}: {action_type} success={success}"
                f"{' backend=' + str(result.get('backend')) if result.get('backend') else ''}"
            )
        except Exception as exc:
            observation = {
                "action": action_type,
                "success": False,
                "error": str(exc),
                "current_step": self._steps,
                "max_steps": self.max_steps,
            }

        return self._check_max_steps(observation)

    def _handle_unknown_action(self, action_type: str) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        observation = {
            "error": f"未知动作: {action_type}. 可用动作: {list(self.tools.keys()) + ['finish']}",
            "current_step": self._steps,
            "max_steps": self.max_steps,
        }
        if self._steps >= self.max_steps:
            return self._timeout_response(observation)
        return observation, 0.0, False, {"error": "unknown_action"}

    def _check_max_steps(self, observation: Dict[str, Any]) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        if self._steps >= self.max_steps:
            return self._timeout_response(observation)
        return observation, 0.0, False, {}

    def _timeout_response(self, observation: Dict[str, Any]) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        self._done = True
        finish_result = {
            "status": "partial" if self._steps > 1 else "blocked",
            "message": f"已使用全部 {self.max_steps} 步，未正常调用 finish 结束。",
            "completed": [],
            "issues": ["步数耗尽"],
            "result": "",
        }
        observation["message"] = "已达到最大步骤数"
        observation["finish_result"] = finish_result
        return observation, 0.0, True, {"finished": True, "finish_result": finish_result}

    async def close(self):
        pass


# Backward compatibility alias
GBAAnalysisEnvironment = TaskExecutionEnvironment
