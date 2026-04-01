PYTHON ?= python3

.PHONY: install-dev fmt lint typecheck test check run api worker clean docker-build docker-up docker-down migrate

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

worker:
	$(PYTHON) -m scoring_service.worker

migrate:
	alembic upgrade head

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

# ── Schema management ────────────────────────────────────────────
schema-check:
	alembic check

schema-audit:
	$(PYTHON) -m pytest tests/test_migrations.py -v

schema-bootstrap:
	alembic upgrade head

schema-history:
	alembic history --verbose

test-migrations:
	$(PYTHON) -m pytest tests/test_migrations.py tests/test_adaptation.py -v
