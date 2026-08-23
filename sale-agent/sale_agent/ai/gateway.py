"""LLM Gateway：chat/embedding/rerank 三端点 + 模型路由 + 重试/超时 + 成本记账。

OpenAI 兼容协议；未配置 api_key 时进入 echo 模式（无外部依赖，供开发/测试）。
rerank 默认走 LLM listwise（架构 §2.4）：让 chat 模型对候选输出按相关性排序，
不部署独立 reranker 模型；echo 模式返回空列表，由管线降级为 RRF 直出（架构 A8）。
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

_PLACEHOLDER_KEYS = {"", "your_api_key", "sk-xxx", "changeme"}


@dataclass
class GatewaySettings:
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    timeout: float = 60.0
    max_retries: int = 2

    @property
    def echo_mode(self) -> bool:
        return self.api_key.strip().lower() in _PLACEHOLDER_KEYS


def load_gateway_settings() -> GatewaySettings:
    def _float(env: str, default: float) -> float:
        raw = os.environ.get(env, "").strip()
        try:
            return float(raw) if raw else default
        except ValueError:
            return default

    def _int(env: str, default: int) -> int:
        raw = os.environ.get(env, "").strip()
        try:
            return int(raw) if raw else default
        except ValueError:
            return default

    return GatewaySettings(
        base_url=os.environ.get("SALE_LLM_BASE_URL", "https://api.openai.com/v1").strip() or "https://api.openai.com/v1",
        api_key=os.environ.get("SALE_LLM_API_KEY", "").strip(),
        chat_model=os.environ.get("SALE_LLM_CHAT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
        embedding_model=os.environ.get("SALE_LLM_EMBEDDING_MODEL", "text-embedding-3-small").strip() or "text-embedding-3-small",
        timeout=_float("SALE_LLM_TIMEOUT", 60.0),
        max_retries=_int("SALE_LLM_MAX_RETRIES", 2),
    )


@dataclass
class ChatResult:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    echo: bool = False


@dataclass
class ModelUsage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class CostLedger:
    """内存成本记账：按模型累计调用次数与 token 用量。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._usage: dict[str, ModelUsage] = {}

    def record(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        with self._lock:
            usage = self._usage.setdefault(model, ModelUsage())
            usage.calls += 1
            usage.prompt_tokens += max(0, prompt_tokens)
            usage.completion_tokens += max(0, completion_tokens)

    def snapshot(self) -> dict[str, dict[str, int]]:
        with self._lock:
            return {
                model: {
                    "calls": usage.calls,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.prompt_tokens + usage.completion_tokens,
                }
                for model, usage in self._usage.items()
            }


@dataclass
class LLMGateway:
    settings: GatewaySettings = field(default_factory=load_gateway_settings)
    ledger: CostLedger = field(default_factory=CostLedger)
    client: httpx.Client | None = None

    def _http(self) -> httpx.Client:
        if self.client is None:
            self.client = httpx.Client(timeout=self.settings.timeout)
        return self.client

    def _endpoint(self, path: str) -> str:
        return f"{self.settings.base_url.rstrip('/')}/{path.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }

    # ---------- chat ----------

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatResult:
        target_model = model or self.settings.chat_model
        if self.settings.echo_mode:
            last_user = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
            return ChatResult(content=f"echo: {last_user}".strip(), model="echo", echo=True)

        payload = {"model": target_model, "temperature": temperature, "messages": messages}
        data = self._post_with_retry("chat/completions", payload)
        try:
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"llm chat decode failed: {exc}") from exc
        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        self.ledger.record(target_model, prompt_tokens, completion_tokens)
        return ChatResult(
            content=content.strip(),
            model=str(data.get("model") or target_model),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    # ---------- embedding ----------

    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        target_model = model or self.settings.embedding_model
        if self.settings.echo_mode:
            # 确定性伪向量（维度 8），供无 key 环境联调
            vectors: list[list[float]] = []
            for text in texts:
                vectors.append([round(((i + 1) * (len(text) + 1)) % 97 / 97.0, 4) for i in range(8)])
            return vectors

        payload = {"model": target_model, "input": texts}
        data = self._post_with_retry("embeddings", payload)
        try:
            items = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
            return [list(item.get("embedding", [])) for item in items]
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"llm embedding decode failed: {exc}") from exc

    # ---------- rerank（LLM listwise，架构 §2.4） ----------

    def rerank(self, query: str, documents: list[dict], top_n: int = 5) -> list[int]:
        """LLM listwise 重排：让 chat 模型对候选按相关性排序，返回下标列表（降序）。

        echo 模式或无候选 → 返回空列表，调用方应降级为 RRF 直出（架构 A8）。
        解析失败 → 同样返回空列表，由调用方降级。
        """
        if self.settings.echo_mode or not documents:
            return []
        limited = documents[:20]  # listwise 候选上限，与 RAG RETRIEVE_TOP 对齐
        numbered = [
            f"[{i}] 标题：{doc.get('title', '')} 内容：{str(doc.get('content', ''))[:200]}"
            for i, doc in enumerate(limited)
        ]
        system = (
            "你是检索重排器。按与查询的相关性从高到低输出候选文档序号，"
            "每行一个 [n] 格式，仅输出序号不要解释。"
        )
        user = f"查询：{query}\n\n候选：\n" + "\n".join(numbered)
        result = self.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
        )
        return self._parse_rerank_indices(result.content, len(limited), top_n)

    @staticmethod
    def _parse_rerank_indices(text: str, total: int, top_n: int) -> list[int]:
        """解析 [n] 序号；去重保序，剔除越界；未出现者按原序兜底。"""
        seen: set[int] = set()
        ordered: list[int] = []
        for match in re.finditer(r"\[(\d+)\]", text):
            idx = int(match.group(1))
            if 0 <= idx < total and idx not in seen:
                seen.add(idx)
                ordered.append(idx)
        for i in range(total):  # 模型漏列的按原序补齐，保证不丢候选
            if i not in seen:
                ordered.append(i)
        return ordered[: max(1, top_n)] if ordered else []

    # ---------- 重试/超时 ----------

    def _post_with_retry(self, path: str, payload: dict) -> dict:
        url = self._endpoint(path)
        last_error: Exception | None = None
        attempts = max(1, self.settings.max_retries + 1)
        for attempt in range(attempts):
            try:
                response = self._http().post(url, json=payload, headers=self._headers())
                if response.status_code >= 400 and response.status_code != 429 and response.status_code < 500:
                    # 客户端错误不重试
                    raise ValueError(f"llm http {response.status_code}: {response.text[:200]}")
                if response.status_code >= 400:
                    raise RuntimeError(f"llm http {response.status_code}: {response.text[:200]}")
                return response.json()
            except (httpx.TimeoutException, httpx.ConnectError, RuntimeError) as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    backoff = 0.5 * (attempt + 1)
                    logger.warning("llm request failed (attempt %s/%s): %s", attempt + 1, attempts, exc)
                    time.sleep(backoff)
                    continue
        raise RuntimeError(f"llm request failed after {attempts} attempts: {last_error}")

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None
