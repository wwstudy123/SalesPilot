#!/usr/bin/env python3
"""SalesPilot 种子数据生成脚本（MVP 方案 §3 数据基线规格）。

产出：business-mock/src/main/resources/db/seed/seed.sql
规格：
- 员工 3：小张/小李（employee）+ 王店长（manager）
- 客户 20：新客 5 / 意向 7 / 老客 5 / 流失风险 3，两位员工各 10 人
- 跟进记录 ~300（人均 15），金标预埋：承诺类/异议/价格敏感/复购信号
- 消费记录 ~80，金额/品类分布合理
确定性：固定随机种子，重复执行产出一致。

用法：
    python3 scripts/generate_seed.py
    make seed          # 灌入 sale-mysql 容器
"""

from __future__ import annotations

import random
from pathlib import Path

random.seed(20260818)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "business-mock" / "src" / "main" / "resources" / "db" / "seed" / "seed.sql"

EMPLOYEES = [
    ("zhangsan", "{noop}pass123", "小张", "employee", "13800000001"),
    ("lisi", "{noop}pass123", "小李", "employee", "13800000002"),
    ("admin", "{noop}admin123", "王店长", "manager", "13800000000"),
]

# 客户生命周期分布：新客5 / 意向7 / 老客5 / 流失风险3 = 20
STAGES = ["new"] * 5 + ["prospective"] * 7 + ["existing"] * 5 + ["churn_risk"] * 3

SURNAMES = "王李张刘陈杨赵黄周吴徐孙马朱胡郭何高林罗"
GIVEN = "芳娜敏静丽强磊军洋勇艳杰娟涛明超秀兰霞平刚桂英华"
SOURCES = ["门店到店", "微信引流", "会员转介绍", "线上咨询", "活动引流"]

CHANNELS = ["chat", "phone", "visit", "wechat"]

# ---- 金标语料（评测金标来源，必须预埋）----
GOLD_COMMIT = [
    "好的，我下周三之前一定把尾款付了，你放心。",
    "行，我答应你这周六到店试穿，到时候见。",
    "没问题，我明天就把资料填好发给你。",
    "我保证这个月内把卡办了，就按你说的套餐。",
]
GOLD_OBJECTION = [
    "你们这个太贵了，别家同样的东西便宜好几百。",
    "我再考虑考虑吧，暂时不太需要。",
    "我不太相信效果，之前买过类似的没什么用。",
    "家里人不同意，我得先问问我老公。",
]
GOLD_PRICE_SENSITIVE = [
    "能不能再便宜点？超我预算了。",
    "最近有什么优惠活动或者优惠券吗？",
    "这个价格有点高，等打折的时候我再来。",
    "你们要是能送点赠品我就考虑一下。",
]
GOLD_REPURCHASE = [
    "上次买的那瓶用完了，效果不错，想再买一套。",
    "帮我留意一下新款，到货了第一时间通知我。",
    "之前那个很好用，这次想给我妈也带一份。",
    "老顾客了，这次有没有会员专属价？",
]
NORMAL_CHAT = [
    "今天过来逛了逛，看了看新品，没着急定。",
    "电话里简单聊了下需求，她说最近比较忙。",
    "到店体验了十五分钟，对材质比较满意。",
    "微信上问了下尺码和颜色，已经回复。",
    "回访确认了收货情况，使用体验还不错。",
    "介绍了本季的搭配方案，她表示有兴趣。",
    "提醒她会员积分月底到期，她表示会来看。",
    "聊了下使用场景，主要是日常通勤用。",
]

PRODUCTS = [
    ("保湿面霜", "美妆护肤", (180, 420)),
    ("精华液", "美妆护肤", (260, 580)),
    ("防晒霜", "美妆护肤", (90, 240)),
    ("香水", "美妆护肤", (350, 900)),
    ("连衣裙", "服饰", (199, 599)),
    ("羊绒围巾", "服饰", (159, 459)),
    ("运动鞋", "服饰", (299, 799)),
    ("保温杯", "生活家居", (79, 259)),
    ("香薰机", "生活家居", (129, 399)),
    ("坚果礼盒", "食品", (69, 199)),
]


def esc(value: str) -> str:
    return value.replace("'", "''")


def pick_content(stage: str) -> str:
    """按生命周期阶段分布抽取跟进内容，确保四类金标均匀预埋。"""
    roll = random.random()
    if stage == "churn_risk" and roll < 0.45:
        return random.choice(GOLD_OBJECTION)
    if stage == "prospective" and roll < 0.35:
        return random.choice(GOLD_PRICE_SENSITIVE)
    if stage == "existing" and roll < 0.35:
        return random.choice(GOLD_REPURCHASE)
    if roll < 0.10:
        return random.choice(GOLD_COMMIT)
    if roll < 0.20:
        return random.choice(GOLD_OBJECTION)
    if roll < 0.28:
        return random.choice(GOLD_PRICE_SENSITIVE)
    if roll < 0.36:
        return random.choice(GOLD_REPURCHASE)
    return random.choice(NORMAL_CHAT)


def main() -> None:
    lines: list[str] = [
        "-- SalesPilot 种子数据（generate_seed.py 自动生成，勿手改）",
        "-- 规格：MVP 方案 §3；员工3/客户20/跟进~300/消费~80，金标四类预埋",
        "SET NAMES utf8mb4;",
        "DELETE FROM purchase;",
        "DELETE FROM follow_up;",
        "DELETE FROM customer;",
        "DELETE FROM employee;",
        "ALTER TABLE employee AUTO_INCREMENT = 1;",
        "ALTER TABLE customer AUTO_INCREMENT = 1;",
        "ALTER TABLE follow_up AUTO_INCREMENT = 1;",
        "ALTER TABLE purchase AUTO_INCREMENT = 1;",
        "",
    ]

    # 员工（id 1..3）
    for username, pwd, name, role, phone in EMPLOYEES:
        lines.append(
            "INSERT INTO employee (username, password_hash, name, role, phone) "
            f"VALUES ('{username}', '{pwd}', '{esc(name)}', '{role}', '{phone}');"
        )
    lines.append("")

    # 客户（id 1..20），小张/小李各 10 人
    stages = STAGES[:]
    random.shuffle(stages)
    customers: list[tuple[int, int, str]] = []  # (id, owner_id, stage)
    for i, stage in enumerate(stages):
        owner_id = 1 if i < 10 else 2
        name = random.choice(SURNAMES) + random.choice(GIVEN) + random.choice(GIVEN)
        gender = random.choice(["F", "F", "M"])
        phone = f"139{random.randint(10000000, 99999999)}"
        source = random.choice(SOURCES)
        customers.append((i + 1, owner_id, stage))
        lines.append(
            "INSERT INTO customer (owner_id, name, phone, gender, lifecycle_stage, source, remark) "
            f"VALUES ({owner_id}, '{esc(name)}', '{phone}', '{gender}', '{stage}', '{esc(source)}', "
            f"'{esc(random.choice(['', '注重性价比', '偏好新品', '老客户维护', '需重点跟进']))}');"
        )
    lines.append("")

    # 跟进记录：每员工 150 条（人均 15 × 10 客户），共 300
    follow_count = 0
    for cust_id, owner_id, stage in customers:
        for _ in range(15):
            channel = random.choice(CHANNELS)
            content = esc(pick_content(stage))
            day = random.randint(1, 60)
            lines.append(
                "INSERT INTO follow_up (customer_id, employee_id, channel, content, created_at) "
                f"VALUES ({cust_id}, {owner_id}, '{channel}', '{content}', "
                f"DATE_SUB(NOW(3), INTERVAL {day} DAY));"
            )
            follow_count += 1
    lines.append("")

    # 消费记录 ~80：老客多、新客少，流失风险客户曾有消费
    purchase_count = 0
    for cust_id, _owner, stage in customers:
        if stage == "existing":
            n = random.randint(8, 12)
        elif stage == "churn_risk":
            n = random.randint(4, 6)
        elif stage == "prospective":
            n = random.randint(1, 3)
        else:
            n = random.randint(0, 2)
        for _ in range(n):
            product, category, (lo, hi) = random.choice(PRODUCTS)
            amount = round(random.uniform(lo, hi), 2)
            quantity = random.choices([1, 2, 3], weights=[7, 2, 1])[0]
            day = random.randint(1, 90)
            lines.append(
                "INSERT INTO purchase (customer_id, product_name, category, amount, quantity, purchased_at) "
                f"VALUES ({cust_id}, '{esc(product)}', '{esc(category)}', {amount}, {quantity}, "
                f"DATE_SUB(NOW(3), INTERVAL {day} DAY));"
            )
            purchase_count += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"seed.sql written: {OUT}")
    print(f"employees=3 customers=20 follow_ups={follow_count} purchases={purchase_count}")


if __name__ == "__main__":
    main()
