from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from agentkit.bootstrap.config import Config, ProviderConfig
from agentkit.bootstrap.configfile import load_config
from agentkit.domain.project import Section
from agentkit.host.host import Host
from agentkit.internal_api.dto import CreateRunRequest, InstructionRequest, ResumeRunRequest
from agentkit.internal_api.errors import ApiError
from agentkit.internal_api.registry import RunRegistry, RunSession
from agentkit.internal_api.tasks import RunTask


class RunService:
    def __init__(self, registry: Optional[RunRegistry] = None) -> None:
        self.registry = registry or RunRegistry()

    def create_run(self, req: CreateRunRequest) -> RunSession:
        existing = self.registry.get(req.run_id)
        if existing is not None:
            return existing
        prompt = (req.input.prompt or "").strip()
        if not prompt:
            raise ApiError("INVALID_ARGUMENT", "prompt is required", 400)
        cfg = self._build_config(req)
        host = Host(cfg)
        self._seed_project_context(host, req)
        session = RunSession(
            run_id=req.run_id,
            project_id=req.project.project_id or req.run_id,
            output_dir=cfg.output_dir,
            cfg=cfg,
            host=host,
            last_operation="create",
        )
        self.registry.put(session)
        self.registry.put_task(RunTask(task_id=str(uuid.uuid4()), run_id=req.run_id, op="start", payload={"prompt": prompt}))
        return session

    def get_run(self, run_id: str) -> RunSession:
        session = self.registry.get(run_id)
        if session is None:
            raise ApiError("RUN_NOT_FOUND", "run not found", 404, {"run_id": run_id})
        return session

    def get_report(self, run_id: str) -> tuple[RunSession, dict[str, object]]:
        session = self.get_run(run_id)
        return session, session.host.report()

    def list_runs(self, status: str = "", project_id: str = "") -> list[tuple[RunSession, dict[str, object]]]:
        out: list[tuple[RunSession, dict[str, object]]] = []
        for session in sorted(self.registry.list(), key=lambda item: item.created_at):
            if project_id and session.project_id != project_id:
                continue
            report = session.host.report()
            if status and str(report.get("lifecycle", "") or "idle") != status:
                continue
            out.append((session, report))
        return out

    def pause_run(self, run_id: str) -> RunSession:
        session = self.get_run(run_id)
        session.host.abort()
        session.last_operation = "pause"
        self.registry.persist(session)
        return session

    def resume_run(self, run_id: str, req: ResumeRunRequest) -> RunSession:
        session = self.get_run(run_id)
        if session.is_busy():
            raise ApiError("CONFLICT", "run is busy", 409, {"run_id": run_id})
        session.state_override = ""
        session.last_operation = "resume"
        self.registry.persist(session)
        self.registry.put_task(
            RunTask(task_id=str(uuid.uuid4()), run_id=run_id, op="resume", payload={"prompt": (req.prompt or "").strip()})
        )
        return session

    def cancel_run(self, run_id: str) -> RunSession:
        session = self.get_run(run_id)
        session.state_override = "canceled"
        session.host.abort()
        session.last_operation = "cancel"
        self.registry.persist(session)
        return session

    def add_instruction(self, run_id: str, req: InstructionRequest) -> RunSession:
        session = self.get_run(run_id)
        text = (req.instruction.text or "").strip()
        if not text:
            raise ApiError("INVALID_ARGUMENT", "instruction text is required", 400)
        if session.is_busy():
            session.host.steer(text)
        else:
            self.registry.put_task(RunTask(task_id=str(uuid.uuid4()), run_id=run_id, op="continue", payload={"text": text}))
        session.last_operation = "instruction"
        self.registry.persist(session)
        return session

    def get_events(self, run_id: str, after_seq: int, limit: int) -> tuple[RunSession, list, int]:
        session = self.get_run(run_id)
        items = session.host.replay_queue(after_seq)
        return session, items[:limit], len(items)

    def _build_config(self, req: CreateRunRequest) -> Config:
        if req.config_path:
            cfg = load_config(req.config_path)
        else:
            provider = req.execution.provider or "openai"
            model = req.execution.model or "gpt-4o-mini"
            cfg = Config(
                output_dir=self._resolve_output_dir(req),
                provider=provider,
                model=model,
                providers={provider: ProviderConfig(api_key="dummy-key")},
                style="default",
                context_window=req.execution.context_window or 128000,
            )
        cfg.output_dir = self._resolve_output_dir(req)
        if req.execution.provider:
            cfg.provider = req.execution.provider
        if req.execution.model:
            cfg.model = req.execution.model
        if req.execution.context_window > 0:
            cfg.context_window = req.execution.context_window
        if (req.project.style or "").strip():
            cfg.style = req.project.style.strip()
        cfg.fill_defaults()
        if cfg.provider not in cfg.providers:
            cfg.providers[cfg.provider] = ProviderConfig(api_key="dummy-key")
        if not cfg.providers[cfg.provider].api_key and cfg.providers[cfg.provider].requires_api_key(cfg.provider):
            cfg.providers[cfg.provider].api_key = "dummy-key"
        return cfg

    def _resolve_output_dir(self, req: CreateRunRequest) -> str:
        base = (req.storage.base_path or "").strip()
        if base:
            return base
        project_id = (req.project.project_id or "").strip()
        if project_id:
            return str(Path("output") / "projects" / project_id)
        return str(Path("output") / "runs" / req.run_id)

    def _seed_project_context(self, host: Host, req: CreateRunRequest) -> None:
        premise = (req.project.premise or "").strip()
        if premise:
            host.store.sections.save_premise(premise)
        sections = [
            Section(
                order=int(item.order or idx + 1),
                section_id=(item.id or "").strip(),
                title=(item.title or "").strip(),
                summary=(item.summary or "").strip(),
                depends_on=list(item.depends_on or []),
            )
            for idx, item in enumerate(req.project.sections)
            if (item.title or "").strip() or (item.id or "").strip()
        ]
        if sections:
            host.store.sections.save_sections(sections)
        host.store.run_meta.set_project_defaults((req.project.title or "").strip())
