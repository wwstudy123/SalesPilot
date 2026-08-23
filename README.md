# DocAssistant-Skeleton（SalesPilot 零售销售智能体系统 · 工程骨架）

> 依据冻结文档：《SalesPilot-需求文档 v1.2》《SalesPilot-技术架构设计 v1.2》《SalesPilot-MVP方案与任务拆解 v1.2》
> 当前阶段：**M1 业务数据域** —— 员工/客户/跟进/消费四域 CRUD + JWT 认证 + 客户归属校验，种子数据一键灌入。

## 架构总览

```
frontend-web (React 18 + Vite 双入口, :5173)
  ├── /api/*     ──代理──▶ business-mock (Spring Boot, :8080) ──▶ MySQL 8
  ├── /api/ai/*  ──代理──▶ sale-agent (FastAPI, :8000) ──▶ LangGraph Runtime
  └── /internal/* ──代理──▶ sale-agent（遗留 run 管理端点，M2 起迁 /api/ai）
business-mock ──HTTP──▶ mcp-server (:9010)（M4 起：统一工具层）
```

## 目录结构

| 目录 | 职责 | 现状（M1） |
|---|---|---|
| `sale-agent/` | Python 3.11 + FastAPI + LangGraph：AI 核心引擎（包名 `sale_agent`） | 保留骨架 run 管线与 Internal API（:8000），M2 起重构为 supervisor/子图 |
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
| sale-agent | 8000 | /internal/v1/health（M2 迁移 /api/ai） |
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

## M1 验收清单

- [x] Flyway V1：employee/customer/follow_up/purchase 四表（utf8mb4、CHECK 枚举、软删除 deleted_token）
- [x] JWT 认证（HS256）+ 角色 employee/manager；`/api/v1/employees` 仅 manager
- [x] 四域 CRUD REST；客户归属校验（非本人客户 403，不存在 404），跟进/消费先过归属闸门
- [x] 种子数据生成器（§3 规格：承诺类/异议/价格敏感/复购信号四类金标预埋）+ `make seed`
- [x] 前端：登录页 + 我的客户列表（阶段中文标签）+ 客户详情（基本信息/跟进时间线/消费记录）
- [x] `make test` 全绿（pytest 5 passed / mvn test 11 tests / npm build 双入口），`make lint` 通过

## 下一步（M2 对话管线）

sale-agent：supervisor + 子图重构，`/api/ai` 对话端点，跟进记录语音/文本录入 → AI 沉淀画像。
