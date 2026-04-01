"""Production hardening tests — critical invariants."""
from __future__ import annotations

import subprocess
import pytest
from sqlalchemy import create_engine, inspect, text

from scoring_service.config import Settings
from scoring_service.db.models import Base


@pytest.fixture(scope="module")
def settings():
    return Settings()


@pytest.fixture(scope="module")
def engine(settings):
    return create_engine(settings.database_url)


class TestMigrationBootstrap:
    """P0: Migrations must work from zero to head."""

    def test_alembic_single_head(self):
        result = subprocess.run(
            ["alembic", "heads"], capture_output=True, text=True,
            cwd="/opt/scoring-service",
        )
        heads = [l for l in result.stdout.strip().split("\n") if "head" in l]
        assert len(heads) == 1, f"Multiple heads: {heads}"

    def test_alembic_check_clean(self):
        result = subprocess.run(
            ["alembic", "check"], capture_output=True, text=True,
            cwd="/opt/scoring-service",
        )
        assert "No new upgrade operations" in result.stdout, f"Schema drift: {result.stderr}"

    def test_linear_chain(self):
        result = subprocess.run(
            ["alembic", "branches"], capture_output=True, text=True,
            cwd="/opt/scoring-service",
        )
        branches = [l for l in result.stdout.strip().split("\n") if l.strip()]
        assert len(branches) == 0, f"Branches detected: {branches}"


class TestFKIntegrity:
    """P0: No orphaned foreign key references."""

    def test_no_orphaned_rows(self, engine):
        with engine.connect() as conn:
            fks = conn.execute(text("""
                SELECT tc.table_name, kcu.column_name, ccu.table_name, ccu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
            """)).fetchall()

            orphans = []
            for child_t, child_c, parent_t, parent_c in fks:
                n = conn.execute(text(
                    f'SELECT COUNT(*) FROM "{child_t}" c '
                    f'WHERE c."{child_c}" IS NOT NULL '
                    f'AND NOT EXISTS (SELECT 1 FROM "{parent_t}" p WHERE p."{parent_c}" = c."{child_c}")'
                )).scalar()
                if n > 0:
                    orphans.append(f"{child_t}.{child_c} -> {parent_t}.{parent_c}: {n}")

            assert not orphans, f"FK orphans found:\n" + "\n".join(orphans)


class TestSchemaModelSync:
    """P0: ORM models match actual DB schema."""

    def test_table_match(self, engine):
        inspector = inspect(engine)
        db_tables = set(inspector.get_table_names()) - {"alembic_version"}
        model_tables = set(Base.metadata.tables.keys())
        assert db_tables == model_tables, f"Mismatch: {db_tables ^ model_tables}"

    def test_column_match(self, engine):
        inspector = inspect(engine)
        issues = []
        for table_name in Base.metadata.tables:
            db_cols = {c["name"] for c in inspector.get_columns(table_name)}
            model_cols = {c.name for c in Base.metadata.tables[table_name].columns}
            for c in model_cols - db_cols:
                issues.append(f"MISSING_IN_DB: {table_name}.{c}")
            for c in db_cols - model_cols:
                issues.append(f"EXTRA_IN_DB: {table_name}.{c}")
        assert not issues, "\n".join(issues)


class TestConfigExtraction:
    """P1: Thresholds are in config, not hardcoded."""

    def test_pipeline_thresholds_in_config(self, settings):
        assert hasattr(settings, "pipeline_alert_score_threshold")
        assert hasattr(settings, "pipeline_alert_critical_threshold")
        assert hasattr(settings, "pipeline_recommendation_min_score")
        assert hasattr(settings, "pipeline_recommendation_high_priority_threshold")
        assert settings.pipeline_alert_score_threshold == 50.0
        assert settings.pipeline_alert_critical_threshold == 80.0

    def test_adaptation_guardrails_in_config(self, settings):
        assert hasattr(settings, "adaptation_max_delta_per_update")
        assert hasattr(settings, "adaptation_min_samples")
        assert settings.adaptation_max_delta_per_update > 0
        assert settings.adaptation_min_samples > 0


class TestScoringDeterminism:
    """P1: Scoring produces deterministic results."""

    def test_default_scorer_deterministic(self):
        from scoring_service.plugins.builtin import DefaultScorer
        scorer = DefaultScorer()
        item = {"event_count": 5, "growth_rate": 2.0, "total_value": 10.0}
        score1 = scorer.score(item)
        score2 = scorer.score(item)
        assert score1 == score2, f"Non-deterministic: {score1} != {score2}"

    def test_scorer_respects_weights(self):
        from scoring_service.plugins.builtin import DefaultScorer
        scorer = DefaultScorer()
        item = {"event_count": 5, "growth_rate": 2.0, "total_value": 10.0}
        score_default = scorer.score(item)
        score_weighted = scorer.score(item, {"event_count": 10.0, "growth_rate": 1.0, "total_value": 0.5})
        assert score_default != score_weighted


class TestDecisionExplainability:
    """P1: Decision outputs include reasoning."""

    def test_trend_has_explanation_fields(self):
        """DecisionTrace model has all required explanation fields."""
        from scoring_service.db.models import DecisionTrace
        cols = {c.name for c in DecisionTrace.__table__.columns}
        required = {"explanation_text", "explanation_json", "factor_contributions_json", "input_summary_json"}
        assert required.issubset(cols), f"Missing: {required - cols}"


class TestCleanBootstrapSQLite:
    """P0: Models can create clean schema in SQLite (structure validation)."""

    def test_create_all_tables(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert len(tables) >= 60
