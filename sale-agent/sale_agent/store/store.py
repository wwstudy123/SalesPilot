from __future__ import annotations

from sale_agent.store.checkpoints import CheckpointStore
from sale_agent.store.io import IO
from sale_agent.store.progress import ProgressStore
from sale_agent.store.project_data import SectionStore
from sale_agent.store.run_meta import RunMetaStore
from sale_agent.store.runtime import RuntimeStore
from sale_agent.store.signals import SignalStore


class Store:
    def __init__(self, directory: str) -> None:
        self._dir = directory
        self.progress = ProgressStore(IO(directory))
        self.run_meta = RunMetaStore(IO(directory))
        self.runtime = RuntimeStore(IO(directory))
        self.sections = SectionStore(IO(directory))
        self.signals = SignalStore(IO(directory))
        self.checkpoints = CheckpointStore(IO(directory))

    def dir(self) -> str:
        return self._dir

    def init(self) -> None:
        self.progress.io.ensure_dirs(
            [
                "sections",
                "summaries",
                "meta",
                "meta/runtime",
                "meta/runtime/tasks",
            ]
        )
