.PHONY: help up down logs build load-data benchmark test

help:
	@echo "Available commands:"
	@echo "  make up         - Start full stack using docker-compose"
	@echo "  make down       - Stop and remove containers"
	@echo "  make logs       - View backend logs"
	@echo "  make build      - Build backend docker image"
	@echo "  make load-data  - Initialize and load parquet data into DuckDB warehouse"
	@echo "  make benchmark  - Run system benchmarks"
	@echo "  make test       - Run pytest unit/integration tests"

up:
	docker compose up -d

down:
	docker compose down

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
