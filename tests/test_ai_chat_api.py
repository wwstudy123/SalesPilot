from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sale_agent.internal_api.app import create_app


def _build_client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("SALE_INTERNAL_API_REGISTRY", str(tmp_path / "runs.json"))
    monkeypatch.setenv("SALE_TRACE_DB", str(tmp_path / "trace.db"))
    monkeypatch.setenv("SALE_INTENT_DB", str(tmp_path / "intents.db"))
    monkeypatch.setenv("SALE_KNOWLEDGE_DB", str(tmp_path / "knowledge.db"))
    monkeypatch.setenv("SALE_SUGGESTION_DB", str(tmp_path / "suggestions.db"))
    # 强制内存降级，避免依赖本机 Redis
    monkeypatch.setenv("SALE_REDIS_URL", "redis://127.0.0.1:16399/0")
    monkeypatch.delenv("SALE_LLM_API_KEY", raising=False)
    return TestClient(create_app())


def _parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            events.append(json.loads(line[5:].strip()))
    return events


def test_chat_sse_echo_stream(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)

    resp = client.post("/api/ai/chat", json={"session_id": "s1", "message": "今天先拜访哪位客户？"})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(resp.text)

    assert events[0]["type"] == "start"
    assert events[1]["type"] == "intent"  # M5 全量事件：意图先行
    tokens = [e for e in events if e["type"] == "token"]
    done = events[-1]
    assert "".join(e["content"] for e in tokens) == "echo: 今天先拜访哪位客户？"
    assert done["type"] == "done"
    assert done["status"] == "completed"
    assert done["run_id"] == events[0]["run_id"]
    assert done["echo"] is True


def test_chat_multi_turn_context_kept(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)

    client.post("/api/ai/chat", json={"session_id": "s2", "message": "第一句"})
    resp = client.post("/api/ai/chat", json={"session_id": "s2", "message": "第二句"})

    assert resp.status_code == 200
    history = client.app.state.context_store.load("s2")
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]
    assert history[0]["content"] == "第一句"
    assert history[2]["content"] == "第二句"


def test_run_trace_queryable(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)

    resp = client.post("/api/ai/chat", json={"session_id": "s3", "message": "trace me"})
    run_id = _parse_sse(resp.text)[0]["run_id"]

    detail = client.get(f"/api/ai/runs/{run_id}")
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["run"]["run_id"] == run_id
    assert data["run"]["session_id"] == "s3"
    assert data["run"]["status"] == "completed"
    # M3 起 route 节点真实分类："trace me" 无关键词、无相似样例 → UNKNOWN 入评测池
    assert data["run"]["intent"] == "unknown"
    assert data["run"]["decision_path"] == "UNKNOWN"
    span_names = [s["name"] for s in data["spans"]]
    assert span_names == ["load_context", "route", "respond", "save_context"]
    assert all(s["status"] == "ok" for s in data["spans"])


def test_run_not_found_404(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)

    resp = client.get("/api/ai/runs/nonexistent")

    assert resp.status_code == 404


def test_ai_health_reports_echo_and_memory(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)

    body = client.get("/api/ai/health").json()

    assert body["data"]["service"] == "sale-agent-ai"
    assert body["data"]["llm_mode"] == "echo"
    assert body["data"]["context_backend"] == "memory"


def test_cost_endpoint_shape(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)

    body = client.get("/api/ai/cost").json()

    assert body["code"] == "OK"
    assert body["data"] == {}  # echo 模式不计费
