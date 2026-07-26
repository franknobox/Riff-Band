from __future__ import annotations

import asyncio
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from base.engine.async_llm import AsyncLLM, LLMConfig


class _FakeUsage:
    prompt_token_count = 11
    candidates_token_count = 7


class _FakeGeminiResponse:
    text = "gemini ok"
    usage_metadata = _FakeUsage()


class _FakeModels:
    def __init__(self):
        self.calls = []

    def generate_content(self, model, contents):
        self.calls.append({"model": model, "contents": contents})
        return _FakeGeminiResponse()


class _FakeClient:
    last_instance = None

    def __init__(self, api_key):
        self.api_key = api_key
        self.models = _FakeModels()
        _FakeClient.last_instance = self


class TestAsyncLLM(unittest.TestCase):
    def test_legacy_root_base_implementation_is_removed(self):
        repo_root = Path(__file__).resolve().parents[1]
        self.assertFalse((repo_root / "base" / "engine" / "async_llm.py").exists())

    def test_gemini_model_uses_google_genai_client(self):
        fake_genai = types.ModuleType("google.genai")
        fake_genai.Client = _FakeClient
        fake_google = types.ModuleType("google")
        fake_google.genai = fake_genai
        config = LLMConfig(
            {
                "model": "Gemini-2.5-Flash-Lite",
                "key": "AQ.test-key",
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "temperature": 0.2,
            }
        )

        with patch.dict("sys.modules", {"google": fake_google, "google.genai": fake_genai}):
            llm = AsyncLLM(config, system_msg="be concise")
            result = asyncio.run(llm("hello"))

        self.assertEqual(result, "gemini ok")
        self.assertIsNotNone(_FakeClient.last_instance)
        self.assertEqual(_FakeClient.last_instance.api_key, "AQ.test-key")
        self.assertEqual(_FakeClient.last_instance.models.calls[0]["model"], "gemini-2.5-flash-lite")
        self.assertIn("System instruction", _FakeClient.last_instance.models.calls[0]["contents"])


if __name__ == "__main__":
    unittest.main()
