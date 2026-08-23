# DocAssistant-Skeleton（SAGT 零售销售智能体系统 · 工程骨架）

> 依据冻结文档：《SAGT-需求文档 v1.2》《SAGT-技术架构设计 v1.2》《SAGT-MVP方案与任务拆解 v1.2》
> 当前阶段：**M0 工程地基** —— Monorepo 骨架 + 中间件 compose + 各服务 hello 端点。

## 目录结构

```
DocAssistant-Skeleton/
├── frontend-web/        # React 18 + Vite 双入口（apps/admin、apps/sidebar）
├── business-mock/       # Java 21 + Spring Boot 3.3（Mock CRM，业务事实唯一写入口）
├── sagt-agent/          # Python 3.11 + FastAPI + LangGraph（AI 核心引擎）
├── mcp-server/          # Python（统一工具层：权限闸门/熔断/幂等/缓存/审计）
├── deploy/              # compose.dev.yml（mysql + redis）、mysql-init、nginx（后续）
└── docs/                # 三份冻结文档的引用说明
```

## 端口总账

| 服务 | 端口 | 说明 |
|---|---|---|
| mysql | 3306 | 库名 sagt，账号 sagt/sagt_pass |
| redis | 6379 | AOF 关闭（演示） |
| business-mock | 8080 | /api/health |
| sagt-agent | 8000 | /api/ai/health |
| mcp-server | 9010 | /health |
| frontend-web | 5173 | /admin.html、/sidebar.html |

## 快速启动

```bash
# 1. 中间件
docker compose -f deploy/compose.dev.yml up -d

# 2. business-mock（需 JDK 21 + Maven）
cd business-mock && ./mvnw spring-boot:run    # 或 mvn spring-boot:run

# 3. sagt-agent（需 Python 3.11）
cd sagt-agent && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000

# 4. mcp-server
cd mcp-server && pip install -r requirements.txt
uvicorn app.main:app --port 9010

# 5. 前端
cd frontend-web && npm install && npm run dev
```

## M0 验收清单

- [ ] `docker compose -f deploy/compose.dev.yml up` 起 mysql/redis 且健康检查通过
- [ ] business-mock：`curl localhost:8080/api/health` 返回 UP
- [ ] sagt-agent：`curl localhost:8000/api/ai/health` 返回 UP
- [ ] mcp-server：`curl localhost:9010/health` 返回 UP
- [ ] 前端 `npm run dev` 后 admin/sidebar 两个入口页均可访问

## 下一步（M1 业务数据域）

Java：JWT 认证 + employee/customer 域 CRUD + 客户归属切面 + follow_up/purchase + Flyway 迁移 + 种子数据脚本。
