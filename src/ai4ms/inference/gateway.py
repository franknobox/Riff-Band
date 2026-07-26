from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from base.engine.async_llm import AsyncLLM, LLMsConfig


class InferenceUnavailableError(RuntimeError):
    """Raised when the configured model cannot complete a request."""


@dataclass(frozen=True)
class InferenceResponse:
    text: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)


class InferenceGateway(Protocol):
    async def generate(self, system_prompt: str, user_prompt: str) -> InferenceResponse: ...


def configured_model_names(primary: str | None = None) -> tuple[str, ...]:
    configured = [
        item.strip()
        for item in os.getenv("AUTOENV_OPENAI_MODELS", "").split(",")
        if item.strip()
    ]
    primary_name = (
        primary.strip()
        if primary is not None
        else os.getenv("AI4MS_MODEL", "").strip()
    )
    if not primary_name and configured:
        primary_name = configured[0]

    candidates = [primary_name]
    candidates.extend(
        item.strip()
        for item in os.getenv("AI4MS_FALLBACK_MODELS", "").split(",")
        if item.strip()
    )
    candidates.extend(configured)
    return tuple(dict.fromkeys(item for item in candidates if item))


def configured_model_name() -> str:
    models = configured_model_names()
    return models[0] if models else ""


def _configured_number(name: str, explicit: float | int | None, default: str, cast: type[float] | type[int]):
    raw: float | int | str = explicit if explicit is not None else os.getenv(name, default)
    try:
        return cast(raw)
    except (TypeError, ValueError) as exc:
        raise InferenceUnavailableError(f"Invalid {name} value: {raw!r}") from exc


def inference_status() -> dict[str, Any]:
    model = configured_model_name()
    if not model:
        return {"configured": False, "model": "", "reason": "AI4MS_MODEL or AUTOENV_OPENAI_MODELS is not set"}
    try:
        config = LLMsConfig.default().get(model)
    except (FileNotFoundError, ValueError) as exc:
        return {"configured": False, "model": model, "reason": str(exc)}
    return {
        "configured": bool(config.key and config.base_url),
        "model": model,
        "reason": "" if config.key and config.base_url else "model API key or base URL is missing",
    }


class OpenAICompatibleGateway:
    """Small product-facing wrapper around the legacy AsyncLLM transport."""

    def __init__(
        self,
        *,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_attempts: int | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self.model_names = configured_model_names(model)
        if not self.model_names:
            raise InferenceUnavailableError("No model is configured for AI4MS stage generation")
        self.configs = []
        configuration_errors: list[str] = []
        try:
            manager = LLMsConfig.default()
        except FileNotFoundError as exc:
            raise InferenceUnavailableError(str(exc)) from exc
        for model_name in self.model_names:
            try:
                config = manager.get(model_name)
            except (FileNotFoundError, ValueError) as exc:
                configuration_errors.append(f"{model_name}: {exc}")
                continue
            if not config.key or not config.base_url:
                configuration_errors.append(
                    f"{model_name}: model API key or base URL is missing"
                )
                continue
            config.temperature = 0.2
            config.top_p = 0.9
            self.configs.append(config)
        if not self.configs:
            detail = "; ".join(configuration_errors) or "no usable model configuration"
            raise InferenceUnavailableError(detail)
        self.model = self.configs[0].model
        self.config = self.configs[0]
        self.timeout_seconds = max(
            1.0,
            _configured_number("AI4MS_INFERENCE_TIMEOUT_SECONDS", timeout_seconds, "90", float),
        )
        self.max_attempts = max(
            1,
            _configured_number("AI4MS_INFERENCE_MAX_ATTEMPTS", max_attempts, "2", int),
        )
        self.max_tokens = max(
            256,
            _configured_number("AI4MS_INFERENCE_MAX_TOKENS", max_tokens, "4000", int),
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> InferenceResponse:
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            config = self.configs[min(attempt, len(self.configs) - 1)]
            llm = AsyncLLM(config, system_msg=system_prompt, max_completion_tokens=self.max_tokens)
            try:
                text = await asyncio.wait_for(llm(user_prompt), timeout=self.timeout_seconds)
                if not isinstance(text, str) or not text.strip():
                    raise RuntimeError("model returned an empty response")
                summary = llm.usage_tracker.get_summary()
                usage = {
                    "input_tokens": summary.get("total_input_tokens", 0),
                    "output_tokens": summary.get("total_output_tokens", 0),
                    "total_tokens": summary.get("total_tokens", 0),
                    "call_count": summary.get("call_count", 0),
                }
                return InferenceResponse(text=text.strip(), model=config.model, usage=usage)
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.max_attempts:
                    await asyncio.sleep(min(2**attempt, 4))

        reason = str(last_error or "unknown inference error")
        for config in self.configs:
            if config.key:
                reason = reason.replace(config.key, "***")
        attempted = ", ".join(
            self.configs[min(index, len(self.configs) - 1)].model
            for index in range(self.max_attempts)
        )
        raise InferenceUnavailableError(
            f"Model request failed after trying [{attempted}]: {reason[:500]}"
        ) from last_error
