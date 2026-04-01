"""Tests for Ranking Evaluation Framework."""
from __future__ import annotations
import pytest
from scoring_service.config import Settings
from scoring_service.evaluation.metrics import (
    precision_at_k, recall_at_k, hit_rate, ndcg_at_k,
    average_precision, compute_all_metrics, score_distribution_stats,
    calibration_error,
)


class TestMetrics:
    def test_precision_at_k(self):
        relevant = [True, False, True, False, True]
        assert precision_at_k(relevant, 3) == pytest.approx(2/3, abs=0.01)
        assert precision_at_k(relevant, 5) == pytest.approx(3/5, abs=0.01)
        assert precision_at_k(relevant, 1) == 1.0
        assert precision_at_k([], 5) == 0.0

    def test_recall_at_k(self):
        relevant = [True, False, True, False, True]
        assert recall_at_k(relevant, 3, 3) == pytest.approx(2/3, abs=0.01)
        assert recall_at_k(relevant, 5, 3) == 1.0
        assert recall_at_k(relevant, 1, 3) == pytest.approx(1/3, abs=0.01)

    def test_hit_rate(self):
        assert hit_rate([True, False, False], 1) == 1.0
        assert hit_rate([False, False, True], 1) == 0.0
        assert hit_rate([False, False, True], 3) == 1.0
        assert hit_rate([False, False, False], 3) == 0.0

    def test_ndcg_at_k(self):
        # Perfect ranking
        assert ndcg_at_k([3, 2, 1, 0], 4) == 1.0
        # Reverse ranking
        reverse = ndcg_at_k([0, 1, 2, 3], 4)
        assert 0 < reverse < 1
        # Empty
        assert ndcg_at_k([], 5) == 0.0
        assert ndcg_at_k([0, 0, 0], 3) == 0.0

    def test_average_precision(self):
        assert average_precision([True, True, True]) == 1.0
        assert average_precision([False, False, False]) == 0.0
        ap = average_precision([True, False, True, False, True])
        assert 0 < ap <= 1

    def test_compute_all_metrics(self):
        items = [
            {"predicted_rank": 1, "predicted_score": 0.9, "is_hit": True, "relevance_grade": 2},
            {"predicted_rank": 2, "predicted_score": 0.8, "is_hit": True, "relevance_grade": 1},
            {"predicted_rank": 3, "predicted_score": 0.7, "is_hit": False, "relevance_grade": 0},
            {"predicted_rank": 4, "predicted_score": 0.5, "is_hit": True, "relevance_grade": 1},
            {"predicted_rank": 5, "predicted_score": 0.3, "is_hit": False, "relevance_grade": 0},
        ]
        metrics = compute_all_metrics(items, k_values=[3, 5])
        assert "precision@3" in metrics
        assert "ndcg@5" in metrics
        assert "map" in metrics
        assert metrics["total_items"] == 5
        assert metrics["total_relevant"] == 3

    def test_score_distribution(self):
        scores = [0.1, 0.3, 0.5, 0.7, 0.9]
        stats = score_distribution_stats(scores)
        assert stats["mean"] == pytest.approx(0.5, abs=0.01)
        assert stats["min"] == 0.1
        assert stats["max"] == 0.9

    def test_calibration_error(self):
        scores = [0.1, 0.3, 0.5, 0.7, 0.9]
        labels = [False, False, True, True, True]
        result = calibration_error(scores, labels, n_bins=2)
        assert "ece" in result
        assert len(result["bins"]) >= 1


@pytest.fixture
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from scoring_service.db.models import Base
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def settings():
    return Settings(database_url="sqlite:///:memory:")


class TestBenchmarkService:
    def test_create_dataset(self, db_session, settings):
        from scoring_service.evaluation.service import BenchmarkService
        svc = BenchmarkService(db_session, settings)
        ds = svc.create_dataset(tenant_id="test", name="ranking-v1", benchmark_type="ranking")
        db_session.commit()
        assert ds.id is not None
        assert ds.name == "ranking-v1"

    def test_import_items(self, db_session, settings):
        from scoring_service.evaluation.service import BenchmarkService
        svc = BenchmarkService(db_session, settings)
        ds = svc.create_dataset(tenant_id="test", name="test-ds")
        db_session.commit()
        result = svc.import_items(ds.id, [
            {"input_json": {"title": "AI trends"}, "expected_label": "relevant", "relevance_grade": 2, "segment_category": "tech"},
            {"input_json": {"title": "Old news"}, "expected_label": "irrelevant", "relevance_grade": 0, "segment_category": "tech"},
        ])
        assert result["imported"] == 2

    def test_freeze_dataset(self, db_session, settings):
        from scoring_service.evaluation.service import BenchmarkService
        svc = BenchmarkService(db_session, settings)
        ds = svc.create_dataset(tenant_id="test", name="freeze-test")
        db_session.commit()
        svc.freeze(ds.id)
        db_session.commit()
        result = svc.import_items(ds.id, [{"input_json": {}}])
        assert "error" in result


class TestEvaluationExecution:
    def test_execute_run(self, db_session, settings):
        from scoring_service.evaluation.service import BenchmarkService, EvaluationExecutionService
        bench = BenchmarkService(db_session, settings)
        ds = bench.create_dataset(tenant_id="test", name="exec-test")
        db_session.commit()
        bench.import_items(ds.id, [
            {"input_json": {"name": "item1", "score": 10}, "expected_label": "excellent", "relevance_grade": 2},
            {"input_json": {"name": "item2", "score": 5}, "expected_label": "approved", "relevance_grade": 1},
            {"input_json": {"name": "item3", "score": 1}, "expected_label": "manual_review", "relevance_grade": 0},
        ])

        eval_svc = EvaluationExecutionService(db_session, settings)
        result = eval_svc.execute_run(ds.id, strategy_name="default", tenant_id="test")
        assert result.get("status") == "completed" or "run_id" in result
        assert result.get("items", 0) >= 0


class TestComparisonService:
    def test_compare_runs(self, db_session, settings):
        from scoring_service.evaluation.repository import EvalRunRepository
        from scoring_service.evaluation.service import ComparisonService
        repo = EvalRunRepository(db_session)
        run1 = repo.create_run(dataset_id=1, strategy_name="baseline", tenant_id="test")
        repo.save_metric(run_id=run1.id, metric_name="precision@5", metric_value=0.8, sample_count=10)
        repo.save_metric(run_id=run1.id, metric_name="ndcg@5", metric_value=0.7, sample_count=10)
        run2 = repo.create_run(dataset_id=1, strategy_name="candidate", tenant_id="test")
        repo.save_metric(run_id=run2.id, metric_name="precision@5", metric_value=0.85, sample_count=10)
        repo.save_metric(run_id=run2.id, metric_name="ndcg@5", metric_value=0.65, sample_count=10)
        run1.status = "completed"
        run2.status = "completed"
        run1.dataset_id = 1
        run2.dataset_id = 1
        db_session.commit()

        comp_svc = ComparisonService(db_session, settings)
        result = comp_svc.compare_runs(run1.id, run2.id)
        assert "verdict" in result
        assert "metric_diffs" in result
        assert result["verdict"] == "mixed"  # one up, one down


class TestGuardrails:
    def test_guardrail_violation(self, db_session, settings):
        from scoring_service.evaluation.repository import EvalRunRepository, GuardrailRepository
        from scoring_service.evaluation.service import ComparisonService

        guard_repo = GuardrailRepository(db_session)
        guard_repo.create(metric_name="precision@5", min_value=0.7, severity="error")
        db_session.flush()

        run_repo = EvalRunRepository(db_session)
        run1 = run_repo.create_run(dataset_id=1, strategy_name="baseline")
        run_repo.save_metric(run_id=run1.id, metric_name="precision@5", metric_value=0.8, sample_count=10)
        run2 = run_repo.create_run(dataset_id=1, strategy_name="candidate")
        run_repo.save_metric(run_id=run2.id, metric_name="precision@5", metric_value=0.5, sample_count=10)
        run1.status = "completed"
        run2.status = "completed"
        run1.dataset_id = 1
        run2.dataset_id = 1
        db_session.commit()

        comp_svc = ComparisonService(db_session, settings)
        result = comp_svc.compare_runs(run1.id, run2.id)
        assert result["verdict"] == "regression"
        assert len(result["guardrail_violations"]) > 0
        assert result["ci_pass"] is False
