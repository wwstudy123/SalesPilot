from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from sagt_agent.domain.project import Section
from sagt_agent.store.io import IO


@dataclass
class SectionSummary:
    section: int
    summary: str = ""
    key_points: list[str] = field(default_factory=list)


class SectionStore:
    """持久化项目上下文（premise）、已提交节正文与节摘要。"""

    def __init__(self, io: IO) -> None:
        self.io = io

    # premise -------------------------------------------------
    def save_premise(self, premise: str) -> None:
        self.io.write_file("meta/premise.md", premise.encode("utf-8"))

    def load_premise(self) -> str:
        try:
            return self.io.read_file("meta/premise.md").decode("utf-8").strip()
        except FileNotFoundError:
            return ""

    # sections planning ---------------------------------------
    def save_sections(self, sections: list[Section]) -> None:
        self.io.write_json("meta/sections.json", [asdict(item) for item in sections])

    def load_sections(self) -> list[Section]:
        try:
            data = self.io.read_json("meta/sections.json")
        except FileNotFoundError:
            return []
        out: list[Section] = []
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict):
                continue
            out.append(
                Section(
                    order=int(item.get("order", 0) or 0),
                    section_id=str(item.get("section_id", "") or ""),
                    title=str(item.get("title", "") or ""),
                    summary=str(item.get("summary", "") or ""),
                    depends_on=[str(x) for x in (item.get("depends_on") or [])],
                )
            )
        return out

    # section text --------------------------------------------
    def save_section_text(self, section: int, text: str) -> None:
        self.io.write_file(f"sections/{section}.md", text.encode("utf-8"))

    def load_section_text(self, section: int) -> str:
        try:
            return self.io.read_file(f"sections/{section}.md").decode("utf-8")
        except FileNotFoundError:
            return ""

    def list_sections(self) -> list[int]:
        out: list[int] = []
        for p in self.io.glob("sections/*.md"):
            try:
                out.append(int(p.stem))
            except ValueError:
                continue
        return sorted(out)

    # summaries -----------------------------------------------
    def save_summary(self, summary: SectionSummary) -> None:
        self.io.write_json(
            f"summaries/{summary.section}.json",
            {"section": summary.section, "summary": summary.summary, "key_points": summary.key_points},
        )

    def load_summary(self, section: int) -> SectionSummary | None:
        try:
            data: dict[str, Any] = self.io.read_json(f"summaries/{section}.json")
        except FileNotFoundError:
            return None
        return SectionSummary(
            section=int(data.get("section", section) or section),
            summary=str(data.get("summary", "") or ""),
            key_points=[str(x) for x in (data.get("key_points") or [])],
        )
