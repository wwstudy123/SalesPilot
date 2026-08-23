from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from agentkit.domain.runtime import RunMeta, SteerEntry
from agentkit.store.io import IO


class RunMetaStore:
    def __init__(self, io: IO) -> None:
        self.io = io

    def load(self) -> RunMeta | None:
        try:
            data = self.io.read_json("meta/run.json")
        except FileNotFoundError:
            return None
        history = [
            SteerEntry(input=str(x.get("input", "") or ""), timestamp=str(x.get("timestamp", "") or ""))
            for x in (data.get("steer_history") or [])
            if isinstance(x, dict)
        ]
        return RunMeta(
            started_at=str(data.get("started_at", "") or ""),
            provider=str(data.get("provider", "") or ""),
            style=str(data.get("style", "") or ""),
            model=str(data.get("model", "") or ""),
            project_title=str(data.get("project_title", "") or ""),
            steer_history=history,
            pending_steer=str(data.get("pending_steer", "") or ""),
        )

    def save(self, meta: RunMeta) -> None:
        self.io.write_json("meta/run.json", asdict(meta))

    def init(self, style: str, provider: str, model: str) -> None:
        existing = self.load()
        meta = RunMeta(
            started_at=datetime.now(timezone.utc).isoformat(),
            provider=provider,
            style=style,
            model=model,
        )
        if existing is not None:
            meta.steer_history = existing.steer_history
            meta.pending_steer = existing.pending_steer
        self.save(meta)

    def set_project_defaults(self, title: str) -> None:
        def op() -> None:
            meta = self.load() or RunMeta()
            meta.project_title = title
            self.save(meta)

        self.io.with_write_lock(op)

    def set_pending_steer(self, text: str) -> None:
        def op() -> None:
            meta = self.load() or RunMeta()
            meta.pending_steer = text
            self.save(meta)

        self.io.with_write_lock(op)

    def consume_pending_steer(self) -> str:
        meta = self.load()
        if meta is None or not meta.pending_steer:
            return ""
        text = meta.pending_steer
        meta.pending_steer = ""
        meta.steer_history.append(SteerEntry(input=text, timestamp=datetime.now(timezone.utc).isoformat()))
        self.save(meta)
        return text
