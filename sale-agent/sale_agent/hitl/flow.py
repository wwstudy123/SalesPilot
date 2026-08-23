"""HITL 确认流（架构 §7.3）：员工确认 → 签发 approval_token → 携凭证执行 write → 收尾。"""

from __future__ import annotations

from fastapi import HTTPException

from sale_agent.hitl.store import ProposalStore
from sale_agent.profile.mcp_client import McpClient, McpError


def confirm_proposal(proposals: ProposalStore, mcp: McpClient, proposal_id: str, jwt: str) -> dict:
    proposal = proposals.get(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"proposal not found: {proposal_id}")
    if proposal["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"提案已处理（{proposal['status']}），不可重复确认")

    idempotency_key = f"proposal:{proposal_id}"
    approval = mcp.issue_approval(proposal["tool"], proposal["customer_id"], {"proposal_id": proposal_id}, idempotency_key, jwt)
    fields = [{"fieldKey": item["fieldKey"], "fieldValue": item["fieldValue"], "evidence": item["evidence"]} for item in proposal["fields"]]
    try:
        updated = mcp.update_profile_fields(proposal["customer_id"], fields, approval["token"], idempotency_key, jwt)
    except McpError as exc:
        raise HTTPException(status_code=exc.http_status, detail=f"{exc.code}: {exc.message}") from exc
    resolved = proposals.resolve(proposal_id, "confirmed")
    return {"proposal": resolved, "profile_fields": updated}


def reject_proposal(proposals: ProposalStore, proposal_id: str) -> dict:
    proposal = proposals.get(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"proposal not found: {proposal_id}")
    if proposal["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"提案已处理（{proposal['status']}），不可放弃")
    resolved = proposals.resolve(proposal_id, "rejected")
    return {"proposal": resolved}
