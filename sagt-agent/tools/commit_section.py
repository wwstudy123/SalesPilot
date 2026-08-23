from __future__ import annotations

from typing import Any

from sagt_agent.domain.checkpoint import section_scope
from sagt_agent.store.project_data import SectionSummary
from sagt_agent.store.store import Store
from sagt_agent.tools.base import ToolError


class CommitSectionTool:
    """示例工具：提交一节产出（正文落盘、进度推进、checkpoint 记录）。"""

    def __init__(self, store: Store) -> None:
        self.store = store

    def name(self) -> str:
        return "commit_section"

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        section = int(args.get("section", 0) or 0)
        content = str(args.get("content", "") or "").strip()
        summary = str(args.get("summary", "") or "").strip()
        if section <= 0:
            raise ToolError("section must be positive")
        if not content:
            raise ToolError("content is required")

        self.store.sections.save_section_text(section, content)
        if summary:
            self.store.sections.save_summary(SectionSummary(section=section, summary=summary))
        self.store.progress.mark_section_complete(section, word_count=len(content))
        checkpoint = self.store.checkpoints.append(section_scope(section), step="commit_section", artifact=f"sections/{section}.md")
        progress = self.store.progress.load()
        completed = progress.completed_sections if progress else []
        total = progress.total_sections if progress else 0
        all_done = bool(total) and len(completed) >= total
        return {
            "committed": True,
            "section": section,
            "word_count": len(content),
            "next_section": section + 1,
            "completed_count": len(completed),
            "all_done": all_done,
            "checkpoint_seq": checkpoint.seq,
        }
