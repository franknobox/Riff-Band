from __future__ import annotations

import unittest

from orchestration_tools.taskplan import (
    TaskDependency,
    TaskPlan,
    TaskPlanExecutor,
    TaskSpec,
    TaskState,
    ready_task_ids,
    validate_plan,
)


class TestTaskPlan(unittest.TestCase):
    def test_validate_plan_and_ready_tasks(self):
        plan = TaskPlan(
            id="plan_1",
            root_task_id="research",
            tasks=[
                TaskSpec(id="research", task_instruction="collect", model="m1"),
                TaskSpec(id="synthesis", task_instruction="merge", model="m1"),
            ],
            dependencies=[TaskDependency(from_task="research", to_task="synthesis")],
        )
        validate_plan(plan)
        states = {}
        self.assertEqual(ready_task_ids(plan, states), ["research"])
        states["research"] = TaskState.SUCCEEDED
        self.assertEqual(ready_task_ids(plan, states), ["synthesis"])

    def test_executor_schema_validation(self):
        executor = TaskPlanExecutor()
        task_ids = executor.create_or_extend(
            [
                {
                    "task_instruction": "return structured output",
                    "model": "m1",
                    "result_schema": {
                        "type": "object",
                        "required": ["summary"],
                        "properties": {"summary": {"type": "string"}},
                    },
                }
            ]
        )
        task_id = task_ids[0]
        executor.mark_running(task_id)
        result = executor.mark_finished(
            task_id,
            {
                "status": "done",
                "result": {"wrong_field": "x"},
            },
        )
        self.assertEqual(result["state"], TaskState.FAILED.value)
        self.assertIn("schema", result["error"])


if __name__ == "__main__":
    unittest.main()
