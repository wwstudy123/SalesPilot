"""M3 意图路由单测：MENU/RULE_LOCKED/EMB_FALLBACK/FUSED/CLARIFY/UNKNOWN 全路径 + Schema 接口。"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sale_agent.ai.gateway import GatewaySettings, LLMGateway
from sale_agent.intent.embedding import EmbeddingClassifier
from sale_agent.intent.fusion import CLARIFY_MARGIN, IntentRouter
from sale_agent.intent.llm import LLMClassifier
from sale_agent.intent.rule import RuleClassifier
from sale_agent.intent.schema import IntentCatalogStore, seed_default_catalog
from sale_agent.internal_api.app import create_app


def _build_router(tmp_path) -> tuple[IntentRouter, IntentCatalogStore]:
    catalog = IntentCatalogStore(str(tmp_path / "intents.db"))
    seed_default_catalog(catalog)
    gateway = LLMGateway(settings=GatewaySettings(api_key=""))  # echo 模式
    router = IntentRouter(catalog, RuleClassifier(), EmbeddingClassifier(catalog), LLMClassifier(gateway, catalog))
    return router, catalog


class _StubLLM:
    """替代 LLMClassifier.classify，构造 FUSED/CLARIFY 场景。"""

    def __init__(self, result: tuple[str, float] | None) -> None:
        self._result = result

    def classify(self, query: str) -> tuple[str, float] | None:
        return self._result


def _router_with_llm(tmp_path, llm_result) -> IntentRouter:
    catalog = IntentCatalogStore(str(tmp_path / "intents.db"))
    seed_default_catalog(catalog)
    return IntentRouter(catalog, RuleClassifier(), EmbeddingClassifier(catalog), _StubLLM(llm_result))


# ---------- 路径：MENU / RULE_LOCKED ----------


def test_menu_direct_bypasses_classifiers(tmp_path):
    router, _ = _build_router(tmp_path)

    decision = router.route("随便什么输入", menu_intent="todo_query")

    assert decision.primary == "todo_query"
    assert decision.confidence == 1.0
    assert decision.decision_path == "MENU"


def test_rule_locked_on_keyword(tmp_path):
    router, _ = _build_router(tmp_path)

    decision = router.route("查下我的待办")

    assert decision.primary == "todo_query"
    assert decision.decision_path == "RULE_LOCKED"
    assert decision.confidence == 0.95


def test_rule_lock_batch_before_tag(tmp_path):
    """“批量打标签”同时命中两条硬规则，batch_task 优先（顺序即优先级）。"""
    router, _ = _build_router(tmp_path)

    decision = router.route("批量给这批客户打上体验标签")

    assert decision.primary == "batch_task"
    assert decision.decision_path == "RULE_LOCKED"


# ---------- 路径：EMB_FALLBACK / CLARIFY / UNKNOWN（LLM=None 降级） ----------


def test_emb_fallback_when_llm_unavailable(tmp_path):
    router, _ = _build_router(tmp_path)

    decision = router.route("张姐的画像给我看下")

    assert decision.primary == "profile_query"
    assert decision.decision_path == "EMB_FALLBACK"
    assert decision.candidates  # 候选明细可供 Monitor 审查


def test_unknown_on_noise_input(tmp_path):
    router, _ = _build_router(tmp_path)

    decision = router.route("xyzz")

    assert decision.decision_path == "UNKNOWN"
    assert decision.primary == "unknown"


# ---------- 路径：FUSED（mock LLM） ----------


def test_fused_formula_llm_emb_agree(tmp_path):
    """LLM 与 Embedding 一致：0.6×llm + 0.3×emb + 一致 +0.05，达阈值走 FUSED。"""
    router = _router_with_llm(tmp_path, ("profile_query", 0.9))

    decision = router.route("看下张姐的客户画像")

    assert decision.decision_path == "FUSED"
    assert decision.primary == "profile_query"
    assert decision.confidence >= 0.6 * 0.9 + 0.05


def test_fused_low_score_goes_unknown(tmp_path):
    router = _router_with_llm(tmp_path, ("profile_query", 0.1))

    decision = router.route("xyzz qqqq")

    assert decision.decision_path == "UNKNOWN"


def test_clarify_margin_constant():
    assert CLARIFY_MARGIN == 0.10


# ---------- LLMClassifier._parse ----------


def test_llm_parse_plain_json():
    assert LLMClassifier._parse('{"intent": "todo_query", "confidence": 0.9}') == ("todo_query", 0.9)


def test_llm_parse_markdown_wrapped():
    assert LLMClassifier._parse('```json\n{"intent": "talk_script", "confidence": 0.8}\n```') == ("talk_script", 0.8)


def test_llm_parse_clamps_and_defaults():
    assert LLMClassifier._parse('{"intent": "chitchat", "confidence": 1.5}') == ("chitchat", 1.0)
    assert LLMClassifier._parse('{"intent": "chitchat"}') == ("chitchat", 0.0)  # 缺失取 0.0
    assert LLMClassifier._parse('{"intent": "chitchat", "confidence": "high"}') == ("chitchat", 0.5)  # 非数值兜底
    assert LLMClassifier._parse("无法解析的回复") is None
    assert LLMClassifier._parse('{"confidence": 0.9}') is None


# ---------- Schema 管理接口 ----------


def _build_client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("SALE_INTERNAL_API_REGISTRY", str(tmp_path / "runs.json"))
    monkeypatch.setenv("SALE_TRACE_DB", str(tmp_path / "trace.db"))
    monkeypatch.setenv("SALE_INTENT_DB", str(tmp_path / "intents.db"))
    monkeypatch.setenv("SALE_REDIS_URL", "redis://127.0.0.1:16399/0")
    monkeypatch.delenv("SALE_LLM_API_KEY", raising=False)
    return TestClient(create_app())


def test_list_intents_returns_13_seeded(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)

    body = client.get("/api/ai/intents").json()

    assert body["code"] == "OK"
    assert len(body["data"]) == 13
    assert all(row["example_count"] >= 5 for row in body["data"])


def test_add_example_reloads_classifier(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)

    resp = client.post("/api/ai/intents/off_topic/examples", json={"text": "帮我写一首诗"})

    assert resp.status_code == 200
    assert resp.json()["data"]["intent"] == "off_topic"
    rows = client.app.state.intent_catalog.list_examples("off_topic")
    assert any(row["text"] == "帮我写一首诗" for row in rows)


def test_add_example_unknown_intent_404(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)

    resp = client.post("/api/ai/intents/not_exist/examples", json={"text": "x"})

    assert resp.status_code == 404


# ---------- chat 全链路：done 事件与 Trace 落库带路由决策 ----------


def _parse_sse(text: str) -> list[dict]:
    return [json.loads(line[5:].strip()) for line in text.splitlines() if line.strip().startswith("data:")]


def test_chat_done_event_carries_routing(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)

    resp = client.post("/api/ai/chat", json={"session_id": "m3-1", "message": "查下我的待办"})
    done = _parse_sse(resp.text)[-1]

    assert done["type"] == "done"
    assert done["intent"] == "todo_query"
    assert done["decision_path"] == "RULE_LOCKED"
    assert done["confidence"] == 0.95

    run = client.get(f"/api/ai/runs/{done['run_id']}").json()["data"]["run"]
    assert run["intent"] == "todo_query"
    assert run["decision_path"] == "RULE_LOCKED"
    assert run["confidence"] == 0.95


def test_chat_menu_intent_injected(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)

    resp = client.post("/api/ai/chat", json={"session_id": "m3-2", "message": "任意输入", "intent": "customer_search"})
    done = _parse_sse(resp.text)[-1]

    assert done["intent"] == "customer_search"
    assert done["decision_path"] == "MENU"
    assert done["confidence"] == 1.0
