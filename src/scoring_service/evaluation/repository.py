"""Repositories for evaluation entities."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from scoring_service.db.models import (
    BenchmarkDataset, BenchmarkItem, EvalComparison, EvalItemResult,
    EvalMetricResult, EvalRunRecord, RegressionGuardrail,
)


class BenchmarkRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_dataset(self, **kwargs: Any) -> BenchmarkDataset:
        ds = BenchmarkDataset(**kwargs)
        self.db.add(ds)
        self.db.flush()
        return ds

    def get_dataset(self, dataset_id: int) -> BenchmarkDataset | None:
        return self.db.get(BenchmarkDataset, dataset_id)

    def list_datasets(self, tenant_id: str | None = None, limit: int = 50) -> list[BenchmarkDataset]:
        q = self.db.query(BenchmarkDataset)
        if tenant_id:
            q = q.filter(BenchmarkDataset.tenant_id == tenant_id)
        return q.order_by(BenchmarkDataset.created_at.desc()).limit(limit).all()

    def add_items(self, dataset_id: int, items: list[dict[str, Any]]) -> int:
        count = 0
        for item_data in items:
            item = BenchmarkItem(dataset_id=dataset_id, **item_data)
            self.db.add(item)
            count += 1
        self.db.flush()
        # Update item_count
        ds = self.get_dataset(dataset_id)
        if ds:
            ds.item_count = (
                self.db.query(func.count(BenchmarkItem.id))
                .filter(BenchmarkItem.dataset_id == dataset_id)
                .scalar() or 0
            )
            self.db.flush()
        return count

    def get_items(self, dataset_id: int, segment_category: str | None = None, segment_value: str | None = None) -> list[BenchmarkItem]:
        q = self.db.query(BenchmarkItem).filter(BenchmarkItem.dataset_id == dataset_id)
        if segment_category:
            q = q.filter(BenchmarkItem.segment_category == segment_category)
        if segment_value:
            q = q.filter(BenchmarkItem.segment_value == segment_value)
        return q.order_by(BenchmarkItem.id).all()

    def freeze_dataset(self, dataset_id: int) -> BenchmarkDataset | None:
        ds = self.get_dataset(dataset_id)
        if ds:
            ds.is_frozen = True
            self.db.flush()
        return ds

    def get_segments(self, dataset_id: int) -> list[dict[str, Any]]:
        rows = (
            self.db.query(BenchmarkItem.segment_category, BenchmarkItem.segment_value, func.count())
            .filter(BenchmarkItem.dataset_id == dataset_id, BenchmarkItem.segment_category.isnot(None))
            .group_by(BenchmarkItem.segment_category, BenchmarkItem.segment_value)
            .all()
        )
        return [{"category": r[0], "value": r[1], "count": r[2]} for r in rows]


class EvalRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_run(self, **kwargs: Any) -> EvalRunRecord:
        run = EvalRunRecord(**kwargs)
        self.db.add(run)
        self.db.flush()
        return run

    def get_run(self, run_id: int) -> EvalRunRecord | None:
        return self.db.get(EvalRunRecord, run_id)

    def list_runs(self, dataset_id: int | None = None, tenant_id: str | None = None, limit: int = 50) -> list[EvalRunRecord]:
        q = self.db.query(EvalRunRecord)
        if dataset_id:
            q = q.filter(EvalRunRecord.dataset_id == dataset_id)
        if tenant_id:
            q = q.filter(EvalRunRecord.tenant_id == tenant_id)
        return q.order_by(EvalRunRecord.created_at.desc()).limit(limit).all()

    def save_item_result(self, **kwargs: Any) -> EvalItemResult:
        r = EvalItemResult(**kwargs)
        self.db.add(r)
        self.db.flush()
        return r

    def save_metric(self, **kwargs: Any) -> EvalMetricResult:
        m = EvalMetricResult(**kwargs)
        self.db.add(m)
        self.db.flush()
        return m

    def get_metrics(self, run_id: int) -> list[EvalMetricResult]:
        return (
            self.db.query(EvalMetricResult)
            .filter(EvalMetricResult.run_id == run_id)
            .order_by(EvalMetricResult.metric_name)
            .all()
        )

    def get_item_results(self, run_id: int) -> list[EvalItemResult]:
        return (
            self.db.query(EvalItemResult)
            .filter(EvalItemResult.run_id == run_id)
            .all()
        )

    def get_failures(self, run_id: int, limit: int = 50) -> list[EvalItemResult]:
        return (
            self.db.query(EvalItemResult)
            .filter(EvalItemResult.run_id == run_id, EvalItemResult.is_hit == False)
            .order_by(EvalItemResult.rank_delta.desc())
            .limit(limit)
            .all()
        )


class ComparisonRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs: Any) -> EvalComparison:
        c = EvalComparison(**kwargs)
        self.db.add(c)
        self.db.flush()
        return c

    def get(self, comparison_id: int) -> EvalComparison | None:
        return self.db.get(EvalComparison, comparison_id)

    def list_for_dataset(self, dataset_id: int, limit: int = 20) -> list[EvalComparison]:
        return (
            self.db.query(EvalComparison)
            .filter(EvalComparison.dataset_id == dataset_id)
            .order_by(EvalComparison.created_at.desc())
            .limit(limit)
            .all()
        )


class GuardrailRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs: Any) -> RegressionGuardrail:
        g = RegressionGuardrail(**kwargs)
        self.db.add(g)
        self.db.flush()
        return g

    def list_active(self, tenant_id: str | None = None) -> list[RegressionGuardrail]:
        q = self.db.query(RegressionGuardrail).filter(RegressionGuardrail.is_active == True)
        if tenant_id:
            q = q.filter(
                (RegressionGuardrail.tenant_id == tenant_id) | (RegressionGuardrail.tenant_id.is_(None))
            )
        return q.all()
