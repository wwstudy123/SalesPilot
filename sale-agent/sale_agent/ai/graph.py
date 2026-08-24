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
    customer_id: int
    jwt: str
    history: list[dict[str, str]]
    intent: str
    routing_reason: str
    confidence: float
    decision_path: str
    reply: str
    model: str
    echo: bool
    error: str
    coach_result: dict
    ops_result: dict


class ChatGraph:
    """主图封装：状态机 + 依赖（gateway/context/trace/intent router）。"""

    def __init__(
        self,
        gateway: LLMGateway,
        context_store: SessionContextStore,
        trace: TraceStore,
        intent_router: IntentRouter | None = None,
        coach=None,
        ops=None,
    ) -> None:
        self.gateway = gateway
        self.context_store = context_store
        self.trace = trace
        self.intent_router = intent_router
        self.coach = coach  # M5：Coach 子图（talk_script/objection_help 分派）
        self.ops = ops  # M6：Ops 子图（tag_review 分派）
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
        # M5：coaching 类意图分派 Coach 子图（事实区 + 话术区 + 建议卡）
        if state.get("intent") in ("talk_script", "objection_help") and self.coach is not None:
            return self._respond_coach(state)
        if state.get("intent") == "tag_review" and self.ops is not None:
            return self._respond_ops(state)
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

    def _respond_coach(self, state: ChatState) -> dict:
        span = self.trace.start_span(state["run_id"], "coach_generate")
        try:
            raw_user = state.get("user_id") or "0"
            try:
                employee_id = int(raw_user)  # JWT eid；非数字身份（anonymous）落 0
            except ValueError:
                employee_id = 0
            result = self.coach.generate(
                intent=state["intent"],
                message=state["message"],
                customer_id=state.get("customer_id"),
                employee_id=employee_id,
                jwt=state.get("jwt"),
                session_id=state["session_id"],
                run_id=state["run_id"],
            )
            self.trace.finish_span(
                span,
                "ok",
                {
                    "skill": result["skill"]["id"],
                    "citations": len(result["citations"]),
                    "suggestion_id": result["suggestion_id"],
                    "echo": result["echo"],
                },
            )
            return {
                "reply": result["reply"],
                "model": "coach",
                "echo": result["echo"],
                "coach_result": result,
            }
        except Exception as exc:  # noqa: BLE001
            self.trace.finish_span(span, "error", {"error": str(exc)})
            return {"reply": f"抱歉，话术生成暂时不可用：{exc}", "model": "none", "echo": False, "error": str(exc)}

    def _respond_ops(self, state: ChatState) -> dict:
        if not state.get("customer_id") or not state.get("jwt"):
            return {
                "reply": "请先选择客户并登录后再生成标签建议。",
                "model": "ops",
                "echo": self.gateway.settings.echo_mode,
            }
        span = self.trace.start_span(state["run_id"], "ops_tag_review")
        try:
            employee_id = int(state.get("user_id") or 0)
            result = self.ops.review(state["customer_id"], employee_id, state["jwt"], source="chat")
            self.trace.finish_span(span, "ok", {"outcome": result["outcome"]})
            reply = "已生成标签建议，请确认后生效。" if result["outcome"] == "proposal" else "未发现需要更新的标签。"
            return {"reply": reply, "model": "ops", "echo": self.gateway.settings.echo_mode, "ops_result": result}
        except Exception as exc:  # noqa: BLE001
            self.trace.finish_span(span, "error", {"error": str(exc)})
            return {"reply": f"抱歉，标签分析暂时不可用：{exc}", "model": "none", "echo": False, "error": str(exc)}

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
