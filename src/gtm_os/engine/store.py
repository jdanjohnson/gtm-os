"""SQLite store — schema, migrations, CRUD for all tables.

Single-writer SQLite design with WAL mode. All access goes through this class so callers
don't have to think about connections.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..types import Experiment, Memory, MemoryType, Run, Schedule

SCHEMA_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS experiments (
        id              TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        description     TEXT,
        hypothesis      TEXT,
        phase           TEXT NOT NULL DEFAULT 'design',
        play_ids        TEXT,
        current_agent   TEXT,
        config          TEXT,
        schedule_id     TEXT,
        token_budget    INTEGER DEFAULT 200000,
        tokens_used     INTEGER DEFAULT 0,
        created_at      TEXT DEFAULT (datetime('now')),
        updated_at      TEXT DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS runs (
        id              TEXT PRIMARY KEY,
        experiment_id   TEXT NOT NULL,
        phase           TEXT NOT NULL,
        status          TEXT NOT NULL DEFAULT 'pending',
        input_context   TEXT,
        output          TEXT,
        tools_used      TEXT,
        tokens_used     INTEGER DEFAULT 0,
        started_at      TEXT,
        completed_at    TEXT,
        error           TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS checkpoints (
        id              TEXT PRIMARY KEY,
        experiment_id   TEXT NOT NULL,
        run_id          TEXT NOT NULL,
        step_name       TEXT NOT NULL,
        result          TEXT,
        created_at      TEXT DEFAULT (datetime('now')),
        UNIQUE(run_id, step_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id              TEXT PRIMARY KEY,
        role            TEXT NOT NULL,
        content         TEXT NOT NULL,
        tool_calls      TEXT,
        tool_call_id    TEXT,
        name            TEXT,
        experiment_id   TEXT,
        thread_id       TEXT,
        created_at      TEXT DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memory (
        id              TEXT PRIMARY KEY,
        type            TEXT NOT NULL,
        content         TEXT NOT NULL,
        source          TEXT,
        experiment_id   TEXT,
        confidence      REAL DEFAULT 0.5,
        reinforced_by   TEXT,
        embedding       BLOB,
        created_at      TEXT DEFAULT (datetime('now')),
        updated_at      TEXT DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS schedules (
        id                    TEXT PRIMARY KEY,
        experiment_id         TEXT,
        type                  TEXT NOT NULL,
        cron_expr             TEXT,
        interval_seconds      INTEGER,
        next_run_at           TEXT NOT NULL,
        last_run_at           TEXT,
        enabled               INTEGER DEFAULT 1,
        consecutive_failures  INTEGER DEFAULT 0,
        max_cost              REAL,
        cost_spent            REAL DEFAULT 0,
        config                TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_runs_experiment ON runs(experiment_id, started_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_messages_experiment ON messages(experiment_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_memory_type ON memory(type)",
    "CREATE INDEX IF NOT EXISTS idx_schedules_due ON schedules(enabled, next_run_at)",
]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex


class Store:
    """Thin SQLite store with thread-safe access via an internal lock."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self.db_path), check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            for stmt in SCHEMA_STATEMENTS:
                self._conn.execute(stmt)
        # WS6: Initialize sqlite-vec if available.
        try:
            from .vec_search import init_vec_table

            init_vec_table(self._conn)
        except Exception:
            pass

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---------- experiments ----------

    def create_experiment(
        self,
        name: str,
        *,
        description: str | None = None,
        hypothesis: str | None = None,
        play_ids: list[str] | None = None,
        config: dict[str, Any] | None = None,
        token_budget: int = 200_000,
        phase: str = "design",
    ) -> Experiment:
        exp_id = _new_id()
        now = _now()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO experiments(
                    id, name, description, hypothesis, phase, play_ids, config,
                    token_budget, tokens_used, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,0,?,?)
                """,
                (
                    exp_id,
                    name,
                    description,
                    hypothesis,
                    phase,
                    json.dumps(play_ids or []),
                    json.dumps(config or {}),
                    int(token_budget),
                    now,
                    now,
                ),
            )
        return self.get_experiment(exp_id)  # type: ignore[return-value]

    def get_experiment(self, exp_id: str) -> Experiment | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM experiments WHERE id = ?", (exp_id,)).fetchone()
        return _row_to_experiment(row) if row else None

    def list_experiments(
        self,
        *,
        phase: str | None = None,
        limit: int = 100,
    ) -> list[Experiment]:
        sql = "SELECT * FROM experiments"
        params: list[Any] = []
        if phase:
            sql += " WHERE phase = ?"
            params.append(phase)
        sql += " ORDER BY datetime(updated_at) DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_experiment(r) for r in rows]

    def update_experiment(self, exp_id: str, **fields: Any) -> Experiment | None:
        if not fields:
            return self.get_experiment(exp_id)
        allowed = {
            "name",
            "description",
            "hypothesis",
            "phase",
            "play_ids",
            "current_agent",
            "config",
            "schedule_id",
            "token_budget",
            "tokens_used",
        }
        sets = []
        params: list[Any] = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k in {"play_ids", "config"}:
                v = json.dumps(v)
            sets.append(f"{k} = ?")
            params.append(v)
        if not sets:
            return self.get_experiment(exp_id)
        sets.append("updated_at = ?")
        params.append(_now())
        params.append(exp_id)
        with self._lock, self._conn:
            self._conn.execute(f"UPDATE experiments SET {', '.join(sets)} WHERE id = ?", params)
        return self.get_experiment(exp_id)

    def add_experiment_tokens(self, exp_id: str, tokens: int) -> None:
        if tokens <= 0:
            return
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE experiments SET tokens_used = tokens_used + ?, updated_at = ? WHERE id = ?",
                (int(tokens), _now(), exp_id),
            )

    # ---------- runs ----------

    def start_run(self, experiment_id: str, phase: str, input_context: dict | None) -> Run:
        run_id = _new_id()
        now = _now()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO runs(id, experiment_id, phase, status, input_context, started_at)
                VALUES(?,?,?,?,?,?)
                """,
                (
                    run_id,
                    experiment_id,
                    phase,
                    "running",
                    json.dumps(input_context or {}),
                    now,
                ),
            )
        return self.get_run(run_id)  # type: ignore[return-value]

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        output: dict | None = None,
        tools_used: list[dict] | None = None,
        tokens_used: int = 0,
        error: str | None = None,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE runs
                SET status = ?, output = ?, tools_used = ?, tokens_used = ?,
                    completed_at = ?, error = ?
                WHERE id = ?
                """,
                (
                    status,
                    json.dumps(output or {}),
                    json.dumps(tools_used or []),
                    int(tokens_used),
                    _now(),
                    error,
                    run_id,
                ),
            )

    def get_run(self, run_id: str) -> Run | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return _row_to_run(row) if row else None

    def list_runs(self, experiment_id: str, limit: int = 20) -> list[Run]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM runs WHERE experiment_id = ?
                ORDER BY datetime(started_at) DESC LIMIT ?
                """,
                (experiment_id, limit),
            ).fetchall()
        return [_row_to_run(r) for r in rows]

    def find_orphan_runs(self, older_than_minutes: int = 90) -> list[Run]:
        """Runs that have been 'running' for too long — likely orphaned by a crash."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM runs
                WHERE status = 'running'
                  AND started_at IS NOT NULL
                  AND (julianday('now') - julianday(started_at)) * 24 * 60 > ?
                """,
                (older_than_minutes,),
            ).fetchall()
        return [_row_to_run(r) for r in rows]

    # ---------- checkpoints ----------

    def save_checkpoint(self, experiment_id: str, run_id: str, step_name: str, result: Any) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO checkpoints(id, experiment_id, run_id, step_name, result)
                VALUES(?,?,?,?,?)
                ON CONFLICT(run_id, step_name) DO UPDATE SET result = excluded.result
                """,
                (_new_id(), experiment_id, run_id, step_name, json.dumps(result)),
            )

    def get_checkpoint(self, run_id: str, step_name: str) -> Any | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT result FROM checkpoints WHERE run_id = ? AND step_name = ?",
                (run_id, step_name),
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["result"])
        except (json.JSONDecodeError, TypeError):
            return row["result"]

    # ---------- messages ----------

    def add_message(
        self,
        *,
        role: str,
        content: str,
        thread_id: str | None = None,
        experiment_id: str | None = None,
        tool_calls: list[dict] | None = None,
        tool_call_id: str | None = None,
        name: str | None = None,
    ) -> str:
        msg_id = _new_id()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO messages(
                    id, role, content, tool_calls, tool_call_id, name,
                    experiment_id, thread_id, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    msg_id,
                    role,
                    content,
                    json.dumps(tool_calls) if tool_calls else None,
                    tool_call_id,
                    name,
                    experiment_id,
                    thread_id,
                    _now(),
                ),
            )
        return msg_id

    def list_messages(
        self,
        *,
        thread_id: str | None = None,
        experiment_id: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM messages WHERE 1=1"
        params: list[Any] = []
        if thread_id:
            sql += " AND thread_id = ?"
            params.append(thread_id)
        if experiment_id:
            sql += " AND experiment_id = ?"
            params.append(experiment_id)
        sql += " ORDER BY datetime(created_at) ASC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            if d.get("tool_calls"):
                try:
                    d["tool_calls"] = json.loads(d["tool_calls"])
                except json.JSONDecodeError:
                    d["tool_calls"] = None
            out.append(d)
        return out

    # ---------- memory ----------

    def insert_memory(
        self,
        *,
        type: MemoryType,
        content: str,
        source: str | None,
        experiment_id: str | None,
        confidence: float,
        embedding: bytes | None,
    ) -> Memory:
        mem_id = _new_id()
        now = _now()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO memory(
                    id, type, content, source, experiment_id, confidence,
                    reinforced_by, embedding, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    mem_id,
                    type,
                    content,
                    source,
                    experiment_id,
                    float(confidence),
                    json.dumps([]),
                    embedding,
                    now,
                    now,
                ),
            )
        return self.get_memory(mem_id)  # type: ignore[return-value]

    def get_memory(self, memory_id: str) -> Memory | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM memory WHERE id = ?", (memory_id,)).fetchone()
        return _row_to_memory(row) if row else None

    def all_memory_rows(self, type_filter: str | None = None) -> Iterable[sqlite3.Row]:
        sql = "SELECT * FROM memory"
        params: list[Any] = []
        if type_filter:
            sql += " WHERE type = ?"
            params.append(type_filter)
        with self._lock:
            return list(self._conn.execute(sql, params).fetchall())

    def update_memory_confidence(
        self, memory_id: str, *, confidence: float, reinforced_by: list[str]
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE memory SET confidence = ?, reinforced_by = ?, updated_at = ?
                WHERE id = ?
                """,
                (float(confidence), json.dumps(reinforced_by), _now(), memory_id),
            )

    def list_memories(
        self,
        *,
        type_filter: str | None = None,
        limit: int = 100,
    ) -> list[Memory]:
        sql = "SELECT * FROM memory"
        params: list[Any] = []
        if type_filter:
            sql += " WHERE type = ?"
            params.append(type_filter)
        sql += " ORDER BY datetime(updated_at) DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_memory(r) for r in rows]

    # ---------- schedules ----------

    def insert_schedule(self, sched: Schedule) -> Schedule:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO schedules(
                    id, experiment_id, type, cron_expr, interval_seconds,
                    next_run_at, last_run_at, enabled, consecutive_failures,
                    max_cost, cost_spent, config
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    sched.id,
                    sched.experiment_id,
                    sched.type,
                    sched.cron_expr,
                    sched.interval_seconds,
                    sched.next_run_at,
                    sched.last_run_at,
                    int(bool(sched.enabled)),
                    int(sched.consecutive_failures),
                    sched.max_cost,
                    float(sched.cost_spent),
                    json.dumps(sched.config),
                ),
            )
        return sched

    def get_schedule(self, schedule_id: str) -> Schedule | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
            ).fetchone()
        return _row_to_schedule(row) if row else None

    def list_schedules(self, *, only_enabled: bool = False) -> list[Schedule]:
        sql = "SELECT * FROM schedules"
        if only_enabled:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY datetime(next_run_at) ASC"
        with self._lock:
            rows = self._conn.execute(sql).fetchall()
        return [_row_to_schedule(r) for r in rows]

    def due_schedules(self, *, now: str | None = None, limit: int = 10) -> list[Schedule]:
        now = now or _now()
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM schedules
                WHERE enabled = 1 AND next_run_at <= ?
                ORDER BY datetime(next_run_at) ASC LIMIT ?
                """,
                (now, limit),
            ).fetchall()
        return [_row_to_schedule(r) for r in rows]

    def update_schedule(self, schedule_id: str, **fields: Any) -> Schedule | None:
        allowed = {
            "next_run_at",
            "last_run_at",
            "enabled",
            "consecutive_failures",
            "max_cost",
            "cost_spent",
            "cron_expr",
            "interval_seconds",
            "config",
        }
        sets: list[str] = []
        params: list[Any] = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == "config":
                v = json.dumps(v)
            if k == "enabled":
                v = int(bool(v))
            sets.append(f"{k} = ?")
            params.append(v)
        if not sets:
            return self.get_schedule(schedule_id)
        params.append(schedule_id)
        with self._lock, self._conn:
            self._conn.execute(f"UPDATE schedules SET {', '.join(sets)} WHERE id = ?", params)
        return self.get_schedule(schedule_id)

    def delete_schedule(self, schedule_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))


def _row_to_experiment(row: sqlite3.Row) -> Experiment:
    return Experiment(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        hypothesis=row["hypothesis"],
        phase=row["phase"],
        play_ids=_json_or(row["play_ids"], []),
        current_agent=row["current_agent"],
        config=_json_or(row["config"], {}),
        schedule_id=row["schedule_id"],
        token_budget=int(row["token_budget"] or 0),
        tokens_used=int(row["tokens_used"] or 0),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_run(row: sqlite3.Row) -> Run:
    return Run(
        id=row["id"],
        experiment_id=row["experiment_id"],
        phase=row["phase"],
        status=row["status"],
        input_context=_json_or(row["input_context"], None),
        output=_json_or(row["output"], None),
        tools_used=_json_or(row["tools_used"], []),
        tokens_used=int(row["tokens_used"] or 0),
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        error=row["error"],
    )


def _row_to_memory(row: sqlite3.Row) -> Memory:
    return Memory(
        id=row["id"],
        type=row["type"],
        content=row["content"],
        source=row["source"],
        experiment_id=row["experiment_id"],
        confidence=float(row["confidence"] or 0.0),
        reinforced_by=_json_or(row["reinforced_by"], []),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_schedule(row: sqlite3.Row) -> Schedule:
    return Schedule(
        id=row["id"],
        experiment_id=row["experiment_id"],
        type=row["type"],
        cron_expr=row["cron_expr"],
        interval_seconds=row["interval_seconds"],
        next_run_at=row["next_run_at"],
        last_run_at=row["last_run_at"],
        enabled=bool(row["enabled"]),
        consecutive_failures=int(row["consecutive_failures"] or 0),
        max_cost=row["max_cost"],
        cost_spent=float(row["cost_spent"] or 0.0),
        config=_json_or(row["config"], {}),
    )


def _json_or(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default
