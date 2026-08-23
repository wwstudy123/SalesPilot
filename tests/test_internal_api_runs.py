from __future__ import annotations

from fastapi.testclient import TestClient
from sale_agent.internal_api.app import create_app


def _client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("SALE_INTERNAL_API_REGISTRY", str(tmp_path / "runs.json"))
    return TestClient(create_app())


def test_create_and_get_run(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    payload = {
        "run_id": "run-smoke",
        "project": {
            "project_id": "proj-smoke",
            "title": "Smoke Project",
            "premise": "最小闭环验证",
            "sections": [{"order": 1, "id": "intro", "title": "Intro"}],
        },
        "execution": {"provider": "openai", "model": "gpt-4o-mini"},
        "input": {"mode": "start", "prompt": "生成第一节"},
        "storage": {"kind": "local", "base_path": str(tmp_path / "run-output")},
    }

    resp = client.post("/internal/v1/runs", json=payload)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["run_id"] == "run-smoke"

    got = client.get("/internal/v1/runs/run-smoke")
    assert got.status_code == 200
    assert got.json()["data"]["run_id"] == "run-smoke"

    listed = client.get("/internal/v1/runs", params={"project_id": "proj-smoke"})
    assert listed.status_code == 200
    assert any(item["run_id"] == "run-smoke" for item in listed.json()["data"]["items"])


def test_create_run_requires_prompt(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    payload = {
        "run_id": "run-no-prompt",
        "project": {"project_id": "proj-x"},
        "input": {"mode": "start", "prompt": ""},
        "storage": {"kind": "local", "base_path": str(tmp_path / "run-output")},
    }

    resp = client.post("/internal/v1/runs", json=payload)
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_ARGUMENT"
