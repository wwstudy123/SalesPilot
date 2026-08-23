from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sagt_agent.internal_api.persistence import RunRegistryStore, RunTaskStore
from sagt_agent.internal_api.project_routes import router as project_router
from sagt_agent.internal_api.project_service import ProjectService
from sagt_agent.internal_api.registry import RunRegistry
from sagt_agent.internal_api.routes import install_error_handlers, router
from sagt_agent.internal_api.service import RunService
from sagt_agent.internal_api.settings import load_settings
from sagt_agent.internal_api.worker import WorkerManager

DEFAULT_CORS_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
]


def _cors_origins() -> list[str]:
    raw = os.environ.get("AGENTKIT_CORS_ORIGINS", "").strip()
    if not raw:
        return list(DEFAULT_CORS_ORIGINS)
    return [item.strip() for item in raw.split(",") if item.strip()]


def create_app() -> FastAPI:
    app = FastAPI(
        title="sagt_agent internal api",
        version="0.1.0",
        description="Internal API to control and observe the Python agent runtime.",
    )
    settings = load_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    store = RunRegistryStore(settings.registry_path)
    task_store = RunTaskStore(settings.registry_path + ".tasks")
    registry = RunRegistry(store, task_store)
    registry.restore()
    worker = WorkerManager(registry)
    worker.start()
    app.state.settings = settings
    app.state.run_registry = registry
    app.state.run_service = RunService(registry)
    app.state.project_service = ProjectService()
    app.state.worker_manager = worker
    app.include_router(router)
    app.include_router(project_router)
    install_error_handlers(app)
    return app


app = create_app()
