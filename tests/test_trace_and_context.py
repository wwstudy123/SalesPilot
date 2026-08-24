from __future__ import annotations

from sale_agent.ai.context_store import InMemoryContextStore, build_context_store
from sale_agent.ai.trace import TraceStore


def test_trace_run_and_span_lifecycle(tmp_path):
    store = TraceStore(str(tmp_path / "trace.db"))

    run_id = store.start_run("sess-1", user_id="emp-1")
    span_id = store.start_span(run_id, "respond")
    store.finish_span(span_id, "ok", {"model": "echo"})
    store.finish_run(run_id, "completed", intent="echo", routing_reason="passthrough", confidence=0.9)

    run = store.get_run(run_id)
    assert run is not None
    assert run["session_id"] == "sess-1"
    assert run["user_id"] == "emp-1"
    assert run["status"] == "completed"
    assert run["intent"] == "echo"
    assert run["confidence"] == 0.9
    assert run["finished_at"] is not None

    spans = store.list_spans(run_id)
    assert len(spans) == 1
    assert spans[0]["name"] == "respond"
    assert spans[0]["status"] == "ok"
    assert '"model": "echo"' in spans[0]["detail"]
    store.close()


def test_trace_missing_run_is_none(tmp_path):
    store = TraceStore(str(tmp_path / "trace.db"))
    assert store.get_run("nope") is None
    store.close()


def test_trace_list_runs_filters_by_monitor_fields(tmp_path):
    store = TraceStore(str(tmp_path / "trace.db"))
    first = store.start_run("session-a", user_id="1")
    second = store.start_run("session-b", user_id="2")
    store.finish_run(first, "completed", intent="talk_script", routing_reason="coach", confidence=0.9)
    store.finish_run(second, "failed", intent="tag_review", routing_reason="ops", confidence=0.8)

    result = store.list_runs(user_id="1", intent="talk_script", status="completed")
    assert [run["run_id"] for run in result] == [first]
    assert store.list_runs(session_id="session-b")[0]["run_id"] == second
    store.close()


def test_in_memory_context_trim():
    store = InMemoryContextStore(max_messages=4)

    for i in range(6):
        store.append("s", "user", f"msg-{i}")

    history = store.load("s")
    assert len(history) == 4
    assert history[0]["content"] == "msg-2"
    assert history[-1]["content"] == "msg-5"
    assert store.backend == "memory"


def test_build_context_store_fallback_when_redis_unreachable(monkeypatch):
    monkeypatch.setenv("SALE_REDIS_URL", "redis://127.0.0.1:16399/0")

    store = build_context_store()

    assert store.backend == "memory"
