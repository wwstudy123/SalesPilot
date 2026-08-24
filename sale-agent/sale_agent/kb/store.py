"""知识库存储（架构 §6.2/6.3）：knowledge_doc / knowledge_chunk。

MVP lite 形态：向量与元数据同落 SQLite（Milvus 接入后 chunk.vector 改回查
collection，接口不变）；入库走 staging → 原子切换 ready，检索只读 ready。
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from sale_agent.intent.embedding import _bigrams

if TYPE_CHECKING:
    from sale_agent.kb.vector_store import VectorBackend

_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_doc (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'staging',
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    CONSTRAINT ck_doc_status CHECK (status IN ('staging', 'ready', 'archived')),
    CONSTRAINT ck_doc_domain CHECK (domain IN ('playbook', 'product'))
);
CREATE TABLE IF NOT EXISTS knowledge_chunk (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES knowledge_doc(id),
    seq INTEGER NOT NULL,
    content TEXT NOT NULL,
    vector TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunk_doc ON knowledge_chunk (doc_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class KnowledgeStore:
    def __init__(self, db_path: str | None = None, vector_backend: VectorBackend | None = None) -> None:
        path = Path(db_path or os.environ.get("SALE_KNOWLEDGE_DB", "") or Path("output") / "ai" / "knowledge.db")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._vector_backend = vector_backend
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # ---------- 入库管线：切片 → 向量化 → staging → 原子切换 ----------

    def ingest(self, domain: str, title: str, source: str, texts: list[str]) -> dict:
        """写入 staging 版本文档；publish 前不参与检索。"""
        chunks = [chunk for text in texts for chunk in split_chunks(text)]
        if not chunks:
            raise ValueError("文档内容为空")
        with self._lock:
            version = self._next_version_locked(domain, source)
            cursor = self._conn.execute(
                "INSERT INTO knowledge_doc (domain, title, source, version, status, chunk_count, created_at)"
                " VALUES (?, ?, ?, ?, 'staging', ?, ?)",
                (domain, title, source, version, len(chunks), _now()),
            )
            doc_id = cursor.lastrowid
            self._conn.executemany(
                "INSERT INTO knowledge_chunk (doc_id, seq, content, vector) VALUES (?, ?, ?, ?)",
                [(doc_id, seq, content, json.dumps(dict(_bigrams(content)), ensure_ascii=False)) for seq, content in enumerate(chunks)],
            )
            self._conn.commit()
        return {"doc_id": doc_id, "domain": domain, "version": version, "chunk_count": len(chunks)}

    def publish(self, domain: str, source: str) -> dict:
        """原子切换：staging 置 ready，同 source 旧 ready 归档（单事务）。"""
        with self._lock:
            old_ready_ids = [
                row["id"]
                for row in self._conn.execute(
                    "SELECT id FROM knowledge_doc WHERE domain = ? AND source = ? AND status = 'ready'",
                    (domain, source),
                ).fetchall()
            ]
            staging_rows = self._conn.execute(
                "SELECT id FROM knowledge_doc WHERE domain = ? AND source = ? AND status = 'staging'",
                (domain, source),
            ).fetchall()
            self._conn.execute(
                "UPDATE knowledge_doc SET status = 'archived' WHERE domain = ? AND source = ? AND status = 'ready'",
                (domain, source),
            )
            cursor = self._conn.execute(
                "UPDATE knowledge_doc SET status = 'ready' WHERE domain = ? AND source = ? AND status = 'staging'",
                (domain, source),
            )
            self._conn.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"无 staging 文档可发布: {domain}/{source}")
        # SQLite 元数据先提交，Milvus 仅作可重建索引；失败时继续走 lite 检索。
        self._sync_vectors(domain, [row["id"] for row in staging_rows], old_ready_ids)
        return {"domain": domain, "source": source, "published": cursor.rowcount}

    # ---------- 检索读取（仅 ready） ----------

    def ready_chunks(self, domain: str | None = None) -> list[dict]:
        """返回 ready 切片（内存向量反序列化）；lite 规模全量载入。"""
        sql = (
            "SELECT c.id, c.doc_id, c.content, c.vector, d.title, d.domain"
            " FROM knowledge_chunk c JOIN knowledge_doc d ON d.id = c.doc_id"
            " WHERE d.status = 'ready'"
        )
        args: tuple = ()
        if domain:
            sql += " AND d.domain = ?"
            args = (domain,)
        with self._lock:
            rows = self._conn.execute(sql + " ORDER BY c.doc_id, c.seq", args).fetchall()
        return [
            {
                "chunk_id": row["id"],
                "doc_id": row["doc_id"],
                "title": row["title"],
                "domain": row["domain"],
                "content": row["content"],
                "vector": Counter(json.loads(row["vector"])),
            }
            for row in rows
        ]

    def stats(self) -> dict:
        with self._lock:
            docs = self._conn.execute("SELECT domain, status, COUNT(*) AS n FROM knowledge_doc GROUP BY domain, status").fetchall()
            chunks = self._conn.execute(
                "SELECT COUNT(*) AS n FROM knowledge_chunk c JOIN knowledge_doc d ON d.id = c.doc_id WHERE d.status = 'ready'"
            ).fetchone()
        return {
            "docs": [{"domain": row["domain"], "status": row["status"], "count": row["n"]} for row in docs],
            "ready_chunks": chunks["n"],
        }

    # ---------- 内部 ----------

    def _sync_vectors(self, domain: str, new_doc_ids: list[int], old_doc_ids: list[int]) -> None:
        backend = self._vector_backend
        if backend is None:
            return
        try:
            if not backend.is_available():
                return
            for doc_id in new_doc_ids:
                backend.upsert(domain, doc_id, self._chunks_for_doc(doc_id))
            for doc_id in old_doc_ids:
                backend.delete_doc(domain, doc_id)
        except Exception:  # noqa: BLE001
            # 向量库不可用不影响 MySQL/SQLite 主数据和 lite RAG 路径。
            return

    def _chunks_for_doc(self, doc_id: int) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, content FROM knowledge_chunk WHERE doc_id = ? ORDER BY seq",
                (doc_id,),
            ).fetchall()
        return [{"chunk_id": row["id"], "content": row["content"]} for row in rows]

    def _next_version_locked(self, domain: str, source: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS v FROM knowledge_doc WHERE domain = ? AND source = ?",
            (domain, source),
        ).fetchone()
        return row["v"] + 1


def split_chunks(text: str, max_len: int = 200) -> list[str]:
    """切片：按段落优先，超长按句号硬切（保引用粒度适中）。"""
    parts = [part.strip() for part in text.replace("\r", "").split("\n") if part.strip()]
    chunks: list[str] = []
    for part in parts:
        if len(part) <= max_len:
            chunks.append(part)
            continue
        buffer = ""
        for sentence in part.split("。"):
            if not sentence.strip():
                continue
            if buffer and len(buffer) + len(sentence) + 1 > max_len:
                chunks.append(buffer)
                buffer = sentence
            else:
                buffer = f"{buffer}。{sentence}" if buffer else sentence
        if buffer:
            chunks.append(buffer)
    return chunks
