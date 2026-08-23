"""Redis 会话上下文装载：chat:ctx:{session_id}，多轮对话上下文保持。

Redis 不可达时自动降级为进程内存储（开发/测试友好），接口不变。
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)

KEY_PREFIX = "chat:ctx:"
DEFAULT_MAX_MESSAGES = 20
DEFAULT_TTL_SECONDS = 1800


class SessionContextStore:
    """会话上下文存取接口：messages 为 [{"role": ..., "content": ...}]。"""

    def load(self, session_id: str) -> list[dict[str, str]]:
        raise NotImplementedError

    def append(self, session_id: str, role: str, content: str) -> None:
        raise NotImplementedError

    @property
    def backend(self) -> str:
        raise NotImplementedError


class RedisContextStore(SessionContextStore):
    def __init__(
        self,
        client,
        max_messages: int = DEFAULT_MAX_MESSAGES,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._redis = client
        self._max = max_messages
        self._ttl = ttl_seconds

    @property
    def backend(self) -> str:
        return "redis"

    def load(self, session_id: str) -> list[dict[str, str]]:
        raw_items = self._redis.lrange(KEY_PREFIX + session_id, 0, -1)
        messages: list[dict[str, str]] = []
        for raw in raw_items:
            try:
                item = json.loads(raw)
                if isinstance(item, dict) and "role" in item and "content" in item:
                    messages.append({"role": str(item["role"]), "content": str(item["content"])})
            except (ValueError, TypeError):
                continue
        return messages

    def append(self, session_id: str, role: str, content: str) -> None:
        key = KEY_PREFIX + session_id
        payload = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        pipe = self._redis.pipeline()
        pipe.rpush(key, payload)
        pipe.ltrim(key, -self._max, -1)
        pipe.expire(key, self._ttl)
        pipe.execute()


class InMemoryContextStore(SessionContextStore):
    def __init__(self, max_messages: int = DEFAULT_MAX_MESSAGES) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, list[dict[str, str]]] = defaultdict(list)
        self._max = max_messages

    @property
    def backend(self) -> str:
        return "memory"

    def load(self, session_id: str) -> list[dict[str, str]]:
        with self._lock:
            return list(self._data.get(session_id, []))

    def append(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            bucket = self._data[session_id]
            bucket.append({"role": role, "content": content})
            if len(bucket) > self._max:
                del bucket[: len(bucket) - self._max]


def build_context_store(redis_url: str | None = None) -> SessionContextStore:
    """按 SALE_REDIS_URL 构建 Redis 存储；连接失败降级为内存存储。"""
    url = (redis_url or os.environ.get("SALE_REDIS_URL", "redis://127.0.0.1:6379/0")).strip()
    try:
        import redis as redis_lib

        client = redis_lib.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=2)
        client.ping()
        return RedisContextStore(client)
    except Exception as exc:  # noqa: BLE001
        logger.warning("redis unavailable (%s), fallback to in-memory session context", exc)
        return InMemoryContextStore()
