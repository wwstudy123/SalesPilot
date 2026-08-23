"""Milvus 向量后端（M5「Milvus 接入」+ 架构 A8 lite 降级）。

架构 §6.3：playbook_kb / product_kb 存 chunk dense 向量，回指 knowledge_chunk.id。
架构 A8：本机跑不动 Milvus 时降级 lite（bigram 余弦，见 rag.pipeline 与 kb.store）。

本模块是「Milvus 接入」的代码结构与降级闸门：
- `MilvusVectorStore`：pymilvus 懒加载，不可用即 `is_available()=False`；
  提供 ensure_collection / upsert / search / delete，向量由外部 embed_fn 产出。
- `build_vector_backend()`：按 `SALE_VECTOR_BACKEND`（默认 lite）构造后端；
  选 milvus 但 pymilvus 缺失或实例不可达时，记日志并返回 None（降级 lite）。

lite 路径（bigram 落 SQLite + 管线内存检索）为 MVP 默认且经测试覆盖；
当 Milvus 可用时，M10 全量 compose 将把 dense 检索切到本后端（接口已就位）。
"""

from __future__ import annotations

import logging
import os
from typing import Callable, Protocol

logger = logging.getLogger(__name__)

# collection 维度（架构 §6.3 两集合）；与 embedding 模型维度对齐由调用方保证
PLAYBOOK_COLLECTION = "playbook_kb"
PRODUCT_COLLECTION = "product_kb"
DIM_DEFAULT = 1536  # text-embedding-3-small；其它模型由 env 覆盖


def _collection_for(domain: str) -> str:
    return PLAYBOOK_COLLECTION if domain == "playbook" else PRODUCT_COLLECTION


class VectorBackend(Protocol):
    """向量后端协议（lite 与 milvus 共同实现，便于后续替换）。"""

    def is_available(self) -> bool: ...

    def upsert(self, domain: str, doc_id: int, chunks: list[dict]) -> None: ...

    def search(self, domain: str, query_embedding: list[float], top_k: int = 20) -> list[tuple[int, float]]: ...

    def delete_doc(self, domain: str, doc_id: int) -> None: ...


class MilvusVectorStore:
    """Milvus 向量后端（pymilvus 懒加载；不可用即 is_available=False，触发 lite 降级）。"""

    def __init__(
        self,
        host: str,
        port: int,
        embed_fn: Callable[[list[str]], list[list[float]]] | None = None,
        dim: int = DIM_DEFAULT,
    ) -> None:
        self._host = host
        self._port = port
        self._embed_fn = embed_fn
        self._dim = dim
        self._client = None  # 懒初始化

    # ---------- 可用性 ----------

    def is_available(self) -> bool:
        """pymilvus 可导入且连通实例 → True；任一不满足 → False（降级 lite）。"""
        try:
            from pymilvus import MilvusClient  # noqa: F401
        except ImportError:
            return False
        try:
            client = self._connect()
            return client is not None
        except Exception as exc:  # noqa: BLE001
            logger.warning("milvus unavailable, fall back to lite: %s", exc)
            return False

    def _connect(self):
        from pymilvus import MilvusClient

        if self._client is None:
            self._client = MilvusClient(uri=f"http://{self._host}:{self._port}")
        return self._client

    # ---------- 集合 ----------

    def ensure_collection(self, domain: str) -> None:
        from pymilvus import DataType

        client = self._connect()
        name = _collection_for(domain)
        if client.has_collection(name):
            return
        schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("chunk_id", DataType.INT64)
        schema.add_field("doc_id", DataType.INT64)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=self._dim)
        client.create_collection(name, schema)
        client.create_index(name, "vector", {"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 200}})

    # ---------- 写入 ----------

    def upsert(self, domain: str, doc_id: int, chunks: list[dict]) -> None:
        """chunks: [{"chunk_id": int, "content": str}, ...]；向量由 embed_fn 产出。"""
        if not chunks or self._embed_fn is None:
            return
        self.ensure_collection(domain)
        client = self._connect()
        name = _collection_for(domain)
        vectors = self._embed_fn([c["content"] for c in chunks])
        rows = [
            {"chunk_id": c["chunk_id"], "doc_id": doc_id, "vector": vec}
            for c, vec in zip(chunks, vectors)
        ]
        client.upsert(name, rows)

    # ---------- 检索 ----------

    def search(self, domain: str, query_embedding: list[float], top_k: int = 20) -> list[tuple[int, float]]:
        """返回 [(chunk_id, score)]，按相关性降序；score 为余弦相似度（0~1）。"""
        client = self._connect()
        name = _collection_for(domain)
        results = client.search(
            name,
            [query_embedding],
            anns_field="vector",
            limit=top_k,
            output_fields=["chunk_id"],
        )
        hits: list[tuple[int, float]] = []
        for match in results[0]:
            chunk_id = match.get("entity", {}).get("chunk_id")
            score = float(match.get("distance", 0.0))
            if chunk_id is not None:
                hits.append((int(chunk_id), score))
        return hits

    # ---------- 删除（原子切换归档旧版时清向量，架构 §6.3 一致性） ----------

    def delete_doc(self, domain: str, doc_id: int) -> None:
        client = self._connect()
        client.delete(_collection_for(domain), filter=f"doc_id == {doc_id}")


def build_vector_backend(
    embed_fn: Callable[[list[str]], list[list[float]]] | None = None,
) -> MilvusVectorStore | None:
    """按 env 构造向量后端；milvus 不可用时降级返回 None（调用方走 lite）。

    - `SALE_VECTOR_BACKEND=lite`（默认）→ 直接 None，走 bigram lite 路径。
    - `SALE_VECTOR_BACKEND=milvus` → 构造 MilvusVectorStore；pymilvus 缺失/实例不可达 → None。
    """
    backend = os.environ.get("SALE_VECTOR_BACKEND", "lite").strip().lower() or "lite"
    if backend != "milvus":
        return None
    host = os.environ.get("MILVUS_HOST", "127.0.0.1").strip()
    port = int(os.environ.get("MILVUS_PORT", "19530") or "19530")
    dim = int(os.environ.get("MILVUS_DIM", str(DIM_DEFAULT)) or DIM_DEFAULT)
    store = MilvusVectorStore(host, port, embed_fn=embed_fn, dim=dim)
    if not store.is_available():
        logger.warning("SALE_VECTOR_BACKEND=milvus 但实例不可用，降级 lite（架构 A8）")
        return None
    return store
