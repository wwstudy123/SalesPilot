"""意图 Schema：13 意图定义（需求 §9.1）+ 样例库，SQLite 存储、动态可增补。

存储说明：MVP 阶段 Schema 存 SQLite（output/ai/intents.db），表结构与 MySQL 等价，
生产切换仅需替换存储后端；样例库动态渲染，新增意图/样例零发版。
"""

from __future__ import annotations

import os
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS intent_def (
    name TEXT PRIMARY KEY,
    intent_group TEXT NOT NULL,
    primary_agent TEXT NOT NULL,
    description TEXT NOT NULL,
    threshold REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS intent_example (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intent TEXT NOT NULL REFERENCES intent_def (name),
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_intent_example_intent ON intent_example (intent);
"""


@dataclass
class IntentDef:
    name: str
    group: str
    primary_agent: str
    description: str
    threshold: float


# 需求 §9.1：员工指令意图 13 个（含 knowledge_qa）
DEFAULT_INTENTS: list[IntentDef] = [
    IntentDef("profile_query", "insight", "orchestrator→profile", "查看/分析客户画像", 0.70),
    IntentDef("similar_customer", "insight", "coach", "相似客户成功案例", 0.72),
    IntentDef("talk_script", "coaching", "coach", "生成话术/沟通建议", 0.70),
    IntentDef("objection_help", "coaching", "coach", "异议处理求助", 0.70),
    IntentDef("knowledge_qa", "coaching", "coach", "业务知识问答（政策/流程/产品知识）", 0.70),
    IntentDef("tag_review", "ops", "ops", "标签查看/重打", 0.70),
    IntentDef("schedule_suggest", "ops", "ops", "日程建议/巡检跟进", 0.70),
    IntentDef("todo_query", "ops", "ops", "查我的待办", 0.70),
    IntentDef("customer_search", "search", "orchestrator", "找客户", 0.72),
    IntentDef("batch_task", "batch", "orchestrator", "批量画像/标签任务", 0.72),
    IntentDef("chitchat", "fallback", "orchestrator", "闲聊寒暄", 0.60),
    IntentDef("off_topic", "fallback", "orchestrator", "域外问题", 0.60),
    IntentDef("human_help", "fallback", "orchestrator", "求助/转人工", 0.60),
]

# 每意图 5 条种子样例（MVP 拆解 §M3：样例库先手工维护 5 条/意图）
DEFAULT_EXAMPLES: dict[str, list[str]] = {
    "profile_query": [
        "看看张姐的画像",
        "帮我分析一下这个客户的消费偏好",
        "王先生的画像最近有更新吗",
        "给我讲讲李姐这个客户的情况",
        "这位客户的画像标签都有哪些",
    ],
    "similar_customer": [
        "有没有和张姐情况类似的成功客户",
        "之前类似的客户最后都怎么成交的",
        "找个和这位客户相似的案例参考下",
        "预算相近的客户别人是怎么跟的",
        "相似客户的成交经验给我看看",
    ],
    "talk_script": [
        "给我一段邀约到店的话术",
        "怎么开口跟客户聊新品比较自然",
        "帮我写一段回访老客户的沟通话术",
        "客户说要考虑一下，我该怎么接话",
        "生成一段促单的话术",
    ],
    "objection_help": [
        "客户嫌贵怎么回应",
        "客户说再看看别家，怎么处理这个异议",
        "客户觉得没必要买，我该怎么说服",
        "客户对效果有怀疑，怎么打消顾虑",
        "客户说回去和家人商量，怎么应对",
    ],
    "knowledge_qa": [
        "退换货政策是怎么规定的",
        "会员积分的有效期是多久",
        "这款产品的保质期是几年",
        "门店的售后服务流程是什么",
        "新客首单折扣的公司政策是多少",
    ],
    "tag_review": [
        "看看这个客户身上有哪些标签",
        "帮我把她的标签改成高净值",
        "这个客户的标签打对了吗",
        "重新梳理一下王先生的标签",
        "哪些客户被打了流失风险标签",
    ],
    "schedule_suggest": [
        "帮我安排一下明天的拜访计划",
        "今天应该优先跟进谁",
        "给我排个本周的巡检路线",
        "哪些客户该安排回访了",
        "下周的跟进日程帮我建议一下",
    ],
    "todo_query": [
        "我还有哪些待办没处理",
        "看看我的待办清单",
        "今天有什么任务要完成",
        "查一下我名下的待办事项",
        "有没有逾期的待办",
    ],
    "customer_search": [
        "帮我找一下住在城东的客户",
        "搜索上个月消费超过五千的客户",
        "哪些客户三个月没来店了",
        "查找买了净水器还没复购的客户",
        "找一下对保健品感兴趣的新客",
    ],
    "batch_task": [
        "给这批新客批量打一下标签",
        "批量更新一下老客户的画像",
        "把这二十个客户的标签统一改成意向客户",
        "批量生成这批客户的画像摘要",
        "帮我批量补全这些客户的联系偏好",
    ],
    "chitchat": [
        "你好呀",
        "早上好",
        "在吗",
        "今天天气不错",
        "谢谢你啦",
    ],
    "off_topic": [
        "帮我写一首诗",
        "明天的股票会涨吗",
        "推荐一部电影给我",
        "帮我翻译一段英文",
        "今晚吃什么好呢",
    ],
    "human_help": [
        "帮我转一下店长",
        "这个问题我搞不定，找个人帮帮我",
        "转人工客服",
        "能找个资深同事指导我吗",
        "我需要人工协助处理这个客户",
    ],
}


class IntentCatalogStore:
    """意图 Schema 与样例库存取（SQLite，线程安全）。"""

    def __init__(self, db_path: str | None = None) -> None:
        path = Path(db_path or os.environ.get("SALE_INTENT_DB", "") or Path("output") / "ai" / "intents.db")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def list_intents(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT d.*, (SELECT COUNT(*) FROM intent_example e WHERE e.intent = d.name) AS example_count"
                " FROM intent_def d ORDER BY d.name"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_intent(self, name: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM intent_def WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None

    def upsert_intent(self, definition: IntentDef) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO intent_def (name, intent_group, primary_agent, description, threshold)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(name) DO UPDATE SET intent_group = excluded.intent_group,"
                " primary_agent = excluded.primary_agent, description = excluded.description,"
                " threshold = excluded.threshold",
                (definition.name, definition.group, definition.primary_agent, definition.description, definition.threshold),
            )
            self._conn.commit()

    def add_example(self, intent: str, text: str) -> int:
        with self._lock:
            cursor = self._conn.execute("INSERT INTO intent_example (intent, text) VALUES (?, ?)", (intent, text.strip()))
            self._conn.commit()
            return int(cursor.lastrowid or 0)

    def list_examples(self, intent: str | None = None) -> list[dict]:
        if intent:
            sql = "SELECT * FROM intent_example WHERE intent = ? ORDER BY id"
            args: tuple = (intent,)
        else:
            sql = "SELECT * FROM intent_example ORDER BY intent, id"
            args = ()
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def seed_default_catalog(store: IntentCatalogStore) -> None:
    """幂等灌入 13 意图定义与 65 条样例。"""
    existing = {row["name"] for row in store.list_intents()}
    for definition in DEFAULT_INTENTS:
        store.upsert_intent(definition)
    seeded = {row["intent"] for row in store.list_examples()} if existing else set()
    for intent, texts in DEFAULT_EXAMPLES.items():
        if intent in seeded:
            continue
        for text in texts:
            store.add_example(intent, text)
