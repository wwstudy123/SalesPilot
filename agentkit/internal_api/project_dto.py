from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from agentkit.internal_api.dto import SectionSpec


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = ""
    title: str = ""
    premise: str = ""
    style: str = "default"
    sections: list[SectionSpec] = Field(default_factory=list)


class UpdateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    premise: Optional[str] = None
    style: Optional[str] = None
    sections: Optional[list[SectionSpec]] = None
