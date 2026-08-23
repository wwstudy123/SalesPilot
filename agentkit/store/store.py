from __future__ import annotations

from agentkit.store.checkpoints import CheckpointStore
from agentkit.store.io import IO
from agentkit.store.progress import ProgressStore
from agentkit.store.project_data import SectionStore
from agentkit.store.run_meta import RunMetaStore
from agentkit.store.runtime import RuntimeStore
from agentkit.store.signals import SignalStore


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
