"""M4 mcp-server 工具网关单测：权限四闸门 + 缓存/no-cache + 幂等重放 + 审计。

用 monkeypatch 替换 ToolGateway._request 隔离 business-mock 上游。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

os.environ.setdefault("SALE_MCP_AUDIT_DB", "/tmp/m4_test_mcp_audit.db")

import pytest
from fastapi.testclient import TestClient
from sale_server import app as mcp_app
from sale_server.tools import TOOL_SPECS, ToolError

SECRET = "sale-dev-jwt-secret-please-change-me-0123456789"


def _jwt(eid: int = 1, role: str = "employee", secret: str = SECRET) -> str:
    def segment(payload: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()

    header, body = (
        segment({"alg": "HS256", "typ": "JWT"}),
        segment({"eid": eid, "sub": f"user{eid}", "name": f"员工{eid}", "role": role, "exp": int(time.time()) + 3600}),
    )
    signature = hmac.new(secret.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


class _FakeUpstream:
    """按路径返回 business-mock 数据，可注入越权 403；统计调用次数。"""

    def __init__(self, forbidden_customer: int | None = None) -> None:
        self.calls = 0
        self.forbidden_customer = forbidden_customer

    def request(self, method: str, path: str, jwt_token: str, json_body: dict | None = None):
        self.calls += 1
        if f"/api/v1/customers/{self.forbidden_customer}" == path:
            raise ToolError("E_FORBIDDEN", 403, f"客户不属于当前员工: {self.forbidden_customer}")
        if path == "/api/v1/customers/1":
            return {"id": 1, "name": "王阿姨"}
        if path == "/api/v1/customers/1/profile":
            return [{"fieldKey": "preference", "fieldValue": "爱喝茶"}]
        if path == "/api/v1/customers/1/follow-ups":
            return [{"id": 101, "content": "跟进内容"}]
        if path == "/api/v1/customers/1/purchases":
            return [{"id": 1, "amount": 100}]
        if path == "/api/v1/customers/1/profile/fields":
            return [{"fieldKey": item["fieldKey"], "version": 1} for item in (json_body or {}).get("fields", [])]
        raise ToolError("E_NOT_FOUND", 404, f"unexpected path: {path}")


@pytest.fixture()
def client(monkeypatch):
    upstream = _FakeUpstream()
    monkeypatch.setattr(mcp_app.gateway, "_request", upstream.request)
    mcp_app.gateway._cache.clear()
    mcp_app.gateway._idempotency.clear()
    return TestClient(mcp_app.app), upstream


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_health_lists_tools(client):
    test_client, _ = client
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["tools"] == len(TOOL_SPECS)  # 与注册表保持一致（含 save_tags）


def test_missing_or_invalid_jwt_returns_401(client):
    test_client, _ = client

    assert test_client.post("/tools/list_follow_ups/call", json={"args": {"customer_id": 1}}).status_code == 401
    bad = _auth(_jwt(secret="wrong-secret"))
    assert test_client.post("/tools/list_follow_ups/call", headers=bad, json={"args": {"customer_id": 1}}).status_code == 401


def test_unknown_role_returns_403(client):
    test_client, _ = client
    response = test_client.post("/tools/list_follow_ups/call", headers=_auth(_jwt(role="customer")), json={"args": {"customer_id": 1}})
    assert response.status_code == 403


def test_readonly_bypass_ownership_gate_ok(client):
    test_client, upstream = client

    response = test_client.post("/tools/list_follow_ups/call", headers=_auth(_jwt()), json={"args": {"customer_id": 1}})

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "OK"
    assert body["data"]["follow_ups"][0]["id"] == 101
    assert upstream.calls >= 2  # 归属校验 + 列表各一次


def test_readonly_cache_and_no_cache(client):
    test_client, upstream = client

    test_client.post("/tools/list_follow_ups/call", headers=_auth(_jwt()), json={"args": {"customer_id": 1}})
    calls_after_first = upstream.calls
    second = test_client.post("/tools/list_follow_ups/call", headers=_auth(_jwt()), json={"args": {"customer_id": 1}})
    assert second.json()["data"].get("_cache") == "hit"
    # 缓存命中仅省数据请求，归属闸门仍校验（+1 而非 +2）
    assert upstream.calls == calls_after_first + 1

    fresh = test_client.post(
        "/tools/list_follow_ups/call",
        headers={**_auth(_jwt()), "X-No-Cache": "true"},
        json={"args": {"customer_id": 1}},
    )
    assert fresh.status_code == 200
    assert fresh.json()["data"].get("_cache") != "hit"
    assert upstream.calls > calls_after_first  # no-cache 绕过缓存


def test_ownership_gate_denies_foreign_customer(client):
    test_client, upstream = client
    upstream.forbidden_customer = 9

    response = test_client.post("/tools/get_customer_profile/call", headers=_auth(_jwt()), json={"args": {"customer_id": 9}})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "E_FORBIDDEN"


def test_write_requires_idempotency_then_approval(client):
    test_client, _ = client
    args = {"args": {"customer_id": 1, "fields": [{"fieldKey": "demand", "fieldValue": "v", "evidence": "e"}]}}

    no_key = test_client.post("/tools/update_profile_field/call", headers=_auth(_jwt()), json=args)
    assert no_key.status_code == 400
    assert no_key.json()["detail"]["code"] == "E_IDEMPOTENCY_REQUIRED"

    no_token = test_client.post("/tools/update_profile_field/call", headers={**_auth(_jwt()), "X-Idempotency-Key": "k1"}, json=args)
    assert no_token.status_code == 403
    assert no_token.json()["detail"]["code"] == "E_APPROVAL_REQUIRED"


def test_write_with_full_credentials_and_idempotent_replay(client):
    test_client, _ = client
    headers = {**_auth(_jwt()), "X-Approval-Token": "tok-1", "X-Idempotency-Key": "proposal:p1"}
    args = {"args": {"customer_id": 1, "fields": [{"fieldKey": "demand", "fieldValue": "v", "evidence": "e"}]}}

    first = test_client.post("/tools/update_profile_field/call", headers=headers, json=args)
    assert first.status_code == 200
    assert first.json()["data"]["fields"][0]["version"] == 1

    replayed = test_client.post("/tools/update_profile_field/call", headers=headers, json=args)
    assert replayed.status_code == 200
    assert replayed.json()["data"]["_replayed"] is True


def test_denied_call_recorded_in_audit(client):
    test_client, upstream = client
    upstream.forbidden_customer = 9
    test_client.post("/tools/get_customer_profile/call", headers=_auth(_jwt()), json={"args": {"customer_id": 9}})

    logs = test_client.get("/audit/recent").json()["data"]["logs"]
    denied = [row for row in logs if row["status"] == "denied" and row["tool"] == "get_customer_profile"]
    assert denied
    assert denied[0]["error_code"] == "E_FORBIDDEN"
