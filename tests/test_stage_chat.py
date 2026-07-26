from __future__ import annotations

from fastapi.testclient import TestClient

from ai4ms.api.app import create_app
from ai4ms.inference.gateway import InferenceResponse
from ai4ms.services.stage_chat import StageChatService


class _FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> InferenceResponse:
        self.calls.append((system_prompt, user_prompt))
        return InferenceResponse(
            text="先明确研究对象，再记录未知信息。",
            model="deepseek-v4-pro",
            usage={"total_tokens": 42, "call_count": 1},
        )


def test_stage_chat_calls_model_and_persists_history(tmp_path):
    gateway = _FakeGateway()
    chat_service = StageChatService(
        tmp_path / "projects",
        gateway_factory=lambda: gateway,
    )
    client = TestClient(create_app(tmp_path, stage_chat=chat_service))
    project = client.post(
        "/api/v1/projects",
        json={
            "title": "平台治理研究",
            "initial_idea": "研究平台规则变化对商家创新的影响",
        },
    ).json()

    response = client.post(
        f"/api/v1/projects/{project['project_id']}/stages/problem/chat",
        json={"message": "这个问题的边界应该怎么收窄？"},
    )

    assert response.status_code == 200
    turn = response.json()
    assert turn["user_message"]["role"] == "user"
    assert turn["assistant_message"]["model"] == "deepseek-v4-pro"
    assert turn["assistant_message"]["usage"]["total_tokens"] == 42
    assert "平台治理研究" in gateway.calls[0][1]
    assert "这个问题的边界应该怎么收窄" in gateway.calls[0][1]

    blank = client.post(
        f"/api/v1/projects/{project['project_id']}/stages/problem/chat",
        json={"message": "   "},
    )
    assert blank.status_code == 422

    history = client.get(
        f"/api/v1/projects/{project['project_id']}/stages/problem/chat"
    ).json()["items"]
    assert [item["role"] for item in history] == ["user", "assistant"]

    restarted = TestClient(
        create_app(
            tmp_path,
            stage_chat=StageChatService(
                tmp_path / "projects",
                gateway_factory=lambda: gateway,
            ),
        )
    )
    persisted = restarted.get(
        f"/api/v1/projects/{project['project_id']}/stages/problem/chat"
    ).json()["items"]
    assert persisted == history
    assert (
        tmp_path
        / "projects"
        / project["project_id"]
        / "artifacts"
        / "chat"
        / "problem.json"
    ).exists()
