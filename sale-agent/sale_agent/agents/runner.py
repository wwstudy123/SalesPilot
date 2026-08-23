from __future__ import annotations

from typing import Any

from sale_agent.agents.orchestrator.interface import OrchestratorBackend
from sale_agent.tools.base import Tool, ToolError


class AgentRunner:
    """工具调度器：按名称执行注册表中的工具。"""

    def __init__(self, tools: dict[str, Tool]) -> None:
        self.tools = tools

    def run_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        tool = self.tools.get(name)
        if tool is None:
            raise ToolError(f"unknown tool: {name}")
        return tool.execute(args)


class CoordinatorLoop:
    """编排后端的统一入口，屏蔽具体实现（LangGraph 等）。"""

    def __init__(self, backend: OrchestratorBackend) -> None:
        self.backend = backend

    def start(self, prompt: str) -> None:
        self.backend.start(prompt)

    def resume(self, prompt: str) -> None:
        self.backend.resume(prompt)

    def follow_up(self, text: str) -> None:
        self.backend.follow_up(text)

    def abort(self) -> None:
        self.backend.abort()

    def wait_idle(self) -> None:
        self.backend.wait_idle()
