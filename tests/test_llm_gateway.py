from __future__ import annotations

import httpx
import pytest
from sale_agent.ai.gateway import CostLedger, GatewaySettings, LLMGateway


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or str(self._payload)

    def json(self) -> dict:
        return self._payload


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def post(self, url: str, json: dict, headers: dict) -> FakeResponse:  # noqa: A002
        self.calls.append({"url": url, "json": json})
        return self.responses.pop(0)

    def close(self) -> None:
        pass


def _live_gateway(responses: list[FakeResponse], max_retries: int = 2) -> tuple[LLMGateway, FakeClient]:
    settings = GatewaySettings(api_key="sk-test", base_url="http://llm.test/v1", max_retries=max_retries)
    gateway = LLMGateway(settings=settings, ledger=CostLedger())
    fake = FakeClient(responses)
    gateway.client = fake  # type: ignore[assignment]
    return gateway, fake


def _chat_payload(content: str = "ok", prompt: int = 10, completion: int = 5) -> dict:
    return {
        "model": "gpt-4o-mini",
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion},
    }


def test_echo_mode_without_api_key(monkeypatch):
    monkeypatch.delenv("SALE_LLM_API_KEY", raising=False)
    gateway = LLMGateway(settings=GatewaySettings(api_key=""))

    result = gateway.chat([{"role": "user", "content": "你好"}])

    assert result.echo is True
    assert result.content == "echo: 你好"
    assert gateway.ledger.snapshot() == {}


def test_chat_success_records_cost(monkeypatch):
    monkeypatch.setattr("sale_agent.ai.gateway.time.sleep", lambda _s: None)
    gateway, fake = _live_gateway([FakeResponse(200, _chat_payload(prompt=12, completion=8))])

    result = gateway.chat([{"role": "user", "content": "hi"}])

    assert result.content == "ok"
    assert result.echo is False
    assert len(fake.calls) == 1
    snapshot = gateway.ledger.snapshot()
    assert snapshot["gpt-4o-mini"]["calls"] == 1
    assert snapshot["gpt-4o-mini"]["prompt_tokens"] == 12
    assert snapshot["gpt-4o-mini"]["completion_tokens"] == 8


def test_chat_retries_on_500_then_succeeds(monkeypatch):
    monkeypatch.setattr("sale_agent.ai.gateway.time.sleep", lambda _s: None)
    gateway, fake = _live_gateway([FakeResponse(500, text="boom"), FakeResponse(200, _chat_payload())])

    result = gateway.chat([{"role": "user", "content": "hi"}])

    assert result.content == "ok"
    assert len(fake.calls) == 2


def test_chat_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr("sale_agent.ai.gateway.time.sleep", lambda _s: None)
    gateway, fake = _live_gateway([FakeResponse(500, text="boom")] * 3, max_retries=2)

    with pytest.raises(RuntimeError, match="after 3 attempts"):
        gateway.chat([{"role": "user", "content": "hi"}])
    assert len(fake.calls) == 3


def test_chat_client_error_not_retried(monkeypatch):
    monkeypatch.setattr("sale_agent.ai.gateway.time.sleep", lambda _s: None)
    gateway, fake = _live_gateway([FakeResponse(401, text="unauthorized")])

    with pytest.raises(ValueError, match="401"):
        gateway.chat([{"role": "user", "content": "hi"}])
    assert len(fake.calls) == 1


def test_chat_timeout_retried(monkeypatch):
    monkeypatch.setattr("sale_agent.ai.gateway.time.sleep", lambda _s: None)
    settings = GatewaySettings(api_key="sk-test", base_url="http://llm.test/v1", max_retries=1)
    gateway = LLMGateway(settings=settings, ledger=CostLedger())

    class TimeoutThenOk(FakeClient):
        def post(self, url: str, json: dict, headers: dict):  # noqa: A002
            self.calls.append({"url": url})
            if len(self.calls) == 1:
                raise httpx.ConnectTimeout("timeout")
            return FakeResponse(200, _chat_payload())

    fake = TimeoutThenOk([])
    gateway.client = fake  # type: ignore[assignment]

    result = gateway.chat([{"role": "user", "content": "hi"}])
    assert result.content == "ok"
    assert len(fake.calls) == 2


def test_embed_echo_returns_deterministic_vectors(monkeypatch):
    monkeypatch.delenv("SALE_LLM_API_KEY", raising=False)
    gateway = LLMGateway(settings=GatewaySettings(api_key=""))

    vectors = gateway.embed(["客户A", "客户B"])

    assert len(vectors) == 2
    assert all(len(v) == 8 for v in vectors)
    assert vectors == gateway.embed(["客户A", "客户B"])


def test_embed_live_parses_sorted_data(monkeypatch):
    monkeypatch.setattr("sale_agent.ai.gateway.time.sleep", lambda _s: None)
    payload = {"data": [{"index": 1, "embedding": [0.2]}, {"index": 0, "embedding": [0.1]}]}
    gateway, _ = _live_gateway([FakeResponse(200, payload)])

    vectors = gateway.embed(["a", "b"])

    assert vectors == [[0.1], [0.2]]
