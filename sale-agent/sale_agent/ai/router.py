"""/api/ai 路由：POST /chat SSE 流式、GET /runs/{run_id} Trace、意图 Schema 管理、
M4：画像刷新/事件触发、提案确认（HITL）、M5：知识库/建议卡、/health。"""

from __future__ import annotations

import base64
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
    customer_id: int | None = Field(default=None, description="客户槽位（话术生成的事实区来源）")


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


class SuggestionAdoptRequest(BaseModel):
    edited_content: str | None = Field(default=None, description="编辑后内容（非空且与原文不同 → modified）")


class SuggestionRejectRequest(BaseModel):
    reason: str = Field(min_length=1, description="拒绝原因（必填）")


class SuggestionRegenerateRequest(BaseModel):
    requirement: str = Field(min_length=1, description="重新生成要求（必填，≤2 次）")


class TagProposalEditRequest(BaseModel):
    tags: list[dict] = Field(min_length=1, description="修正后的标签建议")


class TagReviewRequest(BaseModel):
    customer_id: int


def _jwt_payload(jwt: str) -> dict:
    """解析 JWT payload 取 eid（签名由 mcp-server 闸门校验，此处仅提取身份）。"""
    try:
        part = jwt.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part))
    except Exception:  # noqa: BLE001
        return {}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _chunk_text(text: str, size: int = 16) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


@router.post("/chat")
async def chat(request: Request, body: ChatRequest, authorization: str | None = Header(default=None)) -> StreamingResponse:
    graph = request.app.state.chat_graph
    trace = request.app.state.trace_store
    jwt = (authorization or "").removeprefix("Bearer ").strip()

    session_id = body.session_id or uuid.uuid4().hex
    user_id = body.user_id or str(_jwt_payload(jwt).get("eid", "")) or "anonymous"
    run_id = trace.start_run(session_id, user_id)

    async def event_stream() -> AsyncIterator[str]:
        yield _sse({"type": "start", "run_id": run_id, "session_id": session_id})
        try:
            final = graph.run(
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "run_id": run_id,
                    "message": body.message,
                    "menu_intent": body.intent,
                    "customer_id": body.customer_id,
                    "jwt": jwt,
                }
            )
            # SSE 全量事件：intent → tool_call → rag_citation → token → proposal → done
            yield _sse(
                {
                    "type": "intent",
                    "intent": final.get("intent"),
                    "confidence": final.get("confidence"),
                    "decision_path": final.get("decision_path"),
                    "reason": final.get("routing_reason"),
                }
            )
            agent_result = final.get("coach_result") or final.get("ops_result") or {}
            for call in agent_result.get("tool_calls", []):
                yield _sse({"type": "tool_call", **call})
            if agent_result.get("citations"):
                yield _sse({"type": "rag_citation", "citations": agent_result["citations"]})
            reply = final.get("reply", "")
            for chunk in _chunk_text(reply):
                yield _sse({"type": "token", "content": chunk})
            if agent_result.get("suggestion_id"):
                yield _sse(
                    {
                        "type": "proposal",
                        "suggestion_id": agent_result["suggestion_id"],
                        "skill": agent_result.get("skill", {}).get("id"),
                        "warnings": agent_result.get("warnings", []),
                        "citations": agent_result.get("citations", []),
                    }
                )
            elif agent_result.get("proposal"):
                yield _sse({"type": "proposal", "proposal_id": agent_result["proposal"]["id"], "tool": "save_tags"})
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


# ---------- M5：知识库（入库/检索） ----------


@router.post("/kb/seed")
async def kb_seed(request: Request) -> dict:
    """灌入种子知识并原子发布（幂等，重跑版本 +1）。"""
    from sale_agent.kb.seed_data import load_seed

    result = load_seed(request.app.state.knowledge_store)
    return {"code": "OK", "message": "success", "data": result}


class KbUploadRequest(BaseModel):
    """知识库上传（M5 入库管线：上传 → 切片 → 向量化 → 原子切换 ready）。"""

    domain: str = Field(description="playbook | product")
    title: str = Field(min_length=1, description="文档标题（即场景名/产品名）")
    source: str | None = Field(default=None, description="来源标识，缺省由标题生成；同 source 重发版本 +1")
    texts: list[str] = Field(min_length=1, description="文档正文切片原文列表；入库管线内部再按段落/句号细分切片")
    publish: bool = Field(default=True, description="是否立即原子切换为 ready（默认是，检索立即可见）")


@router.post("/kb/upload")
async def kb_upload(request: Request, body: KbUploadRequest) -> dict:
    """上传文档 → 切片 → 向量化 → 原子切换 ready（验收：上传后即可检索）。

    staging→ready 原子切换：同 source 旧 ready 自动归档，检索无中断。
    """
    if body.domain not in ("playbook", "product"):
        raise HTTPException(status_code=422, detail="domain 仅支持 playbook / product")
    store = request.app.state.knowledge_store
    source = body.source or f"upload-{body.domain}-{body.title}"
    try:
        ingested = store.ingest(body.domain, body.title, source, body.texts)
        published = store.publish(body.domain, source) if body.publish else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "code": "OK",
        "message": "success",
        "data": {"ingested": ingested, "published": published, "ready": published is not None},
    }


@router.get("/kb/search")
async def kb_search(request: Request, q: str, domain: str | None = None, top_k: int = 5) -> dict:
    """检索测试页（M5 验收：检索可用）。"""
    pipeline = request.app.state.rag_pipeline
    result = pipeline.retrieve(q, domain=domain)
    hits = [
        {
            "label": citation["label"],
            "chunk_id": hit.chunk_id,
            "title": hit.title,
            "content": hit.content,
            "score": round(hit.score, 3),
            "rrf": round(hit.rrf, 5),
            "hedge": hit.hedge,
        }
        for citation, hit in zip(result.citations, result.hits[:top_k])
    ]
    return {
        "code": "OK",
        "message": "success",
        "data": {"query": q, "rewritten": result.rewritten_query, "mode": result.mode, "hits": hits},
    }


@router.get("/kb/stats")
async def kb_stats(request: Request) -> dict:
    backend = request.app.state.vector_backend
    data = request.app.state.knowledge_store.stats()
    data["vector_backend"] = "milvus" if backend is not None and backend.is_available() else "lite"
    return {"code": "OK", "message": "success", "data": data}


# ---------- M5：建议卡（HITL 行为记录） ----------


@router.get("/suggestions")
async def list_suggestions(request: Request, customer_id: int | None = None, status: str | None = None) -> dict:
    store = request.app.state.suggestion_store
    return {"code": "OK", "message": "success", "data": store.list(customer_id, status)}


@router.get("/suggestions/{suggestion_id}/actions")
async def suggestion_actions(request: Request, suggestion_id: int) -> dict:
    store = request.app.state.suggestion_store
    if store.get(suggestion_id) is None:
        raise HTTPException(status_code=404, detail=f"suggestion not found: {suggestion_id}")
    return {"code": "OK", "message": "success", "data": store.actions(suggestion_id)}


@router.post("/suggestions/{suggestion_id}/adopt")
async def adopt_suggestion(request: Request, suggestion_id: int, body: SuggestionAdoptRequest) -> dict:
    """采纳（可编辑）；编辑且与原文不同 → modified。"""
    store = request.app.state.suggestion_store
    try:
        result = store.adopt(suggestion_id, body.edited_content)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"suggestion not found: {suggestion_id}") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"code": "OK", "message": "success", "data": result}


@router.post("/suggestions/{suggestion_id}/reject")
async def reject_suggestion(request: Request, suggestion_id: int, body: SuggestionRejectRequest) -> dict:
    """拒绝（原因必填，Pydantic 已校验非空）。"""
    store = request.app.state.suggestion_store
    try:
        result = store.reject(suggestion_id, body.reason)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"suggestion not found: {suggestion_id}") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"code": "OK", "message": "success", "data": result}


@router.post("/suggestions/{suggestion_id}/regenerate")
async def regenerate_suggestion(
    request: Request,
    suggestion_id: int,
    body: SuggestionRegenerateRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    """重新生成（≤2 次）：附要求 → Coach 换素材重生成。"""
    from sale_agent.suggestion.store import RegenerateLimitError

    store = request.app.state.suggestion_store
    coach = request.app.state.coach_subgraph
    current = store.get(suggestion_id)
    if current is None:
        raise HTTPException(status_code=404, detail=f"suggestion not found: {suggestion_id}")
    jwt = (authorization or "").removeprefix("Bearer ").strip()
    if current["customer_id"] and not jwt:
        raise HTTPException(status_code=401, detail="重新生成客户话术需要员工 JWT")
    try:
        result = coach.generate(
            intent="talk_script" if current["skill"] == "intent-followup" else "objection_help",
            message=current["request_message"] or body.requirement,
            customer_id=current["customer_id"] or None,
            employee_id=current["employee_id"],
            jwt=jwt or None,
            session_id=current["session_id"],
            run_id=current["run_id"],
            exclude_chunk_ids=[citation["chunk_id"] for citation in current["citations"]],
            requirement=body.requirement,
            ephemeral=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"重新生成失败：{exc}") from exc
    try:
        updated = store.regenerate(
            suggestion_id,
            body.requirement,
            result["reply"],
            result["citations"],
            result["warnings"],
        )
    except RegenerateLimitError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"code": "OK", "message": "success", "data": updated}


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
    if result["proposal"]["tool"] == "update_profile_field":
        # 画像确认后联动复核标签；仍产出独立 save_tags 提案，绝不静默写入。
        request.app.state.ops_subgraph.review(
            result["proposal"]["customer_id"],
            result["proposal"]["employee_id"],
            jwt,
            source=f"profile_proposal:{proposal_id}",
        )
    return {"code": "OK", "message": "success", "data": result}


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(request: Request, proposal_id: str) -> dict:
    from sale_agent.hitl.flow import reject_proposal as reject

    result = reject(request.app.state.proposal_store, proposal_id)
    return {"code": "OK", "message": "success", "data": result}


@router.post("/proposals/{proposal_id}/tags")
async def edit_tag_proposal(request: Request, proposal_id: str, body: TagProposalEditRequest) -> dict:
    proposal = request.app.state.proposal_store.get(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"proposal not found: {proposal_id}")
    if proposal["tool"] != "save_tags":
        raise HTTPException(status_code=422, detail="仅标签提案支持修正")
    required = {"tagKey", "evidence", "confidence"}
    if any(not required.issubset(item) for item in body.tags):
        raise HTTPException(status_code=422, detail="标签需包含 tagKey、evidence、confidence")
    updated = request.app.state.proposal_store.replace_fields(proposal_id, body.tags)
    if updated is None:
        raise HTTPException(status_code=409, detail="提案已处理，不可修正")
    return {"code": "OK", "message": "success", "data": updated}


@router.post("/tags/review")
async def review_tags(request: Request, body: TagReviewRequest, authorization: str | None = Header(default=None)) -> dict:
    jwt = (authorization or "").removeprefix("Bearer ").strip()
    employee_id = _jwt_payload(jwt).get("eid")
    if not jwt or not employee_id:
        raise HTTPException(status_code=401, detail="需要员工 JWT")
    result = request.app.state.ops_subgraph.review(body.customer_id, int(employee_id), jwt, source="manual")
    return {"code": "OK", "message": "success", "data": result}


@router.get("/health")
async def ai_health(request: Request) -> dict:
    gateway = request.app.state.llm_gateway
    context_store = request.app.state.context_store
    backend = request.app.state.vector_backend
    return {
        "code": "OK",
        "message": "success",
        "data": {
            "status": "ok",
            "service": "sale-agent-ai",
            "llm_mode": "echo" if gateway.settings.echo_mode else "live",
            "context_backend": context_store.backend,
            "vector_backend": "milvus" if backend is not None and backend.is_available() else "lite",
        },
    }


@router.get("/cost")
async def ai_cost(request: Request) -> dict:
    ledger = request.app.state.llm_gateway.ledger
    return {"code": "OK", "message": "success", "data": ledger.snapshot()}
