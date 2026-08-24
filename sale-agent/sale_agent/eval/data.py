"""M9 种子金标：评测运行时仅在内存使用，绝不写业务库。"""

PROFILE_CASES = [
    {"id": "profile-001", "follow_up": "客户预算四千，家里四口，关注滤芯成本。", "expected": {"demand": "四口之家", "value_tier": "medium"}},
    {"id": "profile-002", "follow_up": "客户说价格太贵，先等等活动。", "expected": {"sensitive_point": "价格敏感"}},
]

TAG_CASES = [
    {"id": "tag-001", "profile": {"lifecycle_stage": "prospective", "value_tier": "high"}, "follow_up": "", "expected": ["lifecycle_prospective", "value_high"]},
    {"id": "tag-002", "profile": {"lifecycle_stage": "new", "sensitive_point": "预算有限"}, "follow_up": "觉得太贵想等优惠", "expected": ["lifecycle_new", "preference_price_sensitive"]},
]

TALK_CASES = [
    {"id": "talk-001", "query": "客户嫌太贵怎么回应", "answer": "先认同预算顾虑，再说明长期使用成本。", "citations": ["异议-太贵了"]},
    {"id": "talk-002", "query": "给老客户写回访话术", "answer": "先询问近况和使用体验，再提供维护支持。", "citations": ["回访-使用后关怀"]},
]
