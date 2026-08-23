from __future__ import annotations

from dataclasses import dataclass, field


class Phase:
    INIT = "init"
    PLANNING = "planning"
    GENERATING = "generating"
    COMPLETE = "complete"


class FlowState:
    GENERATING = "generating"
    REVIEWING = "reviewing"
    REVISING = "revising"
    STEERING = "steering"


@dataclass
class Progress:
    project_name: str = ""
    phase: str = Phase.INIT
    current_section: int = 0
    total_sections: int = 0
    completed_sections: list[int] = field(default_factory=list)
    total_word_count: int = 0
    section_word_counts: dict[int, int] = field(default_factory=dict)
    in_progress_section: int = 0
    flow: str = ""
    pending_rewrites: list[int] = field(default_factory=list)
    rewrite_reason: str = ""

    def is_resumable(self) -> bool:
        return self.phase == Phase.GENERATING and self.current_section > 0

    def next_section(self) -> int:
        if not self.completed_sections:
            return 1
        return max(self.completed_sections) + 1


@dataclass
class SteerEntry:
    input: str
    timestamp: str


@dataclass
class RunMeta:
    started_at: str = ""
    provider: str = ""
    style: str = ""
    model: str = ""
    project_title: str = ""
    steer_history: list[SteerEntry] = field(default_factory=list)
    pending_steer: str = ""
