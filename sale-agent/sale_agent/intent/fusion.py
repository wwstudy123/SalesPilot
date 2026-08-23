"""三路融合路由（架构 §2.3）：

query → Rule（锁定短路 RULE_LOCKED）
      └─ 未锁定 → Embedding ∥ LLM
            final = 0.6×llm + 0.3×emb + 0.1×rule_prior（一致 +0.05）
            → FUSED / CLARIFY / EMB_FALLBACK / UNKNOWN
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sale_agent.intent.embedding import EmbeddingClassifier
from sale_agent.intent.llm import LLMClassifier
from sale_agent.intent.rule import RuleClassifier
from sale_agent.intent.schema import IntentCatalogStore

W_LLM, W_EMB, W_RULE, BONUS_AGREE = 0.6, 0.3, 0.1, 0.05
CLARIFY_MARGIN = 0.10
LOCKED_CONFIDENCE = 0.95


@dataclass
class RoutingDecision:
    primary: str
    confidence: float
    decision_path: str  # MENU / RULE_LOCKED / FUSED / EMB_FALLBACK / CLARIFY / UNKNOWN
    reason: str
    secondary: str | None = None
    candidates: list[dict] = field(default_factory=list)


class IntentRouter:
    def __init__(
        self,
        catalog: IntentCatalogStore,
        rule: RuleClassifier,
        embedding: EmbeddingClassifier,
        llm: LLMClassifier,
    ) -> None:
        self._catalog = catalog
        self._rule = rule
        self._embedding = embedding
        self._llm = llm
        self._thresholds: dict[str, float] = {}
        self.reload()

    def reload(self) -> None:
        self._thresholds = {row["name"]: float(row["threshold"]) for row in self._catalog.list_intents()}
        self._embedding.reload()

    def _threshold(self, intent: str) -> float:
        return self._thresholds.get(intent, 0.70)

    # ---------- 主入口 ----------

    def route(self, query: str, menu_intent: str | None = None) -> RoutingDecision:
        if menu_intent:
            return RoutingDecision(
                primary=menu_intent,
                confidence=1.0,
                decision_path="MENU",
                reason="场景菜单直达，免分类（routing_type=menu）",
            )

        hit = self._rule.classify(query)
        if hit and hit.locked:
            return RoutingDecision(
                primary=hit.intent,
                confidence=LOCKED_CONFIDENCE,
                decision_path="RULE_LOCKED",
                reason=f"关键词硬规则锁定：{hit.matched}",
            )

        emb_top = self._embedding.top(query, limit=3)
        emb_scores = dict(self._embedding.scores(query))
        llm_result = self._llm.classify(query)

        if llm_result is None:
            return self._emb_fallback(emb_top, hit.matched if hit else None)

        return self._fuse(query, llm_result, emb_scores, emb_top, hit.intent if hit else None)

    # ---------- 路径实现 ----------

    def _emb_fallback(self, emb_top: list[tuple[str, float]], rule_hint: str | None) -> RoutingDecision:
        candidates = [{"intent": intent, "score": round(score, 4)} for intent, score in emb_top]
        if not emb_top:
            return RoutingDecision("unknown", 0.0, "UNKNOWN", "无可用样例得分", candidates=candidates)
        intent, score = emb_top[0]
        threshold = self._threshold(intent)
        if score >= threshold:
            reason = f"LLM 不可用，Embedding 降级直出（score={score:.2f}≥阈值{threshold:.2f}）"
            if rule_hint == intent:
                score = min(1.0, score + BONUS_AGREE)
                reason += "；与 Rule 提示一致 +0.05"
            return RoutingDecision(intent, round(score, 4), "EMB_FALLBACK", reason, candidates=candidates)
        if score >= threshold - CLARIFY_MARGIN:
            return self._clarify(emb_top, f"Embedding 降级，置信不足（{score:.2f}<{threshold:.2f}）")
        return RoutingDecision("unknown", round(score, 4), "UNKNOWN", "得分过低，入评测池", candidates=candidates)

    def _fuse(
        self,
        query: str,
        llm_result: tuple[str, float],
        emb_scores: dict[str, float],
        emb_top: list[tuple[str, float]],
        rule_hint: str | None,
    ) -> RoutingDecision:
        llm_intent, llm_conf = llm_result
        candidates_names = {llm_intent} | {intent for intent, _ in emb_top}
        fused: list[tuple[str, float]] = []
        for intent in candidates_names:
            score = W_LLM * (llm_conf if intent == llm_intent else 0.0)
            score += W_EMB * emb_scores.get(intent, 0.0)
            score += W_RULE * (1.0 if intent == rule_hint else 0.0)
            if intent == llm_intent and emb_top and intent == emb_top[0][0]:
                score += BONUS_AGREE
            fused.append((intent, score))
        fused.sort(key=lambda item: item[1], reverse=True)

        primary, top_score = fused[0]
        secondary = fused[1][0] if len(fused) > 1 else None
        threshold = self._threshold(primary)
        candidates = [{"intent": intent, "score": round(score, 4)} for intent, score in fused]
        agree = "；LLM/Embedding 一致 +0.05" if primary == llm_intent and emb_top and primary == emb_top[0][0] else ""

        if top_score >= threshold:
            reason = f"三路融合 final={top_score:.2f}≥阈值{threshold:.2f}（0.6llm+0.3emb+0.1rule{agree}）"
            return RoutingDecision(primary, round(top_score, 4), "FUSED", reason, secondary=secondary, candidates=candidates)
        if top_score >= threshold - CLARIFY_MARGIN:
            return self._clarify(fused[:2], f"融合置信不足（{top_score:.2f}<{threshold:.2f}），需员工澄清")
        return RoutingDecision(
            "unknown", round(top_score, 4), "UNKNOWN", "融合得分过低，入评测池", secondary=secondary, candidates=candidates
        )

    @staticmethod
    def _clarify(pairs: list[tuple[str, float]], reason: str) -> RoutingDecision:
        candidates = [{"intent": intent, "score": round(score, 4)} for intent, score in pairs]
        primary = pairs[0][0] if pairs else "unknown"
        secondary = pairs[1][0] if len(pairs) > 1 else None
        return RoutingDecision(
            primary=primary,
            confidence=round(pairs[0][1], 4) if pairs else 0.0,
            decision_path="CLARIFY",
            reason=reason,
            secondary=secondary,
            candidates=candidates,
        )
