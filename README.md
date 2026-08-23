# DocAssistant-Skeleton（SalesPilot 零售销售智能体系统 · 工程骨架）

> 依据冻结文档：《SalesPilot-需求文档 v1.2》《SalesPilot-技术架构设计 v1.2》《SalesPilot-MVP方案与任务拆解 v1.2》
> 当前阶段：**M0 工程地基** —— 由通用三端骨架（AgentKit）改造为 SalesPilot 形态，各端 hello 可跑。

## 架构总览

```
frontend-web (React 18 + Vite 双入口, :5173)
  ├── /api/*     ──代理──▶ business-mock (Spring Boot, :8080) ──▶ MySQL 8
  ├── /api/ai/*  ──代理──▶ sale-agent (FastAPI, :8000) ──▶ LangGraph Runtime
  └── /internal/* ──代理──▶ sale-agent（遗留 run 管理端点，M2 起迁 /api/ai）
business-mock ──HTTP──▶ mcp-server (:9010)（M4 起：统一工具层）
```

## 目录结构

| 目录 | 职责 | 现状（M0） |
|---|---|---|
| `sale-agent/` | Python 3.11 + FastAPI + LangGraph：AI 核心引擎（包名 `sale_agent`） | 保留骨架 run 管线与 Internal API（:8000），M2 起重构为 supervisor/子图 |
| `business-mock/` | Java 21 + Spring Boot 3.3：Mock CRM，业务事实唯一写入口（包名 `com.nova.sale`） | DDD 四层 + Flyway + Project 示例实体，M1 起替换为 employee/customer 等域 |
| `mcp-server/` | Python 统一工具层：权限闸门/熔断/幂等/缓存/审计 | :9010 `/health` 骨架，M4 起落 10 工具 |
| `frontend-web/` | React 双入口：`admin.html`（sale_admin）/ `sidebar.html`（sale_sidebar） | 双入口共享现有页面，M4/M7 起按端分化 |
| `tests/` | pytest 冒烟（health / runs / LangGraph 管线） | 随改名同步通过 |
| `config/` | LLM 配置示例 | `llm.example.json` |

## 端口总账

| 服务 | 端口 | 说明 |
|---|---|---|
| mysql | 3306 | 库名 sale，账号 sale/sale_pass |
| redis | 6379 | AOF 关闭（演示） |
| business-mock | 8080 | /api/v1/health |
| sale-agent | 8000 | /internal/v1/health（M2 迁移 /api/ai） |
| mcp-server | 9010 | /health |
| frontend-web | 5173 | /admin.html、/sidebar.html |

## 本地运行

前置：conda 环境 `sale`（Python ≥ 3.11）、JDK 21 + Maven、Node ≥ 20、Docker。

```bash
conda activate sale             # Python 环境（已装 -e . -e ./mcp-server）
cp .env.example .env            # 按需修改
make compose-up                 # MySQL 8 + Redis 7

export JAVA_HOME=$(/usr/libexec/java_home -v 21)   # 默认 JDK 为 17 时需要
make api                        # sale-agent :8000
make api-mcp                    # mcp-server :9010
make api-java                   # business-mock :8080
make api-web                    # 前端 :5173（/admin.html、/sidebar.html）

make test                       # pytest + mvn test + 前端构建
make lint                       # ruff
```

## M0 验收清单

- [x] Monorepo 目录按 SalesPilot 命名（sale-agent / business-mock / mcp-server / frontend-web）
- [x] docker-compose.yml：MySQL 8（utf8mb4）+ Redis 7，健康检查齐备
- [x] Python 包改名 sale_agent，env 前缀 SALE_，测试同步
- [x] Java 包改名 com.nova.sale，MySQL 驱动 + flyway-mysql，测试走 H2(MySQL 模式)
- [x] mcp-server 骨架（:9010 /health）
- [x] 前端双入口 admin.html / sidebar.html，代理分流 /api/ai→8000、/api→8080
- [x] `make test` 全绿（pytest 5 passed / mvn test H2 / npm build 双入口；conda 环境 `sale` Python 3.12）

## 下一步（M1 业务数据域）

business-mock：JWT 认证 + employee/customer 域 CRUD + 客户归属切面 + follow_up/purchase + Flyway 迁移 + 种子数据脚本（替换 Project 示例实体）。
