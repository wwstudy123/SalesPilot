# DocAssistant-Skeleton（SalesPilot 零售销售智能体系统 · 工程骨架）

> 依据冻结文档：《SalesPilot-需求文档 v1.2》《SalesPilot-技术架构设计 v1.2》《SalesPilot-MVP方案与任务拆解 v1.2》
> 当前阶段：**M2 AI 运行时地基** —— /api/ai/chat SSE 流式 + LLM Gateway + Trace 落库 + Redis 会话上下文。

## 架构总览

```
frontend-web (React 18 + Vite 双入口, :5173)
  ├── /api/*     ──代理──▶ business-mock (Spring Boot, :8080) ──▶ MySQL 8
  ├── /api/ai/*  ──代理──▶ sale-agent (FastAPI, :8000) ──▶ LangGraph Runtime
  └── /internal/* ──代理──▶ sale-agent（遗留 run 管理端点，M2 起迁 /api/ai）
business-mock ──HTTP──▶ mcp-server (:9010)（M4 起：统一工具层）
```

## 目录结构

| 目录 | 职责 | 现状（M2） |
|---|---|---|
| `sale-agent/` | Python 3.11 + FastAPI + LangGraph：AI 核心引擎（包名 `sale_agent`） | `ai/` 包：Gateway（chat/embedding/重试/成本）+ Trace(SQLite) + Redis 上下文 + LangGraph 主图 + /api/ai SSE；旧 run 管线保留 |
| `business-mock/` | Java 21 + Spring Boot 3.3：Mock CRM，业务事实唯一写入口（包名 `com.nova.sale`） | 四域 CRUD + JWT + 归属校验 + Flyway V1 + 种子数据（§3 规格含金标预埋） |
| `mcp-server/` | Python 统一工具层：权限闸门/熔断/幂等/缓存/审计 | :9010 `/health` 骨架，M4 起落 10 工具 |
| `frontend-web/` | React 双入口：`admin.html`（sale_admin）/ `sidebar.html`（sale_sidebar） | 登录 + 我的客户列表 + 客户详情（时间线/消费），M4/M7 起按端分化 |
| `tests/` | pytest 冒烟（health / runs / LangGraph 管线） | 随改名同步通过 |
| `config/` | LLM 配置示例 | `llm.example.json` |

## 端口总账

| 服务 | 端口 | 说明 |
|---|---|---|
| mysql | 3306 | 库名 sale，账号 sale/sale_pass |
| redis | 6379 | AOF 关闭（演示） |
| business-mock | 8080 | /api/v1/health、/api/v1/auth/login、四域 CRUD |
| sale-agent | 8000 | /api/ai/chat（SSE）、/api/ai/runs/{id}、/api/ai/health；旧 /internal/v1 保留 |
| mcp-server | 9010 | /health |
| frontend-web | 5173 | /admin.html、/sidebar.html |

## 本地运行

前置：conda 环境 `sale`（Python ≥ 3.11）、JDK 21 + Maven、Node ≥ 20、Docker。

```bash
conda activate sale             # Python 环境（已装 -e . -e ./mcp-server）
cp .env.example .env            # 按需修改
make compose-up                 # MySQL 8 + Redis 7
make seed                       # 灌入种子数据（员工3/客户20/跟进300/消费~80，需先 compose-up）
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

## M2 验收清单

- [x] `/api/ai/chat` SSE 流式（start/delta/done 事件），curl -N 实测正常；echo 模式无 key 可跑
- [x] LLM Gateway：chat/embedding 两端点 + 模型路由 + 重试/超时（5xx/429/超时重试，4xx 不重试）+ 成本记账（/api/ai/cost）
- [x] Trace 最小版：agent_run + agent_span 落 SQLite（output/ai/trace.db），`GET /api/ai/runs/{run_id}` 一次请求可查 Run + 4 节点 span
- [x] Redis 会话上下文 `chat:ctx:{session_id}`：多轮保持（实测 llen=4），不可达时内存降级
- [x] LangGraph 主图：load_context → route（M3 预留）→ respond → save_context，逐节点埋点
- [x] pytest 23 passed + ruff 全绿

## 下一步（M3 意图分类）

意图 Schema 表 + 13 意图定义与样例入库；Rule + Embedding(内存余弦) + LLM 三路分类器与融合；路由接入主图，routing_reason/confidence 落库。
