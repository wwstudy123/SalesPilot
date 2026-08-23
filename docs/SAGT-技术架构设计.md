# SAGT 零售销售智能体系统 技术架构设计

> 版本：v1.2 ｜ 依据《SAGT 需求文档 v1.2》
> 范围：系统拓扑、模块内部架构、跨模块契约、数据架构、关键流程时序、可观测与评测、安全、部署、目录结构。
> 约束继承：业务事实唯一写入口 = business-mock（Java）；AI 写操作一律经 MCP + HITL；Mock 数据，无真实外部系统。
>
> v1.1 变更：mem_user 挪 ADV（Milvus 3 collection）、删 JWT 黑名单、Rerank 默认 LLM listwise；新增客户移交规则、跨客户注入防护、员工级配额、同字段提案合并；功能授权简化为角色级。
> v1.2 变更：意图 13 个（+knowledge_qa）；RAG chunk 加 domain 分域过滤；新增在线反馈环（P2，monitor_penalty）设计；评测目标基线同步（500 条/四维 Judge/工程指标）。

---

## 1. 系统总览

### 1.1 部署拓扑

```
                    ┌─────────────────────────────────────────┐
                    │            nginx (80)                    │
                    │  / → sagt-admin   /sidebar → sagt-sidebar │
                    │  /api → business-mock   /api/ai → sagt-agent │
                    └──────┬───────────────┬──────────────────┘
                           │REST           │SSE
        ┌──────────────────▼───┐   ┌───────▼─────────────────────┐
        │ business-mock (8080) │   │ sagt-agent (8000)            │
        │ Java21 + Spring Boot │◄──┤ FastAPI + LangGraph          │
        │ Mock CRM / 认证 / 事件 │HTTP│ 意图分类/4Agent/RAG/Memory    │
        └───┬────┬─────┬───────┘   │ Monitor / Eval / 事件消费      │
            │    │     │           └───┬────────┬────────┬────────┘
        ┌───▼─┐┌─▼───┐  │     MCP(HTTP)│    ┌───▼────┐┌──▼───────┐
        │MySQL││Redis │  │   ┌─────────▼──┐ │ Milvus ││ LLM 外部   │
        │  8  ││  7   │  │   │ mcp-server │ │ (2.4)  ││ API(网关化) │
        └─────┘└─────┘  │   │   (9010)   │ └────────┘└──────────┘
                        │   └────────────┘
              Milvus 依赖：etcd + minio（profile full）
```

### 1.2 服务清单与职责边界

| 服务 | 技术 | 职责 | 不做什么 |
|---|---|---|---|
| sagt-admin / sagt-sidebar | React 18 + Vite + TS（同仓库双入口） | 管理端 / 员工端 UI，SSE 消费 | 不直连数据库，不含业务逻辑 |
| business-mock | Java 21 + Spring Boot 3 + Flyway | Mock CRM 全域：员工/客户/跟进/消费/客服/订单/标签/日程；认证签发；业务事件发布 | 不感知 AI，不调 LLM |
| sagt-agent | Python 3.11 + FastAPI + LangGraph | 全部 AI 能力：意图、编排、RAG、记忆、技能、Monitor、Eval、事件消费 | 不直写业务表 |
| mcp-server | Python（FastMCP / HTTP 传输） | 统一工具层：权限闸门、熔断、幂等、缓存、审计 | 不含业务规则，只做封装与治理 |
| sagt_client | OpenAPI 契约 + Python SDK 包 | 对外标准化接口（数据读写/记忆维护/会话记录同步） | 演示期不独立部署 |
| 中间件 | MySQL 8 / Redis 7 / Milvus 2.4 | 见 §6 | — |

**调用纪律**：
- 前端 → business-mock（业务 CRUD）、前端 → sagt-agent（AI 交互，SSE）；
- sagt-agent → mcp-server（唯一业务操作通道）→ business-mock REST；
- sagt-agent → business-mock 仅两类直连：认证校验（JWT 公钥/内网接口）与**事件流消费**（见 §3.3），不做业务写；
- mcp-server 不直连数据库，一切经 business-mock。

### 1.3 技术选型总表

| 层 | 选型 | 版本基线 | 备注 |
|---|---|---|---|
| 前端 | React + TypeScript + Vite + Zustand + TanStack Query | React 18 / Vite 5 | SSE 用原生 EventSource 封装；Markdown 渲染带引用角标 |
| 业务后端 | Java 21 + Spring Boot 3.3 + Spring Data JPA + Flyway | JDK 21 | 虚拟线程处理事件扇出 |
| AI 后端 | Python 3.11 + FastAPI + LangGraph + Pydantic v2 | LangGraph ≥0.2 | uvicorn，SSE 用 sse-starlette |
| 工具协议 | MCP（HTTP+SSE 传输） | MCP SDK py | mcp-server 独立进程 |
| 存储 | MySQL 8.0 / Redis 7 / Milvus 2.4 standalone | — | Milvus 用于话术/产品向量 + 画像向量 |
| LLM | 统一 LLM Gateway（sagt_agent 内聚模块） | OpenAI 兼容协议 | chat / embedding / rerank 三端点 |
| 部署 | Docker Compose（full / lite 双 profile） | — | §11 |

---

## 2. sagt_agent 内部架构（核心）

### 2.1 分层结构

```
┌────────────────────────────────────────────────────┐
│ api 层：/api/ai/chat(SSE) /proposals /runs /eval … │
├────────────────────────────────────────────────────┤
│ orchestration 层（LangGraph）                       │
│   supervisor(路由) → profile|coach|ops 子图         │
│   → aggregate(聚合/自检) → interrupt(HITL) → 输出    │
├──────────┬──────────┬──────────┬───────────────────┤
│ intent   │ rag      │ memory   │ skills            │
│ 三路分类   │ 检索管线   │ 双层记忆   │ 注册/装配          │
├──────────┴──────────┴──────────┴───────────────────┤
│ mcp_client │ llm_gateway │ monitor(trace) │ eval   │
└────────────────────────────────────────────────────┘
```

### 2.2 LangGraph 运行时（Agent 编排骨架）

- **主图**：`route 节点`（产出 RoutingDecision：primary/secondary/reason/confidence）→ 按意图分派至 **profile / coach / ops 三个子图**，或由 supervisor 直答（chitchat/off_topic/简单查询）；
- **子图内循环**：`llm ⇄ tool_call`（ReAct 式，受预算约束：LLM ≤4 轮、工具 ≤6 次）；
- **组合任务**（如"拜访准备"）：supervisor 生成 DAG 计划，节点间以 **Run Blackboard**（Redis `run:{run_id}:blackboard`）传递已确认事实，冲突以 MCP 最新查询为准；
- **HITL**：write 工具调用触发 LangGraph `interrupt`，state 经 **checkpoint 持久化**（存 Redis/PG，演示用 Redis）；确认/放弃/重新生成分别走 resume 分支；
- **fallback 链**：工具重试 → 结构化错误给 Agent → 备用模型 → 降级话术；同 Agent 5 分钟 3 连败熔断，期间该意图直出降级话术；
- **handoff**：子图内检测到跨域意图 → 发 handoff 事件回 supervisor 改派，上下文摘要随行。

### 2.3 意图分类子系统（三路）

```
query → Rule（硬规则锁定可短路）
      ├─ 锁定 → 直出（decision_path=RULE_LOCKED）
      └─ 未锁定 → Embedding ∥ LLM 并行
            → 融合 final = 0.6×llm + 0.3×emb + 0.1×rule_prior（一致 +0.05）
            → FUSED / CLARIFY / EMB_FALLBACK(降级) / UNKNOWN(入评测池)
```

- 员工指令意图 13 个（含 knowledge_qa）+ 场景菜单直达（routing_type=menu，免分类）；
- 跟进信号四分类（promise/objection_open/interest/churn_risk）是 Ops 子图内部任务，不走路由；
- 意图 Schema 存 MySQL，prompt 与样例库动态渲染，新增意图零发版。

### 2.4 RAG 管线（playbook_kb / product_kb）

Query Rewrite（注入客户上下文槽位 + 按意图注入 domain 过滤）→ dense(HNSW)+sparse(BM25) 各 top20 → RRF → Rerank（默认 LLM listwise；不部署独立 reranker 模型，降级为 RRF 直出）→ 阈值过滤（≥0.60 直用 / 0.35~0.60 限定语 / <0.25 弃）→ ≤5 chunks、≤1200 token → 压缩保引用 → 分区注入（知识区/客户事实区分离）。chunk 元数据带 `domain` 字段（product/sales/technical/policy），保持 2 集合纪律不拆集合。
纪律：客户事实一律来自 MCP/画像，RAG 只出话术与方法论；无命中标注"通用建议"。

### 2.5 Memory 子系统

| 层 | 实现 | 说明 |
|---|---|---|
| 会话短期 | Redis Hash `chat:ctx:{conversation_id}`，TTL 24h | 最近 N 轮 + 客户上下文槽位 |
| Run Blackboard | Redis `run:{run_id}:bb` | 编排期共享事实，带来源 |
| 客户长期（结构化） | MySQL customer_profile 字段级 | 经提案-采纳写入，字段级版本 |
| 客户长期（向量） | Milvus mem_customer | 画像 embedding，支撑相似客户 |
| 员工偏好【ADV】 | Milvus mem_user | 话术风格偏好，影响 Coach 生成；MVP 不做，记忆聚焦客户侧 |

Extract：新跟进记录落库 → 事件触发 Profile 子图增量抽取 → diff 产出字段更新提案。

### 2.6 LLM Gateway（内聚模块，接口按独立服务设计）

- 三端点：`chat`（流式）、`embedding`、`rerank`；
- 模型路由：意图/改写/信号分类 → 轻快模型；话术生成/画像抽取 → 强模型；judge → 独立模型；
- 治理：Provider 适配（OpenAI 兼容）、重试与备用模型切换、超时预算、token/成本记账（落 agent_run.cost_micro）、内容自检钩子（话术与画像冲突检测）。

### 2.7 Monitor 与 Eval（数据面）

- 每次请求生成 Run → Span 树（router/agent/llm_call/tool_call/rag_retrieval/memory_op/skill_attach/proposal/interrupt）；异步批量写 MySQL，不阻塞主链路；
- Eval Runner 以 eval_mode 复用同一执行路径（禁写业务库/记忆），Judge 与执行模型分离；员工行为信号（采纳/修正/拒绝）经 business-mock 事件回流评测样本池。

---

## 3. business-mock 内部架构

### 3.1 域划分（Spring Boot 模块内分包）

`auth / employee / customer / followup / purchase / service / order(mock) / tag / schedule / suggestion(行为记录) / report(聚合)`

- 每域标准 REST + JPA 实体 + 领域服务；Flyway 管理迁移与种子数据；
- 认证：JWT 签发（HS256 共享密钥，三端校验），角色 employee/manager；
- 权限：客户归属校验统一切面（employee 仅自己名下客户）。

### 3.2 关键业务规则（Java 侧硬规则，不依赖 AI）

| 规则 | 实现 |
|---|---|
| 标签/画像/日程的写操作必须携带 approval_token | 审批凭证表 + 校验切面；无凭证 403 |
| 幂等 | idempotency_key 唯一索引，重放返回首结果 |
| 采纳率/修正率统计 | suggestion_action 表聚合（非 AI 计算） |
| 日程去重 | 唯一键（customer_id, signal_type, source_record_id） |
| 客户移交 | 画像跟客户走（组织资产）；移交接口记审计事件并清除前员工权限缓存 |

### 3.3 事件机制（业务 → AI 的触发通道）

- 模式：**本地事件表（outbox）+ Redis Stream 投递**，保证"记录落库"与"事件发布"原子一致；
- 事件：`follow_up.created`（触发 Profile 增量 + 信号识别）、`profile.updated`（联动标签复核）、`suggestion.actioned`（采纳/修正/拒绝，回流评测池）、`customer.assigned`；
- sagt-agent 侧消费组幂等消费（event_id 去重键）；消费失败进死信队列可重放；
- 演示期轻量原则：不引入 Kafka，Redis Stream 足够；接口形状按可替换设计。

---

## 4. mcp-server（统一工具层）

- 10 个工具（read 7 + write 3：update_profile_field / save_tags / create_schedule）；
- 治理机制（继承冻结规范）：
  - **权限四闸门**：JWT 身份 → 角色 → 客户归属（actor vs owner）→ Agent 白名单；write 加审批凭证层；
  - **熔断**：每工具独立（5min 窗口 ≥5 失败或失败率 ≥50% → OPEN 30s → HALF-OPEN 探测）；
  - **幂等**：write 必带 idempotency_key（推荐 `{tool}:{customer_id}:{type}:{session_seq}`），Redis 24h 回放；
  - **缓存**：get_customer_profile 10min、list_* 60s、事件主动失效；画像向量与相似检索不缓存；
  - **审计**：每次调用写 tool_call_log（含 cache_hit/replayed/circuit_state）。
- 传输：MCP over HTTP+SSE；Schema 注册自动生成 LLM function-calling 描述。

---

## 5. 前端架构

- **Monorepo 双入口**：`frontend-web/` 下 admin 与 sidebar 两个 Vite 构建入口，共享组件库（建议卡、确认面板、瀑布图、引用角标）；
- **状态**：TanStack Query 管服务端状态；Zustand 管会话/选中客户上下文；
- **SSE 客户端**：EventSource 封装 + 断线重连 + run_id 补齐；事件类型映射到 UI（token→流式渲染、proposal→确认面板、tool_call→状态条）；
- **中断确认面板**：确认 / 放弃（可选原因）/ 重新生成（附要求，≤2 次）三操作对应后端 resume 分支；提案 30min 倒计时展示；
- **路由与权限**：前端菜单按功能授权裁剪，后端同步拦截（双保险）。

---

## 6. 数据架构

### 6.1 存储分工总账

| 存储 | 内容 |
|---|---|
| MySQL | 业务域：employee、customer、follow_up、purchase、service_record、order(mock)、tag、schedule_task、suggestion_action、approval；AI 域：conversation、message、agent_run、agent_span、tool_call_log、memory 元数据、knowledge_doc/chunk、skill、eval 系列、event_outbox |
| Redis | 会话短期记忆、Run Blackboard、提案 TTL 标记、幂等键、工具缓存、限流与员工配额计数、Redis Stream（事件）、LangGraph checkpoint |
| Milvus | playbook_kb、product_kb（dense+sparse）、mem_customer（画像向量）；mem_user（员工偏好向量）【ADV】 |

### 6.2 ER 概要（MySQL，约 24 表）

```
[组织域] employee ─┬─< customer(分配)  [auth: sys_user 语义并入 employee/manager]
[客户域] customer 1─< follow_up   1─< purchase   1─< service_record   1─< order(mock)
         customer 1─1 customer_profile(JSON 字段级+版本)  1─< customer_tag >─ tag_dict
[作业域] employee 1─< schedule_task(含 signal_type/source_record 去重键)
         customer 1─< suggestion(类型:话术/标签/画像/日程) 1─< suggestion_action(采纳/修改/拒绝)
[AI 域]  conversation ─< message 1─1 agent_run 1─< agent_span 1─1 tool_call_log
         knowledge_doc ─< knowledge_chunk(回指 Milvus)   skill ─< skill_version
         memory_item(员工偏好元数据,ADV)   eval_dataset/case/run/result   event_outbox
```

关键设计继承：BIGINT 主键、utf8mb4、DATETIME(3)、VARCHAR+CHECK 枚举、软删除 deleted_token（客户/员工/话术文档）、交易与行为流水不删走保留期（run/span/tool_call 30 天、suggestion_action 180 天）、画像删除合规硬删并同步清向量。

### 6.3 Milvus Collection

| Collection | 向量内容 | 回指 |
|---|---|---|
| playbook_kb / product_kb | chunk dense+sparse | knowledge_chunk.id |
| mem_customer | 画像 embedding（字段拼接文本向量化） | customer.id |
| mem_user【ADV】 | 员工偏好事实向量 | memory_item.id |

一致性规则：MySQL 元数据为主、Milvus 向量为辅；删除以 MySQL 驱动 + 补偿队列；检索结果回查 MySQL 有效性后才可引用。

---

## 7. 关键流程时序

### 7.1 话术生成（F2，核心链路）

```
员工"给王女士写回访话术" (sidebar)
→ POST /api/ai/chat (SSE)
→ 上下文装载(Redis) + 客户槽位 → 三路意图分类 → talk_script(coach)
→ Coach 子图：装配 intent-followup 技能
   → MCP get_customer_profile / list_follow_ups（事实区）
   → RAG playbook_kb（话术区，引用 [c*]）
   → LLM 生成 → Gateway 自检（与画像冲突检测）
→ SSE: token 流式 + rag_citation + proposal(建议卡)
→ 员工采纳/修改 → POST /api/ai/proposals/{id}/confirm
→ mcp-server save(幂等+凭证) → business-mock 落库 suggestion_action
→ Run/Span 收尾；行为事件回流评测池
```

### 7.2 画像增量更新（F1，事件驱动）

```
员工补录跟进记录 → business-mock 落库 + outbox → Redis Stream
→ sagt-agent 消费 follow_up.created（幂等）
→ Profile 子图：list_follow_ups/list_purchases → LLM 结构化抽取
→ 字段级 diff → update_profile_field 提案（interrupt）
→ sidebar 推送"画像更新建议"卡 → 员工采纳 → 执行落库 + mem_customer 向量刷新
→ 联动事件 profile.updated → Ops 标签复核
```

### 7.3 中断确认与恢复（HITL）

```
write 工具调用 → mcp-server 返回 E_APPROVAL_REQUIRED + proposal_id
→ LangGraph interrupt，state 存 checkpoint，Run=waiting_approval
→ SSE: proposal 事件 → 前端确认面板
  ├─ 确认：携 approval_token resume → mcp 执行 → 回执
  ├─ 放弃：resume(rejected) → 记录原因 → 结束
  └─ 重新生成：resume(regenerate, feedback) → 重跑该节点（≤2 次）
→ 30min 未处理：proposal 过期任务置 expired，前端灰显
```

### 7.4 信号识别与日程（F3）

```
follow_up.created / 每日巡检批任务
→ Ops 子图信号四分类（LLM，附来源记录 ID）
→ 结合画像价值分层定优先级/建议时间 → create_schedule 提案
→ 员工确认 → schedule_task 落库（去重键拦截重复信号）
→ 完成跟进后回写闭环
```

---

## 8. 可观测与评测架构

- **采集**：sagt-agent 内 Trace SDK 在编排各节点埋点 → 内存环形缓冲 → 异步批量落 MySQL（失败降级为仅记 Run）；
- **消费**：admin Monitor 页直查；概览聚合用定时任务预计算（意图分布/工具成功率/p50p95/成本）；
- **安全事件**：E_FORBIDDEN、无凭证 write、跨客户越权单独标记告警；
- **评测**：Eval Runner 独立任务队列（Redis），eval_mode 全链路复用；报告表支持基线对比；员工行为信号每周增量生成新样本。目标基线：意图 L1 ≥92%（500 条集）、RAG Recall@5 ≥90%、工具成功率 ≥97%、四维 Judge ≥4.3/5（见需求 §16）。

### 8.1 在线反馈环（P2，monitor_penalty）

- **统计**：Redis 滑动窗口（7 天）按 {intent×agent} 维度统计在线质量：工具成功率、提案采纳率、Run 成功率；
- **反馈**：某维度连续低于阈值 → 向 Orchestrator 注入路由先验惩罚（融合阶段降低置信度，促澄清或降级）；极端值直接出降级话术；
- **衔接**：与每工具熔断形成两级防护——工具层熔断作用于单工具，反馈环作用于 intent×agent 组合；
- **可审计**：反馈调整写入 Run 元数据（penalty_source），Monitor 可回放；
- MVP 不实现，列 P2；是评测飞轮从离线到在线的自然延伸，面试演进题的标准答案。

---

## 9. 安全架构

| 层 | 机制 |
|---|---|
| 认证 | business-mock 签发 JWT；admin/sidebar 携带访问双端；sagt-agent 与 mcp-server 内网校验 |
| 授权 | 角色（employee/manager/visitor）+ 客户归属切面 + MCP 工具白名单；功能级授权矩阵 P2（MVP 角色两级） |
| 配额 | 员工级每日建议生成配额（Redis 计数）；重新生成 ≤2 次；超限提示稍后再试 |
| 写控制 | 一切 write：提案 → approval_token → 幂等键 → 执行；无凭证即拒 + 审计 |
| 数据脱敏 | 相似客户案例脱敏；报表聚合不下钻单条话术 |
| 提示词防护 | 员工输入与系统指令分区；客户上下文槽位锁定当前客户，跨客户请求澄清/拒绝（防提示词注入）；工具结果标注来源防注入；生成后事实自检 |
| 审计 | 采纳/修正/拒绝/授权变更/批量任务全记录（suggestion_action + audit） |

---

## 10. 部署架构（Docker Compose）

| 服务 | 端口 | 依赖 | 备注 |
|---|---|---|---|
| mysql | 3306 | — | init SQL：建表 + 种子（2 员工/20 客户/300 跟进/80 消费） |
| redis | 6379 | — | AOF 关闭（演示），checkpoint 与缓存可丢可重建 |
| etcd / minio | 内部 | — | Milvus 依赖（full profile） |
| milvus-standalone | 19530 | etcd/minio | 3 collection（mem_user 为 ADV） |
| business-mock | 8080 | mysql | Flyway；健康检查先行 |
| mcp-server | 9010 | business-mock | |
| sagt-agent | 8000 | redis/milvus/mcp-server | LLM Key 走 env |
| frontend(nginx) | 80 | 全部 | 双入口反代，同域免 CORS |

- **profile full**：全量（含 Milvus 全家桶）；**profile lite**：无 Milvus，相似客户置灰、RAG 降级关键词检索（演示兜底）；
- 资源基线：全量约 8C/12G（Milvus 占大头），lite 约 4C/6G；
- 一键演示：`docker compose --profile full up` + 预置演示脚本（演示账号、引导话术）。

---

## 11. 项目目录结构（Monorepo）

```
ShopPilot/
├── frontend-web/                  # React 双入口
│   ├── src/
│   │   ├── apps/{admin,sidebar}/  # 两个入口路由
│   │   ├── shared/{components,api,stores,types}
│   │   └── widgets/{proposal-panel,trace-waterfall,citation,chat-stream}
├── business-mock/                 # Java 21 + Spring Boot
│   └── src/main/java/com/nova/sagt/{auth,employee,customer,followup,
│       purchase,service,order,tag,schedule,suggestion,report,event}
├── sagt-agent/                    # Python 3.11 + FastAPI + LangGraph
│   └── app/
│       ├── api/                   # routes + SSE
│       ├── orchestration/         # 主图/子图/blackboard/interrupt
│       ├── intent/                # rule/embedding/llm/fusion/schema
│       ├── rag/                   # rewrite/retrieve/rerank/inject
│       ├── memory/                # redis_session/profile_store/vector
│       ├── skills/                # registry/loader
│       ├── gateway/               # LLM Gateway
│       ├── mcp_client/
│       ├── consumers/             # 事件消费（outbox→stream）
│       ├── monitor/  ├── eval/
├── mcp-server/                    # 10 工具 + 治理
├── sagt_client/                   # OpenAPI 契约 + SDK 包
├── deploy/                        # compose、nginx、mysql-init、milvus 配置
├── eval-data/                     # 5 数据集种子 + 意图样例库
└── docs/                          # PRD / 本文档 / 演示脚本
```

---

## 12. 关键技术决策记录（ADR 摘要）

| # | 决策 | 理由 | 放弃的替代 |
|---|---|---|---|
| A1 | 编排用 LangGraph 而非自研状态机 | checkpoint/interrupt/resume 原生支持 HITL，与需求的中断确认机制精确对应 | 自研（工作量与维护成本高） |
| A2 | 事件用 outbox + Redis Stream | 落库与发布原子一致；演示规模无需 Kafka | 直接发布（丢事件）/ Kafka（过重） |
| A3 | sagt_client 不做独立服务 | 演示期无真实外部调用方，独立进程空转；SDK+契约保留演进路径 | 独立微服务 |
| A4 | mcp-server 独立进程而非并入 sagt-agent | 工具层治理（熔断/幂等/审计）与 Agent 运行时隔离，职责清晰且便于演示 MCP 协议 | 进程内工具函数 |
| A5 | 画像存 MySQL 结构化 + Milvus 向量双轨 | 结构化支撑字段级提案/审计，向量支撑相似检索，各司其职 | 纯向量（无法字段级采纳）/ 纯结构化（无相似检索） |
| A6 | 采纳率等指标由 Java 聚合而非 AI 计算 | 业务指标必须确定性与可审计 | AI 计算（不可复现） |
| A7 | LLM Gateway 内聚于 sagt-agent | 个人项目减少运维面，接口按独立服务设计可平滑拆分 | 独立 Gateway 服务 |
| A8 | Milvus lite 降级方案 | 保证低配机器可演示核心链路 | 强制全量依赖 |

---

## 13. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| LLM 生成与画像事实冲突 | 员工信任崩塌 | Gateway 自检钩子 + 建议卡强制依据区 + 冲突降级要点式输出 |
| 事件消费积压/重复 | 画像重复提案 | event_id 幂等键 + 死信重放 + 提案去重（客户+字段+来源）；同字段已有未处理提案时合并而非新增 |
| Milvus 资源占用高 | 本机跑不动 | lite profile 降级；collection 小规模（<10 万向量） |
| 流式长响应中断 | 体验断裂 | run_id 补齐接口 + 消息落库先行 |
| 演示数据不真实 | 说服力弱 | 种子数据按真实销售节奏设计（含异议、流失、成交案例） |

---

## 附：与需求文档的映射核对

| 需求功能 | 架构落点 |
|---|---|
| 智能聊天建议 | Coach 子图 + playbook/product_kb + HITL 建议卡（§2.2/2.4/7.1） |
| 自动标签标注 | Ops 子图 + save_tags(write) + 修正回流（§2.2/4/8） |
| 智能日程管理 | 信号四分类 + outbox 事件 + create_schedule（§3.3/7.4） |
| 客户画像提取 | Profile 子图 + 事件驱动增量 + 双轨记忆（§2.5/7.2） |
| 中断确认机制 | LangGraph interrupt + checkpoint + resume 三分支（§7.3） |
| 会话监控/Monitor | Trace 异步采集 + 瀑布图（§8） |
| 员工行为即评测 | suggestion_action 事件回流 Eval（§2.7/8） |
