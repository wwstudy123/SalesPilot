from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PendingRunCheckpoint:
    pause_after_section: int
    next_section: int
    completed_count: int
    status: str = "awaiting_confirmation"
