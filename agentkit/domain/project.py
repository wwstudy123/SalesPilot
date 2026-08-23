from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Section:
    order: int
    section_id: str = ""
    title: str = ""
    summary: str = ""
    depends_on: list[str] = field(default_factory=list)


@dataclass
class Project:
    project_id: str
    title: str = ""
    premise: str = ""
    style: str = "default"
    sections: list[Section] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
