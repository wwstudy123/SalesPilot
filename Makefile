.PHONY: help api api-mcp api-java api-web seed seed-gen test test-py test-java test-web lint lint-py compose-up compose-down

help: ## 显示可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ===== 本地启动 =====

api: ## 启动 sale-agent Internal API（uvicorn，:8000）
	python -m sale_agent.entry.internal_api.run

api-mcp: ## 启动 mcp-server（:9010）
	cd mcp-server && python -m sale_server.run

api-java: ## 启动 business-mock（:8080，需先 compose-up）
	cd business-mock && mvn spring-boot:run

api-web: ## 启动前端开发服务器（:5173）
	cd frontend-web && npm run dev

compose-up: ## 启动 MySQL 8 + Redis 7（sale 库）
	docker compose up -d

compose-down: ## 停止 MySQL / Redis
	docker compose down

# ===== 种子数据 =====

seed-gen: ## 重新生成种子 SQL（§3 规格，金标预埋）
	python3 scripts/generate_seed.py

seed: ## 灌入 CRM 与知识库种子（需先 compose-up）
	docker exec -i sale-mysql mysql -usale -psale_pass --default-character-set=utf8mb4 sale < business-mock/src/main/resources/db/seed/seed.sql
	python -m sale_agent.kb.seed

# ===== 测试 =====

test: test-py test-java test-web ## 全量测试（Python + Java + 前端构建）

test-py: ## Python 测试
	python -m pytest tests/ -q

test-java: ## Java 测试
	cd business-mock && mvn test -B -q

test-web: ## 前端类型检查与构建
	cd frontend-web && npm run build

# ===== 代码规范 =====

lint: lint-py ## 代码检查

lint-py: ## ruff 检查与自动修复
	python -m ruff check sale-agent mcp-server tests
	python -m ruff format --check sale-agent mcp-server tests
