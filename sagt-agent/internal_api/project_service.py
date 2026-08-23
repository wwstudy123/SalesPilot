from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sagt_agent.domain.project import Project, Section
from sagt_agent.internal_api.errors import ApiError
from sagt_agent.store.io import IO


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectService:
    """示例 CRUD：Project 元数据的文件持久化（output/projects/{project_id}.json）。"""

    def __init__(self, base_path: str = "") -> None:
        self.base_path = (base_path or "").strip() or str(Path("output") / "projects")
        self.io = IO(self.base_path)

    def list(self) -> list[Project]:
        items = [self._load(path.stem) for path in self.io.glob("*.json")]
        return [item for item in items if item is not None]

    def get(self, project_id: str) -> Project:
        project = self._load(project_id)
        if project is None:
            raise ApiError("PROJECT_NOT_FOUND", "project not found", 404, {"project_id": project_id})
        return project

    def create(self, project: Project) -> Project:
        if not project.project_id:
            raise ApiError("INVALID_ARGUMENT", "project_id is required", 400)
        if self._load(project.project_id) is not None:
            raise ApiError("ALREADY_EXISTS", "project already exists", 409, {"project_id": project.project_id})
        project.created_at = _utcnow_iso()
        project.updated_at = project.created_at
        self._save(project)
        return project

    def update(self, project_id: str, title: str | None, premise: str | None, style: str | None, sections: list[Section] | None) -> Project:
        project = self.get(project_id)
        if title is not None:
            project.title = title
        if premise is not None:
            project.premise = premise
        if style is not None:
            project.style = style or project.style
        if sections is not None:
            project.sections = sections
        project.updated_at = _utcnow_iso()
        self._save(project)
        return project

    def delete(self, project_id: str) -> None:
        self.get(project_id)
        self.io.remove_file(f"{project_id}.json")

    def _load(self, project_id: str) -> Project | None:
        try:
            data = self.io.read_json(f"{project_id}.json")
        except FileNotFoundError:
            return None
        sections = [
            Section(
                order=int(item.get("order", 0) or 0),
                section_id=str(item.get("section_id", "") or ""),
                title=str(item.get("title", "") or ""),
                summary=str(item.get("summary", "") or ""),
                depends_on=[str(x) for x in (item.get("depends_on") or [])],
            )
            for item in (data.get("sections") or [])
            if isinstance(item, dict)
        ]
        return Project(
            project_id=str(data.get("project_id", project_id) or project_id),
            title=str(data.get("title", "") or ""),
            premise=str(data.get("premise", "") or ""),
            style=str(data.get("style", "default") or "default"),
            sections=sections,
            created_at=str(data.get("created_at", "") or ""),
            updated_at=str(data.get("updated_at", "") or ""),
        )

    def _save(self, project: Project) -> None:
        self.io.write_json(f"{project.project_id}.json", asdict(project))
