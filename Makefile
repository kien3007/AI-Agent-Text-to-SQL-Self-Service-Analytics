.PHONY: help up down logs build load-data benchmark test

help:
	@echo "Available commands:"
	@echo "  make up         - Start full stack using docker-compose"
	@echo "  make down       - Stop and remove containers"
	@echo "  make logs       - View backend logs"
	@echo "  make build      - Build backend docker image"
	@echo "  make load-data  - Load sample data into Doris"
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
	@echo "Loading parquet data into Apache Doris..."
	python scripts/load_parquet_to_doris.py

benchmark:
	@echo "Running evaluation benchmark..."
	python evaluation/scripts/run_benchmark.py

test:
	@echo "Running tests..."
	pytest -v
