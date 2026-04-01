"""Migration tests — schema consistency, clean bootstrap, alembic integrity."""
from __future__ import annotations

import subprocess
import pytest
from sqlalchemy import create_engine, inspect, text

from scoring_service.config import Settings
from scoring_service.db.models import Base


@pytest.fixture(scope="module")
def settings():
    return Settings()


class TestAlembicIntegrity:
    """Tests that alembic migration chain is healthy."""

    def test_single_head(self):
        """Ensure no branch divergence — exactly one head."""
        result = subprocess.run(
            ["alembic", "heads"],
            capture_output=True, text=True, cwd="/opt/scoring-service",
        )
        heads = [line.strip() for line in result.stdout.strip().split("\n") if line.strip() and "head" in line]
        assert len(heads) == 1, f"Expected single head, got: {heads}"

    def test_no_branches(self):
        """Ensure linear history — no branches."""
        result = subprocess.run(
            ["alembic", "branches"],
            capture_output=True, text=True, cwd="/opt/scoring-service",
        )
        # branches command outputs nothing if no branches
        branch_lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
        assert len(branch_lines) == 0, f"Unexpected branches: {branch_lines}"

    def test_history_linear(self):
        """Verify migration history is a clean linear chain."""
        result = subprocess.run(
            ["alembic", "history", "--indicate-current"],
            capture_output=True, text=True, cwd="/opt/scoring-service",
        )
        assert result.returncode == 0
        lines = [l for l in result.stdout.strip().split("\n") if l.strip() and "->" in l]
        assert len(lines) >= 6, f"Expected at least 6 migration steps, got {len(lines)}"

    def test_current_at_head(self):
        """Database is at latest revision."""
        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True, text=True, cwd="/opt/scoring-service",
        )
        assert "head" in result.stdout or "0006_schema_reconciliation" in result.stdout


class TestSchemaConsistency:
    """Verify SQLAlchemy models match actual DB schema."""

    def test_all_model_tables_exist_in_db(self, settings):
        engine = create_engine(settings.database_url)
        inspector = inspect(engine)
        db_tables = set(inspector.get_table_names())
        model_tables = set(Base.metadata.tables.keys())

        missing = model_tables - db_tables
        assert not missing, f"Tables in models but not in DB: {missing}"

    def test_no_extra_tables_in_db(self, settings):
        engine = create_engine(settings.database_url)
        inspector = inspect(engine)
        db_tables = set(inspector.get_table_names()) - {"alembic_version"}
        model_tables = set(Base.metadata.tables.keys())

        extra = db_tables - model_tables
        assert not extra, f"Tables in DB but not in models: {extra}"

    def test_column_consistency(self, settings):
        """Every model column exists in DB and vice versa."""
        engine = create_engine(settings.database_url)
        inspector = inspect(engine)
        issues = []

        for table_name in Base.metadata.tables:
            db_cols = {c["name"] for c in inspector.get_columns(table_name)}
            model_cols = {c.name for c in Base.metadata.tables[table_name].columns}

            for col in model_cols - db_cols:
                issues.append(f"MISSING_IN_DB: {table_name}.{col}")
            for col in db_cols - model_cols:
                issues.append(f"EXTRA_IN_DB: {table_name}.{col}")

        assert not issues, f"Column drift detected:\n" + "\n".join(issues)

    def test_index_consistency(self, settings):
        """Model indexes exist in DB (by name)."""
        engine = create_engine(settings.database_url)
        inspector = inspect(engine)
        missing = []

        for table_name, table in Base.metadata.tables.items():
            db_idx_names = {idx["name"] for idx in inspector.get_indexes(table_name) if idx["name"]}

            # Explicit indexes from __table_args__
            for idx in table.indexes:
                if idx.name and idx.name not in db_idx_names:
                    missing.append(f"{table_name}.{idx.name}")

            # Auto-generated from index=True
            for col in table.columns:
                if col.index:
                    auto_name = f"ix_{table_name}_{col.name}"
                    if auto_name not in db_idx_names:
                        missing.append(f"{table_name}.{auto_name} (auto)")

        assert not missing, f"Missing indexes:\n" + "\n".join(missing)

    def test_alembic_check_clean(self):
        """alembic check detects no pending operations."""
        result = subprocess.run(
            ["alembic", "check"],
            capture_output=True, text=True, cwd="/opt/scoring-service",
        )
        assert "No new upgrade operations detected" in result.stdout or result.returncode == 0, \
            f"alembic check failed:\n{result.stdout}\n{result.stderr}"


class TestCleanBootstrap:
    """Test that a fresh DB can be bootstrapped from scratch."""

    def test_upgrade_from_scratch_sqlite(self):
        """Verify models can create all tables in a fresh SQLite DB."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        model_tables = set(Base.metadata.tables.keys())
        assert tables == model_tables, f"Mismatch: {tables ^ model_tables}"

    def test_model_table_count(self):
        """Sanity check: expected number of tables."""
        count = len(Base.metadata.tables)
        assert count == 58, f"Expected 58 tables, got {count}"
