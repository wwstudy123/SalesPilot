"""RAG 管线（架构 §2.4）：rewrite → dense+sparse 各 top20 → RRF → rerank → 阈值 → 注入。

lite 降级（架构 A8 裁决）：无 Milvus，dense 用字符 bigram 余弦、sparse 用 BM25 简化式，
rerank 默认 LLM listwise，echo/无 rerank 时降级 RRF 直出。
纪律：客户事实来自 MCP/画像，RAG 只出话术与方法论；无命中标注"通用建议"。
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from sale_agent.ai.gateway import LLMGateway
from sale_agent.intent.embedding import _bigrams, cosine
from sale_agent.kb.store import KnowledgeStore

# 阈值（架构 §2.4）：≥0.60 直用 / 0.35~0.60 限定语 / <0.25 弃
SCORE_DIRECT = 0.60
SCORE_HEDGED = 0.35
SCORE_DROP = 0.25

RRF_K = 60
RETRIEVE_TOP = 20
INJECT_MAX_CHUNKS = 5
INJECT_MAX_CHARS = 1200  # ≈1200 token（中文按字符近似）


@dataclass
class RagHit:
    chunk_id: int
    title: str
    content: str
    score: float  # dense 余弦（阈值判定依据）
    rrf: float
    hedge: bool = False  # 0.35~0.60 区间需附限定语


@dataclass
class RagResult:
    hits: list[RagHit] = field(default_factory=list)
    knowledge_zone: str = ""
    citations: list[dict] = field(default_factory=list)
    mode: str = "rrf"  # rrf / listwise
    rewritten_query: str = ""


class RAGPipeline:
    def __init__(self, kb: KnowledgeStore, gateway: LLMGateway) -> None:
        self._kb = kb
        self._gateway = gateway

    # ---------- 主入口 ----------

    def retrieve(self, query: str, domain: str | None = None, customer_ctx: dict | None = None) -> RagResult:
        chunks = self._kb.ready_chunks(domain)
        if not chunks:
            return RagResult(rewritten_query=query)

        rewritten = self._rewrite(query, customer_ctx)
        dense = self._dense(rewritten, chunks)
        sparse = self._sparse(rewritten, chunks)
        fused = self._rrf(dense, sparse)  # chunk_id → (rrf, rank)
        hits = self._rank(fused, chunks, dense, customer_ctx)
        reranked = self._rerank_hits(rewritten, hits)  # LLM listwise（echo/失败降级 RRF 直出）
        zone, citations = self._inject(hits)
        return RagResult(
            hits=hits,
            knowledge_zone=zone,
            citations=citations,
            mode="listwise" if reranked else "rrf",
            rewritten_query=rewritten,
        )

    def reinject(self, hits: list[RagHit]) -> tuple[str, list[dict]]:
        """重新格式化注入区（供 Coach 重新生成剔除素材后重排角标）。"""
        return self._inject(hits)

    # ---------- rewrite ----------

    def _rewrite(self, query: str, customer_ctx: dict | None) -> str:
        """注入客户上下文槽位；echo 模式直接拼接关键槽位（确定性可复现）。"""
        if not customer_ctx:
            return query
        slots = [value for key in ("name", "lifecycle_stage", "value_tier", "recent_focus") if (value := customer_ctx.get(key))]
        return f"{query}（客户：{'；'.join(slots)}）" if slots else query

    # ---------- dense：bigram 余弦 top20 ----------

    def _dense(self, query: str, chunks: list[dict]) -> list[int]:
        query_vec = _bigrams(query)
        scored = [(chunk["chunk_id"], cosine(query_vec, chunk["vector"])) for chunk in chunks]
        scored.sort(key=lambda item: item[1], reverse=True)
        return [chunk_id for chunk_id, score in scored[:RETRIEVE_TOP] if score > 0]

    # ---------- sparse：BM25 简化式（bigram 词元 + idf） top20 ----------

    def _sparse(self, query: str, chunks: list[dict]) -> list[int]:
        query_terms = set(_bigrams(query))
        total = len(chunks)
        df: Counter = Counter()
        for chunk in chunks:
            df.update(set(chunk["vector"]))
        scores: list[tuple[int, float]] = []
        for chunk in chunks:
            vector = chunk["vector"]
            length = sum(vector.values()) or 1
            score = 0.0
            for term in query_terms & set(vector):
                idf = math.log((total - df[term] + 0.5) / (df[term] + 0.5) + 1.0)
                tf = vector[term]
                score += idf * (tf * 2.5) / (tf + 1.5 * (0.25 + 0.75 * length / 120))
            if score > 0:
                scores.append((chunk["chunk_id"], score))
        scores.sort(key=lambda item: item[1], reverse=True)
        return [chunk_id for chunk_id, _ in scores[:RETRIEVE_TOP]]

    # ---------- RRF 融合 ----------

    @staticmethod
    def _rrf(dense_rank: list[int], sparse_rank: list[int]) -> dict[int, float]:
        fused: dict[int, float] = {}
        for rank, chunk_id in enumerate(dense_rank):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
        for rank, chunk_id in enumerate(sparse_rank):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
        return fused

    # ---------- 阈值过滤 + rerank（echo 降级 RRF 直出） ----------

    def _rank(self, fused: dict[int, float], chunks: list[dict], dense_rank: list[int], customer_ctx: dict | None) -> list[RagHit]:
        by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
        candidates = [(chunk_id, rrf, by_id[chunk_id]) for chunk_id, rrf in fused.items() if chunk_id in by_id]
        candidates.sort(key=lambda item: item[1], reverse=True)

        hits: list[RagHit] = []
        for chunk_id, rrf, chunk in candidates:
            score = self._content_score(chunk, dense_rank)
            if score < SCORE_DROP:
                continue  # <0.25 弃
            hits.append(
                RagHit(
                    chunk_id=chunk_id,
                    title=chunk["title"],
                    content=chunk["content"],
                    score=score,
                    rrf=rrf,
                    hedge=SCORE_HEDGED <= score < SCORE_DIRECT,
                )
            )
        # echo/无 rerank：RRF 直出（架构降级路径）；live 模式 LLM listwise 重排见 _rerank_hits
        return hits

    def _rerank_hits(self, query: str, hits: list[RagHit]) -> bool:
        """LLM listwise 重排（架构 §2.4 默认）。

        echo 模式 / 调用失败 / 解析空 → 不改动 hits，返回 False（管线降级 RRF 直出，架构 A8）。
        命中 → 按 LLM 序重排 hits（≤20 候选，与 RETRIEVE_TOP 对齐），返回 True。
        阈值/限定语（hedge）仍依据 dense 分数，重排只调整注入顺序与角标。
        """
        if not hits:
            return False
        try:
            ranking = self._gateway.rerank(
                query,
                [{"title": hit.title, "content": hit.content} for hit in hits],
                top_n=len(hits),
            )
        except Exception:  # noqa: BLE001
            return False
        if not ranking:
            return False
        reordered = [hits[i] for i in ranking if 0 <= i < len(hits)]
        if not reordered:
            return False
        hits[:] = reordered
        return True

    @staticmethod
    def _content_score(chunk: dict, dense_rank: list[int]) -> float:
        """以 dense 排名映射置信度：rank1=1.0 线性衰减（RRF 分数本身无量纲，
        用余弦回算成本高且不稳；排名衰减与阈值语义对齐，演示可解释）。"""
        try:
            rank = dense_rank.index(chunk["chunk_id"])
        except ValueError:
            return 0.0
        return max(0.0, 1.0 - rank * 0.05)

    # ---------- 注入：≤5 chunks / ≤1200 token / 引用角标 ----------

    @staticmethod
    def _inject(hits: list[RagHit]) -> tuple[str, list[dict]]:
        zone_parts: list[str] = []
        citations: list[dict] = []
        used = 0
        for index, hit in enumerate(hits[:INJECT_MAX_CHUNKS]):
            label = f"c{index + 1}"
            prefix = "（参考，需结合客户情况调整）" if hit.hedge else ""
            part = f"[{label}] {hit.title}：{hit.content}{prefix}"
            if used + len(part) > INJECT_MAX_CHARS:
                break
            zone_parts.append(part)
            citations.append({"label": label, "chunk_id": hit.chunk_id, "title": hit.title, "score": round(hit.score, 3)})
            used += len(part)
        return "\n".join(zone_parts), citations
