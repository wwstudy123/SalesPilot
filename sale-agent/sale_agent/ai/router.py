"""/api/ai 路由：POST /chat SSE 流式、GET /runs/{run_id} Trace、意图 Schema 管理、
M4：画像刷新/事件触发、提案确认（HITL）、/health。"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai")


class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None, description="会话 ID，缺省自动生成")
    user_id: str | None = None
    message: str = Field(min_length=1, description="员工输入")
    intent: str | None = Field(default=None, description="场景菜单直达注入（routing_type=menu，免分类）")


class ExampleRequest(BaseModel):
    text: str = Field(min_length=1, description="意图样例文本")


class FollowUpEvent(BaseModel):
    """business-mock 跟进落库事件（架构 §3.3 的 MVP 简化形态）。"""

    event: str = "follow_up.created"
    follow_up_id: int
    customer_id: int
    employee_id: int
    jwt: str | None = Field(default=None, description="员工 JWT（用于只读工具拉事实）")


class ProfileRefreshRequest(BaseModel):
    customer_id: int
    employee_id: int


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _chunk_text(text: str, size: int = 16) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


@router.post("/chat")
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    graph = request.app.state.chat_graph
    trace = request.app.state.trace_store

    session_id = body.session_id or uuid.uuid4().hex
    run_id = trace.start_run(session_id, body.user_id)

    async def event_stream() -> AsyncIterator[str]:
        yield _sse({"type": "start", "run_id": run_id, "session_id": session_id})
        try:
            final = graph.run(
                {
                    "session_id": session_id,
                    "user_id": body.user_id,
                    "run_id": run_id,
                    "message": body.message,
                    "menu_intent": body.intent,
                }
            )
            reply = final.get("reply", "")
            for chunk in _chunk_text(reply):
                yield _sse({"type": "delta", "content": chunk})
            status = "failed" if final.get("error") else "completed"
            trace.finish_run(
                run_id,
                status,
                intent=final.get("intent"),
                routing_reason=final.get("routing_reason"),
                confidence=final.get("confidence"),
                decision_path=final.get("decision_path"),
            )
            yield _sse(
                {
                    "type": "done",
                    "run_id": run_id,
                    "session_id": session_id,
                    "intent": final.get("intent"),
                    "confidence": final.get("confidence"),
                    "decision_path": final.get("decision_path"),
                    "model": final.get("model"),
                    "echo": final.get("echo", False),
                    "status": status,
                }
            )
        except Exception as exc:  # noqa: BLE001
            trace.finish_run(run_id, "failed")
            yield _sse({"type": "error", "run_id": run_id, "message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/runs/{run_id}")
async def get_run(request: Request, run_id: str) -> dict:
    trace = request.app.state.trace_store
    run = trace.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return {"code": "OK", "message": "success", "data": {"run": run, "spans": trace.list_spans(run_id)}}


@router.get("/intents")
async def list_intents(request: Request) -> dict:
    catalog = request.app.state.intent_catalog
    return {"code": "OK", "message": "success", "data": catalog.list_intents()}


@router.post("/intents/{name}/examples")
async def add_intent_example(request: Request, name: str, body: ExampleRequest) -> dict:
    catalog = request.app.state.intent_catalog
    if catalog.get_intent(name) is None:
        raise HTTPException(status_code=404, detail=f"intent not found: {name}")
    example_id = catalog.add_example(name, body.text)
    request.app.state.intent_router.reload()  # 样例库动态渲染，零发版
    return {"code": "OK", "message": "success", "data": {"id": example_id, "intent": name}}


# ---------- M4：画像触发与提案（HITL） ----------


@router.post("/events/follow_up_created")
async def follow_up_event(request: Request, body: FollowUpEvent) -> dict:
    """触发链路：新跟进落库 → 异步增量画像（验收：30s 内出提案）。"""
    if not body.jwt:
        return {"code": "OK", "message": "skipped: missing jwt", "data": {"accepted": False}}
    subgraph = request.app.state.profile_subgraph
    thread = threading.Thread(
        target=subgraph.refresh,
        args=(body.customer_id, body.employee_id, body.jwt),
        kwargs={"source": f"follow_up#{body.follow_up_id}", "fresh": True},
        daemon=True,
        name=f"profile-refresh-{body.customer_id}",
    )
    thread.start()
    return {"code": "OK", "message": "success", "data": {"accepted": True, "customer_id": body.customer_id}}


@router.post("/profile/refresh")
async def profile_refresh(request: Request, body: ProfileRefreshRequest, authorization: str | None = Header(default=None)) -> dict:
    """手动重新分析（同步）：前端携员工 JWT。"""
    jwt = (authorization or "").removeprefix("Bearer ").strip()
    if not jwt:
        raise HTTPException(status_code=401, detail="需要员工 JWT")
    result = request.app.state.profile_subgraph.refresh(body.customer_id, body.employee_id, jwt, source="manual")
    return {"code": "OK", "message": "success", "data": result}


@router.get("/proposals")
async def list_proposals(request: Request, customer_id: int | None = None, status: str | None = None) -> dict:
    store = request.app.state.proposal_store
    return {"code": "OK", "message": "success", "data": store.list(customer_id, status)}


@router.post("/proposals/{proposal_id}/confirm")
async def confirm_proposal(request: Request, proposal_id: str, authorization: str | None = Header(default=None)) -> dict:
    """员工确认：签发 approval_token → 携凭证执行 write → 提案收尾。"""
    from sale_agent.hitl.flow import confirm_proposal as confirm

    jwt = (authorization or "").removeprefix("Bearer ").strip()
    if not jwt:
        raise HTTPException(status_code=401, detail="需要员工 JWT")
    result = confirm(request.app.state.proposal_store, request.app.state.mcp_client, proposal_id, jwt)
    return {"code": "OK", "message": "success", "data": result}


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(request: Request, proposal_id: str) -> dict:
    from sale_agent.hitl.flow import reject_proposal as reject

    result = reject(request.app.state.proposal_store, proposal_id)
    return {"code": "OK", "message": "success", "data": result}


@router.get("/health")
async def ai_health(request: Request) -> dict:
    gateway = request.app.state.llm_gateway
    context_store = request.app.state.context_store
    return {
        "code": "OK",
        "message": "success",
        "data": {
            "status": "ok",
            "service": "sale-agent-ai",
            "llm_mode": "echo" if gateway.settings.echo_mode else "live",
            "context_backend": context_store.backend,
        },
    }


@router.get("/cost")
async def ai_cost(request: Request) -> dict:
    ledger = request.app.state.llm_gateway.ledger
    return {"code": "OK", "message": "success", "data": ledger.snapshot()}
