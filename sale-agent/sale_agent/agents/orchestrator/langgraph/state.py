from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    seed_text: str
    resume_mode: bool
    pending_action: str
    current_section: int
    context: dict[str, Any]
    latest_draft: str
    latest_commit_result: dict[str, Any]
    stop_requested: bool
    error: str
    out_lines: list[str]
