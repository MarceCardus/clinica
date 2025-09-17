.PHONY: dev migrate test seed

install:
poetry install

dev:
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port \
$${API_PORT:-8000}

migrate:
poetry run alembic upgrade head

seed:
poetry run python -m app.seed.seed_data

test:
poetry run pytest
