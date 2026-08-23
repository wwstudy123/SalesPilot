from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from langgraph.graph import END, START, StateGraph

from sagt_agent.agents.context_manager import ContextManager
from sagt_agent.agents.llm_client import OpenAICompatClient
from sagt_agent.agents.runner import AgentRunner
from sagt_agent.assets import load_bundle
from sagt_agent.bootstrap.config import Config
from sagt_agent.domain.runs import PendingRunCheckpoint
from sagt_agent.host.events import Event
from sagt_agent.store.store import Store

from .nodes import (
    checkpoint_node,
    commit_section_node,
    finish_node,
    generate_section_node,
    load_runtime_context,
    route_after_load,
)
from .state import GraphState


@dataclass
class LangGraphRuntime:
    """最小 LangGraph 编排运行时：load_context -> generate -> commit -> checkpoint -> finish。"""

    cfg: Config
    runner: AgentRunner
    store: Store
    emit_event: Callable[[Event], None]
    emit_stream: Callable[[str, str], None]
    on_checkpoint_pending: Callable[[PendingRunCheckpoint], None] | None = None

    def __post_init__(self) -> None:
        self._aborted = False
        self.context_manager = ContextManager(context_window=self.cfg.context_window)
        self.assets = load_bundle(self.cfg.style)
        self.graph = self._build_graph()

    def start(self, prompt: str) -> None:
        self._aborted = False
        self._invoke(prompt, resume_mode=False)

    def resume(self, prompt: str) -> None:
        self._aborted = False
        self._invoke(prompt, resume_mode=True)

    def follow_up(self, text: str) -> None:
        self._aborted = False
        self._invoke(text, resume_mode=False)

    def abort(self) -> None:
        self._aborted = True

    def wait_idle(self) -> None:
        return

    def emit_checkpoint_pending(self, pending: PendingRunCheckpoint) -> None:
        if self.on_checkpoint_pending is not None:
            self.on_checkpoint_pending(pending)

    def build_client(self) -> OpenAICompatClient:
        pc = self.cfg.providers.get(self.cfg.provider)
        if pc is None or not pc.api_key:
            raise RuntimeError(f"provider {self.cfg.provider} api_key 未配置")
        key_norm = pc.api_key.strip().lower()
        if key_norm in {"dummy-key", "dummy", "test", "placeholder", "changeme", "your-key", "your_api_key"}:
            raise RuntimeError(f"provider {self.cfg.provider} api_key 为占位值")
        return OpenAICompatClient(
            api_key=pc.api_key,
            model=self.cfg.model,
            base_url=pc.base_url,
            timeout=120.0,
        )

    def _invoke(self, seed_text: str, resume_mode: bool) -> None:
        state: GraphState = {
            "seed_text": seed_text,
            "resume_mode": resume_mode,
            "pending_action": "load",
            "stop_requested": self._aborted,
            "out_lines": [f"[LangGraph] 协调器开始执行：{seed_text}"],
        }
        result = self.graph.invoke(state)
        out_lines = result.get("out_lines") or []
        if out_lines:
            self.emit_stream("thinking", "\n".join(out_lines) + "\n")

    def _build_graph(self):
        graph = StateGraph(GraphState)
        graph.add_node("load_runtime_context", load_runtime_context(self))
        graph.add_node("generate_section", generate_section_node(self))
        graph.add_node("commit_section", commit_section_node(self))
        graph.add_node("checkpoint", checkpoint_node(self))
        graph.add_node("finish", finish_node(self))
        graph.add_edge(START, "load_runtime_context")
        graph.add_conditional_edges(
            "load_runtime_context",
            route_after_load,
            {
                "generate_section": "generate_section",
                "finish": "finish",
            },
        )
        graph.add_edge("generate_section", "commit_section")
        graph.add_edge("commit_section", "checkpoint")
        graph.add_edge("checkpoint", "finish")
        graph.add_edge("finish", END)
        return graph.compile()
