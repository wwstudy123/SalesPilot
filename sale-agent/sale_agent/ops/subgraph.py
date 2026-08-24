"""Ops 最小子图：画像和近期跟进 → 带依据的标签提案（M6）。"""

from __future__ import annotations

from sale_agent.ai.trace import TraceStore
from sale_agent.hitl.store import ProposalStore
from sale_agent.profile.mcp_client import McpClient


class OpsSubgraph:
    def __init__(self, mcp: McpClient, proposals: ProposalStore, trace: TraceStore) -> None:
        self._mcp = mcp
        self._proposals = proposals
        self._trace = trace

    def review(self, customer_id: int, employee_id: int, jwt: str, source: str = "manual") -> dict:
        run_id = self._trace.start_run(f"tags:{customer_id}", str(employee_id))
        try:
            span = self._trace.start_span(run_id, "tag_load_facts")
            profile_rows = self._mcp.get_profile(customer_id, jwt)
            follow_ups = self._mcp.list_follow_ups(customer_id, jwt)
            self._trace.finish_span(span, "ok", {"profile_fields": len(profile_rows), "follow_ups": len(follow_ups)})
            profile = {row["fieldKey"]: row.get("fieldValue", "") for row in profile_rows}

            span = self._trace.start_span(run_id, "tag_infer")
            tags = self._infer(profile, follow_ups)
            self._trace.finish_span(span, "ok", {"tags": len(tags)})
            if not tags:
                self._trace.finish_run(run_id, "completed", intent="tag_review", routing_reason="no_change", confidence=1.0)
                return {"outcome": "no_change", "customer_id": customer_id, "run_id": run_id}

            span = self._trace.start_span(run_id, "tag_propose")
            proposal, merged = self._proposals.create_or_merge(
                customer_id, employee_id, "save_tags", tags, run_id=run_id, source=source
            )
            self._trace.finish_span(span, "ok", {"proposal_id": proposal["id"], "tags": len(tags), "merged": merged})
            self._trace.finish_run(run_id, "completed", intent="tag_review", routing_reason="proposal", confidence=1.0)
            return {"outcome": "proposal", "customer_id": customer_id, "proposal": proposal, "merged": merged, "run_id": run_id}
        except Exception as exc:  # noqa: BLE001
            self._trace.finish_run(run_id, "failed", intent="tag_review", routing_reason="error", confidence=0.0)
            return {"outcome": "error", "customer_id": customer_id, "error": str(exc), "run_id": run_id}

    @staticmethod
    def _infer(profile: dict, follow_ups: list[dict]) -> list[dict]:
        text = "\n".join(str(item.get("content", "")) for item in follow_ups[:10])
        tags: list[dict] = []

        stage = str(profile.get("lifecycle_stage", ""))
        stage_key = {"new": "lifecycle_new", "prospective": "lifecycle_prospective", "existing": "lifecycle_existing"}.get(stage)
        if stage_key:
            tags.append({"tagKey": stage_key, "evidence": f"画像生命周期：{stage}", "confidence": 0.95})
        if profile.get("value_tier") == "high":
            tags.append({"tagKey": "value_high", "evidence": "画像价值分层：high", "confidence": 0.9})
        if any(word in f"{profile.get('sensitive_point', '')} {text}" for word in ("价格", "预算", "优惠", "太贵")):
            tags.append({"tagKey": "preference_price_sensitive", "evidence": "画像或近期跟进提及价格/预算", "confidence": 0.82})
        if stage == "churn_risk" or any(word in text for word in ("不需要", "别联系", "流失", "投诉")):
            tags.append({"tagKey": "risk_churn", "evidence": "生命周期或近期跟进出现流失风险信号", "confidence": 0.78})
        return tags
