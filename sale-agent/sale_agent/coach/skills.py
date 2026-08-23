"""技能配置（M5 硬编码 2 个；正式版落 skill/skill_version 表）。"""

from __future__ import annotations

SKILLS: dict[str, dict] = {
    "intent-followup": {
        "id": "intent-followup",
        "label": "回访话术",
        "intents": ("talk_script",),
        "description": "面向回访/触达场景：开场破冰、需求探询、关系维护。",
        "default_query": "客户回访 开场 跟进 需求探询",
    },
    "objection-handling": {
        "id": "objection-handling",
        "label": "异议化解",
        "intents": ("objection_help",),
        "description": "面向客户异议场景：价格顾虑、拖延决策、竞品比较。",
        "default_query": "客户异议 价格 太贵 考虑 对比",
    },
}

_FALLBACK = SKILLS["intent-followup"]


def select_skill(intent: str | None) -> dict:
    """按意图装配技能；未登记的 coaching 意图回落回访话术。"""
    for skill in SKILLS.values():
        if intent in skill["intents"]:
            return skill
    return _FALLBACK
