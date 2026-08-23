"""LLM 分类器：意图 Schema 动态渲染进 prompt（新增意图零发版）。

echo 模式（无 key）返回 None，由融合层走 EMB_FALLBACK 降级路径。
"""

from __future__ import annotations

import json
import logging

from sale_agent.ai.gateway import LLMGateway
from sale_agent.intent.schema import IntentCatalogStore

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = (
    "你是销售 Copilot 的意图分类器。从下列意图中选择最匹配员工输入的一个，"
    '只输出 JSON：{{"intent": "<意图名>", "confidence": <0~1>}}。\n'
    "意图列表：\n{intent_list}\n\n员工输入：{query}"
)


class LLMClassifier:
    def __init__(self, gateway: LLMGateway, catalog: IntentCatalogStore) -> None:
        self._gateway = gateway
        self._catalog = catalog

    def classify(self, query: str) -> tuple[str, float] | None:
        if self._gateway.settings.echo_mode:
            return None
        intent_list = "\n".join(f"- {row['name']}: {row['description']}" for row in self._catalog.list_intents())
        prompt = _PROMPT_TEMPLATE.format(intent_list=intent_list, query=query)
        try:
            result = self._gateway.chat([{"role": "user", "content": prompt}], temperature=0.0)
            return self._parse(result.content)
        except Exception as exc:  # noqa: BLE001
            logger.warning("llm intent classify failed: %s", exc)
            return None

    @staticmethod
    def _parse(content: str) -> tuple[str, float] | None:
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            return None
        intent = data.get("intent")
        confidence = data.get("confidence", 0.0)
        if not isinstance(intent, str) or not intent:
            return None
        try:
            score = max(0.0, min(1.0, float(confidence)))
        except (ValueError, TypeError):
            score = 0.5
        return intent, score
