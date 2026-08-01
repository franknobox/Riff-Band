from __future__ import annotations

import hashlib
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


def _json_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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

                CREATE TABLE IF NOT EXISTS knowledge_candidates (
                    candidate_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL CHECK(kind IN ('method', 'formula')),
                    revision INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL
                        CHECK(status IN ('pending', 'approved', 'rejected', 'changes_requested')),
                    query TEXT NOT NULL,
                    proposed_content_json TEXT NOT NULL,
                    source_links_json TEXT NOT NULL,
                    search_trace_json TEXT NOT NULL,
                    review_json TEXT,
                    promoted_record_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_records (
                    record_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL CHECK(kind IN ('method', 'formula')),
                    current_revision INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active', 'archived')),
                    source_candidate_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (source_candidate_id)
                        REFERENCES knowledge_candidates(candidate_id)
                );

                CREATE TABLE IF NOT EXISTS knowledge_record_revisions (
                    revision_id TEXT PRIMARY KEY,
                    record_id TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('method', 'formula')),
                    revision INTEGER NOT NULL,
                    content_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    change_reason TEXT NOT NULL,
                    author_type TEXT NOT NULL CHECK(author_type = 'human'),
                    created_at TEXT NOT NULL,
                    UNIQUE(record_id, revision),
                    FOREIGN KEY (record_id)
                        REFERENCES knowledge_records(record_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_stage_revisions_project
                    ON stage_revisions(project_id, stage_key, revision DESC);
                CREATE INDEX IF NOT EXISTS idx_approval_events_project
                    ON approval_events(project_id, stage_key, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_data_assets_project
                    ON data_assets(project_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_knowledge_candidates_kind
                    ON knowledge_candidates(kind, status, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_knowledge_records_kind
                    ON knowledge_records(kind, status, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_knowledge_record_revisions
                    ON knowledge_record_revisions(record_id, revision DESC);
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

    def create_knowledge_candidate(
        self,
        *,
        candidate_id: str,
        kind: str,
        query: str,
        proposed_content: dict[str, Any],
        source_links: list[dict[str, Any]],
        search_trace: dict[str, Any],
    ) -> dict[str, Any]:
        timestamp = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO knowledge_candidates
                    (candidate_id, kind, revision, status, query,
                     proposed_content_json, source_links_json,
                     search_trace_json, review_json, promoted_record_id,
                     created_at, updated_at)
                VALUES (?, ?, 1, 'pending', ?, ?, ?, ?, NULL, NULL, ?, ?)
                """,
                (
                    candidate_id,
                    kind,
                    query,
                    json.dumps(
                        proposed_content,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    json.dumps(
                        source_links,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    json.dumps(
                        search_trace,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_knowledge_candidate(candidate_id)

    def list_knowledge_candidates(
        self,
        kind: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[str] = []
        if kind:
            clauses.append("kind = ?")
            parameters.append(kind)
        if status:
            clauses.append("status = ?")
            parameters.append(status)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM knowledge_candidates
                {where}
                ORDER BY updated_at DESC, candidate_id
                """,
                parameters,
            ).fetchall()
        return [self._decode_knowledge_candidate(row) for row in rows]

    def get_knowledge_candidate(self, candidate_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM knowledge_candidates WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
        if row is None:
            raise KeyError(candidate_id)
        return self._decode_knowledge_candidate(row)

    def review_knowledge_candidate(
        self,
        *,
        candidate_id: str,
        decision: str,
        reason: str,
        edits: dict[str, Any],
        expected_revision: int,
        promoted_record_id: str | None,
    ) -> dict[str, Any]:
        timestamp = _now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM knowledge_candidates WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            if row is None:
                raise KeyError(candidate_id)
            current_revision = int(row["revision"])
            if current_revision != expected_revision:
                raise RevisionConflictError(
                    expected_revision,
                    current_revision,
                )
            proposed = json.loads(str(row["proposed_content_json"]))
            proposed.update(edits)
            status = {
                "approve": "approved",
                "reject": "rejected",
                "request_changes": "changes_requested",
            }[decision]
            review = {
                "decision": decision,
                "reason": reason,
                "reviewed_by": "human",
                "reviewed_at": timestamp,
            }
            conn.execute(
                """
                UPDATE knowledge_candidates
                SET revision = ?, status = ?, proposed_content_json = ?,
                    review_json = ?, promoted_record_id = ?, updated_at = ?
                WHERE candidate_id = ?
                """,
                (
                    current_revision + 1,
                    status,
                    json.dumps(
                        proposed,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    json.dumps(review, ensure_ascii=False, sort_keys=True),
                    promoted_record_id,
                    timestamp,
                    candidate_id,
                ),
            )
        return self.get_knowledge_candidate(candidate_id)

    def promote_knowledge_candidate(
        self,
        *,
        candidate_id: str,
        expected_revision: int,
        reason: str,
        content: dict[str, Any],
        record_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Approve a candidate and write its authority revision atomically."""

        timestamp = _now()
        with self._connect() as conn:
            candidate = conn.execute(
                "SELECT * FROM knowledge_candidates WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            if candidate is None:
                raise KeyError(candidate_id)
            current_candidate_revision = int(candidate["revision"])
            if current_candidate_revision != expected_revision:
                raise RevisionConflictError(
                    expected_revision,
                    current_candidate_revision,
                )

            existing_record_id = str(
                candidate["promoted_record_id"] or ""
            ).strip()
            resolved_record_id = existing_record_id or record_id
            record = conn.execute(
                "SELECT * FROM knowledge_records WHERE record_id = ?",
                (resolved_record_id,),
            ).fetchone()
            if existing_record_id and record is None:
                raise ValueError(
                    "promoted knowledge record is missing: "
                    f"{existing_record_id}"
                )
            if record is not None and not existing_record_id:
                raise ValueError(
                    f"knowledge record already exists: {resolved_record_id}"
                )
            kind = str(candidate["kind"])
            if record is not None and str(record["kind"]) != kind:
                raise ValueError(
                    f"knowledge record kind mismatch: {resolved_record_id}"
                )

            if record is None:
                record_revision = 1
                conn.execute(
                    """
                    INSERT INTO knowledge_records
                        (record_id, kind, current_revision, status,
                         source_candidate_id, created_at, updated_at)
                    VALUES (?, ?, 1, 'active', ?, ?, ?)
                    """,
                    (
                        resolved_record_id,
                        kind,
                        candidate_id,
                        timestamp,
                        timestamp,
                    ),
                )
            else:
                record_revision = int(record["current_revision"]) + 1
                conn.execute(
                    """
                    UPDATE knowledge_records
                    SET current_revision = ?, status = 'active',
                        updated_at = ?
                    WHERE record_id = ?
                    """,
                    (
                        record_revision,
                        timestamp,
                        resolved_record_id,
                    ),
                )

            conn.execute(
                """
                INSERT INTO knowledge_record_revisions
                    (revision_id, record_id, kind, revision, content_json,
                     content_hash, change_reason, author_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'human', ?)
                """,
                (
                    f"krev_{uuid4().hex[:12]}",
                    resolved_record_id,
                    kind,
                    record_revision,
                    json.dumps(content, ensure_ascii=False, sort_keys=True),
                    _json_hash(content),
                    reason,
                    timestamp,
                ),
            )
            review = {
                "decision": "approve",
                "reason": reason,
                "reviewed_by": "human",
                "reviewed_at": timestamp,
            }
            conn.execute(
                """
                UPDATE knowledge_candidates
                SET revision = ?, status = 'approved',
                    proposed_content_json = ?, review_json = ?,
                    promoted_record_id = ?, updated_at = ?
                WHERE candidate_id = ?
                """,
                (
                    current_candidate_revision + 1,
                    json.dumps(content, ensure_ascii=False, sort_keys=True),
                    json.dumps(review, ensure_ascii=False, sort_keys=True),
                    resolved_record_id,
                    timestamp,
                    candidate_id,
                ),
            )
        return (
            self.get_knowledge_candidate(candidate_id),
            self.get_knowledge_record(resolved_record_id),
        )

    @staticmethod
    def _decode_knowledge_candidate(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["proposed_content"] = json.loads(
            str(item.pop("proposed_content_json"))
        )
        item["source_links"] = json.loads(str(item.pop("source_links_json")))
        item["search_trace"] = json.loads(str(item.pop("search_trace_json")))
        raw_review = item.pop("review_json")
        item["review"] = json.loads(str(raw_review)) if raw_review else None
        return item

    def create_knowledge_record(
        self,
        *,
        record_id: str,
        kind: str,
        content: dict[str, Any],
        change_reason: str,
        source_candidate_id: str | None = None,
    ) -> dict[str, Any]:
        timestamp = _now()
        content_hash = _json_hash(content)
        with self._connect() as conn:
            if conn.execute(
                "SELECT 1 FROM knowledge_records WHERE record_id = ?",
                (record_id,),
            ).fetchone():
                raise ValueError(
                    f"knowledge record already exists: {record_id}"
                )
            conn.execute(
                """
                INSERT INTO knowledge_records
                    (record_id, kind, current_revision, status,
                     source_candidate_id, created_at, updated_at)
                VALUES (?, ?, 1, 'active', ?, ?, ?)
                """,
                (
                    record_id,
                    kind,
                    source_candidate_id,
                    timestamp,
                    timestamp,
                ),
            )
            conn.execute(
                """
                INSERT INTO knowledge_record_revisions
                    (revision_id, record_id, kind, revision, content_json,
                     content_hash, change_reason, author_type, created_at)
                VALUES (?, ?, ?, 1, ?, ?, ?, 'human', ?)
                """,
                (
                    f"krev_{uuid4().hex[:12]}",
                    record_id,
                    kind,
                    json.dumps(content, ensure_ascii=False, sort_keys=True),
                    content_hash,
                    change_reason,
                    timestamp,
                ),
            )
        return self.get_knowledge_record(record_id)

    def list_knowledge_records(
        self,
        kind: str | None = None,
        *,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[str] = []
        if kind:
            clauses.append("r.kind = ?")
            parameters.append(kind)
        if not include_archived:
            clauses.append("r.status = 'active'")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT r.*, v.content_json, v.content_hash,
                       v.change_reason, v.author_type,
                       v.created_at AS revision_created_at
                FROM knowledge_records r
                JOIN knowledge_record_revisions v
                  ON v.record_id = r.record_id
                 AND v.revision = r.current_revision
                {where}
                ORDER BY r.kind, r.record_id
                """,
                parameters,
            ).fetchall()
        return [self._decode_knowledge_record(row) for row in rows]

    def get_knowledge_record(self, record_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT r.*, v.content_json, v.content_hash,
                       v.change_reason, v.author_type,
                       v.created_at AS revision_created_at
                FROM knowledge_records r
                JOIN knowledge_record_revisions v
                  ON v.record_id = r.record_id
                 AND v.revision = r.current_revision
                WHERE r.record_id = ?
                """,
                (record_id,),
            ).fetchone()
        if row is None:
            raise KeyError(record_id)
        return self._decode_knowledge_record(row)

    @staticmethod
    def _decode_knowledge_record(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["revision"] = int(item.pop("current_revision"))
        item["content"] = json.loads(str(item.pop("content_json")))
        return item

    def update_knowledge_record(
        self,
        *,
        record_id: str,
        content: dict[str, Any],
        expected_revision: int,
        change_reason: str,
    ) -> dict[str, Any]:
        timestamp = _now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM knowledge_records WHERE record_id = ?",
                (record_id,),
            ).fetchone()
            if row is None:
                raise KeyError(record_id)
            current_revision = int(row["current_revision"])
            if current_revision != expected_revision:
                raise RevisionConflictError(
                    expected_revision,
                    current_revision,
                )
            revision = current_revision + 1
            conn.execute(
                """
                INSERT INTO knowledge_record_revisions
                    (revision_id, record_id, kind, revision, content_json,
                     content_hash, change_reason, author_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'human', ?)
                """,
                (
                    f"krev_{uuid4().hex[:12]}",
                    record_id,
                    str(row["kind"]),
                    revision,
                    json.dumps(content, ensure_ascii=False, sort_keys=True),
                    _json_hash(content),
                    change_reason,
                    timestamp,
                ),
            )
            conn.execute(
                """
                UPDATE knowledge_records
                SET current_revision = ?, updated_at = ?
                WHERE record_id = ?
                """,
                (revision, timestamp, record_id),
            )
        return self.get_knowledge_record(record_id)

    def list_knowledge_record_revisions(
        self,
        record_id: str,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if conn.execute(
                "SELECT 1 FROM knowledge_records WHERE record_id = ?",
                (record_id,),
            ).fetchone() is None:
                raise KeyError(record_id)
            rows = conn.execute(
                """
                SELECT revision_id, record_id, kind, revision, content_hash,
                       change_reason, author_type, created_at
                FROM knowledge_record_revisions
                WHERE record_id = ?
                ORDER BY revision DESC
                """,
                (record_id,),
            ).fetchall()
        return [dict(row) for row in rows]

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
