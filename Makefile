.PHONY: help api api-java api-web test test-py test-java test-web lint lint-py compose-up compose-down

help: ## 显示可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ===== 本地启动 =====

api: ## 启动 Python Internal API（uvicorn，:8000）
	python -m agentkit.entry.internal_api.run

api-java: ## 启动 Java 平台层（:8080，需先 compose-up）
	cd java-platform && mvn spring-boot:run

api-web: ## 启动前端开发服务器（:5173）
	cd frontend-web && npm run dev

compose-up: ## 启动 PostgreSQL（agentkit 库）
	docker compose up -d

compose-down: ## 停止 PostgreSQL
	docker compose down

# ===== 测试 =====

test: test-py test-java test-web ## 全量测试（Python + Java + 前端构建）

test-py: ## Python 测试
	python -m pytest tests/ -q

test-java: ## Java 测试
	cd java-platform && mvn test -B -q

test-web: ## 前端类型检查与构建
	cd frontend-web && npm run build

# ===== 代码规范 =====

lint: lint-py ## 代码检查

lint-py: ## ruff 检查与自动修复
	python -m ruff check agentkit tests
	python -m ruff format --check agentkit tests
