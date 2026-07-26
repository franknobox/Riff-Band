from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(ValueError):
    pass


def extract_json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    decoder = json.JSONDecoder()
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            value, _end = decoder.raw_decode(raw, index)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise StructuredOutputError("model response does not contain a valid JSON object")


def validate_structured_output(text: str, contract: type[T]) -> T:
    try:
        return contract.model_validate(extract_json_object(text))
    except ValidationError as exc:
        errors = "; ".join(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in exc.errors()[:8]
        )
        raise StructuredOutputError(f"model JSON failed contract validation: {errors}") from exc
