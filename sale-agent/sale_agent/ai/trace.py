"""Trace 最小版：agent_run + agent_span 落 SQLite，支撑"一次请求可查 Run"。"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_run (
    run_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT,
    intent TEXT,
    routing_reason TEXT,
    confidence REAL,
    status TEXT NOT NULL DEFAULT 'running',
    started_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_agent_run_session ON agent_run (session_id);

CREATE TABLE IF NOT EXISTS agent_span (
    span_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES agent_run (run_id),
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    started_at TEXT NOT NULL,
    finished_at TEXT,
    detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_agent_span_run ON agent_span (run_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class TraceStore:
    def __init__(self, db_path: str | None = None) -> None:
        path = Path(db_path or os.environ.get("SALE_TRACE_DB", "") or Path("output") / "ai" / "trace.db")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            try:
                # M3 增量列：旧 dev 库兼容（SQLite 不支持 ADD COLUMN IF NOT EXISTS）
                self._conn.execute("ALTER TABLE agent_run ADD COLUMN decision_path TEXT")
            except sqlite3.OperationalError:
                pass
            self._conn.commit()

    # ---------- run ----------

    def start_run(self, session_id: str, user_id: str | None = None) -> str:
        run_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                "INSERT INTO agent_run (run_id, session_id, user_id, status, started_at) VALUES (?, ?, ?, 'running', ?)",
                (run_id, session_id, user_id, _now()),
            )
            self._conn.commit()
        return run_id

    def finish_run(
        self,
        run_id: str,
        status: str,
        intent: str | None = None,
        routing_reason: str | None = None,
        confidence: float | None = None,
        decision_path: str | None = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE agent_run SET status = ?, finished_at = ?,"
                " intent = COALESCE(?, intent),"
                " routing_reason = COALESCE(?, routing_reason),"
                " confidence = COALESCE(?, confidence),"
                " decision_path = COALESCE(?, decision_path)"
                " WHERE run_id = ?",
                (status, _now(), intent, routing_reason, confidence, decision_path, run_id),
            )
            self._conn.commit()

    def get_run(self, run_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM agent_run WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def list_runs(
        self,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        intent: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        clauses: list[str] = []
        args: list[object] = []
        for column, value in (("session_id", session_id), ("user_id", user_id), ("intent", intent), ("status", status)):
            if value:
                clauses.append(f"{column} = ?")
                args.append(value)
        sql = "SELECT * FROM agent_run"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY started_at DESC LIMIT ?"
        args.append(min(max(limit, 1), 200))
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        return [dict(row) for row in rows]

    # ---------- span ----------

    def start_span(self, run_id: str, name: str) -> str:
        span_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                "INSERT INTO agent_span (span_id, run_id, name, status, started_at) VALUES (?, ?, ?, 'running', ?)",
                (span_id, run_id, name, _now()),
            )
            self._conn.commit()
        return span_id

    def finish_span(self, span_id: str, status: str, detail: dict | None = None) -> None:
        payload = json.dumps(detail, ensure_ascii=False) if detail else None
        with self._lock:
            self._conn.execute(
                "UPDATE agent_span SET status = ?, finished_at = ?, detail = ? WHERE span_id = ?",
                (status, _now(), payload, span_id),
            )
            self._conn.commit()

    def list_spans(self, run_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM agent_span WHERE run_id = ? ORDER BY started_at", (run_id,)).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
