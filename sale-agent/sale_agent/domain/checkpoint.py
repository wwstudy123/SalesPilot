from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class ScopeKind:
    SECTION = "section"
    GLOBAL = "global"


@dataclass
class Scope:
    kind: str
    section: int = 0

    def matches(self, other: "Scope") -> bool:
        if self.kind != other.kind:
            return False
        if self.kind == ScopeKind.SECTION:
            return self.section == other.section
        return True


def section_scope(section: int) -> Scope:
    return Scope(kind=ScopeKind.SECTION, section=section)


def global_scope() -> Scope:
    return Scope(kind=ScopeKind.GLOBAL)


@dataclass
class Checkpoint:
    seq: int
    scope: Scope
    step: str
    artifact: str = ""
    digest: str = ""
    occurred_at: datetime = datetime.utcnow()
