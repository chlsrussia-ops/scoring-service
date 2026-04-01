"""Observability — Prometheus metrics + structured event emitters."""
from __future__ import annotations

import logging
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

from scoring_service.correlation import get_correlation_id

logger = logging.getLogger("scoring_service")

# ── HTTP metrics ─────────────────────────────────────────────────────
REQUEST_COUNTER = Counter(
    "scoring_http_requests_total",
    "Total scoring operations",
    ["operation", "status"],
)
SCORE_COUNTER = Counter(
    "scoring_completed_total",
    "Completed scoring",
    ["review_label"],
)
SCORE_HISTOGRAM = Histogram(
    "scoring_final_score",
    "Score distribution",
    buckets=(0, 10, 20, 40, 60, 80, 100),
)

# ── Job metrics ──────────────────────────────────────────────────────
JOB_ENQUEUED = Counter("scoring_jobs_enqueued_total", "Jobs enqueued", ["job_type"])
JOB_COMPLETED = Counter("scoring_jobs_completed_total", "Jobs completed", ["job_type", "status"])
JOB_RETRIES = Counter("scoring_jobs_retries_total", "Job retries", ["job_type"])
JOB_QUEUE_DEPTH = Gauge("scoring_jobs_queue_depth", "Pending jobs in queue")
JOB_PROCESSING_SECONDS = Histogram(
    "scoring_job_processing_seconds",
    "Job processing duration",
    ["job_type"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60),
)

# ── Outbox metrics ───────────────────────────────────────────────────
OUTBOX_PENDING = Gauge("scoring_outbox_pending", "Pending outbox events")
OUTBOX_DISPATCHED = Counter("scoring_outbox_dispatched_total", "Dispatched outbox events")
OUTBOX_FAILED = Counter("scoring_outbox_failed_total", "Failed outbox dispatches")

# ── Failure metrics ──────────────────────────────────────────────────
FAILURE_TOTAL = Counter("scoring_failures_total", "Total failures recorded", ["entity_type"])
DLQ_DEPTH = Gauge("scoring_dlq_depth", "Dead letter queue depth")

# ── Source metrics ───────────────────────────────────────────────────
SOURCE_REQUESTS = Counter("scoring_source_requests_total", "Per-source requests", ["source"])
SOURCE_ERRORS = Counter("scoring_source_errors_total", "Per-source errors", ["source"])
SOURCES_QUARANTINED = Gauge("scoring_sources_quarantined", "Quarantined sources count")

# ── Circuit breaker metrics ──────────────────────────────────────────
CIRCUIT_STATE = Gauge("scoring_circuit_breaker_open", "Circuit breaker open (1=open)", ["name"])

# ── Delivery metrics ────────────────────────────────────────────────
DELIVERY_ATTEMPTS = Counter(
    "scoring_delivery_attempts_total", "Delivery attempts", ["channel", "status"]
)


def emit_metric(name: str, value: float, **tags: Any) -> None:
    cid = get_correlation_id()
    logger.debug("metric name=%s value=%s cid=%s tags=%s", name, value, cid, tags)


def emit_event(name: str, **payload: Any) -> None:
    cid = get_correlation_id()
    logger.info("event name=%s cid=%s payload=%s", name, cid, payload)
