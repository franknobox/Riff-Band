from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Set


# 运行态状态机
class TaskState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_CHILD_PLAN = "waiting_child_plan"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def is_terminal(self) -> bool:
        return self in {TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED}


@dataclass
class TaskDependency:
    from_task: str
    to_task: str

# 单任务
@dataclass
class TaskSpec:
    id: str
    task_instruction: str
    model: str
    context: str = ""
    tools: List[str] = field(default_factory=list)
    result_schema: Dict[str, Any] | None = None


@dataclass
class TaskRuntimeRecord:
    state: TaskState = TaskState.QUEUED
    result: Any = None
    error: str = ""


@dataclass
class TaskPlan:
    id: str
    root_task_id: str
    tasks: List[TaskSpec] = field(default_factory=list)
    dependencies: List[TaskDependency] = field(default_factory=list)


def validate_plan(plan: TaskPlan) -> None:
    if not plan.id.strip():
        raise ValueError("plan.id cannot be empty")
    if not plan.root_task_id.strip():
        raise ValueError("plan.root_task_id cannot be empty")
    if not plan.tasks:
        raise ValueError("task plan must contain at least one task")

    task_ids: Set[str] = set()
    for task in plan.tasks:
        if not task.id.strip():
            raise ValueError("task.id cannot be empty")
        if not task.model.strip():
            raise ValueError(f"task `{task.id}` model cannot be empty")
        if task.id in task_ids:
            raise ValueError(f"duplicate task id `{task.id}`")
        task_ids.add(task.id)

    if plan.root_task_id not in task_ids:
        raise ValueError(f"root_task_id `{plan.root_task_id}` does not reference a task")

    for dep in plan.dependencies:
        if dep.from_task == dep.to_task:
            raise ValueError(f"task `{dep.from_task}` cannot depend on itself")
        if dep.from_task not in task_ids:
            raise ValueError(f"dependency from_task `{dep.from_task}` does not reference a task")
        if dep.to_task not in task_ids:
            raise ValueError(f"dependency to_task `{dep.to_task}` does not reference a task")

    _validate_acyclic(plan)


def _validate_acyclic(plan: TaskPlan) -> None:
    outgoing: Dict[str, List[str]] = {task.id: [] for task in plan.tasks}
    indegree: Dict[str, int] = {task.id: 0 for task in plan.tasks}
    for dep in plan.dependencies:
        outgoing[dep.from_task].append(dep.to_task)
        indegree[dep.to_task] += 1

    queue = [task_id for task_id, degree in indegree.items() if degree == 0]
    visited = 0
    while queue:
        current = queue.pop(0)
        visited += 1
        for nxt in outgoing[current]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if visited != len(plan.tasks):
        raise ValueError("task plan contains a dependency cycle")


def ready_task_ids(plan: TaskPlan, states: Dict[str, TaskState]) -> List[str]:
    validate_plan(plan)
    ready: List[str] = []
    for task in plan.tasks:
        state = states.get(task.id, TaskState.QUEUED)
        if state != TaskState.QUEUED:
            continue
        deps_ok = all(
            states.get(dep.from_task, TaskState.QUEUED) == TaskState.SUCCEEDED
            for dep in plan.dependencies
            if dep.to_task == task.id
        )
        if deps_ok:
            ready.append(task.id)
    return ready


class TaskPlanExecutor:
    """Execution-state holder used by the orchestrator (coordinator) layer."""

    def __init__(self, plan_id: str = "main_plan"):
        self.plan_id = plan_id
        self._counter = 0
        self.plan: TaskPlan | None = None
        self.task_map: Dict[str, TaskSpec] = {}
        self.runtime: Dict[str, TaskRuntimeRecord] = {}

    def reset(self) -> None:
        self._counter = 0
        self.plan = None
        self.task_map = {}
        self.runtime = {}

    # ── persistence ───────────────────────────────────────────────

    def dump(self) -> Dict[str, Any]:
        """Serialize executor state for session persistence."""
        plan_data = None
        if self.plan:
            plan_data = {
                "id": self.plan.id,
                "root_task_id": self.plan.root_task_id,
                "tasks": [
                    {
                        "id": task.id,
                        "task_instruction": task.task_instruction,
                        "model": task.model,
                        "context": task.context,
                        "tools": list(task.tools),
                        "result_schema": task.result_schema,
                    }
                    for task in self.plan.tasks
                ],
                "dependencies": [
                    {"from_task": dep.from_task, "to_task": dep.to_task}
                    for dep in self.plan.dependencies
                ],
            }
        return {
            "plan_id": self.plan_id,
            "_counter": self._counter,
            "plan": plan_data,
            "task_map": {
                task_id: {
                    "id": spec.id,
                    "task_instruction": spec.task_instruction,
                    "model": spec.model,
                    "context": spec.context,
                    "tools": list(spec.tools),
                    "result_schema": spec.result_schema,
                }
                for task_id, spec in self.task_map.items()
            },
            "runtime": {
                task_id: {
                    "state": record.state.value,
                    "result": record.result,
                    "error": record.error,
                }
                for task_id, record in self.runtime.items()
            },
        }

    def restore(self, data: Dict[str, Any]) -> None:
        """Restore executor state from a previously dumped payload."""
        self.plan_id = str(data.get("plan_id", "main_plan"))
        self._counter = int(data.get("_counter", 0))

        plan_data = data.get("plan")
        if isinstance(plan_data, dict) and plan_data.get("tasks"):
            tasks = []
            for item in plan_data["tasks"]:
                tasks.append(
                    TaskSpec(
                        id=str(item["id"]),
                        task_instruction=str(item.get("task_instruction", "")),
                        model=str(item.get("model", "")),
                        context=str(item.get("context", "")),
                        tools=[str(t) for t in (item.get("tools") or [])],
                        result_schema=item.get("result_schema"),
                    )
                )
            deps = [
                TaskDependency(
                    from_task=str(dep["from_task"]),
                    to_task=str(dep["to_task"]),
                )
                for dep in (plan_data.get("dependencies") or [])
            ]
            root_id = str(plan_data.get("root_task_id", tasks[0].id if tasks else ""))
            self.plan = TaskPlan(
                id=str(plan_data.get("id", "main_plan")),
                root_task_id=root_id,
                tasks=tasks,
                dependencies=deps,
            )
        else:
            self.plan = None

        self.task_map = {}
        for task_id, item in (data.get("task_map") or {}).items():
            self.task_map[task_id] = TaskSpec(
                id=str(item.get("id", task_id)),
                task_instruction=str(item.get("task_instruction", "")),
                model=str(item.get("model", "")),
                context=str(item.get("context", "")),
                tools=[str(t) for t in (item.get("tools") or [])],
                result_schema=item.get("result_schema"),
            )

        self.runtime = {}
        for task_id, item in (data.get("runtime") or {}).items():
            record = TaskRuntimeRecord()
            raw_state = str(item.get("state", "queued"))
            try:
                record.state = TaskState(raw_state)
            except ValueError:
                record.state = TaskState.QUEUED
            record.result = item.get("result")
            record.error = str(item.get("error", ""))
            self.runtime[task_id] = record


    # 新增任务
    def create_or_extend(
        self,
        tasks: List[Dict[str, Any]],
        dependencies: List[TaskDependency] | None = None,
    ) -> List[str]:
        if not tasks:
            return []
        created_ids: List[str] = []
        for item in tasks:
            self._counter += 1
            task_id = f"task_{self._counter}"
            spec = TaskSpec(
                id=task_id,
                task_instruction=str(item.get("task_instruction", "")),
                model=str(item.get("model", "")),
                context=str(item.get("context", "")),
                tools=[str(t) for t in (item.get("tools") or [])],
                result_schema=item.get("result_schema"),
            )
            created_ids.append(task_id)
            self.task_map[task_id] = spec
            self.runtime[task_id] = TaskRuntimeRecord()

        all_tasks = list(self.task_map.values())
        all_deps = (self.plan.dependencies if self.plan else []) + (dependencies or [])
        root_task_id = self.plan.root_task_id if self.plan else created_ids[0]
        self.plan = TaskPlan(
            id=self.plan_id,
            root_task_id=root_task_id,
            tasks=all_tasks,
            dependencies=all_deps,
        )
        validate_plan(self.plan)  # 校验
        return created_ids

    def mark_running(self, task_id: str) -> None:
        self._ensure_task(task_id)
        self.runtime[task_id].state = TaskState.RUNNING

    def mark_finished(self, task_id: str, finish_result: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_task(task_id)
        status = str(finish_result.get("status", "")).strip().lower()
        if status == "done":
            self.runtime[task_id].state = TaskState.SUCCEEDED
            self.runtime[task_id].result = finish_result.get("result")
        elif status in {"partial", "blocked", "timeout"}:
            self.runtime[task_id].state = TaskState.FAILED
            self.runtime[task_id].result = finish_result.get("result")
            self.runtime[task_id].error = str(finish_result.get("message", "task not completed"))
        else:
            self.runtime[task_id].state = TaskState.FAILED
            self.runtime[task_id].error = f"unexpected finish status: {status or 'empty'}"

        schema_issue = self.validate_task_output(task_id, self.runtime[task_id].result)
        if schema_issue:
            self.runtime[task_id].state = TaskState.FAILED
            self.runtime[task_id].error = schema_issue
        return {
            "task_id": task_id,
            "state": self.runtime[task_id].state.value,
            "error": self.runtime[task_id].error,
        }

    def ready_tasks(self) -> List[str]:
        if not self.plan:
            return []
        states = {task_id: record.state for task_id, record in self.runtime.items()}
        return ready_task_ids(self.plan, states)

    def snapshot(self) -> Dict[str, Any]:
        if not self.plan:
            return {"plan_id": self.plan_id, "tasks": []}
        return {
            "plan_id": self.plan.id,
            "root_task_id": self.plan.root_task_id,
            "tasks": [
                {
                    "task_id": task.id,
                    "model": task.model,
                    "state": self.runtime.get(task.id, TaskRuntimeRecord()).state.value,
                    "error": self.runtime.get(task.id, TaskRuntimeRecord()).error,
                }
                for task in self.plan.tasks
            ],
            "ready_task_ids": self.ready_tasks(),
        }

    def validate_task_output(self, task_id: str, output: Any) -> str:
        task = self.task_map.get(task_id)
        if not task or not task.result_schema:
            return ""
        try:
            import jsonschema  # type: ignore
        except ImportError:
            return "jsonschema is not installed; cannot validate delegated task output schema"
        try:
            jsonschema.validate(output, task.result_schema)
            return ""
        except Exception as exc:
            return f"output schema validation failed: {exc}"

    def _ensure_task(self, task_id: str) -> None:
        if task_id not in self.task_map:
            raise ValueError(f"unknown task id: {task_id}")
