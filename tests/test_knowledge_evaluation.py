import asyncio
import json

from ai4ms.inference.gateway import InferenceResponse
from ai4ms.knowledge import KnowledgeEvaluationService
from ai4ms.services.models import KnowledgeEvaluationRequest


class _FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def generate(
        self, system_prompt: str, user_prompt: str
    ) -> InferenceResponse:
        self.calls.append((system_prompt, user_prompt))
        return InferenceResponse(
            text=json.dumps(
                {
                    "methods": [
                        {
                            "candidate_id": "M01",
                            "score": 84,
                            "rationale": "与当前面板研究和控制变量结构较匹配。",
                            "missing_information": ["固定效应层级"],
                        }
                    ],
                    "formulas": [
                        {
                            "candidate_id": "F01",
                            "score": 79,
                            "rationale": "可表达候选模型，但尚未冻结变量口径。",
                            "missing_information": ["变量定义"],
                        }
                    ],
                    "summary": "分数为当前输入下的相对适配评估。",
                },
                ensure_ascii=False,
            ),
            model="fake-model",
            usage={"total_tokens": 123},
        )


def _project() -> dict:
    return {
        "project_id": "prj_eval",
        "title": "AI 采用与企业创新",
        "initial_idea": "AI 采用如何影响企业创新？",
        "stages": [
            {
                "key": "problem",
                "revision": 1,
                "content": {"questions": ["AI 采用如何影响企业创新？"]},
            },
            {
                "key": "literature",
                "revision": 0,
                "content": {"papers": []},
            },
            {"key": "theory", "revision": 0, "content": {}},
            {"key": "design", "revision": 0, "content": {}},
            {"key": "data", "revision": 0, "content": {}},
        ],
    }


def test_knowledge_scores_are_model_generated_persisted_and_invalidated(tmp_path):
    gateway = _FakeGateway()
    service = KnowledgeEvaluationService(
        tmp_path, gateway_factory=lambda: gateway
    )
    project = _project()
    request = KnowledgeEvaluationRequest(
        methods=[
            {
                "candidate_id": "M01",
                "name": "面板固定效应",
                "description": "控制不可观测时间不变异质性。",
                "assumptions": ["严格外生性"],
            }
        ],
        formulas=[
            {
                "candidate_id": "F01",
                "name": "双向固定效应式",
                "description": "企业和时间固定效应模型。",
                "assumptions": ["误差结构可处理"],
            }
        ],
    )

    evaluated = asyncio.run(service.evaluate(project, request))

    assert evaluated["status"] == "current"
    assert evaluated["model"] == "fake-model"
    assert evaluated["methods"][0]["score"] == 84
    assert evaluated["formulas"][0]["score"] == 79
    assert gateway.calls
    assert "不是成功概率" in gateway.calls[0][0]
    assert service.load(project)["status"] == "current"

    project["stages"][0]["revision"] = 2
    assert service.load(project)["status"] == "stale"
