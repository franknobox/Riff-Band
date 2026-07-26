from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

import yaml


VALID_MODES = {"single", "multi", "auto"}


@dataclass
class AgentConfig:
    main_model: str
    sub_models: list[str]
    sources_dir: Path
    model_profiles: list[dict[str, Any]] = field(default_factory=list)
    workspace_dir: Path = Path("workspace")
    max_attempts: int = 6
    max_subagent_steps: int = 10
    max_parallel_subtasks: int = 3
    subagent_process_timeout_seconds: int = 180
    mode: str = "auto"
    profile_name: str = "generic"

    @classmethod
    def load(cls, config_path: str | Path) -> "AgentConfig":
        config_path = Path(config_path)
        with config_path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}

        mode = str(raw.get("mode", "auto")).strip().lower() or "auto"
        if mode not in VALID_MODES:
            raise ValueError(f"Invalid mode `{mode}`. Supported modes are: single, multi, auto.")

        workspace_raw = raw.get("workspace_dir", "workspace")
        workspace_dir = _resolve_path(config_path, str(workspace_raw)) if workspace_raw else Path("workspace")

        return cls(
            main_model=str(raw["main_model"]),
            sub_models=_normalize_sub_models(raw.get("sub_models") or [str(raw["main_model"])]),
            model_profiles=_normalize_model_profiles(raw),
            sources_dir=_resolve_path(config_path, raw["sources_dir"]),
            workspace_dir=workspace_dir,
            max_attempts=int(raw.get("max_attempts", 6)),
            max_subagent_steps=int(raw.get("max_subagent_steps", 10)),
            max_parallel_subtasks=int(raw.get("max_parallel_subtasks", 3)),
            subagent_process_timeout_seconds=int(raw.get("subagent_process_timeout_seconds", 180)),
            mode=mode,
            profile_name=str(raw.get("profile_name", "generic")).strip() or "generic",
        )


def _resolve_path(config_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (config_path.parent / path).resolve()


def _normalize_sub_models(raw_models: Any) -> list[str]:
    names: list[str] = []
    for item in raw_models or []:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("model") or "").strip()
        else:
            name = str(item).strip()
        if name:
            names.append(name)
    return names


def _normalize_model_profiles(raw: dict[str, Any]) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for item in raw.get("sub_models") or []:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("model") or "").strip()
            if name:
                copied = dict(item)
                copied["name"] = name
                profiles.append(copied)

    explicit = raw.get("model_profiles") or []
    if isinstance(explicit, dict):
        for name, profile in explicit.items():
            if not str(name).strip():
                continue
            copied = dict(profile or {})
            copied["name"] = str(name).strip()
            profiles.append(copied)
    elif isinstance(explicit, list):
        for item in explicit:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("model") or "").strip()
                if name:
                    copied = dict(item)
                    copied["name"] = name
                    profiles.append(copied)
    return profiles


# Backward compatibility alias
GBAAnalysisConfig = AgentConfig
