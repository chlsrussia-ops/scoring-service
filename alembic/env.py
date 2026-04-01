"""Alembic env.py — production-grade configuration.

Features:
- Naming convention for constraints (FK, UQ, IX, CK, PK)
- compare_type=True for type drift detection
- compare_server_default=False (avoid false positives from server defaults)
- Proper metadata from models
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from scoring_service.config import Settings
from scoring_service.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = Settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=False,
            include_schemas=False,
            # Render explicit constraint names
            render_as_batch=False,
        )

        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
