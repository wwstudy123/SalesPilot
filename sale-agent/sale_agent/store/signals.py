from __future__ import annotations

from dataclasses import asdict

from sale_agent.domain.commit import PendingCommit
from sale_agent.domain.runs import PendingRunCheckpoint
from sale_agent.store.io import IO


class SignalStore:
    def __init__(self, io: IO) -> None:
        self.io = io

    def save_last_commit(self, result: dict) -> None:
        self.io.write_json("meta/last_commit.json", result)

    def load_last_commit(self) -> dict | None:
        try:
            return self.io.read_json("meta/last_commit.json")
        except FileNotFoundError:
            return None

    def clear_last_commit(self) -> None:
        self.io.remove_file("meta/last_commit.json")

    def save_pending_commit(self, pending: PendingCommit) -> None:
        self.io.write_json("meta/pending_commit.json", asdict(pending))

    def load_pending_commit(self) -> PendingCommit | None:
        try:
            data = self.io.read_json("meta/pending_commit.json")
        except FileNotFoundError:
            return None
        return PendingCommit(
            section=int(data.get("section", 0) or 0),
            stage=str(data.get("stage", "") or ""),
            summary=str(data.get("summary", "") or ""),
            result=data.get("result"),
            started_at=str(data.get("started_at", "") or ""),
            updated_at=str(data.get("updated_at", "") or ""),
        )

    def clear_pending_commit(self) -> None:
        self.io.remove_file("meta/pending_commit.json")

    def save_pending_checkpoint(self, pending: PendingRunCheckpoint) -> None:
        self.io.write_json("meta/pending_checkpoint.json", asdict(pending))

    def load_pending_checkpoint(self) -> PendingRunCheckpoint | None:
        try:
            data = self.io.read_json("meta/pending_checkpoint.json")
        except FileNotFoundError:
            return None
        return PendingRunCheckpoint(
            pause_after_section=int(data.get("pause_after_section", 0) or 0),
            next_section=int(data.get("next_section", 0) or 0),
            completed_count=int(data.get("completed_count", 0) or 0),
            status=str(data.get("status", "awaiting_confirmation") or "awaiting_confirmation"),
        )

    def clear_pending_checkpoint(self) -> None:
        self.io.remove_file("meta/pending_checkpoint.json")

    def clear_stale_signals(self) -> None:
        self.clear_pending_commit()
        self.clear_last_commit()
