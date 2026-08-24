"""sale-agent 侧轻量客户端：mcp-server 工具调用 + business-mock 凭证签发。"""

from __future__ import annotations

import os

import httpx

DEFAULT_MCP_URL = "http://127.0.0.1:9010"
DEFAULT_BUSINESS_URL = "http://127.0.0.1:8080"


class McpError(Exception):
    def __init__(self, code: str, http_status: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.message = message


class McpClient:
    def __init__(self, mcp_base_url: str | None = None, business_base_url: str | None = None) -> None:
        self._mcp = (mcp_base_url or os.environ.get("SALE_MCP_BASE_URL", DEFAULT_MCP_URL)).rstrip("/")
        self._business = (business_base_url or os.environ.get("SALE_BUSINESS_BASE_URL", DEFAULT_BUSINESS_URL)).rstrip("/")

    # ---------- 只读工具（bypass 免确认） ----------

    def list_follow_ups(self, customer_id: int, jwt: str, no_cache: bool = False) -> list[dict]:
        data = self._call_tool("list_follow_ups", {"customer_id": customer_id}, jwt, no_cache=no_cache)
        return data.get("follow_ups", [])

    def list_purchases(self, customer_id: int, jwt: str, no_cache: bool = False) -> list[dict]:
        data = self._call_tool("list_purchases", {"customer_id": customer_id}, jwt, no_cache=no_cache)
        return data.get("purchases", [])

    def get_profile(self, customer_id: int, jwt: str, no_cache: bool = False) -> list[dict]:
        data = self._call_tool("get_customer_profile", {"customer_id": customer_id}, jwt, no_cache=no_cache)
        return data.get("fields", [])

    def get_tags(self, customer_id: int, jwt: str) -> list[dict]:
        response = self._get(f"{self._business}/api/v1/customers/{customer_id}/tags", jwt)
        return response["data"]

    # ---------- write：凭证签发 + 携凭证执行 ----------

    def issue_approval(self, tool: str, customer_id: int, payload: dict, idempotency_key: str, jwt: str) -> dict:
        response = self._post(
            f"{self._business}/api/v1/approvals",
            {"tool": tool, "customerId": customer_id, "payload": payload, "idempotencyKey": idempotency_key},
            jwt,
        )
        return response["data"]

    def update_profile_fields(
        self, customer_id: int, fields: list[dict], approval_token: str, idempotency_key: str, jwt: str
    ) -> list[dict]:
        data = self._call_tool(
            "update_profile_field",
            {"customer_id": customer_id, "fields": fields},
            jwt,
            approval_token=approval_token,
            idempotency_key=idempotency_key,
        )
        return data.get("fields", [])

    def save_tags(self, customer_id: int, tags: list[dict], approval_token: str, idempotency_key: str, jwt: str) -> list[dict]:
        data = self._call_tool(
            "save_tags",
            {"customer_id": customer_id, "tags": tags},
            jwt,
            approval_token=approval_token,
            idempotency_key=idempotency_key,
        )
        return data.get("tags", [])

    # ---------- 内部 ----------

    def _call_tool(
        self, name: str, args: dict, jwt: str, approval_token: str | None = None, idempotency_key: str | None = None, no_cache: bool = False
    ) -> dict:
        headers = {"Authorization": f"Bearer {jwt}"}
        if approval_token:
            headers["X-Approval-Token"] = approval_token
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        if no_cache:
            headers["X-No-Cache"] = "true"
        try:
            response = httpx.post(f"{self._mcp}/tools/{name}/call", headers=headers, json={"args": args}, timeout=5.0)
        except httpx.HTTPError as exc:
            raise McpError("E_MCP_UNAVAILABLE", 502, f"mcp-server 不可用: {exc}") from exc
        # mcp-server 成功响应为信封 {code, message, data}，工具结果在 data 内
        envelope = self._unwrap(response)
        return envelope.get("data") or {}

    @staticmethod
    def _post(url: str, body: dict, jwt: str) -> dict:
        try:
            response = httpx.post(url, headers={"Authorization": f"Bearer {jwt}"}, json=body, timeout=5.0)
        except httpx.HTTPError as exc:
            raise McpError("E_BUSINESS_UNAVAILABLE", 502, f"业务后端不可用: {exc}") from exc
        return McpClient._unwrap_static(response)

    @staticmethod
    def _get(url: str, jwt: str) -> dict:
        try:
            response = httpx.get(url, headers={"Authorization": f"Bearer {jwt}"}, timeout=5.0)
        except httpx.HTTPError as exc:
            raise McpError("E_BUSINESS_UNAVAILABLE", 502, f"业务后端不可用: {exc}") from exc
        return McpClient._unwrap_static(response)

    def _unwrap(self, response: httpx.Response) -> dict:
        return self._unwrap_static(response)

    @staticmethod
    def _unwrap_static(response: httpx.Response) -> dict:
        if response.status_code < 400:
            return response.json()
        try:
            detail = response.json().get("detail") or response.json()
        except ValueError:
            detail = {}
        if isinstance(detail, dict):
            code = detail.get("code", f"E_HTTP_{response.status_code}")
            message = detail.get("message", response.text)
        else:
            code, message = f"E_HTTP_{response.status_code}", str(detail)
        raise McpError(code, response.status_code, message)
