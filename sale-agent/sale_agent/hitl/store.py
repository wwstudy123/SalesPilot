"""HITL 通用机制：proposal 表 + 30min 过期 + 同字段提案合并（架构 §7.3）。

approval_token 本身由 business-mock 签发与消费（审批凭证表 + 校验切面），
本表承载 AI 侧提案编排状态：pending → confirmed / rejected / expired。
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROPOSAL_TTL = timedelta(minutes=30)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS proposal (
    id TEXT PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    employee_id INTEGER NOT NULL,
    tool TEXT NOT NULL,
    fields TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    run_id TEXT NULL,
    source TEXT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    resolved_at TEXT NULL,
    CONSTRAINT ck_proposal_status CHECK (status IN ('pending', 'confirmed', 'rejected', 'expired'))
);
CREATE INDEX IF NOT EXISTS idx_proposal_customer ON proposal (customer_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class ProposalStore:
    def __init__(self, db_path: str | None = None) -> None:
        path = Path(db_path or os.environ.get("SALE_PROPOSAL_DB", "") or Path("output") / "ai" / "proposals.db")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # ---------- 写入 ----------

    def create_or_merge(
        self,
        customer_id: int,
        employee_id: int,
        tool: str,
        fields: list[dict],
        run_id: str | None = None,
        source: str | None = None,
    ) -> tuple[dict, bool]:
        """同客户同工具存在 pending 提案时按 fieldKey 合并进原提案（不新增，架构 v1.1）。

        返回 (提案, merged)。
        """
        with self._lock:
            self._expire_locked()
            row = self._conn.execute(
                "SELECT * FROM proposal WHERE customer_id = ? AND tool = ? AND status = 'pending'",
                (customer_id, tool),
            ).fetchone()
            expires = _now_plus_ttl()
            if row is None:
                proposal_id = uuid.uuid4().hex
                self._conn.execute(
                    "INSERT INTO proposal (id, customer_id, employee_id, tool, fields, status,"
                    " run_id, source, created_at, expires_at) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)",
                    (proposal_id, customer_id, employee_id, tool, json.dumps(fields, ensure_ascii=False), run_id, source, _now(), expires),
                )
                self._conn.commit()
                return self._row_to_dict(self._get_locked(proposal_id)), False
            merged = _merge_fields(json.loads(row["fields"]), fields)
            self._conn.execute(
                "UPDATE proposal SET fields = ?, expires_at = ?, run_id = COALESCE(?, run_id) WHERE id = ?",
                (json.dumps(merged, ensure_ascii=False), expires, run_id, row["id"]),
            )
            self._conn.commit()
            return self._row_to_dict(self._get_locked(row["id"])), True

    def resolve(self, proposal_id: str, status: str) -> dict | None:
        """confirm/reject 的本地状态收尾（business-mock 执行成功后调用）。"""
        with self._lock:
            self._conn.execute(
                "UPDATE proposal SET status = ?, resolved_at = ? WHERE id = ? AND status = 'pending'",
                (status, _now(), proposal_id),
            )
            self._conn.commit()
            row = self._get_locked(proposal_id)
        return self._row_to_dict(row) if row else None

    def expire_pending(self) -> int:
        with self._lock:
            return self._expire_locked()

    # ---------- 读取 ----------

    def get(self, proposal_id: str) -> dict | None:
        with self._lock:
            self._expire_locked()
            row = self._get_locked(proposal_id)
        return self._row_to_dict(row) if row else None

    def list(self, customer_id: int | None = None, status: str | None = None) -> list[dict]:
        with self._lock:
            self._expire_locked()
            sql, args = "SELECT * FROM proposal", []
            clauses = []
            if customer_id is not None:
                clauses.append("customer_id = ?")
                args.append(customer_id)
            if status:
                clauses.append("status = ?")
                args.append(status)
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            rows = self._conn.execute(sql + " ORDER BY created_at DESC", args).fetchall()
        return [self._row_to_dict(row) for row in rows]

    # ---------- 内部 ----------

    def _get_locked(self, proposal_id: str) -> sqlite3.Row | None:
        return self._conn.execute("SELECT * FROM proposal WHERE id = ?", (proposal_id,)).fetchone()

    def _expire_locked(self) -> int:
        cursor = self._conn.execute(
            "UPDATE proposal SET status = 'expired', resolved_at = ? WHERE status = 'pending' AND expires_at <= ?",
            (_now(), _now()),
        )
        self._conn.commit()
        return cursor.rowcount

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        data = dict(row)
        data["fields"] = json.loads(data["fields"])
        return data


def _now_plus_ttl() -> str:
    return (datetime.now(timezone.utc) + PROPOSAL_TTL).isoformat(timespec="milliseconds")


def _merge_fields(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """同字段提案合并：incoming 按 fieldKey 覆盖既有，其余保留。"""
    by_key = {item["fieldKey"]: item for item in existing}
    for item in incoming:
        by_key[item["fieldKey"]] = item
    return sorted(by_key.values(), key=lambda item: item["fieldKey"])
