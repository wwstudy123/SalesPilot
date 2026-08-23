"""M4 画像 HITL 单测：ProposalStore 合并/过期、抽取器启发式与解析、子图 diff、确认流。"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from sale_agent.hitl.flow import confirm_proposal, reject_proposal
from sale_agent.hitl.store import ProposalStore
from sale_agent.profile.extractor import ProfileExtractor
from sale_agent.profile.subgraph import ProfileSubgraph


def _store(tmp_path) -> ProposalStore:
    return ProposalStore(str(tmp_path / "proposals.db"))


def _field(key: str, value: str, evidence: str = "follow_up#1") -> dict:
    return {"fieldKey": key, "fieldValue": value, "evidence": evidence}


# ---------- ProposalStore ----------


def test_create_new_pending_with_ttl(tmp_path):
    store = _store(tmp_path)

    proposal, merged = store.create_or_merge(1, 1, "update_profile_field", [_field("demand", "想买净水器")])

    assert merged is False
    assert proposal["status"] == "pending"
    assert proposal["created_at"] < proposal["expires_at"]
    assert proposal["fields"][0]["fieldKey"] == "demand"


def test_merge_overwrites_same_field_and_keeps_others(tmp_path):
    store = _store(tmp_path)
    first, _ = store.create_or_merge(1, 1, "update_profile_field", [_field("demand", "旧值"), _field("preference", "爱喝茶")])

    second, merged = store.create_or_merge(1, 1, "update_profile_field", [_field("demand", "新值")])

    assert merged is True
    assert second["id"] == first["id"]
    by_key = {item["fieldKey"]: item for item in second["fields"]}
    assert by_key["demand"]["fieldValue"] == "新值"
    assert by_key["preference"]["fieldValue"] == "爱喝茶"


def test_expired_proposal_not_merged(tmp_path):
    store = _store(tmp_path)
    proposal, _ = store.create_or_merge(1, 1, "update_profile_field", [_field("demand", "v1")])
    # 直接把过期时间改到过去，模拟 30min TTL 到期（惰性过期）
    store._conn.execute("UPDATE proposal SET expires_at = '2000-01-01T00:00:00.000+00:00' WHERE id = ?", (proposal["id"],))
    store._conn.commit()

    assert store.get(proposal["id"])["status"] == "expired"
    fresh, merged = store.create_or_merge(1, 1, "update_profile_field", [_field("demand", "v2")])
    assert merged is False
    assert fresh["id"] != proposal["id"]


def test_resolve_and_list_filter(tmp_path):
    store = _store(tmp_path)
    proposal, _ = store.create_or_merge(1, 1, "update_profile_field", [_field("demand", "v")])

    resolved = store.resolve(proposal["id"], "confirmed")
    assert resolved["status"] == "confirmed"
    assert resolved["resolved_at"]

    assert store.list(customer_id=1, status="pending") == []
    assert len(store.list(customer_id=1, status="confirmed")) == 1
    assert store.list(customer_id=2) == []


# ---------- 抽取器（echo 启发式 + _parse） ----------


class _EchoGateway:
    class settings:
        echo_mode = True


def test_heuristic_extracts_fields_with_evidence():
    extractor = ProfileExtractor(_EchoGateway())
    follow_ups = [
        {"id": 10, "channel": "visit", "content": "客户喜欢喝绿茶"},
        {"id": 11, "channel": "phone", "content": "想买一台净水器，预算8000"},
        {"id": 12, "channel": "wechat", "content": "觉得太贵了，担心滤芯成本"},
    ]
    purchases = [{"id": 1, "productName": "保温杯", "amount": 120, "quantity": 1}]

    fields = extractor.extract(follow_ups, purchases)
    by_key = {item["fieldKey"]: item for item in fields}

    assert by_key["preference"]["evidence"] == "follow_up#10"
    assert by_key["demand"]["evidence"] == "follow_up#11"
    assert by_key["sensitive_point"]["evidence"] == "follow_up#12"
    assert by_key["value_tier"]["fieldValue"] == "low"


def test_heuristic_value_tier_thresholds():
    extractor = ProfileExtractor(_EchoGateway())

    def tier(total: float) -> str:
        fields = extractor.extract([], [{"id": 1, "amount": total, "quantity": 1}])
        return next(item["fieldValue"] for item in fields if item["fieldKey"] == "value_tier")

    assert tier(20000) == "high"
    assert tier(5000) == "medium"
    assert tier(4999) == "low"


def test_parse_valid_json_and_markdown_fence():
    payload = {"fields": [{"fieldKey": "demand", "fieldValue": "想买净水器", "evidence": "follow_up#3"}]}

    assert ProfileExtractor._parse(json.dumps(payload, ensure_ascii=False)) is not None
    assert ProfileExtractor._parse(f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```") is not None


def test_parse_rejects_invalid_content():
    assert ProfileExtractor._parse("不是 JSON") is None
    assert ProfileExtractor._parse('{"fields": "not-a-list"}') is None
    # fieldKey 白名单外 / 缺 evidence 的条目被过滤，全部无效则返回 None
    bad = {"fields": [{"fieldKey": "unknown_key", "fieldValue": "x", "evidence": "e"}]}
    assert ProfileExtractor._parse(json.dumps(bad)) is None


# ---------- 子图 diff ----------


def test_diff_only_changed_or_new_fields():
    extracted = [_field("demand", "新需求"), _field("preference", "爱喝茶")]
    current = [{"fieldKey": "preference", "fieldValue": "爱喝茶"}, {"fieldKey": "recent_focus", "fieldValue": "净水器"}]

    diff = ProfileSubgraph._diff("run", extracted, current)

    assert len(diff) == 1
    assert diff[0]["fieldKey"] == "demand"
    assert "oldValue" not in diff[0]


def test_diff_value_change_keeps_old_value():
    extracted = [_field("demand", "新需求")]
    current = [{"fieldKey": "demand", "fieldValue": "旧需求"}]

    diff = ProfileSubgraph._diff("run", extracted, current)

    assert diff[0]["oldValue"] == "旧需求"


# ---------- HITL 确认流 ----------


class _FakeMcp:
    """替代 McpClient：记录调用，可注入 write 异常。"""

    def __init__(self, write_error: Exception | None = None) -> None:
        self.calls: list[str] = []
        self.write_error = write_error
        self.last_token: str | None = None
        self.last_key: str | None = None

    def issue_approval(self, tool, customer_id, payload, idempotency_key, jwt):
        self.calls.append("issue_approval")
        return {"token": "approval-token-xyz"}

    def update_profile_fields(self, customer_id, fields, approval_token, idempotency_key, jwt):
        self.calls.append("update_profile_fields")
        self.last_token, self.last_key = approval_token, idempotency_key
        if self.write_error:
            raise self.write_error
        return [{"fieldKey": item["fieldKey"], "version": 1} for item in fields]


def test_confirm_flow_issues_approval_then_writes(tmp_path):
    store, mcp = _store(tmp_path), _FakeMcp()
    proposal, _ = store.create_or_merge(1, 1, "update_profile_field", [_field("demand", "想买净水器")])

    result = confirm_proposal(store, mcp, proposal["id"], "jwt")

    assert mcp.calls == ["issue_approval", "update_profile_fields"]
    assert mcp.last_token == "approval-token-xyz"
    assert mcp.last_key == f"proposal:{proposal['id']}"
    assert result["proposal"]["status"] == "confirmed"


def test_confirm_missing_or_resolved_proposal(tmp_path):
    store, mcp = _store(tmp_path), _FakeMcp()

    with pytest.raises(HTTPException) as not_found:
        confirm_proposal(store, mcp, "nope", "jwt")
    assert not_found.value.status_code == 404

    proposal, _ = store.create_or_merge(1, 1, "update_profile_field", [_field("demand", "v")])
    store.resolve(proposal["id"], "rejected")
    with pytest.raises(HTTPException) as conflict:
        confirm_proposal(store, mcp, proposal["id"], "jwt")
    assert conflict.value.status_code == 409


def test_confirm_propagates_mcp_error_status(tmp_path):
    from sale_agent.profile.mcp_client import McpError

    store = _store(tmp_path)
    mcp = _FakeMcp(write_error=McpError("E_APPROVAL_EXPIRED", 403, "凭证已过期"))
    proposal, _ = store.create_or_merge(1, 1, "update_profile_field", [_field("demand", "v")])

    with pytest.raises(HTTPException) as err:
        confirm_proposal(store, mcp, proposal["id"], "jwt")
    assert err.value.status_code == 403
    assert "E_APPROVAL_EXPIRED" in err.value.detail
    # write 失败时提案保持 pending，可重试
    assert store.get(proposal["id"])["status"] == "pending"


def test_reject_flow(tmp_path):
    store = _store(tmp_path)
    proposal, _ = store.create_or_merge(1, 1, "update_profile_field", [_field("demand", "v")])

    assert reject_proposal(store, proposal["id"])["proposal"]["status"] == "rejected"
    with pytest.raises(HTTPException) as conflict:
        reject_proposal(store, proposal["id"])
    assert conflict.value.status_code == 409
