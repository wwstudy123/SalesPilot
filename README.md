# SalesPilot 零售销售智能体系统

> 依据冻结文档：《SalesPilot-需求文档 v1.2》《SalesPilot-技术架构设计 v1.2》《SalesPilot-MVP方案与任务拆解 v1.2》
> 当前阶段：**M8 Monitor 简版** —— Run 筛选列表与 Span 时间线，支持查看 AI 决策链。

## 架构总览

```
frontend-web (React 18 + Vite 双入口, :5173)
  ├── /api/*     ──代理──▶ business-mock (Spring Boot, :8080) ──▶ MySQL 8
  ├── /api/ai/*  ──代理──▶ sale-agent (FastAPI, :8000) ──▶ LangGraph Runtime
  └── /internal/* ──代理──▶ sale-agent（遗留 run 管理端点，M2 起迁 /api/ai）
sale-agent ──工具调用──▶ mcp-server (:9010) ──转发──▶ business-mock
business-mock ──事件通知──▶ sale-agent /api/ai/events/follow_up_created（补录即触发画像刷新）
```

## 目录结构

| 目录 | 职责 | 现状（M4） |
|---|---|---|
| `sale-agent/` | Python 3.11 + FastAPI + LangGraph：AI 核心引擎（包名 `sale_agent`） | `ai/` 包：Gateway + Trace + Redis 上下文 + 主图 + SSE；`intent/` 包：13 意图三路融合路由；`profile/` 包：画像子图（抽取/diff/提案）；`rag/`、`kb/`、`coach/` 与 `suggestion/` 提供 M5 话术链路 |
| `business-mock/` | Java 21 + Spring Boot 3.3：Mock CRM，业务事实唯一写入口（包名 `com.nova.sale`） | 四域 CRUD + JWT + 归属校验 + Flyway V1/V2（画像字段表 + 审批凭证表）+ 无凭证 write 403 + AI 事件通知器 |
| `mcp-server/` | Python 统一工具层：权限闸门/熔断/幂等/缓存/审计 | 5 工具（4 只读 + update_profile_field）+ 权限四闸门 + 幂等重放 + SQLite 审计 |
| `frontend-web/` | React 双入口：`admin.html`（sale_admin）/ `sidebar.html`（sale_sidebar） | 登录 + 客户列表/详情 + AI 画像面板（画像卡/确认面板/首访清单，10s 轮询提案） |
| `tests/` | pytest 冒烟与单测（62 条） | 意图路由 16 + 画像 HITL 15 + 网关四闸门 9 + 其余 |
| `config/` | LLM 配置示例 | `llm.example.json` |

## 端口总账

| 服务 | 端口 | 说明 |
|---|---|---|
| mysql | 3306 | 库名 sale，账号 sale/sale_pass |
| redis | 6379 | AOF 关闭（演示） |
| business-mock | 8080 | /api/v1/health、/api/v1/auth/login、四域 CRUD、画像/凭证接口 |
| sale-agent | 8000 | /api/ai/chat（SSE）、/api/ai/profile/refresh、/api/ai/proposals；旧 /internal/v1 保留 |
| mcp-server | 9010 | /health、/tools、/tools/{name}/call、/audit/recent |
| frontend-web | 5173 | /admin.html、/sidebar.html |

## 本地运行

前置：conda 环境 `sale`（Python ≥ 3.11）、JDK 21 + Maven、Node ≥ 20、Docker。

```bash
conda activate sale             # Python 环境（已装 -e . -e ./mcp-server）
cp .env.example .env            # 按需修改
make compose-up                 # MySQL 8 + Redis 7
make seed                       # 灌入 CRM + M5 知识库种子（员工3/客户20/跟进300/消费~80，需先 compose-up）
make seed-gen                   # 重新生成种子 SQL（scripts/generate_seed.py，确定性）

export JAVA_HOME=$(/usr/libexec/java_home -v 21)   # 默认 JDK 为 17 时需要
make api                        # sale-agent :8000
make api-mcp                    # mcp-server :9010
make api-java                   # business-mock :8080
make api-web                    # 前端 :5173（/admin.html、/sidebar.html）

make test                       # pytest + mvn test + 前端构建
make lint                       # ruff
```

种子账号：`zhangsan/pass123`、`lisi/pass123`（employee，各挂 10 个客户）、`admin/admin123`（manager，可见全部客户）。前端登录页 `/login` 已预填 zhangsan。

AI 侧环境变量（可选）：`SALE_LLM_API_KEY` / `SALE_LLM_BASE_URL` / `SALE_LLM_CHAT_MODEL` / `SALE_LLM_EMBEDDING_MODEL`；未配 key 时 Gateway 自动进入 echo 模式（无外部依赖）。会话上下文存 Redis `chat:ctx:{session_id}`（TTL 30min），Redis 不可达自动降级内存。

向量检索默认使用 lite（SQLite + bigram）。设置 `SALE_VECTOR_BACKEND=milvus`、`MILVUS_HOST`、`MILVUS_PORT` 后，知识库发布会同步向量，RAG dense 检索自动切至 Milvus；服务或 embedding 不可用时自动回落 lite。

## M2 验收清单

- [x] `/api/ai/chat` SSE 流式（start/delta/done 事件），curl -N 实测正常；echo 模式无 key 可跑
- [x] LLM Gateway：chat/embedding 两端点 + 模型路由 + 重试/超时（5xx/429/超时重试，4xx 不重试）+ 成本记账（/api/ai/cost）
- [x] Trace 最小版：agent_run + agent_span 落 SQLite（output/ai/trace.db），`GET /api/ai/runs/{run_id}` 一次请求可查 Run + 4 节点 span
- [x] Redis 会话上下文 `chat:ctx:{session_id}`：多轮保持（实测 llen=4），不可达时内存降级
- [x] LangGraph 主图：load_context → route（M3 预留）→ respond → save_context，逐节点埋点
- [x] pytest 23 passed + ruff 全绿

## M3 验收清单

- [x] 意图 Schema：13 意图定义 + 每意图 5 条种子样例入 SQLite（output/ai/intents.db），`GET /api/ai/intents` 返回带 example_count；`POST /intents/{name}/examples` 增补后分类器即时 reload（零发版）
- [x] Rule 分类器：菜单直达（MENU 免分类）+ 关键词硬规则锁定（RULE_LOCKED，0.95）+ 软规则 prior
- [x] Embedding 简化版：字符 bigram 内存余弦 + 锚点校准（SALE_INTENT_EMB_ANCHOR，默认 0.50）；LLM 分类器 Schema 动态渲染 prompt，echo 模式返回 None 走 EMB_FALLBACK 降级
- [x] 三路融合：0.6×llm + 0.3×emb + 0.1×rule（一致 +0.05）→ FUSED/CLARIFY/EMB_FALLBACK/UNKNOWN，阈值 0.60~0.72 逐意图判定
- [x] 路由接入主图：done 事件与 Trace 均带 intent/confidence/decision_path/routing_reason（Monitor 可验收）
- [x] 自测集（tests/intent_eval_set.py，39 条 paraphrase）L1 = 36/39 = **92.3%** ≥ 85%；pytest 39 passed + ruff 全绿

## M4 验收清单

- [x] mcp-server 工具网关：5 工具（search_customers/get_customer_profile/list_follow_ups/list_purchases + update_profile_field）；权限四闸门：JWT 身份（401）→ 角色（403）→ 客户归属（越权 403 E_FORBIDDEN）→ write 凭证（无 approval_token 100% 拒 E_APPROVAL_REQUIRED）；只读 bypass 免确认 + 缓存（profile 10min/list 60s，X-No-Cache 供事件刷新绕过）；幂等键重放；SQLite 审计（ok/denied/upstream_error + bypass 标记，`GET /audit/recent`）
- [x] business-mock V2：customer_profile_field（字段级 upsert，version+1 留痕）+ approval（一次性凭证：SecureRandom token / 30min TTL / CAS 消费 / 错误码 E_APPROVAL_REQUIRED、INVALID、MISMATCH、EXPIRED、USED）；无凭证 write 403；补录跟进异步通知 sale-agent（失败仅 warn 不阻断主链路）
- [x] Profile 子图：事实装载（三工具）→ 结构化抽取（LLM JSON Schema 约束；echo 降级确定性规则，每条附 evidence 回溯 follow_up#id；累计消费额定 value_tier）→ 字段级 diff（变更附 oldValue）→ 提案；记录 <3 条不抽取，返首访采集清单（E13）；全程 Trace span
- [x] HITL 确认流：proposal 表（SQLite）+ 30min 惰性过期 + 同客户同字段 pending 提案自动合并；confirm → 签发 approval_token → 携凭证经网关 write → 提案收尾；重复确认 409；write 失败提案保持 pending 可重试
- [x] 触发链路：补录跟进 → business-mock 事件通知 → sale-agent 异步刷新（fresh 绕缓存）→ 实测 6s 内出 pending 提案；前端画像面板 10s 轮询自动呈现
- [x] 前端：客户详情页 AI 画像面板（画像卡字段/依据/版本；待确认提案新旧值并呈 + 确认写入/放弃；空态首访清单）
- [x] pytest 62 passed（新增：HITL 15 + 网关四闸门 9）+ ruff 全绿 + mvn test + 前端构建通过

## M5 验收清单

- [x] 知识库：`knowledge_doc/chunk` staging → ready 原子切换；上传、检索测试页、话术 ≥30 条与产品 ≥10 条种子；`make seed` 同步灌入。
- [x] RAG：rewrite → dense/sparse top20 → RRF → LLM listwise rerank → 阈值注入；Milvus 可用时走真实 dense 检索，不可用自动降级 lite。
- [x] Coach：两项硬编码技能；MCP 读取画像/跟进；产品相关请求补充 product_kb；事实自检与引用角标。
- [x] 建议卡：采纳（可编辑）、重新生成 ≤2、拒绝必填原因，行为完整落入 `suggestion_action`。
- [x] SSE：intent / tool_call / rag_citation / token / proposal / done；客户详情页可直接带客户上下文进入话术助手。

## M6 验收清单

- [x] `tag_dict` / `customer_tag` 由 Flyway V3 建表并灌入基础标签；`save_tags` 经过 approval token 与幂等闸门。
- [x] Ops 子图根据画像与近期跟进生成带依据、置信度的标签提案；确认画像后自动触发复核。
- [x] 客户详情展示标签建议卡，支持确认、修正或放弃；客户列表按已生效标签筛选。

## M7 验收清单

- [x] 管理端可查看员工与全量客户；可切换角色、移交客户并记录移交审计事件。
- [x] 会话监控展示员工、客户、建议技能、引用数量和采纳状态。
- [x] 会话条目保留 `session_id`，供 M8 Monitor 按会话关联 Run。

## M8 验收清单

- [x] 管理者可按会话、员工、意图、状态筛选 Run。
- [x] Run 可展开 Span 时间线，显示名称、状态、耗时与输入输出摘要。
- [x] 管理端会话建议可跳转关联 Run 的 Monitor 详情。

## 下一步（M9）

实现 profile/tag/talk 三类评测 CLI；M10 再提供包含 Milvus 的 full compose。
