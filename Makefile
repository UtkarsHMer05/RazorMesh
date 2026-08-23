# RazorMesh Trust — root development commands (Phase 1)
# `make help` lists everything. DESTRUCTIVE targets are marked below.

SHELL := /bin/zsh
.DEFAULT_GOAL := help

API_DIR := services/api
WEB_DIR := apps/web
UV      := uv

.PHONY: help setup format lint typecheck test test-backend test-frontend \
        security-check benchmark infra-up infra-down migrate seed \
        dev dev-api dev-web reset-local keys

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Install backend deps (uv sync), frontend deps (pnpm), generate dev keys
	$(UV) sync --project $(API_DIR)
	@if [ -d "$(WEB_DIR)" ]; then cd $(WEB_DIR) && pnpm install; else echo "skip pnpm: $(WEB_DIR) not scaffolded yet"; fi
	@$(MAKE) --no-print-directory keys

keys: ## Generate local Ed25519 dev signing keys (never committed)
	python3 scripts/generate_dev_keys.py

format: ## Format backend (ruff) and frontend (prettier if present)
	$(UV) run --project $(API_DIR) ruff format .
	$(UV) run --project $(API_DIR) ruff check --fix .
	@if [ -f "$(WEB_DIR)/package.json" ]; then cd $(WEB_DIR) && (pnpm format || true); fi

lint: ## Lint backend (ruff) and frontend (eslint)
	$(UV) run --project $(API_DIR) ruff check .
	@if [ -d "$(WEB_DIR)" ]; then cd $(WEB_DIR) && pnpm lint; else echo "skip eslint: not scaffolded yet"; fi

typecheck: ## Static type checks (mypy backend, tsc frontend)
	$(UV) run --project $(API_DIR) mypy -p razormesh_api
	@if [ -d "$(WEB_DIR)" ]; then cd $(WEB_DIR) && pnpm typecheck; else echo "skip tsc: not scaffolded yet"; fi

test: test-backend test-frontend ## Run full local test suite

test-backend: ## Backend pytest suite (unit/integration/security/concurrency)
	$(UV) run --project $(API_DIR) pytest

test-frontend: ## Frontend vitest suite
	@if [ -d "$(WEB_DIR)" ]; then cd $(WEB_DIR) && pnpm test; else echo "frontend not scaffolded yet"; fi

security-check: ## Secret scan + dependency audit findings
	python3 scripts/security_check.py

benchmark: ## Run adversarial evaluation runner + paired benchmark (real metrics)
	$(UV) run --project $(API_DIR) python -m benchmark.runner.main

infra-up: ## Start PostgreSQL + Redis via Docker Compose
	docker compose up -d
	docker compose ps

infra-down: ## Stop Docker Compose services (data volume preserved)
	docker compose down

migrate: ## Apply database migrations (alembic upgrade head)
	$(UV) run --project $(API_DIR) alembic upgrade head

seed: ## Load synthetic merchant catalog + fixtures
	$(UV) run --project $(API_DIR) python -m services.api.scripts.seed

dev: dev-api ## Convenience alias

dev-api: ## Run FastAPI locally (127.0.0.1:8000)
	$(UV) run --project $(API_DIR) uvicorn services.api.api.main:app --host 127.0.0.1 --port 8000 --reload

dev-web: ## Run Next.js locally (localhost:3000)
	@if [ -d "$(WEB_DIR)" ]; then cd $(WEB_DIR) && pnpm dev; else echo "frontend not scaffolded yet"; fi

reset-local: ## ⚠️ DESTRUCTIVE: drops Docker volumes + local DB data for THIS project only. Asks nothing.
	@echo "⚠️  DESTRUCTIVE: removing razormesh docker volumes and containers"
	@echo "   (does NOT touch your other Docker state or the system PostgreSQL on :5432)"
	@read "?Type DESTROY to continue: " a || true; \
	if [ "$$a" != "DESTROY" ]; then echo "aborted"; exit 1; fi
	docker compose down -v
	rm -rf infra/data
	@echo "reset complete; run: make infra-up && make migrate && make seed"
