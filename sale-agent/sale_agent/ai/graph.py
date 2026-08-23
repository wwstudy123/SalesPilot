"""LangGraph 主图：load_context → route → respond → save_context。

route 节点接入 M3 三路意图分类（Rule/Embedding/LLM 融合），产出
RoutingDecision；每个节点进出均打 agent_span，支撑 Monitor 观察。
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from sale_agent.ai.context_store import SessionContextStore
from sale_agent.ai.gateway import LLMGateway
from sale_agent.ai.trace import TraceStore
from sale_agent.intent.fusion import IntentRouter

SYSTEM_PROMPT = "你是 SalesPilot 零售销售 Copilot，面向一线销售员工。基于对话历史简明作答，涉及客户信息时提醒员工核对。"


class ChatState(TypedDict, total=False):
    session_id: str
    user_id: str
    run_id: str
    message: str
    menu_intent: str
    history: list[dict[str, str]]
    intent: str
    routing_reason: str
    confidence: float
    decision_path: str
    reply: str
    model: str
    echo: bool
    error: str


class ChatGraph:
    """主图封装：状态机 + 依赖（gateway/context/trace/intent router）。"""

    def __init__(
        self,
        gateway: LLMGateway,
        context_store: SessionContextStore,
        trace: TraceStore,
        intent_router: IntentRouter | None = None,
    ) -> None:
        self.gateway = gateway
        self.context_store = context_store
        self.trace = trace
        self.intent_router = intent_router
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
        # M3 三路意图分类：Rule 锁定短路，否则 Embedding ∥ LLM 融合
        span = self.trace.start_span(state["run_id"], "route")
        if self.intent_router is None:
            decision = None
            result = {"intent": "echo", "routing_reason": "router unavailable", "confidence": 0.0, "decision_path": "UNKNOWN"}
        else:
            decision = self.intent_router.route(state["message"], state.get("menu_intent"))
            result = {
                "intent": decision.primary,
                "routing_reason": decision.reason,
                "confidence": decision.confidence,
                "decision_path": decision.decision_path,
            }
        self.trace.finish_span(
            span,
            "ok",
            {"intent": result["intent"], "path": result["decision_path"], "confidence": result["confidence"]},
        )
        return result

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
