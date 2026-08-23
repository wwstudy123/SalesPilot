from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sale_agent.ai.context_store import build_context_store
from sale_agent.ai.gateway import LLMGateway
from sale_agent.ai.graph import ChatGraph
from sale_agent.ai.router import router as ai_router
from sale_agent.ai.trace import TraceStore
from sale_agent.intent.embedding import EmbeddingClassifier
from sale_agent.intent.fusion import IntentRouter
from sale_agent.intent.llm import LLMClassifier
from sale_agent.intent.rule import RuleClassifier
from sale_agent.intent.schema import IntentCatalogStore, seed_default_catalog
from sale_agent.internal_api.persistence import RunRegistryStore, RunTaskStore
from sale_agent.internal_api.project_routes import router as project_router
from sale_agent.internal_api.project_service import ProjectService
from sale_agent.internal_api.registry import RunRegistry
from sale_agent.internal_api.routes import install_error_handlers, router
from sale_agent.internal_api.service import RunService
from sale_agent.internal_api.settings import load_settings
from sale_agent.internal_api.worker import WorkerManager

DEFAULT_CORS_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
]


def _cors_origins() -> list[str]:
    raw = os.environ.get("SALE_CORS_ORIGINS", "").strip()
    if not raw:
        return list(DEFAULT_CORS_ORIGINS)
    return [item.strip() for item in raw.split(",") if item.strip()]


def create_app() -> FastAPI:
    app = FastAPI(
        title="sale_agent internal api",
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
    gateway = LLMGateway()
    trace_store = TraceStore()
    context_store = build_context_store()
    intent_catalog = IntentCatalogStore()
    seed_default_catalog(intent_catalog)
    intent_router = IntentRouter(
        intent_catalog,
        RuleClassifier(),
        EmbeddingClassifier(intent_catalog),
        LLMClassifier(gateway, intent_catalog),
    )
    app.state.llm_gateway = gateway
    app.state.trace_store = trace_store
    app.state.context_store = context_store
    app.state.intent_catalog = intent_catalog
    app.state.intent_router = intent_router
    app.state.chat_graph = ChatGraph(gateway, context_store, trace_store, intent_router)
    app.include_router(router)
    app.include_router(project_router)
    app.include_router(ai_router)
    install_error_handlers(app)
    return app


app = create_app()
