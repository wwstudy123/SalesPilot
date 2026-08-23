"""Embedding 简化版分类器：字符 bigram 词频向量 + 内存余弦（架构 §2.3）。

不依赖外部向量服务；M5 起 Milvus 接入后可平滑替换为 dense+sparse 检索。
原始余弦经锚点校准：paraphrase 相似度经验上集中在 0.3~0.6，
以 ANCHOR（默认 0.50）为“明确匹配”基准线性放大到 1.0，与意图阈值语义对齐。
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter

from sale_agent.intent.schema import IntentCatalogStore

_WS = re.compile(r"\s+")


def _anchor() -> float:
    raw = os.environ.get("SALE_INTENT_EMB_ANCHOR", "0.50").strip()
    try:
        value = float(raw)
        if 0.1 <= value <= 0.9:
            return value
    except ValueError:
        pass
    return 0.50


def _bigrams(text: str) -> Counter:
    cleaned = _WS.sub("", text.lower())
    grams = [cleaned[i : i + 2] for i in range(len(cleaned) - 1)] or ([cleaned] if cleaned else [])
    return Counter(grams)


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[g] * b[g] for g in common)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingClassifier:
    def __init__(self, catalog: IntentCatalogStore) -> None:
        self._catalog = catalog
        self._vectors: list[tuple[str, Counter]] = []
        self.reload()

    def reload(self) -> None:
        """样例库动态增补后重建内存向量（新增样例零发版）。"""
        self._vectors = [(row["intent"], _bigrams(row["text"])) for row in self._catalog.list_examples()]

    def scores(self, query: str) -> dict[str, float]:
        """每意图得分 = 与其样例的最大余弦，经锚点校准到 0~1。"""
        query_vec = _bigrams(query)
        anchor = _anchor()
        best: dict[str, float] = {}
        for intent, example_vec in self._vectors:
            raw = cosine(query_vec, example_vec)
            if raw < anchor / 2:
                continue  # 噪声分不入候选
            score = min(1.0, raw / anchor)
            if score > best.get(intent, 0.0):
                best[intent] = score
        return best

    def top(self, query: str, limit: int = 3) -> list[tuple[str, float]]:
        ranked = sorted(self.scores(query).items(), key=lambda item: item[1], reverse=True)
        return ranked[:limit]
