"""Rule 分类器：菜单直达（routing_type=menu 免分类）+ 关键词硬规则（锁定可短路）。"""

from __future__ import annotations

from dataclasses import dataclass

# 硬规则：命中即锁定（decision_path=RULE_LOCKED），关键词唯一指向单一意图
# 顺序即优先级：batch_task 先于 tag_review（“批量打标签”归批量任务）
_LOCK_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("todo_query", ("待办",)),
    ("schedule_suggest", ("日程", "巡检", "拜访计划", "今天优先", "先跟进谁")),
    ("batch_task", ("批量",)),
    ("tag_review", ("标签",)),
    ("similar_customer", ("相似客户", "类似客户", "相似的案例", "成功案例")),
    ("talk_script", ("话术",)),
    ("objection_help", ("异议",)),
    ("human_help", ("转人工", "转店长", "找店长", "人工协助", "人工客服")),
]

# 软规则：不锁定，仅作为融合阶段的 rule_prior 提示
_SOFT_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("profile_query", ("画像",)),
    ("customer_search", ("找客户", "搜客户", "搜索客户", "哪些客户")),
    ("knowledge_qa", ("政策", "制度", "流程", "规定", "有效期", "保质期")),
    ("chitchat", ("你好", "早上好", "下午好", "晚上好", "在吗", "谢谢")),
]


@dataclass
class RuleHit:
    intent: str
    locked: bool
    matched: str


class RuleClassifier:
    def classify(self, query: str) -> RuleHit | None:
        text = query.strip()
        for intent, keywords in _LOCK_RULES:
            for keyword in keywords:
                if keyword in text:
                    return RuleHit(intent=intent, locked=True, matched=keyword)
        for intent, keywords in _SOFT_RULES:
            for keyword in keywords:
                if keyword in text:
                    return RuleHit(intent=intent, locked=False, matched=keyword)
        return None
