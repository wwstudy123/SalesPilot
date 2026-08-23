"""sale-mcp-server：统一工具层 HTTP 网关（架构 §4）。

调用信封：POST /tools/{name}/call，Header 携 Authorization(JWT) /
X-Approval-Token(write) / X-Idempotency-Key(write)。
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from sale_server.audit import AuditStore
from sale_server.auth import verify_jwt
from sale_server.tools import TOOL_SPECS, ToolError, ToolGateway

app = FastAPI(title="sale-mcp-server", version="0.2.0")
audit_store = AuditStore()
gateway = ToolGateway(audit_store)


class ToolCallRequest(BaseModel):
    args: dict = Field(default_factory=dict, description="工具入参")


def _ok(data: dict) -> dict:
    return {"code": "OK", "message": "success", "data": data}


@app.get("/health")
def health() -> dict:
    return {
        "service": "mcp-server",
        "status": "UP",
        "tools": len(TOOL_SPECS),
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/tools")
def list_tools() -> dict:
    """工具清单 + 入参 schema（未来生成 LLM function-calling 描述）。"""
    return _ok(
        {
            "tools": [
                {
                    "name": name,
                    "readonly": spec["readonly"],
                    "timeout_ms": spec["timeout_ms"],
                    "description": spec["description"],
                    "args": spec["args"],
                }
                for name, spec in TOOL_SPECS.items()
            ]
        }
    )


@app.post("/tools/{name}/call")
def call_tool(
    name: str,
    body: ToolCallRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    x_approval_token: str | None = Header(default=None),
    x_idempotency_key: str | None = Header(default=None),
    x_no_cache: str | None = Header(default=None),
) -> dict:
    # 闸门①：JWT 身份
    token = (authorization or "").removeprefix("Bearer ").strip()
    identity = verify_jwt(token) if token else None
    if identity is None:
        raise HTTPException(status_code=401, detail={"code": "E_UNAUTHORIZED", "message": "无效或缺失的 JWT"})
    # 闸门②：角色
    if identity.role not in ("employee", "manager"):
        raise HTTPException(status_code=403, detail={"code": "E_FORBIDDEN", "message": f"未知角色: {identity.role}"})
    try:
        data = gateway.call(
            name,
            body.args,
            identity,
            token,
            approval_token=x_approval_token,
            idempotency_key=x_idempotency_key,
            no_cache=(x_no_cache or "").lower() in ("1", "true"),
        )
    except ToolError as err:
        raise HTTPException(status_code=err.http_status, detail={"code": err.code, "message": err.message}) from err
    return _ok(data)


@app.get("/audit/recent")
def audit_recent(limit: int = 50) -> dict:
    """审计查询（Monitor 验收：bypass/确认/拒绝均留痕）。"""
    return _ok({"logs": audit_store.recent(min(limit, 200))})
