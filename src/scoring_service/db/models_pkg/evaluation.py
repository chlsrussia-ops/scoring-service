"""Auto-split from monolithic models.py."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean, DateTime, Float, Index, Integer, JSON, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from scoring_service.db.models_pkg._base import Base, _utcnow

import enum
from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship


class BenchmarkDataset(Base):
    __tablename__ = "benchmark_datasets"
    __table_args__ = (
        Index("ix_benchmark_ds_tenant", "tenant_id"),
        UniqueConstraint("tenant_id", "name", "version", name="uq_benchmark_ds_name_ver"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    benchmark_type: Mapped[str] = mapped_column(String(64), nullable=False, default="ranking")  # ranking/classification/scoring
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class BenchmarkItem(Base):
    __tablename__ = "benchmark_items"
    __table_args__ = (
        Index("ix_bench_item_dataset", "dataset_id"),
        Index("ix_bench_item_segment", "segment_category", "segment_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(Integer, ForeignKey("benchmark_datasets.id", ondelete="CASCADE"), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    input_json: Mapped[dict] = mapped_column(JSON, nullable=False)  # the item to rank/score
    expected_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_label: Mapped[str | None] = mapped_column(String(64), nullable=True)  # relevant/irrelevant/high/low
    relevance_grade: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-4 graded relevance for nDCG
    segment_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    segment_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(32), nullable=True)  # easy/medium/hard
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class EvalRunRecord(Base):
    __tablename__ = "eval_run_records"
    __table_args__ = (
        Index("ix_eval_rec_tenant", "tenant_id"),
        Index("ix_eval_rec_dataset", "dataset_id"),
        Index("ix_eval_rec_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dataset_id: Mapped[int] = mapped_column(Integer, ForeignKey("benchmark_datasets.id", ondelete="CASCADE"), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1")
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending/running/completed/failed
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class EvalItemResult(Base):
    __tablename__ = "eval_item_results"
    __table_args__ = (
        Index("ix_eval_item_run", "run_id"),
        Index("ix_eval_item_benchmark", "benchmark_item_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("eval_run_records.id", ondelete="CASCADE"), nullable=False)
    benchmark_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("benchmark_items.id", ondelete="CASCADE"), nullable=False)
    predicted_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    predicted_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # True if item appeared in top-k
    rank_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)  # predicted_rank - expected_rank
    details_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class EvalMetricResult(Base):
    __tablename__ = "eval_metric_results"
    __table_args__ = (
        Index("ix_eval_metric_run", "run_id"),
        Index("ix_eval_metric_name", "metric_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("eval_run_records.id", ondelete="CASCADE"), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    k: Mapped[int | None] = mapped_column(Integer, nullable=True)  # for @k metrics
    segment_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    segment_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class EvalComparison(Base):
    __tablename__ = "eval_comparisons"
    __table_args__ = (
        Index("ix_eval_comp_baseline", "baseline_run_id"),
        Index("ix_eval_comp_candidate", "candidate_run_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    baseline_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("eval_run_records.id", ondelete="CASCADE"), nullable=False)
    candidate_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("eval_run_records.id", ondelete="CASCADE"), nullable=False)
    dataset_id: Mapped[int] = mapped_column(Integer, nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # better/worse/neutral/regression/pending
    verdict_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_diffs_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    segment_diffs_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    regression_flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    improvement_flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    guardrail_violations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class RegressionGuardrail(Base):
    __tablename__ = "regression_guardrails"
    __table_args__ = (
        Index("ix_guardrail_tenant", "tenant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_regression_delta: Mapped[float | None] = mapped_column(Float, nullable=True)  # max allowed drop
    segment_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    segment_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="error")  # error/warning
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


