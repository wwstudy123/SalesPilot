from __future__ import annotations

from typing import Any

from agentkit.store.store import Store


class LoadProjectContextTool:
    """示例工具：装配当前项目上下文（概述、进度、已完成节摘要）。"""

    def __init__(self, store: Store) -> None:
        self.store = store

    def name(self) -> str:
        return "load_project_context"

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        _ = args
        progress = self.store.progress.load()
        completed = sorted(progress.completed_sections) if progress else []
        recent_summaries = []
        for section in completed[-4:]:
            summary = self.store.sections.load_summary(section)
            if summary:
                recent_summaries.append({"section": section, "summary": summary.summary})
        return {
            "premise": self.store.sections.load_premise(),
            "phase": progress.phase if progress else "init",
            "next_section": progress.next_section() if progress else 1,
            "total_sections": progress.total_sections if progress else 0,
            "completed_sections": completed,
            "recent_summaries": recent_summaries,
        }
