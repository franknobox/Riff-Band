from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from ai4ms.services.models import STAGE_DEFINITIONS, ApprovalDecision, ProjectStatus, StageStatus


LEGACY_STAGE_RENAMES: tuple[tuple[str, str], ...] = (
    ("idea", "problem"),
    ("topic", "theory"),
    ("analysis", "identification"),
    ("run", "analysis"),
)


class RevisionConflictError(RuntimeError):
    def __init__(self, expected_revision: int, current_revision: int):
        self.expected_revision = expected_revision
        self.current_revision = current_revision
        super().__init__(
            f"stage revision changed: expected {expected_revision}, current {current_revision}"
        )


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


class ProjectStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    initial_idea TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_stage TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS stage_states (
                    project_id TEXT NOT NULL,
                    stage_key TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    current_revision INTEGER NOT NULL DEFAULT 0,
                    approved_at TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, stage_key),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS stage_revisions (
                    revision_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    stage_key TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    content_json TEXT NOT NULL,
                    change_reason TEXT NOT NULL,
                    author_type TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(project_id, stage_key, revision),
                    FOREIGN KEY (project_id, stage_key) REFERENCES stage_states(project_id, stage_key) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS approval_events (
                    approval_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    stage_key TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    actor_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id, stage_key) REFERENCES stage_states(project_id, stage_key) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS data_assets (
                    asset_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(project_id, stored_path),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS user_profiles (
                    profile_id TEXT PRIMARY KEY,
                    interface_theme TEXT NOT NULL
                        CHECK(interface_theme IN ('graphite', 'blueprint', 'paper')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_stage_revisions_project
                    ON stage_revisions(project_id, stage_key, revision DESC);
                CREATE INDEX IF NOT EXISTS idx_approval_events_project
                    ON approval_events(project_id, stage_key, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_data_assets_project
                    ON data_assets(project_id, created_at DESC);
                """
            )
            timestamp = _now()
            conn.execute(
                """
                INSERT OR IGNORE INTO user_profiles
                    (profile_id, interface_theme, created_at, updated_at)
                VALUES ('local-user', 'graphite', ?, ?)
                """,
                (timestamp, timestamp),
            )
            self._synchronize_stage_model(conn)

    def create_project(self, title: str, initial_idea: str) -> dict[str, Any]:
        project_id = f"prj_{uuid4().hex[:12]}"
        timestamp = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    project_id,
                    title,
                    initial_idea,
                    ProjectStatus.ACTIVE.value,
                    STAGE_DEFINITIONS[0].key,
                    timestamp,
                    timestamp,
                ),
            )
            for stage in STAGE_DEFINITIONS:
                status = StageStatus.IN_PROGRESS.value if stage.position == 1 else StageStatus.NOT_STARTED.value
                conn.execute(
                    "INSERT INTO stage_states VALUES (?, ?, ?, ?, 0, NULL, ?)",
                    (project_id, stage.key, stage.position, status, timestamp),
                )
            self._write_revision(
                conn,
                project_id=project_id,
                stage_key="problem",
                content={"initial_idea": initial_idea, "questions": [], "unknowns": []},
                change_reason="Project created",
                author_type="human",
            )
        return self.get_project(project_id)

    def _synchronize_stage_model(self, conn: sqlite3.Connection) -> None:
        project_rows = conn.execute("SELECT project_id, current_stage FROM projects").fetchall()
        definitions = {stage.key: stage for stage in STAGE_DEFINITIONS}
        valid_keys = set(definitions)
        timestamp = _now()

        for project in project_rows:
            project_id = str(project["project_id"])
            current_stage = str(project["current_stage"])

            for old_key, new_key in LEGACY_STAGE_RENAMES:
                old_state = conn.execute(
                    "SELECT * FROM stage_states WHERE project_id = ? AND stage_key = ?",
                    (project_id, old_key),
                ).fetchone()
                if old_state is None or old_key == new_key:
                    continue
                new_state = conn.execute(
                    "SELECT 1 FROM stage_states WHERE project_id = ? AND stage_key = ?",
                    (project_id, new_key),
                ).fetchone()
                if new_state is not None:
                    continue
                conn.execute(
                    """
                    INSERT INTO stage_states
                        (project_id, stage_key, position, status, current_revision, approved_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        new_key,
                        int(old_state["position"]),
                        str(old_state["status"]),
                        int(old_state["current_revision"]),
                        old_state["approved_at"],
                        str(old_state["updated_at"]),
                    ),
                )
                conn.execute(
                    "UPDATE stage_revisions SET stage_key = ? WHERE project_id = ? AND stage_key = ?",
                    (new_key, project_id, old_key),
                )
                conn.execute(
                    "UPDATE approval_events SET stage_key = ? WHERE project_id = ? AND stage_key = ?",
                    (new_key, project_id, old_key),
                )
                conn.execute(
                    "DELETE FROM stage_states WHERE project_id = ? AND stage_key = ?",
                    (project_id, old_key),
                )
                if current_stage == old_key:
                    current_stage = new_key

            existing_rows = conn.execute(
                "SELECT stage_key FROM stage_states WHERE project_id = ?",
                (project_id,),
            ).fetchall()
            existing_keys = {str(row["stage_key"]) for row in existing_rows}
            for stage in STAGE_DEFINITIONS:
                if stage.key in existing_keys:
                    conn.execute(
                        "UPDATE stage_states SET position = ? WHERE project_id = ? AND stage_key = ?",
                        (stage.position, project_id, stage.key),
                    )
                    continue
                conn.execute(
                    """
                    INSERT INTO stage_states
                        (project_id, stage_key, position, status, current_revision, approved_at, updated_at)
                    VALUES (?, ?, ?, ?, 0, NULL, ?)
                    """,
                    (
                        project_id,
                        stage.key,
                        stage.position,
                        StageStatus.NOT_STARTED.value,
                        timestamp,
                    ),
                )

            obsolete_keys = existing_keys - valid_keys
            for obsolete_key in obsolete_keys:
                conn.execute(
                    "DELETE FROM stage_states WHERE project_id = ? AND stage_key = ?",
                    (project_id, obsolete_key),
                )

            stage_statuses = {
                str(row["stage_key"]): str(row["status"])
                for row in conn.execute(
                    "SELECT stage_key, status FROM stage_states WHERE project_id = ?",
                    (project_id,),
                ).fetchall()
            }
            first_unapproved = next(
                (
                    stage.key
                    for stage in STAGE_DEFINITIONS
                    if stage_statuses.get(stage.key) != StageStatus.APPROVED.value
                ),
                STAGE_DEFINITIONS[-1].key,
            )
            if current_stage not in valid_keys or definitions[current_stage].position > definitions[first_unapproved].position:
                current_stage = first_unapproved

            current_state = conn.execute(
                "SELECT status FROM stage_states WHERE project_id = ? AND stage_key = ?",
                (project_id, current_stage),
            ).fetchone()
            if current_state and current_state["status"] == StageStatus.NOT_STARTED.value:
                conn.execute(
                    "UPDATE stage_states SET status = ?, updated_at = ? WHERE project_id = ? AND stage_key = ?",
                    (StageStatus.IN_PROGRESS.value, timestamp, project_id, current_stage),
                )
            conn.execute(
                "UPDATE projects SET current_stage = ? WHERE project_id = ?",
                (current_stage, project_id),
            )

    def list_projects(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_project(self, project_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            project = conn.execute(
                "SELECT * FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
            if project is None:
                raise KeyError(project_id)
            stages = self._load_stages(conn, project_id)
            approvals = conn.execute(
                "SELECT * FROM approval_events WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        result = dict(project)
        result["stages"] = stages
        result["approvals"] = [dict(row) for row in approvals]
        return result

    def get_stage(self, project_id: str, stage_key: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        for stage in project["stages"]:
            if stage["key"] == stage_key:
                return stage
        raise KeyError(stage_key)

    def list_stage_revisions(
        self, project_id: str, stage_key: str
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            self._get_stage_state(conn, project_id, stage_key)
            rows = conn.execute(
                """
                SELECT revision_id, project_id, stage_key, revision, change_reason,
                       author_type, content_hash, created_at
                FROM stage_revisions
                WHERE project_id = ? AND stage_key = ?
                ORDER BY revision DESC
                """,
                (project_id, stage_key),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_stage_revision(
        self, project_id: str, stage_key: str, revision: int
    ) -> dict[str, Any]:
        with self._connect() as conn:
            self._get_stage_state(conn, project_id, stage_key)
            row = conn.execute(
                """
                SELECT revision_id, project_id, stage_key, revision, content_json,
                       change_reason, author_type, content_hash, created_at
                FROM stage_revisions
                WHERE project_id = ? AND stage_key = ? AND revision = ?
                """,
                (project_id, stage_key, revision),
            ).fetchone()
        if row is None:
            raise KeyError(f"{project_id}:{stage_key}:revision:{revision}")
        item = dict(row)
        item["content"] = json.loads(str(item.pop("content_json")))
        return item

    def update_project(self, project_id: str, title: str, initial_idea: str) -> dict[str, Any]:
        timestamp = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE projects
                SET title = ?, initial_idea = ?, updated_at = ?
                WHERE project_id = ?
                """,
                (title, initial_idea, timestamp, project_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(project_id)
        return self.get_project(project_id)

    def get_user_profile(self, profile_id: str = "local-user") -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_profiles WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
        if row is None:
            raise KeyError(profile_id)
        return dict(row)

    def update_user_profile(
        self,
        interface_theme: str,
        profile_id: str = "local-user",
    ) -> dict[str, Any]:
        timestamp = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE user_profiles
                SET interface_theme = ?, updated_at = ?
                WHERE profile_id = ?
                """,
                (interface_theme, timestamp, profile_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(profile_id)
        return self.get_user_profile(profile_id)

    def create_data_asset(
        self,
        *,
        project_id: str,
        asset_id: str,
        original_name: str,
        stored_path: str,
        media_type: str,
        size_bytes: int,
        sha256: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        timestamp = _now()
        with self._connect() as conn:
            if conn.execute(
                "SELECT 1 FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone() is None:
                raise KeyError(project_id)
            conn.execute(
                """
                INSERT INTO data_assets
                    (asset_id, project_id, original_name, stored_path, media_type,
                     size_bytes, sha256, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    project_id,
                    original_name,
                    stored_path,
                    media_type,
                    size_bytes,
                    sha256,
                    json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                    timestamp,
                ),
            )
            conn.execute(
                "UPDATE projects SET updated_at = ? WHERE project_id = ?",
                (timestamp, project_id),
            )
        return self.get_data_asset(project_id, asset_id)

    def list_data_assets(self, project_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM data_assets WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        return [self._decode_data_asset(row) for row in rows]

    def get_data_asset(self, project_id: str, asset_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM data_assets WHERE project_id = ? AND asset_id = ?",
                (project_id, asset_id),
            ).fetchone()
        if row is None:
            raise KeyError(f"{project_id}:{asset_id}")
        return self._decode_data_asset(row)

    @staticmethod
    def _decode_data_asset(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["metadata"] = json.loads(str(item.pop("metadata_json")))
        return item

    def update_stage(
        self,
        project_id: str,
        stage_key: str,
        content: dict[str, Any],
        change_reason: str,
        author_type: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        timestamp = _now()
        with self._connect() as conn:
            state = self._get_stage_state(conn, project_id, stage_key)
            current_revision = int(state["current_revision"])
            if expected_revision is not None and current_revision != expected_revision:
                raise RevisionConflictError(expected_revision, current_revision)
            self._write_revision(
                conn,
                project_id=project_id,
                stage_key=stage_key,
                content=content,
                change_reason=change_reason,
                author_type=author_type,
            )
            conn.execute(
                "UPDATE stage_states SET status = ?, approved_at = NULL, updated_at = ? WHERE project_id = ? AND stage_key = ?",
                (StageStatus.NEEDS_REVIEW.value, timestamp, project_id, stage_key),
            )
            conn.execute(
                """
                UPDATE stage_states
                SET status = CASE WHEN current_revision = 0 THEN ? ELSE ? END,
                    approved_at = NULL,
                    updated_at = ?
                WHERE project_id = ? AND position > ?
                """,
                (
                    StageStatus.NOT_STARTED.value,
                    StageStatus.NEEDS_REVIEW.value,
                    timestamp,
                    project_id,
                    int(state["position"]),
                ),
            )
            conn.execute(
                "UPDATE projects SET current_stage = ?, status = ?, updated_at = ? WHERE project_id = ?",
                (stage_key, ProjectStatus.ACTIVE.value, timestamp, project_id),
            )
        return self.get_project(project_id)

    def decide_stage(
        self,
        project_id: str,
        stage_key: str,
        decision: ApprovalDecision,
        reason: str,
        actor_type: str,
    ) -> dict[str, Any]:
        if actor_type != "human":
            raise ValueError("only a human actor may decide a gate")

        timestamp = _now()
        with self._connect() as conn:
            state = self._get_stage_state(conn, project_id, stage_key)
            revision = int(state["current_revision"])
            if revision < 1:
                raise ValueError("stage has no revision to decide")

            conn.execute(
                "INSERT INTO approval_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"apr_{uuid4().hex[:12]}",
                    project_id,
                    stage_key,
                    revision,
                    decision.value,
                    reason,
                    actor_type,
                    timestamp,
                ),
            )

            if decision is ApprovalDecision.APPROVE:
                status = StageStatus.APPROVED.value
                approved_at = timestamp
            elif decision is ApprovalDecision.REQUEST_CHANGES:
                status = StageStatus.IN_PROGRESS.value
                approved_at = None
            else:
                status = StageStatus.BLOCKED.value
                approved_at = None

            conn.execute(
                "UPDATE stage_states SET status = ?, approved_at = ?, updated_at = ? WHERE project_id = ? AND stage_key = ?",
                (status, approved_at, timestamp, project_id, stage_key),
            )

            current_stage = stage_key
            project_status = ProjectStatus.ACTIVE.value
            if decision is ApprovalDecision.APPROVE:
                next_state = conn.execute(
                    "SELECT * FROM stage_states WHERE project_id = ? AND position > ? ORDER BY position LIMIT 1",
                    (project_id, int(state["position"])),
                ).fetchone()
                if next_state is None:
                    project_status = ProjectStatus.COMPLETED.value
                else:
                    current_stage = str(next_state["stage_key"])
                    if next_state["status"] == StageStatus.NOT_STARTED.value:
                        conn.execute(
                            "UPDATE stage_states SET status = ?, updated_at = ? WHERE project_id = ? AND stage_key = ?",
                            (StageStatus.IN_PROGRESS.value, timestamp, project_id, current_stage),
                        )

            conn.execute(
                "UPDATE projects SET current_stage = ?, status = ?, updated_at = ? WHERE project_id = ?",
                (current_stage, project_status, timestamp, project_id),
            )
        return self.get_project(project_id)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _get_stage_state(self, conn: sqlite3.Connection, project_id: str, stage_key: str) -> sqlite3.Row:
        state = conn.execute(
            "SELECT * FROM stage_states WHERE project_id = ? AND stage_key = ?",
            (project_id, stage_key),
        ).fetchone()
        if state is None:
            raise KeyError(f"{project_id}:{stage_key}")
        return state

    def _write_revision(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        stage_key: str,
        content: dict[str, Any],
        change_reason: str,
        author_type: str,
    ) -> int:
        import hashlib

        state = self._get_stage_state(conn, project_id, stage_key)
        revision = int(state["current_revision"]) + 1
        content_json = json.dumps(content, ensure_ascii=False, sort_keys=True)
        content_hash = hashlib.sha256(content_json.encode("utf-8")).hexdigest()
        timestamp = _now()
        conn.execute(
            "INSERT INTO stage_revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"rev_{uuid4().hex[:12]}",
                project_id,
                stage_key,
                revision,
                content_json,
                change_reason,
                author_type,
                content_hash,
                timestamp,
            ),
        )
        conn.execute(
            "UPDATE stage_states SET current_revision = ?, updated_at = ? WHERE project_id = ? AND stage_key = ?",
            (revision, timestamp, project_id, stage_key),
        )
        return revision

    def _load_stages(self, conn: sqlite3.Connection, project_id: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT s.*, r.revision_id, r.content_json, r.content_hash, r.author_type,
                   r.change_reason, r.created_at AS revision_created_at
            FROM stage_states s
            LEFT JOIN stage_revisions r
              ON r.project_id = s.project_id
             AND r.stage_key = s.stage_key
             AND r.revision = s.current_revision
            WHERE s.project_id = ?
            ORDER BY s.position
            """,
            (project_id,),
        ).fetchall()
        definitions = {stage.key: stage for stage in STAGE_DEFINITIONS}
        stages: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            definition = definitions[str(item.pop("stage_key"))]
            content_json = item.pop("content_json", None)
            item.update(definition.model_dump())
            item["revision"] = int(item.pop("current_revision"))
            item["content"] = json.loads(content_json) if content_json else {}
            stages.append(item)
        return stages
