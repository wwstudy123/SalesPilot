from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextSnapshot:
    scope: str = ""
    strategy: str = ""
    active_messages: int = 0
    summary_messages: int = 0
    compacted_count: int = 0
    kept_count: int = 0


@dataclass
class ContextPack:
    summary_block: str = ""
    compacted_keys: list[str] = field(default_factory=list)


@dataclass
class ContextManager:
    """通用上下文预算管理：在上下文窗口内装配本轮生成所需的摘要块。"""

    context_window: int = 128000
    reserve_tokens: int = 32000
    snapshots: list[ContextSnapshot] = field(default_factory=list)

    def record(self, snapshot: ContextSnapshot) -> None:
        self.snapshots.append(snapshot)

    def latest(self) -> ContextSnapshot | None:
        if not self.snapshots:
            return None
        return self.snapshots[-1]

    def build_pack(self, context: dict[str, Any]) -> ContextPack:
        summary_lines: list[str] = []
        compacted: list[str] = []

        premise = str(context.get("premise", "") or "").strip()
        if premise:
            summary_lines.append("[项目概述]\n" + premise[:300])
            compacted.append("premise")

        sections = context.get("completed_sections") or []
        if sections:
            summary_lines.append("[已完成节]\n" + "\n".join(f"- {item}" for item in sections[-8:]))
            compacted.append("completed_sections")

        instruction = str(context.get("instruction", "") or "").strip()
        if instruction:
            summary_lines.append("[本轮指令]\n" + instruction[:300])
            compacted.append("instruction")

        return ContextPack(summary_block="\n\n".join(summary_lines).strip(), compacted_keys=compacted)
