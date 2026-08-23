from __future__ import annotations

import json
from typing import Any

from sale_agent.domain.project import Section


def extract_json_object(raw: str) -> dict[str, Any]:
    """从 LLM 原始输出中提取首个 JSON 对象（兼容 ``` 围栏）。"""
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty response")
    candidates = [text]
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            fence_body = "\n".join(lines[1:-1]).strip()
            if fence_body:
                candidates.insert(0, fence_body)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    raise ValueError("response is not a valid JSON object")


def parse_section_entry(data: dict[str, Any]) -> Section:
    return Section(
        order=int(data.get("order", 0) or 0),
        section_id=str(data.get("id", data.get("section_id", "")) or "").strip(),
        title=str(data.get("title", "") or "").strip(),
        summary=str(data.get("summary", "") or "").strip(),
        depends_on=[str(x) for x in (data.get("dependsOn") or data.get("depends_on") or [])],
    )
