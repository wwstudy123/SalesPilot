from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class StreamChunk:
    channel: str = "content"
    delta: str = ""


@dataclass
class Event:
    time: datetime = field(default_factory=datetime.now)
    category: str = "SYSTEM"
    summary: str = ""
    level: str = "info"


def build_start_prompt(prompt: str) -> str:
    text = prompt.strip()
    return (
        "请根据以下要求开始执行任务。按工作节（Section）逐节推进，"
        "不要编造上下文中不存在的事实。\n\n[任务要求]\n" + text + "\n\n若某些细节未明确，请在不违背用户方向的前提下合理补全。"
    )


@dataclass
class UISnapshot:
    provider: str = ""
    model_name: str = ""
    style: str = ""
    runtime_state: str = ""
    status_label: str = ""
    phase: str = ""
    flow: str = ""
    current_section: int = 0
    total_sections: int = 0
    completed_count: int = 0
    total_word_count: int = 0
    pending_rewrites: list[int] = field(default_factory=list)
    rewrite_reason: str = ""
    pending_steer: str = ""
    premise: str = ""
    recent_summaries: list[str] = field(default_factory=list)
    context_tokens: int = 0
    context_window: int = 0
    context_percent: float = 0.0
    backend: str = ""
    agent_status: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
