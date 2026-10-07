SHELL := /bin/bash
UV := uv
export UV_CACHE_DIR ?= /tmp/scns-uv-cache
export npm_config_cache ?= /tmp/scns-npm-cache
export TEST_DATABASE_URL ?= postgresql+psycopg://scns:scns_local@localhost:54329/scns_test
DATASET ?= ../data/demo/campus.json

.PHONY: setup db migrate seed-demo dev api web test test-unit test-integration test-e2e test-migrations check build containers generate-api validate-dataset test-db demo
setup:
	cd backend && $(UV) sync --frozen
	npm ci
	@test -f .env || cp .env.example .env

db:
	docker compose up -d --wait db

migrate:
	cd backend && $(UV) run --frozen alembic upgrade head

seed-demo:
	cd backend && DEMO_ENABLED=true $(UV) run --frozen python -m app.cli.dataset seed-demo "$(DATASET)"

demo: db migrate seed-demo

dev:
	./scripts/dev.sh

api:
	cd backend && $(UV) run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

worker:
	cd backend && $(UV) run --frozen python -m app.cli.imports worker

web:
	cd frontend && npm run dev -- --host 127.0.0.1

test-unit:
	cd backend && $(UV) run --frozen pytest -q tests/unit
	cd frontend && npm test

test-db: db
	./scripts/test-db.sh

test-integration: test-db
	cd backend && $(UV) run --frozen pytest -q tests/integration

test-e2e: test-db
	cd backend && $(UV) run --frozen python -m tests.browser_runner

test-migrations: test-db
	cd backend && $(UV) run --frozen python -m tests.migration_runner

test: test-unit test-integration test-migrations test-e2e

check:
	cd backend && $(UV) run --frozen ruff check app migrations tests
	cd backend && $(UV) run --frozen ruff format --check app migrations tests
	cd frontend && npm run check

build:
	cd frontend && npm run build
	cd backend && $(UV) run --frozen python -m compileall -q app

containers:
	docker compose build api frontend

generate-api:
	cd backend && $(UV) run --frozen python -m app.cli.contracts
	cd frontend && npm run generate:api

validate-dataset:
	cd backend && $(UV) run --frozen python -m app.cli.dataset validate "$(DATASET)"
