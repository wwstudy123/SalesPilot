from __future__ import annotations

from pathlib import Path

from agentkit.agents.build import build_coordinator_loop, build_tool_registry
from agentkit.bootstrap.config import Config, ProviderConfig
from agentkit.store.store import Store


def _cfg(output_dir: Path) -> Config:
    cfg = Config(
        output_dir=str(output_dir),
        provider="openai",
        model="gpt-4o-mini",
        providers={"openai": ProviderConfig(api_key="dummy-key")},
        style="default",
        context_window=128000,
    )
    cfg.fill_defaults()
    return cfg


def test_tool_registry_contains_example_tools(tmp_path):
    store = Store(str(tmp_path))
    store.init()

    tools = build_tool_registry(store)
    assert "load_project_context" in tools
    assert "commit_section" in tools


def test_minimal_pipeline_runs_without_llm(tmp_path):
    store = Store(str(tmp_path))
    store.init()
    store.progress.init("Smoke Project", 1)

    loop = build_coordinator_loop(_cfg(tmp_path), store, lambda event: None, lambda channel, delta: None)

    graph_view = loop.backend.graph.get_graph()
    node_ids = set(graph_view.nodes)
    for required in ("load_runtime_context", "generate_section", "commit_section", "checkpoint", "finish"):
        assert required in node_ids

    # 占位 key 触发降级：无 LLM 也能产出 placeholder draft 并完成提交
    loop.backend.start("生成第一节")

    sections = list((tmp_path / "sections").glob("*.md"))
    assert sections, "pipeline should commit at least one section"
