"""上下文路由与协作 Agent 单测：

- 指代/短句经会话历史改写后正确路由（无历史时无法分类的对照）
- 上轮意图先验（sticky）对近分候选的动态重排
- RoutingDecision 携带主责 Agent 与协作 Agent
- ChatGraph 协作分派：主责 Coach 生成后，次选跨域指向 Ops 时附带标签建议
"""

from __future__ import annotations

from sale_agent.ai.gateway import GatewaySettings, LLMGateway
from sale_agent.ai.graph import ChatGraph
from sale_agent.intent.embedding import EmbeddingClassifier
from sale_agent.intent.fusion import IntentRouter, RoutingDecision
from sale_agent.intent.llm import LLMClassifier
from sale_agent.intent.rule import RuleClassifier
from sale_agent.intent.schema import IntentCatalogStore, seed_default_catalog


def _catalog(tmp_path) -> IntentCatalogStore:
    catalog = IntentCatalogStore(str(tmp_path / "intents.db"))
    seed_default_catalog(catalog)
    return catalog


def _echo_router(tmp_path) -> IntentRouter:
    """echo 网关：LLM 分类器返回 None，走 EMB_FALLBACK 路径（确定性）。"""
    catalog = _catalog(tmp_path)
    gateway = LLMGateway(settings=GatewaySettings(api_key=""))
    return IntentRouter(catalog, RuleClassifier(), EmbeddingClassifier(catalog), LLMClassifier(gateway, catalog))


class _StubLLM:
    def __init__(self, result: tuple[str, float] | None) -> None:
        self._result = result

    def classify(self, query: str) -> tuple[str, float] | None:
        return self._result


class _FakeEmb:
    """可控 Embedding 打分，构造近分候选场景。"""

    def __init__(self, scores: dict[str, float]) -> None:
        self._scores = scores

    def reload(self) -> None:
        pass

    def scores(self, query: str) -> dict[str, float]:
        return dict(self._scores)

    def top(self, query: str, limit: int = 3) -> list[tuple[str, float]]:
        ranked = sorted(self._scores.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:limit]


# ---------- 上下文改写：指代/短句路由 ----------

_CONTEXT_CASES = [
    # (expected, query, history)
    ("profile_query", "更新了没呢", [{"role": "user", "content": "帮我看看王先生的客户画像"}]),
    ("profile_query", "他现在处于什么阶段", [{"role": "user", "content": "看看张姐的画像"}]),
    ("talk_script", "这个客户该怎么开场", [{"role": "user", "content": "给我一段邀约到店的话术"}]),
    ("customer_search", "还有谁也这样", [{"role": "user", "content": "帮我找一下住在城东的客户"}]),
    ("schedule_suggest", "他排在第几位", [{"role": "user", "content": "帮我安排一下明天的拜访计划"}]),
    ("todo_query", "第一条是什么", [{"role": "user", "content": "查一下我名下的待办事项"}]),
    ("similar_customer", "最后都成什么样", [{"role": "user", "content": "之前类似的客户最后都怎么成交的"}]),
    ("objection_help", "那这类怎么处理", [{"role": "user", "content": "客户嫌贵怎么回应"}]),
]


def test_context_rewrite_routes_deixis_queries(tmp_path):
    """短句/指代查询：无历史时不可自动路由（UNKNOWN/CLARIFY），结合历史改写后命中并达阈值。"""
    router = _echo_router(tmp_path)
    for expected, query, history in _CONTEXT_CASES:
        bare = router.route(query)
        assert bare.decision_path in ("UNKNOWN", "CLARIFY"), f"用例失去区分度（无历史即达阈值 {bare.primary}）：{query}"
        decision = router.route(query, history=history)
        assert decision.primary == expected, f"{query} → {decision.primary}（期望 {expected}）"
        assert decision.decision_path in ("EMB_FALLBACK", "RULE_LOCKED", "FUSED"), "有历史后应产出可自动路由的决策"
        assert decision.rewritten_query, "改写查询应记录用于 Monitor 回放"


def test_no_history_keeps_original_query(tmp_path):
    """无历史/无指代时不改写，保持原语义（回归保护）。"""
    router = _echo_router(tmp_path)
    decision = router.route("张姐的画像给我看下")
    assert decision.primary == "profile_query"
    assert decision.rewritten_query == ""
    # 无历史的短句不强行改写
    short = router.route("最近有更新吗")
    assert short.rewritten_query == ""


# ---------- 上轮意图先验：候选动态重排 ----------


def test_sticky_intent_reorders_near_tie_candidates(tmp_path):
    """近分候选：上轮意图 +0.05 先验使候选动态重排（排序观测于 candidates）。"""
    catalog = _catalog(tmp_path)
    # LLM 弱置信选 customer_search；Embedding 使 chitchat（软规则命中）与之近分
    router = IntentRouter(
        catalog,
        RuleClassifier(),
        _FakeEmb({"customer_search": 0.60, "chitchat": 0.92}),
        _StubLLM(("customer_search", 0.40)),
    )
    plain = router.route("你好呀")
    assert plain.candidates[0]["intent"] == "customer_search", "无上下文时 LLM 主导候选排序"

    sticky = router.route("你好呀", sticky_intent="chitchat")
    assert sticky.candidates[0]["intent"] == "chitchat", "上轮意图先验应使近分候选动态重排"
    assert "上轮意图上下文" in sticky.reason


# ---------- 主责 / 协作 Agent ----------


def test_decision_carries_primary_and_collaborator_agents(tmp_path):
    """融合排序确定主责 Agent，次选意图跨域时产出协作 Agent。"""
    catalog = _catalog(tmp_path)
    router = IntentRouter(
        catalog,
        RuleClassifier(),
        _FakeEmb({"talk_script": 0.90, "tag_review": 0.85}),
        _StubLLM(("talk_script", 0.85)),
    )
    decision = router.route("结合这位客户的情况给点建议")
    assert decision.decision_path == "FUSED"
    assert decision.primary_agent == "coach", "主责 Agent 应由意图 Schema 查表"
    assert decision.secondary == "tag_review"
    assert decision.collaborators == ["ops"], "次选意图跨域（Ops）应列为协作 Agent"

    # 次选同域（coach→coach）不产生协作 Agent
    same_domain = IntentRouter(
        catalog,
        RuleClassifier(),
        _FakeEmb({"talk_script": 0.90, "objection_help": 0.85}),
        _StubLLM(("talk_script", 0.85)),
    ).route("结合这位客户的情况给点建议")
    assert same_domain.collaborators == []


# ---------- ChatGraph：上下文注入 + 协作分派 ----------


class _RecordingRouter:
    def __init__(self, decision: RoutingDecision) -> None:
        self.decision = decision
        self.calls: list[dict] = []

    def route(self, query, menu_intent=None, history=None, sticky_intent=None):
        self.calls.append({"query": query, "history": history, "sticky": sticky_intent})
        return self.decision


class _StubCoach:
    def generate(self, **kwargs):
        return {"reply": "话术草稿", "skill": {"id": "intent-followup"}, "citations": [], "suggestion_id": "s1", "echo": True}


class _StubOps:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def review(self, customer_id, employee_id, jwt, source="manual"):
        self.calls.append((customer_id, source))
        return {"outcome": "proposal", "proposal_id": "p1"}


class _StubTrace:
    def __init__(self) -> None:
        self.spans: list[str] = []

    def start_span(self, run_id, name, **kwargs):
        self.spans.append(name)
        return name

    def finish_span(self, span, status, output=None):
        pass


class _StubContextStore:
    backend = "memory"

    def __init__(self) -> None:
        self.messages: list[tuple] = []

    def load(self, session_id):
        return []

    def append(self, session_id, role, content):
        self.messages.append((role, content))


def _graph(router, ops):
    return ChatGraph(
        gateway=object(),
        context_store=_StubContextStore(),
        trace=_StubTrace(),
        intent_router=router,
        coach=_StubCoach(),
        ops=ops,
    )


_TALK_DECISION = RoutingDecision(
    primary="talk_script", confidence=0.83, decision_path="FUSED", reason="t",
    secondary="tag_review", primary_agent="coach", collaborators=["ops"],
)


def test_graph_dispatches_collaborator_agent(tmp_path):
    """主责 Coach 生成话术后，协作 Agent Ops 附带一轮标签建议。"""
    router = _RecordingRouter(_TALK_DECISION)
    ops = _StubOps()
    graph = _graph(router, ops)
    trace = graph.trace

    state = {
        "session_id": "s1", "user_id": "1", "run_id": "r1",
        "message": "给王女士写回访话术，顺便看看标签", "customer_id": 5, "jwt": "t",
    }
    out = graph.run(state)

    assert out["reply"].startswith("话术草稿")
    assert "[协作 Agent · Ops]" in out["reply"]
    assert out["collab_result"]["proposal_id"] == "p1"
    assert ops.calls == [(5, "collab")], "协作调用应携带来源标记"
    assert "collab_ops_tag_review" in trace.spans, "协作分派应有独立 span"


def test_graph_skips_collab_without_customer_context(tmp_path):
    """无客户上下文/凭证时不触发协作（不产生越权或空跑）。"""
    router = _RecordingRouter(_TALK_DECISION)
    ops = _StubOps()
    graph = _graph(router, ops)

    out = graph.run({
        "session_id": "s2", "user_id": "1", "run_id": "r2",
        "message": "给王女士写回访话术，顺便看看标签",
    })
    assert ops.calls == []
    assert "collab_result" not in out


def test_graph_passes_history_and_sticky_to_router(tmp_path):
    """路由节点注入会话历史与上轮意图先验（第二轮回填 sticky）。"""
    router = _RecordingRouter(_TALK_DECISION)
    graph = _graph(router, _StubOps())

    first = {"session_id": "s3", "user_id": "1", "run_id": "r3", "message": "给王女士写回访话术", "customer_id": 5, "jwt": "t"}
    graph.run(first)
    assert router.calls[0]["sticky"] is None, "首轮无上轮意图"

    graph.run({**first, "run_id": "r4", "message": "顺便看看标签"})
    assert router.calls[1]["sticky"] == "talk_script", "次轮应携带上轮意图先验"
