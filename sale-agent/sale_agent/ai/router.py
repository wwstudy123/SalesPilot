"""/api/ai 路由：POST /chat SSE 流式、GET /runs/{run_id} Trace、意图 Schema 管理、/health。"""

from __future__ import annotations

import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/ai")


class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None, description="会话 ID，缺省自动生成")
    user_id: str | None = None
    message: str = Field(min_length=1, description="员工输入")
    intent: str | None = Field(default=None, description="场景菜单直达注入（routing_type=menu，免分类）")


class ExampleRequest(BaseModel):
    text: str = Field(min_length=1, description="意图样例文本")


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
