.PHONY: install check lint format typecheck test run clean

install:
	python -m pip install -e ".[dev]"

check: lint test

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy src tests

test:
	pytest -v

run:
	python -m scoring_service.main --pretty

clean:
	find . -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -rf .mypy_cache .ruff_cache .pytest_cache *.egg-info build dist
