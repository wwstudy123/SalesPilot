"""M3 自测集：13 意图 paraphrase 用例（与种子样例不同句），目标 L1 ≥85%。"""

SELF_TEST_SET: list[tuple[str, str]] = [
    # profile_query（软规则"画像" + emb）
    ("profile_query", "张姐的画像给我看下"),
    ("profile_query", "分析下这位客户的购买偏好画像"),
    ("profile_query", "李先生的客户画像更新了没"),
    # similar_customer
    ("similar_customer", "有没有跟这位客户差不多的成功案例"),
    ("similar_customer", "相似客户是怎么把单子签下来的"),
    ("similar_customer", "找个情况相近的客户案例学习下"),
    # talk_script（锁：话术）
    ("talk_script", "给我一段促成下单的话术"),
    ("talk_script", "约客户周末到店的话术怎么写"),
    ("talk_script", "首次电话沟通的话术帮我想想"),
    # objection_help（锁：异议）
    ("objection_help", "客户提出价格异议怎么接"),
    ("objection_help", "客户对质量有意见算异议吗怎么处理"),
    ("objection_help", "遇到竞品对比的异议怎么化解"),
    # knowledge_qa（软规则：政策/流程/规定/有效期/保质期）
    ("knowledge_qa", "退换货政策具体怎么规定的"),
    ("knowledge_qa", "会员积分有效期到什么时候"),
    ("knowledge_qa", "售后维修流程是怎样的"),
    # tag_review（锁：标签）
    ("tag_review", "这个客户的标签需要重新打一下"),
    ("tag_review", "帮我看看她有哪些标签"),
    ("tag_review", "标签里的意向等级改成A"),
    # schedule_suggest（锁：日程/巡检/拜访计划/今天优先/先跟进谁）
    ("schedule_suggest", "今天的拜访计划怎么排"),
    ("schedule_suggest", "巡检路线帮我规划下"),
    ("schedule_suggest", "今天优先联系哪位客户"),
    # todo_query（锁：待办）
    ("todo_query", "我的待办还剩几个"),
    ("todo_query", "查下待办有没有快逾期的"),
    ("todo_query", "今天有什么待办要处理"),
    # customer_search（软规则：找客户/搜客户/哪些客户）
    ("customer_search", "帮我找客户里住城南的"),
    ("customer_search", "搜客户中上个月买过净水器的"),
    ("customer_search", "哪些客户最近没来店里了"),
    # batch_task（锁：批量）
    ("batch_task", "批量给新客打上体验标签"),
    ("batch_task", "这批客户批量刷新下画像"),
    ("batch_task", "批量整理一下客户等级"),
    # chitchat（软规则：你好/早上好/在吗/谢谢）
    ("chitchat", "你好呀在忙吗"),
    ("chitchat", "早上好呀"),
    ("chitchat", "太谢谢你了"),
    # off_topic
    ("off_topic", "帮我推荐一部电影"),
    ("off_topic", "明天股票行情会怎样"),
    ("off_topic", "把这句话翻译成英文"),
    # human_help（锁：转人工/转店长/找店长/人工协助/人工客服）
    ("human_help", "转人工帮我处理下"),
    ("human_help", "帮我转店长接一下"),
    ("human_help", "需要人工协助跟进这个大单"),
]
