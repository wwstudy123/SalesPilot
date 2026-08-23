from __future__ import annotations

from datetime import datetime
from typing import Optional

from sale_agent.domain.runtime_events import RuntimeQueueItem, RuntimeQueueKind
from sale_agent.internal_api.registry import RunSession


def iso_or_none(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def envelope(data: object, code: str = "OK", message: str = "success") -> dict[str, object]:
    return {"code": code, "message": message, "data": data}


def map_product_status(session: RunSession, lifecycle: str, awaiting_confirmation: dict | None = None) -> str:
    if session.is_busy():
        return "running"
    if awaiting_confirmation:
        return "waiting_input"
    if session.state_override == "failed":
        return "failed"
    if session.state_override == "canceled":
        return "canceled"
    if getattr(session, "has_queued_task", False):
        return "queued"
    if lifecycle == "running":
        return "running"
    if lifecycle == "completed":
        return "completed"
    return "idle"


def map_run(session: RunSession, report: dict[str, object]) -> dict[str, object]:
    lifecycle = str(report.get("lifecycle", "") or "idle")
    awaiting_confirmation = report.get("awaiting_confirmation") if isinstance(report.get("awaiting_confirmation"), dict) else None
    status = map_product_status(session, lifecycle, awaiting_confirmation)
    return {
        "run_id": session.run_id,
        "project_id": session.project_id,
        "status": status,
        "kernel_status": lifecycle,
        "phase": report.get("phase") or "",
        "flow": report.get("flow") or "",
        "provider": report.get("provider") or "",
        "model": report.get("model") or "",
        "current_section": int(report.get("current_section", 0) or 0),
        "completed_count": int(report.get("completed_sections", 0) or 0),
        "total_word_count": int(report.get("total_word_count", 0) or 0),
        "latest_checkpoint": report.get("latest_checkpoint"),
        "has_last_commit": bool(report.get("has_last_commit", False)),
        "started_at": iso_or_none(session.started_at),
        "finished_at": iso_or_none(session.finished_at),
        "last_error": {
            "code": session.last_error_code,
            "message": session.last_error_message,
        }
        if status == "failed" and (session.last_error_code or session.last_error_message)
        else None,
        "awaiting_confirmation": awaiting_confirmation,
    }


def map_create_run(session: RunSession, report: dict[str, object]) -> dict[str, object]:
    lifecycle = str(report.get("lifecycle", "") or "idle")
    awaiting_confirmation = report.get("awaiting_confirmation") if isinstance(report.get("awaiting_confirmation"), dict) else None
    return {
        "accepted": True,
        "run_id": session.run_id,
        "status": map_product_status(session, lifecycle, awaiting_confirmation),
        "kernel_status": lifecycle,
        "started_at": iso_or_none(session.started_at),
    }


def map_instruction_ack(session: RunSession, report: dict[str, object]) -> dict[str, object]:
    return {
        "run_id": session.run_id,
        "accepted": True,
        "status": map_product_status(session, str(report.get("lifecycle", "") or "idle")),
    }


def map_pause_ack(session: RunSession, report: dict[str, object]) -> dict[str, object]:
    lifecycle = str(report.get("lifecycle", "") or "idle")
    return {
        "run_id": session.run_id,
        "status": map_product_status(session, lifecycle),
        "kernel_status": lifecycle,
    }


def map_event(run_id: str, item: RuntimeQueueItem) -> dict[str, object]:
    if item.kind == RuntimeQueueKind.UI_EVENT:
        payload = item.payload if isinstance(item.payload, dict) else {}
        return {
            "event_id": f"evt_{run_id}_{item.seq}",
            "seq": item.seq,
            "run_id": run_id,
            "type": "ui.event",
            "category": item.category or "SYSTEM",
            "time": item.time.isoformat(),
            "payload": {
                "summary": item.summary,
                **payload,
                "level": payload.get("level", "info"),
            },
        }
    if item.kind == RuntimeQueueKind.STREAM_CLEAR:
        return {
            "event_id": f"evt_{run_id}_{item.seq}",
            "seq": item.seq,
            "run_id": run_id,
            "type": "stream.clear",
            "category": item.category or "content",
            "time": item.time.isoformat(),
            "payload": item.payload if isinstance(item.payload, dict) else {},
        }
    payload = item.payload if isinstance(item.payload, dict) else {}
    category = str(payload.get("channel", item.category or "content") or "content")
    return {
        "event_id": f"evt_{run_id}_{item.seq}",
        "seq": item.seq,
        "run_id": run_id,
        "type": "stream.chunk",
        "category": category,
        "time": item.time.isoformat(),
        "payload": payload,
    }


def map_events(
    run_id: str,
    items: list[RuntimeQueueItem],
    has_more: bool,
    after_seq: int = 0,
    limit: int = 0,
    total_available: int = 0,
) -> dict[str, object]:
    next_after_seq = items[-1].seq if items else after_seq
    return {
        "run_id": run_id,
        "after_seq": after_seq,
        "limit": limit,
        "returned_count": len(items),
        "total_available": total_available,
        "next_after_seq": next_after_seq,
        "has_more": has_more,
        "items": [map_event(run_id, item) for item in items],
    }


def map_project(project) -> dict[str, object]:
    return {
        "project_id": project.project_id,
        "title": project.title,
        "premise": project.premise,
        "style": project.style,
        "section_count": len(project.sections),
        "created_at": project.created_at or None,
        "updated_at": project.updated_at or None,
    }
