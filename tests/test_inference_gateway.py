from __future__ import annotations

import asyncio
from types import SimpleNamespace

import ai4ms.inference.gateway as gateway_module
from ai4ms.inference.gateway import OpenAICompatibleGateway, configured_model_names
from base.engine.async_llm import LLMsConfig


class _UsageTracker:
    @staticmethod
    def get_summary() -> dict:
        return {
            "total_input_tokens": 10,
            "total_output_tokens": 2,
            "total_tokens": 12,
            "call_count": 1,
        }


class _FallbackAsyncLLM:
    calls: list[str] = []

    def __init__(self, config, **_kwargs):
        self.config = config
        self.usage_tracker = _UsageTracker()

    async def __call__(self, _prompt: str) -> str:
        self.calls.append(self.config.model)
        if self.config.model == "deepseek-v4-pro":
            raise RuntimeError("primary unavailable")
        return "fallback ok"


class _ConfigManager:
    @staticmethod
    def get(model: str):
        return SimpleNamespace(
            model=model,
            key="test-key",
            base_url="https://example.invalid",
            temperature=1.0,
            top_p=1.0,
        )


def test_gateway_uses_ordered_model_fallback(monkeypatch):
    monkeypatch.setenv("AI4MS_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("AI4MS_FALLBACK_MODELS", "deepseek-v4-flash")
    monkeypatch.setenv(
        "AUTOENV_OPENAI_MODELS",
        "deepseek-v4-pro,deepseek-v4-flash",
    )
    monkeypatch.setattr(
        gateway_module.LLMsConfig,
        "default",
        staticmethod(lambda: _ConfigManager()),
    )
    monkeypatch.setattr(gateway_module, "AsyncLLM", _FallbackAsyncLLM)
    _FallbackAsyncLLM.calls = []

    gateway = OpenAICompatibleGateway(max_attempts=2)
    response = asyncio.run(gateway.generate("system", "user"))

    assert configured_model_names() == (
        "deepseek-v4-pro",
        "deepseek-v4-flash",
    )
    assert _FallbackAsyncLLM.calls == [
        "deepseek-v4-pro",
        "deepseek-v4-flash",
    ]
    assert response.model == "deepseek-v4-flash"
    assert response.text == "fallback ok"
    assert response.usage["total_tokens"] == 12


def test_model_specific_key_does_not_require_generic_key(monkeypatch):
    monkeypatch.delenv("AUTOENV_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AUTOENV_OPENAI_MODELS", "deepseek-v4-pro")
    monkeypatch.setenv("AUTOENV_OPENAI_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("AUTOENV_DEEPSEEK_V4_PRO_API_KEY", "model-key")

    config = LLMsConfig._load_config_from_env()

    assert config is not None
    assert config["deepseek-v4-pro"]["api_key"] == "model-key"
    assert config["deepseek-v4-pro"]["base_url"] == "https://api.deepseek.com"
