"""M5 话术 Agent + RAG：知识库/检索/Coach 子图/建议卡 HITL/SSE 全量事件。"""

from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient
from sale_agent.ai.gateway import LLMGateway
from sale_agent.coach.skills import select_skill
from sale_agent.coach.subgraph import CoachSubgraph
from sale_agent.internal_api.app import create_app
from sale_agent.kb.seed_data import PLAYBOOKS, PRODUCTS, load_seed
from sale_agent.kb.store import KnowledgeStore, split_chunks
from sale_agent.kb.vector_store import MilvusVectorStore, build_vector_backend
from sale_agent.profile.mcp_client import McpError
from sale_agent.rag.pipeline import RAGPipeline
from sale_agent.suggestion.store import RegenerateLimitError, SuggestionStore

# ---------- 基建 ----------


class _EchoGateway:
    class settings:  # noqa: D401
        echo_mode = True

    def chat(self, messages):
        raise AssertionError("echo 模式不应调用 LLM")


class _FakeMcp:
    """McpClient 替身：可控返回画像/跟进，或抛 McpError。"""

    def __init__(self, profile=None, follow_ups=None, fail: bool = False) -> None:
        self._profile = profile or []
        self._follow_ups = follow_ups or []
        self._fail = fail

    def get_profile(self, customer_id, jwt, no_cache=False):
        if self._fail:
            raise McpError("E_FORBIDDEN", 403, "越权")
        return self._profile

    def list_follow_ups(self, customer_id, jwt, no_cache=False):
        if self._fail:
            raise McpError("E_FORBIDDEN", 403, "越权")
        return self._follow_ups


@pytest.fixture()
def kb(tmp_path):
    store = KnowledgeStore(str(tmp_path / "knowledge.db"))
    load_seed(store)
    return store


@pytest.fixture()
def rag(kb):
    return RAGPipeline(kb, _EchoGateway())


def _build_coach(tmp_path, rag_pipeline, mcp=None):
    suggestions = SuggestionStore(str(tmp_path / "suggestions.db"))
    return CoachSubgraph(mcp or _FakeMcp(), rag_pipeline, suggestions, _EchoGateway()), suggestions


# ---------- 知识库入库管线 ----------


def test_seed_playbook_count_meets_baseline(kb):
    assert len(PLAYBOOKS) >= 30
    stats = kb.stats()
    assert stats["ready_chunks"] >= 30


def test_split_chunks_respects_max_len():
    long_text = "。".join(f"第{i}句内容测试" for i in range(60))
    chunks = split_chunks(long_text, max_len=100)
    assert all(len(chunk) <= 110 for chunk in chunks)  # 句尾拼接允许微量超限
    assert "".join(chunks).count("第") == 60


def test_ingest_staging_invisible_until_publish(tmp_path):
    store = KnowledgeStore(str(tmp_path / "kb.db"))
    store.ingest("playbook", "草稿", "draft-src", ["话术：先测试后发布。"])
    assert store.ready_chunks() == []  # staging 不可检索
    store.publish("playbook", "draft-src")
    assert len(store.ready_chunks()) == 1


def test_publish_atomic_switch_archives_old_version(tmp_path):
    store = KnowledgeStore(str(tmp_path / "kb.db"))
    store.ingest("playbook", "手册v1", "src-a", ["旧版话术内容。"])
    store.publish("playbook", "src-a")
    store.ingest("playbook", "手册v2", "src-a", ["新版话术内容。"])
    store.publish("playbook", "src-a")
    chunks = store.ready_chunks()
    assert len(chunks) == 1  # 原子切换：旧版归档，检索只见新版
    assert "新版" in chunks[0]["content"]


def test_publish_without_staging_raises(tmp_path):
    store = KnowledgeStore(str(tmp_path / "kb.db"))
    with pytest.raises(ValueError):
        store.publish("playbook", "nonexistent")


# ---------- RAG 管线 ----------


def test_rag_hits_price_objection(kb, rag):
    result = rag.retrieve("客户说太贵了怎么办", domain="playbook")
    assert result.citations, "应命中话术"
    titles = [citation["title"] for citation in result.citations]
    assert any("太贵" in title for title in titles)


def test_rag_domain_filter_excludes_other_collection(kb, rag):
    result = rag.retrieve("滤芯更换成本多少钱", domain="playbook")
    for hit in result.hits:
        assert "滤芯更换成本说明" != hit.title  # product_kb 不串集合


def test_rag_inject_limits(kb, rag):
    result = rag.retrieve("回访 异议 促单 售后 送礼 竞品", domain="playbook")
    assert len(result.citations) <= 5
    assert len(result.knowledge_zone) <= 1300  # ≤1200 token + 角标余量
    for index, citation in enumerate(result.citations):
        assert citation["label"] == f"c{index + 1}"


def test_rag_empty_kb_returns_no_hits(tmp_path):
    empty = KnowledgeStore(str(tmp_path / "empty.db"))
    pipeline = RAGPipeline(empty, _EchoGateway())
    result = pipeline.retrieve("随便问点什么")
    assert result.hits == []
    assert result.citations == []


def test_rag_rewrite_injects_customer_slots(rag):
    result = rag.retrieve(
        "写回访话术", domain="playbook", customer_ctx={"name": "王女士", "value_tier": "high", "recent_focus": "滤芯成本"}
    )
    assert "王女士" in result.rewritten_query
    assert "high" in result.rewritten_query


# ---------- Coach 子图 ----------


def test_coach_generate_with_citations_and_profile(tmp_path, rag):
    mcp = _FakeMcp(
        profile=[{"fieldKey": "value_tier", "fieldValue": "medium"}, {"fieldKey": "lifecycle_stage", "fieldValue": "意向期"}],
        follow_ups=[{"channel": "visit", "content": "客户到店看了 X800"}],
    )
    coach, suggestions = _build_coach(tmp_path, rag, mcp)
    result = coach.generate(
        intent="talk_script",
        message="给客户写回访话术",
        customer_id=1,
        employee_id=1,
        jwt="fake",
        session_id="s1",
        run_id="r1",
    )
    assert result["skill"]["id"] == "intent-followup"
    assert result["citations"], "话术必须带引用"
    assert "X800" in result["reply"]  # medium 分层产品匹配
    assert result["suggestion_id"] is not None
    assert suggestions.get(result["suggestion_id"])["status"] == "pending"


def test_coach_self_check_strips_push_for_sensitive_customer(tmp_path, rag):
    mcp = _FakeMcp(profile=[{"fieldKey": "sensitive_point", "fieldValue": "反感催促，别催我"}])
    coach, _ = _build_coach(tmp_path, rag, mcp)
    result = coach.generate(
        intent="objection_help",
        message="客户说太贵了，帮我促单留名额",
        customer_id=1,
        employee_id=1,
        jwt="fake",
        session_id="s1",
        run_id="r1",
    )
    assert "名额" not in result["reply"]  # 促单表述被冲突降级剔除
    assert any("催促" in warning for warning in result["warnings"])


def test_coach_mcp_failure_degrades_to_generic(tmp_path, rag):
    coach, _ = _build_coach(tmp_path, rag, _FakeMcp(fail=True))
    result = coach.generate(
        intent="talk_script",
        message="写话术",
        customer_id=1,
        employee_id=1,
        jwt="fake",
        session_id="s1",
        run_id="r1",
    )
    assert any("拉取失败" in warning for warning in result["warnings"])
    assert result["tool_calls"][0]["ok"] is False
    assert result["reply"]  # 降级不阻断


def test_coach_no_customer_context_marks_warning(tmp_path, rag):
    coach, _ = _build_coach(tmp_path, rag)
    result = coach.generate(
        intent="talk_script",
        message="写话术",
        customer_id=None,
        employee_id=1,
        jwt=None,
        session_id="s1",
        run_id="r1",
    )
    assert any("未装载客户事实" in warning for warning in result["warnings"])


def test_select_skill_mapping():
    assert select_skill("talk_script")["id"] == "intent-followup"
    assert select_skill("objection_help")["id"] == "objection-handling"
    assert select_skill("schedule_help")["id"] == "intent-followup"  # 回落


# ---------- 建议卡 HITL ----------


def test_suggestion_adopt_and_modify(tmp_path, rag):
    coach, store = _build_coach(tmp_path, rag)
    result = coach.generate(
        intent="talk_script",
        message="写话术",
        customer_id=1,
        employee_id=1,
        jwt=None,
        session_id="s1",
        run_id="r1",
    )
    suggestion_id = result["suggestion_id"]
    adopted = store.adopt(suggestion_id)
    assert adopted["status"] == "adopted"

    modified = coach.generate(
        intent="talk_script",
        message="再写一版",
        customer_id=1,
        employee_id=1,
        jwt=None,
        session_id="s1",
        run_id="r2",
    )
    edited = store.adopt(modified["suggestion_id"], edited_content="员工手动改写的话术")
    assert edited["status"] == "modified"
    assert edited["content"] == "员工手动改写的话术"
    actions = store.actions(modified["suggestion_id"])
    assert [action["action"] for action in actions] == ["create", "modify"]


def test_suggestion_reject_requires_reason(tmp_path, rag):
    coach, store = _build_coach(tmp_path, rag)
    result = coach.generate(
        intent="talk_script",
        message="写话术",
        customer_id=1,
        employee_id=1,
        jwt=None,
        session_id="s1",
        run_id="r1",
    )
    rejected = store.reject(result["suggestion_id"], "口径不合适")
    assert rejected["status"] == "rejected"
    with pytest.raises(ValueError):
        store.adopt(result["suggestion_id"])  # 已拒绝不可再采纳


def test_suggestion_regenerate_limit(tmp_path, rag):
    coach, store = _build_coach(tmp_path, rag)
    result = coach.generate(
        intent="talk_script",
        message="写话术",
        customer_id=1,
        employee_id=1,
        jwt=None,
        session_id="s1",
        run_id="r1",
    )
    suggestion_id = result["suggestion_id"]
    for round_no in (1, 2):
        updated = store.regenerate(suggestion_id, f"要求{round_no}", f"新内容{round_no}", [], [])
        assert updated["regenerate_count"] == round_no
    with pytest.raises(RegenerateLimitError):
        store.regenerate(suggestion_id, "第三次", "不可能", [], [])
    actions = store.actions(suggestion_id)
    assert sum(1 for action in actions if action["action"] == "regenerate") == 2


# ---------- API：SSE 全量事件 + kb/建议卡端点 ----------


def _build_client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("SALE_INTERNAL_API_REGISTRY", str(tmp_path / "runs.json"))
    monkeypatch.setenv("SALE_TRACE_DB", str(tmp_path / "trace.db"))
    monkeypatch.setenv("SALE_INTENT_DB", str(tmp_path / "intents.db"))
    monkeypatch.setenv("SALE_KNOWLEDGE_DB", str(tmp_path / "knowledge.db"))
    monkeypatch.setenv("SALE_SUGGESTION_DB", str(tmp_path / "suggestions.db"))
    monkeypatch.setenv("SALE_REDIS_URL", "redis://127.0.0.1:16399/0")
    monkeypatch.delenv("SALE_LLM_API_KEY", raising=False)
    return TestClient(create_app())


def _parse_sse(text: str) -> list[dict]:
    return [json.loads(line[5:].strip()) for line in text.splitlines() if line.startswith("data:")]


def _fake_jwt(employee_id: int = 1) -> str:
    """仅构造 payload（签名由 mcp-server 闸门校验，此处只测身份提取）。"""
    payload = base64.urlsafe_b64encode(json.dumps({"eid": employee_id, "role": "employee"}).encode()).rstrip(b"=")
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=")
    return f"{header.decode()}.{payload.decode()}.sig"


def test_chat_sse_coach_full_event_sequence(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)
    client.post("/api/ai/kb/seed")
    client.app.state.chat_graph.coach._mcp = _FakeMcp(
        profile=[{"fieldKey": "value_tier", "fieldValue": "medium"}],
        follow_ups=[{"channel": "visit", "content": "看过 X800"}],
    )

    resp = client.post(
        "/api/ai/chat",
        json={"session_id": "s-talk", "message": "给王女士写一段回访话术", "customer_id": 1, "intent": "talk_script"},
        headers={"Authorization": f"Bearer {_fake_jwt()}"},
    )
    events = _parse_sse(resp.text)
    types = [event["type"] for event in events]
    assert types[0] == "start"
    assert "intent" in types and "rag_citation" in types and "token" in types
    assert "proposal" in types and types[-1] == "done"
    tool_events = [event for event in events if event["type"] == "tool_call"]
    assert {call["tool"] for call in tool_events} == {"get_customer_profile", "list_follow_ups"}
    proposal = next(event for event in events if event["type"] == "proposal")
    assert proposal["suggestion_id"] > 0
    reply = "".join(event["content"] for event in events if event["type"] == "token")
    assert "[c" in reply  # 引用角标进入正文


def test_kb_search_endpoint(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)
    assert client.post("/api/ai/kb/seed").json()["data"]["stats"]["ready_chunks"] >= 30
    body = client.get("/api/ai/kb/search", params={"q": "客户嫌太贵", "domain": "playbook"}).json()
    assert body["code"] == "OK"
    assert any("太贵" in hit["title"] for hit in body["data"]["hits"])


def test_suggestion_endpoints_flow(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)
    client.post("/api/ai/kb/seed")
    client.app.state.chat_graph.coach._mcp = _FakeMcp()
    resp = client.post(
        "/api/ai/chat",
        json={"session_id": "s-sug", "message": "写回访话术", "intent": "talk_script"},
    )
    proposal = next(event for event in _parse_sse(resp.text) if event["type"] == "proposal")
    suggestion_id = proposal["suggestion_id"]

    # 重新生成 ≤2
    regen = client.post(f"/api/ai/suggestions/{suggestion_id}/regenerate", json={"requirement": "更口语化一些"})
    assert regen.status_code == 200
    regen2 = client.post(f"/api/ai/suggestions/{suggestion_id}/regenerate", json={"requirement": "再简短一点"})
    assert regen2.status_code == 200
    regen3 = client.post(f"/api/ai/suggestions/{suggestion_id}/regenerate", json={"requirement": "再来一次"})
    assert regen3.status_code == 409  # 超限
    # 拒绝必填原因（Pydantic 422）+ 正常拒绝
    assert client.post(f"/api/ai/suggestions/{suggestion_id}/reject", json={"reason": ""}).status_code == 422
    assert client.post(f"/api/ai/suggestions/{suggestion_id}/reject", json={"reason": "不合适"}).status_code == 200
    # 已拒绝重复操作 409
    assert client.post(f"/api/ai/suggestions/{suggestion_id}/adopt", json={}).status_code == 409
    actions = client.get(f"/api/ai/suggestions/{suggestion_id}/actions").json()["data"]
    kinds = [action["action"] for action in actions]
    assert kinds == ["create", "regenerate", "regenerate", "reject"]


# ---------- M5 续：listwise rerank / 上传端点 / Milvus 降级 / 种子基线 ----------


def test_rag_mode_is_rrf_in_echo(tmp_path):
    """echo 模式下 LLM listwise 重排被跳过，RagResult.mode == 'rrf'（架构 A8 降级）。"""
    store = KnowledgeStore(str(tmp_path / "rag.db"))
    load_seed(store)
    rag = RAGPipeline(store, _EchoGateway())
    result = rag.retrieve("客户嫌价格太贵了", customer_ctx={"tags": ["价格敏感"]})
    assert result.mode == "rrf"
    assert result.citations  # 命中
    assert result.rewritten_query  # 改写已产出


def test_rerank_parser_indices_dedup_and_fallback():
    """_parse_rerank_indices：去重保序、剔除越界、漏列按原序补齐。"""
    parse = LLMGateway._parse_rerank_indices
    assert parse("[1]\n[0]\n[2]", 3, 3) == [1, 0, 2]
    assert parse("[0]\n[0]\n[9]", 3, 3) == [0, 1, 2]  # 越界/重复被过滤，剩余按原序补齐
    assert parse("模型未给序号", 3, 3) == [0, 1, 2]  # 解析空 → 原序兜底


def test_rag_listwise_reranks_hits(tmp_path):
    """live 模式 LLM listwise 重排：mode='listwise'，命中按模型序重排。"""
    store = KnowledgeStore(str(tmp_path / "rag2.db"))
    # 3 条可控话术，均含「客户嫌太贵」保证 query 命中全部且过阈值
    store.ingest(
        "playbook",
        "异议-太贵",
        "up-too-expensive",
        ["客户嫌太贵时，先认同再算账，对比滤芯年均成本与桶装水，凸显长期省钱。"],
    )
    store.ingest(
        "playbook",
        "异议-再考虑",
        "up-think-again",
        ["客户嫌太贵说要再考虑，用二选一封闭提问锁定顾虑，给台阶同时约下次跟进。"],
    )
    store.ingest(
        "playbook",
        "异议-网上便宜",
        "up-online-cheap",
        ["客户嫌太贵说网上更便宜，对比本地安装售后与滤芯真伪，强调服务价值而非贬低对手。"],
    )
    store.publish("playbook", "up-too-expensive")
    store.publish("playbook", "up-think-again")
    store.publish("playbook", "up-online-cheap")

    # echo 基线：RRF 直出
    echo_rag = RAGPipeline(store, _EchoGateway())
    echo = echo_rag.retrieve("客户嫌太贵")
    assert echo.mode == "rrf"
    echo_titles = [c["title"] for c in echo.citations]
    assert len(echo_titles) == 3

    # live listwise：模型输出逆序
    rag = RAGPipeline(store, _ReverseListwiseGateway())
    live = rag.retrieve("客户嫌太贵")
    assert live.mode == "listwise"
    live_titles = [c["title"] for c in live.citations]
    assert live_titles == list(reversed(echo_titles))  # 重排生效


def test_kb_upload_endpoint_publishes_and_searchable(monkeypatch, tmp_path):
    """POST /api/ai/kb/upload：上传 → 切片 → 原子发布 → 立即可检索。"""
    client = _build_client(monkeypatch, tmp_path)
    resp = client.post(
        "/api/ai/kb/upload",
        json={
            "domain": "product",
            "title": "上传测试产品",
            "source": "up-test-prod",
            "texts": [
                "这是一段测试正文，讲产品卖点与售后。",
                "另一段讲价格与适用场景，客户嫌贵可算账。",
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["ready"] is True
    assert data["ingested"]["chunk_count"] >= 1
    assert data["published"]["published"] >= 1
    # 立即可检索
    search = client.get("/api/ai/kb/search", params={"q": "测试产品"}).json()["data"]
    assert any(hit["title"] == "上传测试产品" for hit in search["hits"])
    # 非法 domain 422
    assert client.post("/api/ai/kb/upload", json={"domain": "x", "title": "t", "texts": ["a"]}).status_code == 422


def test_kb_stats_reports_vector_backend_lite(monkeypatch, tmp_path):
    """/kb/stats 与 /health 报告 vector_backend=lite（默认无 Milvus，A8 降级）。"""
    client = _build_client(monkeypatch, tmp_path)
    stats = client.get("/api/ai/kb/stats").json()["data"]
    assert stats["vector_backend"] == "lite"
    health = client.get("/api/ai/health").json()["data"]
    assert health["vector_backend"] == "lite"


def test_milvus_backend_unavailable_when_no_pymilvus_or_host():
    """无 pymilvus 或实例不可达 → is_available=False；build_vector_backend env=lite 默认 None。"""
    store = MilvusVectorStore(host="127.0.0.1", port=19530)
    # 本机通常无 pymilvus 或 Milvus 未起，is_available 应为 False（触发 lite 降级）
    assert store.is_available() is False
    # 默认 env（lite）→ None，调用方走 lite
    assert build_vector_backend() is None
    # 显式 milvus 但不可用 → 同样降级 None
    import os

    os.environ["SALE_VECTOR_BACKEND"] = "milvus"
    try:
        assert build_vector_backend() is None
    finally:
        os.environ.pop("SALE_VECTOR_BACKEND", None)


def test_seed_data_meets_baseline():
    """种子基线：话术 ≥30、商品 ≥10（doc §2.1 MVP 基线）。"""
    assert len(PLAYBOOKS) >= 30
    assert len(PRODUCTS) >= 10


# ---------- 测试辅助：live listwise 假 gateway ----------


class _ReverseListwiseGateway:
    """live 模式假 gateway：rerank 把候选逆序返回，证明 _rerank_hits 重排生效。"""

    class settings:  # noqa: D401
        echo_mode = False

    def rerank(self, query, documents, top_n=5):
        # 逆序返回候选下标，模拟 LLM listwise 输出
        n = len(documents)
        return list(reversed(range(n)))[: max(1, top_n)]
