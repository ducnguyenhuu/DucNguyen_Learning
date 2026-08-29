.PHONY: dev dev-backend dev-frontend test test-backend test-frontend test-e2e \
        lint lint-backend lint-frontend type-check type-check-backend type-check-frontend \
        build codegen install install-backend install-frontend clean

# ─── Development ────────────────────────────────────────────────────────────

dev: ## Start both backend and frontend dev servers concurrently
	@echo "Starting HACP dev servers…"
	@$(MAKE) dev-backend &
	@$(MAKE) dev-frontend

dev-backend: ## Start FastAPI dev server on :3001
	cd backend && uv run uvicorn hacp.api.app:app --reload --port 3001

dev-frontend: ## Start Vite dev server on :5173
	cd frontend && npm run dev

# ─── Installation ────────────────────────────────────────────────────────────

install: install-backend install-frontend ## Install all dependencies

install-backend: ## Install Python dependencies with uv
	cd backend && uv sync --extra dev

install-frontend: ## Install Node dependencies
	cd frontend && npm install

# ─── Testing ────────────────────────────────────────────────────────────────

test: test-backend test-frontend ## Run all tests

test-backend: ## Run pytest with coverage
	cd backend && uv run pytest tests/ --cov=hacp --cov-report=term --cov-report=html:coverage -q

test-frontend: ## Run Vitest unit tests
	cd frontend && npm run test

test-e2e: ## Run Playwright E2E tests (requires both servers running)
	cd frontend && npm run test:e2e

bench: ## Run performance benchmark tests
	cd backend && uv run pytest tests/perf/ -m perf --benchmark-autosave -v

# ─── Linting & Formatting ────────────────────────────────────────────────────

lint: lint-backend lint-frontend ## Lint both backend and frontend

lint-backend: ## Ruff lint + format check
	cd backend && uv run ruff check src/ tests/
	cd backend && uv run ruff format --check src/ tests/

lint-frontend: ## ESLint + Prettier check
	cd frontend && npm run lint
	cd frontend && npm run format:check

lint-fix: ## Auto-fix linting issues
	cd backend && uv run ruff check --fix src/ tests/
	cd backend && uv run ruff format src/ tests/
	cd frontend && npm run lint:fix
	cd frontend && npm run format

# ─── Type Checking ───────────────────────────────────────────────────────────

type-check: type-check-backend type-check-frontend ## Type-check both stacks

type-check-backend: ## Mypy strict type check
	cd backend && uv run mypy src/

type-check-frontend: ## TypeScript type check
	cd frontend && npm run type-check

# ─── Build ───────────────────────────────────────────────────────────────────

build: ## Build frontend for production
	cd frontend && npm run build

# ─── Code Generation ─────────────────────────────────────────────────────────

codegen: ## Generate TypeScript types from FastAPI OpenAPI schema
	@echo "Generating TypeScript API types (backend must be running on :3001)…"
	cd frontend && npm run codegen

# ─── Cleanup ─────────────────────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	rm -rf frontend/dist frontend/coverage
	rm -rf backend/coverage backend/.pytest_cache backend/__pycache__
	find backend/src -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend/src -name "*.pyc" -delete 2>/dev/null || true

# ─── Help ────────────────────────────────────────────────────────────────────

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}' | sort
