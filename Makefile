PYTHON ?= python3

.PHONY: install-dev fmt lint typecheck test check run api clean docker-build docker-up docker-down

install-dev:
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -e ".[dev]"

fmt:
	ruff format .
	ruff check . --fix

lint:
	ruff check .

typecheck:
	mypy src tests

test:
	pytest

check: lint typecheck test

run:
	$(PYTHON) -m scoring_service.main --pretty

api:
	uvicorn scoring_service.api.app:create_app --factory --host 0.0.0.0 --port 8000 --reload

docker-build:
	docker build -t scoring-service:latest .

docker-up:
	docker compose up --build

docker-down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -prune -exec rm -rf {} +
	rm -f .coverage coverage.xml
