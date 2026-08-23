"""Profile 子图（F1 增量画像）：事实装载 → 结构化抽取 → 字段级 diff → 更新提案。

- 记录不足 3 条不抽取，产出首访信息采集清单（E13 冷启动引导）；
- diff 仅保留新增/变更字段（字段级，不整包覆盖）；
- 提案落 ProposalStore（同客户同字段 pending 提案自动合并），等待员工确认；
- 全程打 Trace span，Run 可回放（Monitor 验收）。
"""

from __future__ import annotations

import logging

from sale_agent.ai.trace import TraceStore
from sale_agent.hitl.store import ProposalStore
from sale_agent.profile.extractor import ProfileExtractor
from sale_agent.profile.mcp_client import McpClient

logger = logging.getLogger(__name__)

MIN_RECORDS = 3

FIRST_VISIT_CHECKLIST = [
    "基础信息：称呼、联系方式、家庭结构（谁一起用）",
    "需求场景：自用还是送礼？解决什么问题？",
    "预算范围与决策时间：大概预算、什么时候要",
    "偏好与禁忌：品牌偏好、过往使用体验、敏感点",
    "竞品对比：是否在看别家、关注哪些差异",
]


class ProfileSubgraph:
    def __init__(
        self,
        mcp: McpClient,
        extractor: ProfileExtractor,
        proposals: ProposalStore,
        trace: TraceStore,
    ) -> None:
        self._mcp = mcp
        self._extractor = extractor
        self._proposals = proposals
        self._trace = trace

    def refresh(self, customer_id: int, employee_id: int, jwt: str, source: str = "manual", fresh: bool = False) -> dict:
        """主流程。返回 outcome: first_visit_checklist / no_change / proposal / error。fresh：事件触发时绕过网关读缓存。"""
        run_id = self._trace.start_run(f"profile:{customer_id}", str(employee_id))
        try:
            facts = self._load_facts(run_id, customer_id, jwt, fresh=fresh)
            follow_ups, purchases, current = facts
            if len(follow_ups) < MIN_RECORDS:
                self._finish(run_id, "completed", "first_visit_checklist")
                return {
                    "outcome": "first_visit_checklist",
                    "customer_id": customer_id,
                    "record_count": len(follow_ups),
                    "checklist": FIRST_VISIT_CHECKLIST,
                    "run_id": run_id,
                }

            extracted = self._extract(run_id, follow_ups, purchases)
            diff = self._diff(run_id, extracted, current)
            if not diff:
                self._finish(run_id, "completed", "no_change")
                return {"outcome": "no_change", "customer_id": customer_id, "run_id": run_id}

            proposal, merged = self._propose(run_id, customer_id, employee_id, diff, source)
            self._finish(run_id, "completed", "proposal")
            return {
                "outcome": "proposal",
                "customer_id": customer_id,
                "proposal": proposal,
                "merged": merged,
                "run_id": run_id,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("profile refresh failed customer=%s: %s", customer_id, exc)
            self._finish(run_id, "failed", "error", str(exc))
            return {"outcome": "error", "customer_id": customer_id, "error": str(exc), "run_id": run_id}

    # ---------- 节点 ----------

    def _load_facts(self, run_id: str, customer_id: int, jwt: str, fresh: bool = False) -> tuple[list[dict], list[dict], list[dict]]:
        span = self._trace.start_span(run_id, "load_facts")
        try:
            follow_ups = self._mcp.list_follow_ups(customer_id, jwt, no_cache=fresh)
            purchases = self._mcp.list_purchases(customer_id, jwt, no_cache=fresh)
            current = self._mcp.get_profile(customer_id, jwt, no_cache=fresh)
            self._trace.finish_span(span, "ok", {"follow_ups": len(follow_ups), "purchases": len(purchases)})
            return follow_ups, purchases, current
        except Exception as exc:  # noqa: BLE001
            self._trace.finish_span(span, "error", {"error": str(exc)})
            raise

    def _extract(self, run_id: str, follow_ups: list[dict], purchases: list[dict]) -> list[dict]:
        span = self._trace.start_span(run_id, "extract")
        try:
            fields = self._extractor.extract(follow_ups, purchases)
            self._trace.finish_span(span, "ok", {"fields": len(fields)})
            return fields
        except Exception as exc:  # noqa: BLE001
            self._trace.finish_span(span, "error", {"error": str(exc)})
            raise

    @staticmethod
    def _diff(run_id: str, extracted: list[dict], current: list[dict]) -> list[dict]:
        """字段级 diff：值变更或字段缺失才入提案（冲突双值并呈交由前端展示新旧值）。"""
        current_by_key = {row["fieldKey"]: row for row in current}
        changes = []
        for item in extracted:
            existing = current_by_key.get(item["fieldKey"])
            if existing is None or (existing.get("fieldValue") != item["fieldValue"]):
                entry = dict(item)
                if existing is not None:
                    entry["oldValue"] = existing.get("fieldValue")
                changes.append(entry)
        return changes

    def _propose(self, run_id: str, customer_id: int, employee_id: int, diff: list[dict], source: str) -> tuple[dict, bool]:
        span = self._trace.start_span(run_id, "propose")
        try:
            proposal, merged = self._proposals.create_or_merge(
                customer_id, employee_id, "update_profile_field", diff, run_id=run_id, source=source
            )
            self._trace.finish_span(span, "ok", {"proposal_id": proposal["id"], "merged": merged, "fields": len(diff)})
            return proposal, merged
        except Exception as exc:  # noqa: BLE001
            self._trace.finish_span(span, "error", {"error": str(exc)})
            raise

    def _finish(self, run_id: str, status: str, outcome: str, error: str | None = None) -> None:
        self._trace.finish_run(
            run_id,
            status,
            intent="profile_refresh",
            routing_reason=outcome,
            confidence=1.0,
            decision_path="EVENT" if error is None else "ERROR",
        )
