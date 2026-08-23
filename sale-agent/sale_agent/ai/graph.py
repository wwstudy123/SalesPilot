"""LangGraph 主图（M2 最小版）：load_context → route → respond → save_context。

route 节点为 M3 意图分类预留占位（当前直通 echo intent）；
每个节点进出均打 agent_span，支撑 Monitor 观察。
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from sale_agent.ai.context_store import SessionContextStore
from sale_agent.ai.gateway import LLMGateway
from sale_agent.ai.trace import TraceStore

SYSTEM_PROMPT = "你是 SalesPilot 零售销售 Copilot，面向一线销售员工。基于对话历史简明作答，涉及客户信息时提醒员工核对。"


class ChatState(TypedDict, total=False):
    session_id: str
    user_id: str
    run_id: str
    message: str
    history: list[dict[str, str]]
    intent: str
    routing_reason: str
    reply: str
    model: str
    echo: bool
    error: str


class ChatGraph:
    """主图封装：状态机 + 依赖（gateway/context/trace）。"""

    def __init__(self, gateway: LLMGateway, context_store: SessionContextStore, trace: TraceStore) -> None:
        self.gateway = gateway
        self.context_store = context_store
        self.trace = trace
        self._graph = self._build()

    def _build(self):
        builder = StateGraph(ChatState)
        builder.add_node("load_context", self._load_context)
        builder.add_node("route", self._route)
        builder.add_node("respond", self._respond)
        builder.add_node("save_context", self._save_context)
        builder.set_entry_point("load_context")
        builder.add_edge("load_context", "route")
        builder.add_edge("route", "respond")
        builder.add_edge("respond", "save_context")
        builder.add_edge("save_context", END)
        return builder.compile()

    # ---------- nodes ----------

    def _load_context(self, state: ChatState) -> dict:
        span = self.trace.start_span(state["run_id"], "load_context")
        try:
            history = self.context_store.load(state["session_id"])
            self.trace.finish_span(span, "ok", {"messages": len(history), "backend": self.context_store.backend})
            return {"history": history}
        except Exception as exc:  # noqa: BLE001
            self.trace.finish_span(span, "error", {"error": str(exc)})
            return {"history": [], "error": f"load_context failed: {exc}"}

    def _route(self, state: ChatState) -> dict:
        # M3 意图分类接入点：Rule + Embedding + LLM 三路融合；M2 直通
        span = self.trace.start_span(state["run_id"], "route")
        intent, reason = "echo", "M2 placeholder: route passthrough"
        self.trace.finish_span(span, "ok", {"intent": intent})
        return {"intent": intent, "routing_reason": reason}

    def _respond(self, state: ChatState) -> dict:
        span = self.trace.start_span(state["run_id"], "respond")
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(state.get("history", []))
        messages.append({"role": "user", "content": state["message"]})
        try:
            result = self.gateway.chat(messages)
            self.trace.finish_span(
                span,
                "ok",
                {"model": result.model, "completion_tokens": result.completion_tokens, "echo": result.echo},
            )
            return {"reply": result.content, "model": result.model, "echo": result.echo}
        except Exception as exc:  # noqa: BLE001
            self.trace.finish_span(span, "error", {"error": str(exc)})
            return {"reply": f"抱歉，AI 服务暂时不可用：{exc}", "model": "none", "echo": False, "error": str(exc)}

    def _save_context(self, state: ChatState) -> dict:
        span = self.trace.start_span(state["run_id"], "save_context")
        try:
            self.context_store.append(state["session_id"], "user", state["message"])
            self.context_store.append(state["session_id"], "assistant", state.get("reply", ""))
            self.trace.finish_span(span, "ok")
        except Exception as exc:  # noqa: BLE001
            self.trace.finish_span(span, "error", {"error": str(exc)})
        return {}

    # ---------- invoke ----------

    def run(self, state: ChatState) -> ChatState:
        return self._graph.invoke(state)
