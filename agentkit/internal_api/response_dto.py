from __future__ import annotations

from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    code: str
    message: str
    data: T


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None


class HealthPayload(BaseModel):
    status: str
    host: str
    port: int
    run_count: int


class RunPayload(BaseModel):
    run_id: str
    project_id: str
    status: str
    kernel_status: str
    phase: str
    flow: str
    provider: str
    model: str
    current_section: int
    completed_count: int
    total_word_count: int
    latest_checkpoint: Optional[dict] = None
    has_last_commit: bool
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    last_error: Optional[dict] = None
    awaiting_confirmation: Optional[dict] = None


class CreateRunPayload(BaseModel):
    accepted: bool
    run_id: str
    status: str
    kernel_status: str
    started_at: Optional[str] = None


class AckPayload(BaseModel):
    run_id: str
    status: str
    kernel_status: Optional[str] = None
    accepted: Optional[bool] = None


class RunListPayload(BaseModel):
    items: list[RunPayload]


class EventItemPayload(BaseModel):
    event_id: str
    seq: int
    run_id: str
    type: str
    category: str
    time: str
    payload: dict


class EventsPagePayload(BaseModel):
    run_id: str
    after_seq: int
    limit: int
    returned_count: int
    total_available: int
    next_after_seq: int
    has_more: bool
    items: list[EventItemPayload]


class ProjectPayload(BaseModel):
    project_id: str
    title: str
    premise: str
    style: str
    section_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProjectListPayload(BaseModel):
    items: list[ProjectPayload]
