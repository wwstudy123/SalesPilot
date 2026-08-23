"""审计闸门：每次工具调用写 tool_call_log（含 bypass/cache_hit/replayed/拒绝原因）。"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tool_call_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    tool TEXT NOT NULL,
    actor_id INTEGER NULL,
    customer_id INTEGER NULL,
    status TEXT NOT NULL,
    http_status INTEGER NULL,
    latency_ms INTEGER NULL,
    bypass INTEGER NOT NULL DEFAULT 0,
    cache_hit INTEGER NOT NULL DEFAULT 0,
    replayed INTEGER NOT NULL DEFAULT 0,
    idempotency_key TEXT NULL,
    error_code TEXT NULL
);
CREATE INDEX IF NOT EXISTS idx_tool_call_log_tool ON tool_call_log (tool);
"""


class AuditStore:
    def __init__(self, db_path: str | None = None) -> None:
        path = Path(db_path or os.environ.get("SALE_MCP_AUDIT_DB", "") or Path("output") / "ai" / "mcp_audit.db")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def log(
        self,
        *,
        tool: str,
        actor_id: int | None,
        customer_id: int | None,
        status: str,  # ok / denied / upstream_error
        http_status: int | None = None,
        latency_ms: int | None = None,
        bypass: bool = False,
        cache_hit: bool = False,
        replayed: bool = False,
        idempotency_key: str | None = None,
        error_code: str | None = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO tool_call_log (created_at, tool, actor_id, customer_id, status, http_status,
                    latency_ms, bypass, cache_hit, replayed, idempotency_key, error_code)
                VALUES (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tool,
                    actor_id,
                    customer_id,
                    status,
                    http_status,
                    latency_ms,
                    int(bypass),
                    int(cache_hit),
                    int(replayed),
                    idempotency_key,
                    error_code,
                ),
            )
            self._conn.commit()

    def recent(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM tool_call_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]
