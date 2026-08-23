from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SectionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: int = 0
    id: str = ""
    title: str = ""
    summary: str = ""
    depends_on: list[str] = Field(default_factory=list)


class ProjectSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = ""
    title: str = ""
    premise: str = ""
    style: str = "default"
    sections: list[SectionSpec] = Field(default_factory=list)


class ExecutionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = ""
    model: str = ""
    context_window: int = 0
    temperature: Optional[float] = None


class InputSpec(BaseModel):
    mode: str = "start"
    prompt: str = ""


class StorageSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "local"
    base_path: str = ""


class MetadataSpec(BaseModel):
    extra: dict[str, Any] = Field(default_factory=dict)


class CreateRunRequest(BaseModel):
    run_id: str
    project: ProjectSpec = Field(default_factory=ProjectSpec)
    execution: ExecutionSpec = Field(default_factory=ExecutionSpec)
    input: InputSpec = Field(default_factory=InputSpec)
    storage: StorageSpec = Field(default_factory=StorageSpec)
    metadata: MetadataSpec = Field(default_factory=MetadataSpec)
    config_path: str = ""


class InstructionSpec(BaseModel):
    kind: str = "continue"
    text: str = ""


class InstructionRequest(BaseModel):
    instruction: InstructionSpec = Field(default_factory=InstructionSpec)
    metadata: MetadataSpec = Field(default_factory=MetadataSpec)


class ResumeRunRequest(BaseModel):
    prompt: str = ""


class PauseRunRequest(BaseModel):
    reason: str = ""
