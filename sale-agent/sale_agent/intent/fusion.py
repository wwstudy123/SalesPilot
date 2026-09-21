"""三路融合路由（架构 §2.3）：

query → 上下文改写（指代消解/短句补全，结合会话历史）
      → Rule（锁定短路 RULE_LOCKED）
      └─ 未锁定 → Embedding ∥ LLM
            final = 0.6×llm + 0.3×emb + 0.1×rule_prior（一致 +0.05；上轮意图先验 +0.05）
            → 按综合得分对候选意图动态排序 → 确定主责 Agent 与协作 Agent
            → FUSED / CLARIFY / EMB_FALLBACK / UNKNOWN
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sale_agent.intent.embedding import EmbeddingClassifier
from sale_agent.intent.llm import LLMClassifier
from sale_agent.intent.rule import RuleClassifier
from sale_agent.intent.schema import IntentCatalogStore

W_LLM, W_EMB, W_RULE, BONUS_AGREE = 0.6, 0.3, 0.1, 0.05
CTX_BOOST = 0.05  # 会话上下文先验：上轮意图候选加成，近分时动态重排（PRD R2 语义连贯）
CLARIFY_MARGIN = 0.10
LOCKED_CONFIDENCE = 0.95

# 指代/省略词表：命中或短句（≤8 字）触发上下文改写（仅用于分类打分，不改写下游生成）
_DEIXIS = ("他", "她", "它", "他们", "这位", "那位", "这个客户", "最近", "怎么样", "咋样", "呢")


@dataclass
class RoutingDecision:
    primary: str
    confidence: float
    decision_path: str  # MENU / RULE_LOCKED / FUSED / EMB_FALLBACK / CLARIFY / UNKNOWN
    reason: str
    secondary: str | None = None
    candidates: list[dict] = field(default_factory=list)
    primary_agent: str = "orchestrator"  # 主责 Agent（意图 Schema 查表）
    collaborators: list[str] = field(default_factory=list)  # 协作 Agent（次选意图且跨域）
    rewritten_query: str = ""  # 上下文改写后的查询（Monitor 回放路由依据）


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
        self._agent_map: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        rows = self._catalog.list_intents()
        self._thresholds = {row["name"]: float(row["threshold"]) for row in rows}
        self._agent_map = {row["name"]: row["primary_agent"] for row in rows}
        self._embedding.reload()

    def _threshold(self, intent: str) -> float:
        return self._thresholds.get(intent, 0.70)

    def _agents(self, primary: str, secondary: str | None) -> tuple[str, list[str]]:
        """主责 Agent = 意图 Schema 查表；协作 Agent = 次选意图归属且与主责不同域。"""
        pa = self._agent_map.get(primary, "orchestrator")
        if not secondary:
            return pa, []
        sa = self._agent_map.get(secondary, "")
        return pa, ([sa] if sa and sa != pa else [])

    # ---------- 主入口 ----------

    def route(
        self,
        query: str,
        menu_intent: str | None = None,
        history: list[dict] | None = None,
        sticky_intent: str | None = None,
    ) -> RoutingDecision:
        """结合会话上下文路由：history 供指代消解改写，sticky_intent 为上轮意图先验。"""
        if menu_intent:
            pa, collab = self._agents(menu_intent, None)
            return RoutingDecision(
                menu_intent, 1.0, "MENU", "场景菜单直达，免分类（routing_type=menu）",
                primary_agent=pa, collaborators=collab,
            )

        hit = self._rule.classify(query)
        if hit and hit.locked:
            pa, collab = self._agents(hit.intent, None)
            return RoutingDecision(
                hit.intent, LOCKED_CONFIDENCE, "RULE_LOCKED", f"关键词硬规则锁定：{hit.matched}",
                primary_agent=pa, collaborators=collab,
            )

        rewritten, ctx_note = self._rewrite(query, history)
        rw = rewritten if ctx_note else ""  # 仅实际改写时记录（Monitor 回放）
        if ctx_note:
            # 规则同样感知有效查询：恢复被指代省略的关键词（如上轮谈"话术"，本轮"该怎么开场"）
            ctx_hit = self._rule.classify(rewritten)
            if ctx_hit and (ctx_hit.locked or hit is None):
                hit = ctx_hit
            if hit and hit.locked:
                pa, collab = self._agents(hit.intent, None)
                return RoutingDecision(
                    hit.intent, LOCKED_CONFIDENCE, "RULE_LOCKED",
                    f"{ctx_note}；关键词硬规则锁定：{hit.matched}",
                    primary_agent=pa, collaborators=collab, rewritten_query=rw,
                )
        # Embedding 改写只增强不劣化：原始与改写查询逐意图取最大
        emb_scores = dict(self._embedding.scores(query))
        if ctx_note:
            for intent, score in self._embedding.scores(rewritten).items():
                if score > emb_scores.get(intent, 0.0):
                    emb_scores[intent] = score
        emb_top = sorted(emb_scores.items(), key=lambda item: item[1], reverse=True)[:3]
        llm_result = self._llm.classify(rewritten)

        if llm_result is None:
            return self._emb_fallback(emb_top, hit.matched if hit else None, sticky_intent, rw, ctx_note)

        return self._fuse(llm_result, emb_scores, emb_top, hit.intent if hit else None, sticky_intent, ctx_note, rw)

    # ---------- 上下文改写（确定性，echo 模式可用） ----------

    @staticmethod
    def _rewrite(query: str, history: list[dict] | None) -> tuple[str, str]:
        """短句/指代省略时拼接上轮用户消息，供三路分类打分。

        仅影响分类输入，不改写下游生成；改写结果落 rewritten_query 供 Monitor 回放。
        """
        if not history:
            return query, ""
        last_user = next((m.get("content", "") for m in reversed(history) if m.get("role") == "user"), "")
        if not last_user:
            return query, ""
        is_short = len(query.strip()) <= 8
        has_deixis = any(word in query for word in _DEIXIS)
        if not (is_short or has_deixis):
            return query, ""
        rewritten = f"{last_user}{query}"
        note = f"上下文改写：指代/短句 → 拼接上轮主题（{last_user[:16]}）"
        return rewritten, note

    # ---------- 路径实现 ----------

    def _emb_fallback(
        self,
        emb_top: list[tuple[str, float]],
        rule_hint: str | None,
        sticky_intent: str | None = None,
        rewritten: str = "",
        ctx_note: str = "",
    ) -> RoutingDecision:
        if sticky_intent:
            # 上下文先验：上轮意图加分后重排候选（近分场景动态排序）
            emb_top = sorted(
                [(intent, score + (CTX_BOOST if intent == sticky_intent else 0.0)) for intent, score in emb_top],
                key=lambda item: item[1],
                reverse=True,
            )
        candidates = [{"intent": intent, "score": round(score, 4)} for intent, score in emb_top]
        if not emb_top:
            return RoutingDecision("unknown", 0.0, "UNKNOWN", "无可用样例得分", candidates=candidates, rewritten_query=rewritten)
        intent, score = emb_top[0]
        threshold = self._threshold(intent)
        pa, collab = self._agents(intent, emb_top[1][0] if len(emb_top) > 1 else None)
        if score >= threshold:
            reason = f"LLM 不可用，Embedding 降级直出（score={score:.2f}≥阈值{threshold:.2f}）"
            if rule_hint == intent:
                score = min(1.0, score + BONUS_AGREE)
                reason += "；与 Rule 提示一致 +0.05"
            if sticky_intent == intent:
                reason += "；上轮意图上下文 +0.05"
            if ctx_note:
                reason = f"{ctx_note}；{reason}"
            return RoutingDecision(
                intent, round(score, 4), "EMB_FALLBACK", reason,
                candidates=candidates, primary_agent=pa, collaborators=collab, rewritten_query=rewritten,
            )
        if score >= threshold - CLARIFY_MARGIN:
            reason = f"Embedding 降级，置信不足（{score:.2f}<{threshold:.2f}）"
            if ctx_note:
                reason = f"{ctx_note}；{reason}"
            return self._clarify(emb_top[:2], reason, primary_agent=pa, collaborators=collab, rewritten_query=rewritten)
        return RoutingDecision(
            "unknown", round(score, 4), "UNKNOWN", "得分过低，入评测池",
            candidates=candidates, primary_agent=pa, collaborators=collab, rewritten_query=rewritten,
        )

    def _fuse(
        self,
        llm_result: tuple[str, float],
        emb_scores: dict[str, float],
        emb_top: list[tuple[str, float]],
        rule_hint: str | None,
        sticky_intent: str | None = None,
        ctx_note: str = "",
        rw: str = "",
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
            if sticky_intent and intent == sticky_intent:
                score += CTX_BOOST
            fused.append((intent, score))
        fused.sort(key=lambda item: item[1], reverse=True)

        primary, top_score = fused[0]
        secondary = fused[1][0] if len(fused) > 1 else None
        threshold = self._threshold(primary)
        candidates = [{"intent": intent, "score": round(score, 4)} for intent, score in fused]
        pa, collab = self._agents(primary, secondary)
        agree = "；LLM/Embedding 一致 +0.05" if primary == llm_intent and emb_top and primary == emb_top[0][0] else ""
        sticky = "；上轮意图上下文 +0.05" if sticky_intent and primary == sticky_intent else ""

        if top_score >= threshold:
            reason = f"三路融合 final={top_score:.2f}≥阈值{threshold:.2f}（0.6llm+0.3emb+0.1rule{agree}{sticky}）"
            if ctx_note:
                reason = f"{ctx_note}；{reason}"
            return RoutingDecision(
                primary, round(top_score, 4), "FUSED", reason,
                secondary=secondary, candidates=candidates, primary_agent=pa, collaborators=collab, rewritten_query=rw,
            )
        if top_score >= threshold - CLARIFY_MARGIN:
            reason = f"融合置信不足（{top_score:.2f}<{threshold:.2f}），需员工澄清"
            if ctx_note:
                reason = f"{ctx_note}；{reason}"
            return self._clarify(fused[:2], reason, primary_agent=pa, collaborators=collab, rewritten_query=rw)
        unknown_reason = "融合得分过低，入评测池"
        if sticky:
            unknown_reason += sticky
        return RoutingDecision(
            "unknown", round(top_score, 4), "UNKNOWN", unknown_reason,
            secondary=secondary, candidates=candidates, primary_agent=pa, collaborators=collab, rewritten_query=rw,
        )

    @staticmethod
    def _clarify(pairs: list[tuple[str, float]], reason: str, **extra) -> RoutingDecision:
        candidates = [{"intent": intent, "score": round(score, 4)} for intent, score in pairs]
        primary = pairs[0][0] if pairs else "unknown"
        secondary = pairs[1][0] if len(pairs) > 1 else None
        return RoutingDecision(
            primary,
            round(pairs[0][1], 4) if pairs else 0.0,
            "CLARIFY",
            reason,
            secondary=secondary,
            candidates=candidates,
            **extra,
        )
