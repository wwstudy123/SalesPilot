from sale_agent.ai.trace import TraceStore
from sale_agent.hitl.store import ProposalStore
from sale_agent.ops.subgraph import OpsSubgraph


class FakeMcp:
    def get_profile(self, customer_id, jwt):
        return [
            {"fieldKey": "lifecycle_stage", "fieldValue": "prospective"},
            {"fieldKey": "value_tier", "fieldValue": "high"},
            {"fieldKey": "sensitive_point", "fieldValue": "预算有限"},
        ]

    def list_follow_ups(self, customer_id, jwt):
        return [{"content": "客户觉得太贵，想等优惠"}]


def test_ops_creates_evidence_backed_tag_proposal(tmp_path):
    ops = OpsSubgraph(
        FakeMcp(),
        ProposalStore(str(tmp_path / "proposals.db")),
        TraceStore(str(tmp_path / "trace.db")),
    )
    result = ops.review(1, 1, "jwt")

    assert result["outcome"] == "proposal"
    tags = result["proposal"]["fields"]
    assert {tag["tagKey"] for tag in tags} >= {"lifecycle_prospective", "value_high", "preference_price_sensitive"}
    assert all(tag["evidence"] for tag in tags)


def test_ops_merges_follow_up_tag_review(tmp_path):
    proposals = ProposalStore(str(tmp_path / "proposals.db"))
    ops = OpsSubgraph(FakeMcp(), proposals, TraceStore(str(tmp_path / "trace.db")))

    first = ops.review(1, 1, "jwt")
    second = ops.review(1, 1, "jwt", source="profile_confirmed")

    assert second["merged"] is True
    assert second["proposal"]["id"] == first["proposal"]["id"]
