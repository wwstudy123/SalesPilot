from __future__ import annotations

from dataclasses import asdict

from sale_agent.domain.runtime import FlowState, Phase, Progress
from sale_agent.domain.transitions import validate_flow_transition, validate_phase_transition
from sale_agent.store.io import IO


class ProgressStore:
    def __init__(self, io: IO) -> None:
        self.io = io

    def load(self) -> Progress | None:
        try:
            data = self.io.read_json("meta/progress.json")
        except FileNotFoundError:
            return None
        return _progress_from_dict(data)

    def save(self, progress: Progress) -> None:
        self.io.write_json("meta/progress.json", asdict(progress))

    def init(self, project_name: str, total_sections: int) -> None:
        self.save(Progress(project_name=project_name, phase=Phase.INIT, total_sections=total_sections))

    def set_total_sections(self, total: int) -> None:
        def op() -> None:
            p = self.load() or Progress()
            p.total_sections = total
            self.save(p)

        self.io.with_write_lock(op)

    def update_phase(self, phase: str) -> None:
        def op() -> None:
            p = self.load() or Progress()
            validate_phase_transition(p.phase, phase)
            p.phase = phase
            self.save(p)

        self.io.with_write_lock(op)

    def update_flow(self, flow: str) -> None:
        def op() -> None:
            p = self.load() or Progress()
            validate_flow_transition(p.flow, flow)
            p.flow = flow
            self.save(p)

        self.io.with_write_lock(op)

    def start_section(self, section: int) -> None:
        if section <= 0:
            raise ValueError("section must be > 0")

        def op() -> None:
            p = self.load() or Progress()
            p.phase = Phase.GENERATING
            if p.flow != FlowState.REVISING:
                p.flow = FlowState.GENERATING
            p.current_section = max(p.current_section, section)
            p.in_progress_section = section
            self.save(p)

        self.io.with_write_lock(op)

    def mark_section_complete(self, section: int, word_count: int) -> None:
        def op() -> None:
            p = self.load() or Progress()
            old_wc = p.section_word_counts.get(section, 0)
            p.total_word_count -= old_wc
            p.section_word_counts[section] = word_count
            p.total_word_count += word_count
            if section not in p.completed_sections:
                p.completed_sections.append(section)
            p.current_section = max(p.current_section, section + 1)
            p.in_progress_section = 0
            validate_phase_transition(p.phase, Phase.GENERATING)
            p.phase = Phase.GENERATING
            self.save(p)

        self.io.with_write_lock(op)

    def mark_complete(self) -> None:
        def op() -> None:
            p = self.load() or Progress()
            p.phase = Phase.COMPLETE
            p.flow = ""
            p.in_progress_section = 0
            self.save(p)

        self.io.with_write_lock(op)

    def queue_rewrite(self, section: int, reason: str) -> None:
        def op() -> None:
            p = self.load() or Progress()
            if section not in p.pending_rewrites:
                p.pending_rewrites.append(section)
            p.rewrite_reason = reason
            validate_flow_transition(p.flow, FlowState.REVISING)
            p.flow = FlowState.REVISING
            self.save(p)

        self.io.with_write_lock(op)

    def complete_rewrite(self, section: int) -> None:
        def op() -> None:
            p = self.load() or Progress()
            p.pending_rewrites = [x for x in p.pending_rewrites if x != section]
            if not p.pending_rewrites:
                validate_flow_transition(p.flow, FlowState.GENERATING)
                p.flow = FlowState.GENERATING
                p.rewrite_reason = ""
            self.save(p)

        self.io.with_write_lock(op)

    def clear_in_progress(self) -> None:
        def op() -> None:
            p = self.load() or Progress()
            p.in_progress_section = 0
            self.save(p)

        self.io.with_write_lock(op)


def _progress_from_dict(data: dict) -> Progress:
    section_word_counts = {int(k): int(v) for k, v in (data.get("section_word_counts") or {}).items()}
    return Progress(
        project_name=str(data.get("project_name", "") or ""),
        phase=str(data.get("phase", Phase.INIT) or Phase.INIT),
        current_section=int(data.get("current_section", 0) or 0),
        total_sections=int(data.get("total_sections", 0) or 0),
        completed_sections=[int(x) for x in (data.get("completed_sections") or [])],
        total_word_count=int(data.get("total_word_count", 0) or 0),
        section_word_counts=section_word_counts,
        in_progress_section=int(data.get("in_progress_section", 0) or 0),
        flow=str(data.get("flow", "") or ""),
        pending_rewrites=[int(x) for x in (data.get("pending_rewrites") or [])],
        rewrite_reason=str(data.get("rewrite_reason", "") or ""),
    )
