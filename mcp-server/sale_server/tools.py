"""统一工具网关（架构 §4 的 MVP 形态：纯 HTTP，接口形状按可迁移 MCP SDK 设计）。

权限四闸门：① JWT 身份（app 层）→ ② 角色 → ③ 客户归属（转发 business-mock 校验）
           → ④ bypass 白名单：只读工具免确认，write 强制 approval_token。
治理：只读缓存（profile 10min / list 60s）、write 幂等重放、逐调用审计。
"""

from __future__ import annotations

import os
import time

import httpx

from sale_server.audit import AuditStore
from sale_server.auth import Identity

BUSINESS_BASE_URL = os.environ.get("SALE_BUSINESS_BASE_URL", "http://127.0.0.1:8080")

# 工具清单：name → (只读, 超时ms, 入参 schema 描述)。bypass 白名单 = 只读集合。
TOOL_SPECS: dict[str, dict] = {
    "search_customers": {
        "readonly": True,
        "timeout_ms": 1500,
        "description": "按姓名/标签/阶段检索当前员工可见客户",
        "args": {"keyword": "string?", "stage": "new|prospective|existing|churn_risk?"},
    },
    "get_customer_profile": {
        "readonly": True,
        "timeout_ms": 1000,
        "description": "客户画像（字段级：值/依据/版本/更新时间）",
        "args": {"customer_id": "int(必填)"},
    },
    "list_follow_ups": {
        "readonly": True,
        "timeout_ms": 1500,
        "description": "客户跟进记录（倒序）",
        "args": {"customer_id": "int(必填)"},
    },
    "list_purchases": {
        "readonly": True,
        "timeout_ms": 1500,
        "description": "客户消费记录",
        "args": {"customer_id": "int(必填)"},
    },
    "update_profile_field": {
        "readonly": False,
        "timeout_ms": 2000,
        "description": "画像字段更新（write：必须携 approval_token + idempotency_key）",
        "args": {"customer_id": "int(必填)", "fields": "[{fieldKey,fieldValue,evidence}](必填)"},
    },
}

# 只读缓存 TTL（架构 §4：profile 10min、list 60s；演示期内存实现，事件失效留 M5）
_CACHE_TTL = {"get_customer_profile": 600, "list_follow_ups": 60, "list_purchases": 60}


class ToolError(Exception):
    def __init__(self, code: str, http_status: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.message = message


class ToolGateway:
    def __init__(self, audit: AuditStore, business_base_url: str | None = None) -> None:
        self._audit = audit
        self._base_url = (business_base_url or BUSINESS_BASE_URL).rstrip("/")
        self._cache: dict[tuple, tuple[float, dict]] = {}
        self._idempotency: dict[str, dict] = {}

    # ---------- 主入口 ----------

    def call(
        self,
        name: str,
        args: dict,
        identity: Identity,
        jwt_token: str,
        approval_token: str | None = None,
        idempotency_key: str | None = None,
        no_cache: bool = False,
    ) -> dict:
        spec = TOOL_SPECS.get(name)
        if spec is None:
            raise ToolError("E_TOOL_NOT_FOUND", 404, f"未知工具: {name}")
        customer_id = args.get("customer_id")
        started = time.monotonic()
        try:
            if spec["readonly"]:
                data = self._call_readonly(name, args, identity, jwt_token, no_cache=no_cache)
            else:
                data = self._call_write(name, args, identity, jwt_token, approval_token, idempotency_key)
        except ToolError as err:
            self._audit.log(
                tool=name,
                actor_id=identity.employee_id,
                customer_id=customer_id,
                status="denied",
                http_status=err.http_status,
                latency_ms=int((time.monotonic() - started) * 1000),
                bypass=spec["readonly"],
                idempotency_key=idempotency_key,
                error_code=err.code,
            )
            raise
        except httpx.HTTPError as err:
            self._audit.log(
                tool=name,
                actor_id=identity.employee_id,
                customer_id=customer_id,
                status="upstream_error",
                latency_ms=int((time.monotonic() - started) * 1000),
                bypass=spec["readonly"],
                idempotency_key=idempotency_key,
                error_code="E_UPSTREAM",
            )
            raise ToolError("E_UPSTREAM", 502, f"业务后端不可用: {err}") from err
        self._audit.log(
            tool=name,
            actor_id=identity.employee_id,
            customer_id=customer_id,
            status="ok",
            http_status=200,
            latency_ms=int((time.monotonic() - started) * 1000),
            bypass=spec["readonly"],
            idempotency_key=idempotency_key,
        )
        return data

    # ---------- 只读路径（bypass 免确认 + 归属闸门 + 缓存） ----------

    def _call_readonly(self, name: str, args: dict, identity: Identity, jwt_token: str, no_cache: bool = False) -> dict:
        customer_id = args.get("customer_id")
        if name != "search_customers" and not customer_id:
            raise ToolError("E_INVALID_ARGUMENT", 400, f"{name} 需要 customer_id")
        if customer_id:
            self._ownership_gate(customer_id, jwt_token)

        cache_key = (identity.employee_id, name, str(customer_id), str(args.get("keyword")), str(args.get("stage")))
        ttl = _CACHE_TTL.get(name, 0)
        if ttl and no_cache:
            # 事件触发刷新：丢弃旧缓存，确保抽取拿到最新事实（正式事件失效留 M5）
            self._cache.pop(cache_key, None)
        if ttl:
            hit = self._cache.get(cache_key)
            if hit and hit[0] > time.monotonic():
                return {**hit[1], "_cache": "hit"}
        data = self._dispatch_readonly(name, args, jwt_token)
        if ttl:
            self._cache[cache_key] = (time.monotonic() + ttl, data)
        return data

    def _dispatch_readonly(self, name: str, args: dict, jwt_token: str) -> dict:
        if name == "search_customers":
            rows = self._get("/api/v1/customers", jwt_token)
            keyword, stage = args.get("keyword"), args.get("stage")
            return {
                "customers": [
                    row
                    for row in rows
                    if (not stage or row.get("lifecycleStage") == stage)
                    and (
                        not keyword
                        or keyword in (row.get("name") or "")
                        or keyword in (row.get("phone") or "")
                        or keyword in (row.get("remark") or "")
                    )
                ]
            }
        customer_id = args["customer_id"]
        if name == "get_customer_profile":
            return {"customer_id": customer_id, "fields": self._get(f"/api/v1/customers/{customer_id}/profile", jwt_token)}
        if name == "list_follow_ups":
            return {"customer_id": customer_id, "follow_ups": self._get(f"/api/v1/customers/{customer_id}/follow-ups", jwt_token)}
        return {"customer_id": customer_id, "purchases": self._get(f"/api/v1/customers/{customer_id}/purchases", jwt_token)}

    # ---------- write 路径（凭证闸门 + 幂等重放） ----------

    def _call_write(
        self,
        name: str,
        args: dict,
        identity: Identity,
        jwt_token: str,
        approval_token: str | None,
        idempotency_key: str | None,
    ) -> dict:
        if not idempotency_key:
            raise ToolError("E_IDEMPOTENCY_REQUIRED", 400, "write 工具必须携带 idempotency_key")
        if not approval_token:
            raise ToolError("E_APPROVAL_REQUIRED", 403, "write 工具必须携带 approval_token（绕过确认 100% 拒）")
        replayed = self._idempotency.get(idempotency_key)
        if replayed is not None:
            return {**replayed, "_replayed": True}

        customer_id = args.get("customer_id")
        if not customer_id:
            raise ToolError("E_INVALID_ARGUMENT", 400, f"{name} 需要 customer_id")
        self._ownership_gate(customer_id, jwt_token)

        if name == "update_profile_field":
            fields = args.get("fields")
            if not fields:
                raise ToolError("E_INVALID_ARGUMENT", 400, "fields 不能为空")
            result = self._put(
                f"/api/v1/customers/{customer_id}/profile/fields",
                {"approvalToken": approval_token, "fields": fields},
                jwt_token,
            )
            data = {"customer_id": customer_id, "fields": result}
        else:
            raise ToolError("E_TOOL_NOT_FOUND", 404, f"write 工具未实现: {name}")
        self._idempotency[idempotency_key] = data
        return data

    # ---------- 闸门与转发 ----------

    def _ownership_gate(self, customer_id: int, jwt_token: str) -> None:
        """归属闸门：转发 business-mock 校验（employee 仅自己名下客户，越权 403）。"""
        try:
            self._get(f"/api/v1/customers/{customer_id}", jwt_token)
        except ToolError as err:
            if err.http_status == 403:
                raise ToolError("E_FORBIDDEN", 403, f"客户不属于当前员工: {customer_id}") from err
            if err.http_status == 404:
                raise ToolError("E_NOT_FOUND", 404, f"客户不存在: {customer_id}") from err
            raise

    def _request(self, method: str, path: str, jwt_token: str, json_body: dict | None = None) -> dict:
        response = httpx.request(
            method,
            f"{self._base_url}{path}",
            headers={"Authorization": f"Bearer {jwt_token}"},
            json=json_body,
            timeout=2.0,
        )
        if response.status_code == 403:
            detail = self._error_message(response, "FORBIDDEN")
            raise ToolError(detail_code(detail), 403, detail)
        if response.status_code == 404:
            raise ToolError("E_NOT_FOUND", 404, self._error_message(response, "not found"))
        if response.status_code >= 400:
            raise ToolError("E_UPSTREAM", 502, self._error_message(response, f"upstream {response.status_code}"))
        return response.json().get("data")

    @staticmethod
    def _error_message(response: httpx.Response, fallback: str) -> str:
        try:
            return response.json().get("message", fallback)
        except ValueError:
            return fallback

    def _get(self, path: str, jwt_token: str):
        return self._request("GET", path, jwt_token)

    def _put(self, path: str, body: dict, jwt_token: str):
        return self._request("PUT", path, jwt_token, json_body=body)


def detail_code(message: str) -> str:
    """透传 business-mock 的 E_APPROVAL_* 错误码，其余归一为 E_FORBIDDEN。"""
    return message.split(":")[0] if message.startswith("E_") else "E_FORBIDDEN"
