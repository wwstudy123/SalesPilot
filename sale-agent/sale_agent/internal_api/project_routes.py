from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from sale_agent.domain.project import Project, Section
from sale_agent.internal_api.deps import get_project_service, require_internal_auth
from sale_agent.internal_api.mappers import envelope, map_project
from sale_agent.internal_api.project_dto import CreateProjectRequest, UpdateProjectRequest
from sale_agent.internal_api.project_service import ProjectService
from sale_agent.internal_api.response_dto import Envelope, ErrorResponse, ProjectListPayload, ProjectPayload

router = APIRouter(prefix="/internal/v1/projects", dependencies=[Depends(require_internal_auth)])


def _to_sections(items) -> list[Section]:
    return [
        Section(
            order=int(item.order or idx + 1),
            section_id=(item.id or "").strip(),
            title=(item.title or "").strip(),
            summary=(item.summary or "").strip(),
            depends_on=list(item.depends_on or []),
        )
        for idx, item in enumerate(items)
    ]


@router.get("", response_model=Envelope[ProjectListPayload], responses={401: {"model": ErrorResponse}})
async def list_projects(service: ProjectService = Depends(get_project_service)) -> dict[str, object]:
    items = [map_project(project) for project in service.list()]
    return envelope({"items": items})


@router.post("", response_model=Envelope[ProjectPayload], responses={401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
async def create_project(req: CreateProjectRequest, service: ProjectService = Depends(get_project_service)) -> dict[str, object]:
    project = Project(
        project_id=(req.project_id or "").strip() or str(uuid.uuid4()),
        title=(req.title or "").strip(),
        premise=(req.premise or "").strip(),
        style=(req.style or "default").strip() or "default",
        sections=_to_sections(req.sections),
    )
    return envelope(map_project(service.create(project)))


@router.get(
    "/{project_id}", response_model=Envelope[ProjectPayload], responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}
)
async def get_project(project_id: str, service: ProjectService = Depends(get_project_service)) -> dict[str, object]:
    return envelope(map_project(service.get(project_id)))


@router.put(
    "/{project_id}", response_model=Envelope[ProjectPayload], responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}
)
async def update_project(
    project_id: str, req: UpdateProjectRequest, service: ProjectService = Depends(get_project_service)
) -> dict[str, object]:
    sections = _to_sections(req.sections) if req.sections is not None else None
    project = service.update(project_id, req.title, req.premise, req.style, sections)
    return envelope(map_project(project))


@router.delete("/{project_id}", response_model=Envelope[dict], responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
async def delete_project(project_id: str, service: ProjectService = Depends(get_project_service)) -> dict[str, object]:
    service.delete(project_id)
    return envelope({"deleted": True, "project_id": project_id})
