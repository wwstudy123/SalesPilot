"""Profile 结构化抽取：LLM JSON Schema 约束；echo 模式降级为确定性规则抽取。

字段集（需求 §13）：preference/demand/value_tier/lifecycle_stage/sensitive_point/recent_focus。
每条抽取必须附依据（evidence 引用具体跟进记录 id），无依据宁缺勿造。
"""

from __future__ import annotations

import json
import logging

from sale_agent.ai.gateway import LLMGateway

logger = logging.getLogger(__name__)

FIELD_KEYS = ("preference", "demand", "value_tier", "lifecycle_stage", "sensitive_point", "recent_focus")

_PROMPT = (
    "你是客户画像抽取器。基于跟进记录与消费记录，抽取客户画像字段，只输出 JSON：\n"
    '{{"fields": [{{"fieldKey": "<{}>", "fieldValue": "<简述>", "evidence": "follow_up#<id>"}}]}}\n'
    "规则：fieldKey 只能取上述之一；每条结论必须能回溯到具体记录；没有依据的字段不要输出。\n\n"
    "跟进记录：\n{follow_ups}\n\n消费记录：\n{purchases}"
)

# echo 模式确定性规则：关键词 → 字段（演示可复现，面试可解释降级策略）
_KEYWORD_RULES: list[tuple[str, tuple[str, ...], str]] = [
    ("preference", ("喜欢", "偏好", "爱喝", "爱吃", "感兴趣", "常买"), "兴趣偏好"),
    ("demand", ("想买", "打算买", "考虑", "需要", "预算"), "明确需求"),
    ("sensitive_point", ("太贵", "价格高", "便宜点", "优惠", "担心", "顾虑"), "价格/顾虑敏感点"),
    ("recent_focus", ("最近", "这几天", "下周", "回头", "再看看"), "近期关注"),
]


class ProfileExtractor:
    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    def extract(self, follow_ups: list[dict], purchases: list[dict]) -> list[dict]:
        """返回 [{fieldKey, fieldValue, evidence}]；echo 模式走规则抽取。"""
        if self._gateway.settings.echo_mode:
            return self._heuristic(follow_ups, purchases)
        prompt = _PROMPT.format(
            "/".join(FIELD_KEYS),
            follow_ups=self._fmt_follow_ups(follow_ups),
            purchases=self._fmt_purchases(purchases),
        )
        try:
            result = self._gateway.chat([{"role": "user", "content": prompt}], temperature=0.0)
            fields = self._parse(result.content)
            return fields if fields is not None else self._heuristic(follow_ups, purchases)
        except Exception as exc:  # noqa: BLE001
            logger.warning("profile extract llm failed, fallback to heuristic: %s", exc)
            return self._heuristic(follow_ups, purchases)

    # ---------- echo/降级：确定性规则 ----------

    @staticmethod
    def _heuristic(follow_ups: list[dict], purchases: list[dict]) -> list[dict]:
        fields: dict[str, dict] = {}
        for record in follow_ups:
            content = record.get("content") or ""
            record_id = record.get("id")
            excerpt = content[:40]
            for field_key, keywords, label in _KEYWORD_RULES:
                if field_key in fields:
                    continue
                hit = next((kw for kw in keywords if kw in content), None)
                if hit:
                    fields[field_key] = {
                        "fieldKey": field_key,
                        "fieldValue": f"{label}：提到“{hit}”（{excerpt}）",
                        "evidence": f"follow_up#{record_id}",
                    }
        # 价值分层：累计消费额（规则透明可调）
        total = sum(float(purchase.get("amount") or 0) for purchase in purchases)
        if purchases:
            tier = "high" if total >= 20000 else "medium" if total >= 5000 else "low"
            fields["value_tier"] = {
                "fieldKey": "value_tier",
                "fieldValue": tier,
                "evidence": f"purchase 累计 {total:.0f} 元（{len(purchases)} 笔）",
            }
        return sorted(fields.values(), key=lambda item: FIELD_KEYS.index(item["fieldKey"]))

    # ---------- LLM 输出解析 ----------

    @staticmethod
    def _parse(content: str) -> list[dict] | None:
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            return None
        raw_fields = data.get("fields")
        if not isinstance(raw_fields, list):
            return None
        valid = [
            {"fieldKey": item["fieldKey"], "fieldValue": str(item["fieldValue"]), "evidence": str(item.get("evidence", ""))}
            for item in raw_fields
            if isinstance(item, dict) and item.get("fieldKey") in FIELD_KEYS and item.get("fieldValue") and item.get("evidence")
        ]
        return valid or None

    @staticmethod
    def _fmt_follow_ups(follow_ups: list[dict]) -> str:
        return "\n".join(f"- follow_up#{item.get('id')} [{item.get('channel')}] {item.get('content')}" for item in follow_ups) or "（无）"

    @staticmethod
    def _fmt_purchases(purchases: list[dict]) -> str:
        return (
            "\n".join(
                f"- purchase#{item.get('id')} {item.get('productName') or item.get('product_name')}"
                f" {item.get('amount')}元 x{item.get('quantity')}"
                for item in purchases
            )
            or "（无）"
        )
