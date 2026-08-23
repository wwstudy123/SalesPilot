from __future__ import annotations

from sale_agent.agents.runner import AgentRunner, CoordinatorLoop
from sale_agent.bootstrap.config import Config
from sale_agent.store.store import Store
from sale_agent.tools.base import Tool
from sale_agent.tools.commit_section import CommitSectionTool
from sale_agent.tools.project_context import LoadProjectContextTool


def build_tool_registry(store: Store) -> dict[str, Tool]:
    tools: list[Tool] = [
        LoadProjectContextTool(store),
        CommitSectionTool(store),
    ]
    return {tool.name(): tool for tool in tools}


def build_coordinator_loop(
    cfg: Config,
    store: Store,
    emit_event,
    emit_stream,
    on_checkpoint_pending=None,
) -> CoordinatorLoop:
    from sale_agent.agents.orchestrator.langgraph.core import LangGraphRuntime

    runner = AgentRunner(build_tool_registry(store))
    impl = LangGraphRuntime(
        cfg,
        runner,
        store,
        emit_event,
        emit_stream,
        on_checkpoint_pending=on_checkpoint_pending,
    )
    return CoordinatorLoop(impl)
