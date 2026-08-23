from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from sagt_agent.agents.orchestrator.langgraph.state import GraphState
from sagt_agent.domain.runs import PendingRunCheckpoint
from sagt_agent.domain.runtime import Phase

if TYPE_CHECKING:
    from sagt_agent.agents.orchestrator.langgraph.core import LangGraphRuntime


def load_runtime_context(rt: "LangGraphRuntime") -> Callable[[dict], dict]:
    def node(state: "GraphState") -> dict:
        out_lines = list(state.get("out_lines") or [])
        if state.get("stop_requested"):
            return {"pending_action": "finish", "out_lines": out_lines + ["[load] stop requested"]}

        if rt.store.progress.load() is None:
            rt.store.progress.init("", 0)
        context = rt.runner.run_tool("load_project_context", {})
        context["instruction"] = str(state.get("seed_text", "") or "")

        next_section = int(context.get("next_section", 1) or 1)
        total = int(context.get("total_sections", 0) or 0)
        if total and next_section > total:
            rt.store.progress.update_phase(Phase.COMPLETE)
            out_lines.append(f"[load] all {total} sections completed")
            return {"context": context, "pending_action": "finish", "out_lines": out_lines}

        out_lines.append(f"[load] next section: {next_section}" + (f" / total {total}" if total else ""))
        return {
            "context": context,
            "current_section": next_section,
            "pending_action": "generate",
            "out_lines": out_lines,
        }

    return node


def generate_section_node(rt: "LangGraphRuntime") -> Callable[[dict], dict]:
    def node(state: "GraphState") -> dict:
        section = int(state.get("current_section", 0) or 0)
        context = state.get("context") or {}
        rt.store.progress.start_section(section)
        rt.emit_stream("thinking", f"[generate] section {section}\n")

        pack = rt.context_manager.build_pack(context)
        system_prompt = rt.assets.prompts.get("writer") or ("你是一个内容生成 Agent。请根据上下文生成一节 Markdown 内容。")
        user_prompt = (pack.summary_block or "请生成第一节内容。") + f"\n\n请生成第 {section} 节的 Markdown 正文。"

        draft = ""
        try:
            client = rt.build_client()
            draft = (client.complete(system_prompt, user_prompt, temperature=0.6) or "").strip()
        except Exception as exc:
            rt.emit_stream("thinking", f"[generate] LLM unavailable ({exc}), using placeholder draft\n")
        if not draft:
            draft = _placeholder_draft(section, str(context.get("premise", "") or ""))

        rt.emit_stream("content", draft + "\n")
        out_lines = list(state.get("out_lines") or []) + [f"[generate] section {section} drafted ({len(draft)} chars)"]
        return {"latest_draft": draft, "out_lines": out_lines}

    return node


def commit_section_node(rt: "LangGraphRuntime") -> Callable[[dict], dict]:
    def node(state: "GraphState") -> dict:
        section = int(state.get("current_section", 0) or 0)
        draft = str(state.get("latest_draft", "") or "")
        summary = draft.strip().splitlines()[0][:120] if draft.strip() else ""
        result = rt.runner.run_tool("commit_section", {"section": section, "content": draft, "summary": summary})
        rt.store.signals.save_last_commit(result)
        out_lines = list(state.get("out_lines") or []) + [
            f"[commit] section {section} committed (checkpoint seq {result.get('checkpoint_seq')})"
        ]
        return {"latest_commit_result": result, "out_lines": out_lines}

    return node


def checkpoint_node(rt: "LangGraphRuntime") -> Callable[[dict], dict]:
    def node(state: "GraphState") -> dict:
        result = state.get("latest_commit_result") or {}
        section = int(state.get("current_section", 0) or 0)
        out_lines = list(state.get("out_lines") or [])

        if result.get("all_done"):
            rt.store.progress.mark_complete()
            rt.store.signals.clear_pending_checkpoint()
            out_lines.append("[checkpoint] all sections completed")
            return {"pending_action": "finish", "out_lines": out_lines}

        pending = PendingRunCheckpoint(
            pause_after_section=section,
            next_section=int(result.get("next_section", section + 1) or section + 1),
            completed_count=int(result.get("completed_count", 0) or 0),
        )
        rt.store.signals.save_pending_checkpoint(pending)
        rt.emit_checkpoint_pending(pending)
        out_lines.append(f"[checkpoint] paused after section {section}, awaiting confirmation")
        return {"pending_action": "finish", "out_lines": out_lines}

    return node


def finish_node(rt: "LangGraphRuntime") -> Callable[[dict], dict]:
    def node(state: "GraphState") -> dict:
        _ = rt
        out_lines = list(state.get("out_lines") or []) + ["[finish] run complete"]
        return {"out_lines": out_lines}

    return node


def route_after_load(state: "GraphState") -> str:
    return "generate_section" if state.get("pending_action") == "generate" else "finish"


def _placeholder_draft(section: int, premise: str) -> str:
    intro = premise.strip().splitlines()[0][:80] if premise.strip() else "示例项目"
    return (
        f"## 第 {section} 节\n\n"
        f"> 占位产出：LLM 未配置时由骨架自动生成。\n\n"
        f"项目概述：{intro}\n\n"
        f"本节为第 {section} 节的示例内容，接入真实模型后将被 LLM 产出替换。\n"
    )
