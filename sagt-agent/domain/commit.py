from __future__ import annotations

from dataclasses import dataclass


class CommitStage:
    STARTED = "started"
    STATE_APPLIED = "state_applied"
    PROGRESS_MARKED = "progress_marked"
    SIGNAL_SAVED = "signal_saved"


@dataclass
class PendingCommit:
    section: int
    stage: str
    summary: str = ""
    result: dict | None = None
    started_at: str = ""
    updated_at: str = ""


@dataclass
class CommitResult:
    section: int
    committed: bool
    word_count: int
    next_section: int
    review_required: bool = False
    review_reason: str = ""
