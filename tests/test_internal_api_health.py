from __future__ import annotations

from fastapi.testclient import TestClient

from sagt_agent.internal_api.app import create_app


def test_health_returns_ok(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTKIT_INTERNAL_API_REGISTRY", str(tmp_path / "runs.json"))
    client = TestClient(create_app())

    resp = client.get("/internal/v1/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "OK"
    assert body["data"]["status"] == "ok"
    assert "run_count" in body["data"]
