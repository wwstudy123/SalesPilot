"""建议卡存储（架构 §6.2 suggestion / suggestion_action）：话术建议的 HITL 行为记录。

采纳(可编辑)/重新生成(≤2,附要求)/拒绝(必填原因)；行为全量落 suggestion_action，
回流评测池（架构 §2.7 员工行为即评测）。
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS suggestion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    employee_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'talk_script',
    skill TEXT NOT NULL,
    content TEXT NOT NULL,
    citations TEXT NOT NULL DEFAULT '[]',
    warnings TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending',
    regenerate_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    CONSTRAINT ck_sug_status CHECK (status IN ('pending', 'adopted', 'modified', 'rejected'))
);
CREATE TABLE IF NOT EXISTS suggestion_action (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    suggestion_id INTEGER NOT NULL REFERENCES suggestion(id),
    action TEXT NOT NULL,
    reason TEXT,
    edited_content TEXT,
    created_at TEXT NOT NULL,
    CONSTRAINT ck_act_type CHECK (action IN ('create', 'adopt', 'modify', 'regenerate', 'reject'))
);
CREATE INDEX IF NOT EXISTS idx_sug_customer ON suggestion (customer_id, status);
"""

REGENERATE_LIMIT = 2


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class RegenerateLimitError(Exception):
    """重新生成次数超限（≤2）。"""


class SuggestionStore:
    def __init__(self, db_path: str | None = None) -> None:
        path = Path(db_path or os.environ.get("SALE_SUGGESTION_DB", "") or Path("output") / "ai" / "suggestions.db")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # ---------- 创建 / 查询 ----------

    def create(
        self,
        *,
        customer_id: int,
        employee_id: int,
        session_id: str,
        run_id: str,
        skill: str,
        content: str,
        citations: list[dict],
        warnings: list[str],
        kind: str = "talk_script",
    ) -> dict:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO suggestion (customer_id, employee_id, session_id, run_id, kind, skill,"
                " content, citations, warnings, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    customer_id,
                    employee_id,
                    session_id,
                    run_id,
                    kind,
                    skill,
                    content,
                    json.dumps(citations, ensure_ascii=False),
                    json.dumps(warnings, ensure_ascii=False),
                    _now(),
                ),
            )
            suggestion_id = cursor.lastrowid
            self._conn.execute(
                "INSERT INTO suggestion_action (suggestion_id, action, created_at) VALUES (?, 'create', ?)",
                (suggestion_id, _now()),
            )
            self._conn.commit()
        return self.get(suggestion_id)

    def get(self, suggestion_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM suggestion WHERE id = ?", (suggestion_id,)).fetchone()
        return self._to_dict(row) if row else None

    def list(self, customer_id: int | None = None, status: str | None = None) -> list[dict]:
        sql = "SELECT * FROM suggestion WHERE 1 = 1"
        args: list = []
        if customer_id is not None:
            sql += " AND customer_id = ?"
            args.append(customer_id)
        if status:
            sql += " AND status = ?"
            args.append(status)
        with self._lock:
            rows = self._conn.execute(sql + " ORDER BY id DESC LIMIT 100", args).fetchall()
        return [self._to_dict(row) for row in rows]

    def actions(self, suggestion_id: int) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM suggestion_action WHERE suggestion_id = ? ORDER BY id", (suggestion_id,)).fetchall()
        return [dict(row) for row in rows]

    # ---------- HITL 行为 ----------

    def adopt(self, suggestion_id: int, edited_content: str | None = None) -> dict:
        """采纳；附编辑内容且与原文不同 → modified（修正即时记录）。"""
        return self._resolve(
            suggestion_id,
            edited_content=edited_content,
            resolve=lambda current: (
                ("modified", "modify") if edited_content and edited_content.strip() != current["content"] else ("adopted", "adopt")
            ),
        )

    def reject(self, suggestion_id: int, reason: str) -> dict:
        """拒绝（原因必填，由路由层校验非空）。"""
        return self._resolve(suggestion_id, reason=reason, resolve=lambda _: ("rejected", "reject"))

    def regenerate(self, suggestion_id: int, requirement: str, new_content: str, citations: list[dict], warnings: list[str]) -> dict:
        """重新生成（≤2 次）：要求落 action，内容替换，状态保持 pending。"""
        with self._lock:
            row = self._lock_fetch(suggestion_id)
            if row["status"] != "pending":
                raise ValueError(f"建议已{row['status']}，不可重新生成")
            if row["regenerate_count"] >= REGENERATE_LIMIT:
                raise RegenerateLimitError("重新生成次数已达上限（≤2）")
            self._conn.execute(
                "UPDATE suggestion SET content = ?, citations = ?, warnings = ?, regenerate_count = regenerate_count + 1 WHERE id = ?",
                (new_content, json.dumps(citations, ensure_ascii=False), json.dumps(warnings, ensure_ascii=False), suggestion_id),
            )
            self._conn.execute(
                "INSERT INTO suggestion_action (suggestion_id, action, reason, created_at) VALUES (?, 'regenerate', ?, ?)",
                (suggestion_id, requirement, _now()),
            )
            self._conn.commit()
        return self.get(suggestion_id)

    # ---------- 内部 ----------

    def _resolve(self, suggestion_id: int, resolve, *, edited_content: str | None = None, reason: str | None = None) -> dict:
        with self._lock:
            current = self._lock_fetch(suggestion_id)
            if current["status"] != "pending":
                raise ValueError(f"建议已{current['status']}，操作被拒绝")
            status, action = resolve(current)
            content = edited_content if (status == "modified" and edited_content) else current["content"]
            self._conn.execute(
                "UPDATE suggestion SET status = ?, content = ?, resolved_at = ? WHERE id = ?",
                (status, content, _now(), suggestion_id),
            )
            self._conn.execute(
                "INSERT INTO suggestion_action (suggestion_id, action, reason, edited_content, created_at) VALUES (?, ?, ?, ?, ?)",
                (suggestion_id, action, reason, edited_content, _now()),
            )
            self._conn.commit()
        return self.get(suggestion_id)

    def _lock_fetch(self, suggestion_id: int) -> dict:
        row = self._conn.execute("SELECT * FROM suggestion WHERE id = ?", (suggestion_id,)).fetchone()
        if row is None:
            raise KeyError(f"建议不存在: {suggestion_id}")
        return self._to_dict(row)

    @staticmethod
    def _to_dict(row: sqlite3.Row) -> dict:
        item = dict(row)
        item["citations"] = json.loads(item["citations"] or "[]")
        item["warnings"] = json.loads(item["warnings"] or "[]")
        return item
