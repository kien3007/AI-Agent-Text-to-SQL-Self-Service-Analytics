.PHONY: help up down logs build load-data benchmark test supabase-up supabase-down supabase-logs

help:
	@echo "Available commands:"
	@echo "  make up            - Start full stack using docker-compose"
	@echo "  make down          - Stop and remove containers"
	@echo "  make logs          - View backend logs"
	@echo "  make build         - Build backend docker image"
	@echo "  make load-data     - Initialize and load parquet data into DuckDB warehouse"
	@echo "  make benchmark     - Run system benchmarks"
	@echo "  make test          - Run pytest unit/integration tests"
	@echo "  make supabase-up   - Start self-hosted Supabase stack (Auth, Kong, Studio, DB)"
	@echo "  make supabase-down - Stop self-hosted Supabase stack"
	@echo "  make supabase-logs - Follow Supabase logs"

up:
	docker compose up -d

down:
	docker compose down

supabase-up:
	docker compose -f infra/supabase/docker-compose.yml up -d

supabase-down:
	docker compose -f infra/supabase/docker-compose.yml down

supabase-logs:
	docker compose -f infra/supabase/docker-compose.yml logs -f

logs:
	docker compose logs -f backend

build:
	docker compose build backend

load-data:
	@echo "Initializing DuckDB warehouse and mapping 3.5M records..."
	python scripts/init_duckdb.py

benchmark:
	@echo "Running evaluation benchmark..."
	python evaluation/scripts/run_benchmark.py

test:
	@echo "Running tests..."
	pytest -v
