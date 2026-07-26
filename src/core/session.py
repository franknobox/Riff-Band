from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ConversationSession:
    """Manages persistence of a multi-turn conversation with an agent.

    Directory layout::

        {workspace}/sessions/{session_id}/
        ├── session.json     ← this file
        └── agent_state.json ← serialised MainAgent state
    """

    session_id: str
    work_dir: Path
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""
    turn_count: int = 0
    instruction: str = ""
    profile_name: str = "generic"
    mode: str = "auto"
    meta: Dict[str, Any] = field(default_factory=dict)

    # ── factory ───────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        session_id: str,
        work_dir: str | Path,
        *,
        instruction: str = "",
        profile_name: str = "generic",
        mode: str = "auto",
        meta: Optional[Dict[str, Any]] = None,
    ) -> "ConversationSession":
        wd = Path(work_dir).resolve()
        return cls(
            session_id=session_id,
            work_dir=wd,
            instruction=instruction,
            profile_name=profile_name,
            mode=mode,
            meta=dict(meta or {}),
        )

    # ── paths ─────────────────────────────────────────────────────

    @property
    def session_dir(self) -> Path:
        return self.work_dir / "sessions" / self.session_id

    @property
    def session_file(self) -> Path:
        return self.session_dir / "session.json"

    @property
    def agent_state_file(self) -> Path:
        return self.session_dir / "agent_state.json"

    # ── agent state ───────────────────────────────────────────────

    def save_agent_state(self, main_agent) -> None:
        """Persist MainAgent runtime state to disk."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        payload = main_agent.dump_state()
        # store alongside a lightweight snapshot of this session
        payload["_session_turn"] = self.turn_count
        payload["_saved_at"] = datetime.now(timezone.utc).isoformat()
        self.agent_state_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_agent_state(self, main_agent) -> bool:
        """Restore MainAgent state from disk.  Returns True on success."""
        if not self.agent_state_file.exists():
            return False
        try:
            payload = json.loads(
                self.agent_state_file.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            return False
        main_agent.load_state(payload)
        return True

    # ── persistence ───────────────────────────────────────────────

    def save(self) -> None:
        """Write session metadata to disk."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.session_file.write_text(
            json.dumps(self._serialise(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, session_id: str, work_dir: str | Path) -> Optional["ConversationSession"]:
        """Load session metadata from disk.  Returns None if not found."""
        wd = Path(work_dir).resolve()
        sf = wd / "sessions" / session_id / "session.json"
        if not sf.exists():
            return None
        try:
            data = json.loads(sf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return cls._deserialise(data, wd)

    @classmethod
    def list_sessions(cls, work_dir: str | Path) -> List[Dict[str, Any]]:
        """List available sessions in the workspace."""
        wd = Path(work_dir).resolve()
        sessions_dir = wd / "sessions"
        if not sessions_dir.exists():
            return []
        results: List[Dict[str, Any]] = []
        for child in sorted(sessions_dir.iterdir(), reverse=True):
            sf = child / "session.json"
            if sf.exists():
                try:
                    data = json.loads(sf.read_text(encoding="utf-8"))
                    results.append(
                        {
                            "session_id": data.get("session_id", child.name),
                            "created_at": data.get("created_at", ""),
                            "updated_at": data.get("updated_at", ""),
                            "turn_count": data.get("turn_count", 0),
                            "instruction": data.get("instruction", ""),
                            "profile_name": data.get("profile_name", ""),
                        }
                    )
                except (json.JSONDecodeError, OSError):
                    pass
        return results

    # ── helpers ───────────────────────────────────────────────────

    def _serialise(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "turn_count": self.turn_count,
            "instruction": self.instruction,
            "profile_name": self.profile_name,
            "mode": self.mode,
            "meta": self.meta,
        }

    @classmethod
    def _deserialise(cls, data: Dict[str, Any], work_dir: Path) -> "ConversationSession":
        return cls(
            session_id=data.get("session_id", ""),
            work_dir=work_dir,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            turn_count=data.get("turn_count", 0),
            instruction=data.get("instruction", ""),
            profile_name=data.get("profile_name", "generic"),
            mode=data.get("mode", "auto"),
            meta=data.get("meta", {}),
        )
