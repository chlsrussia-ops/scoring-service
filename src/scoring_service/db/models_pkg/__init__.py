"""Models package — re-exports all models from split files.

All existing imports like `from scoring_service.db.models import Trend` continue to work.
Canonical split files:
  _base.py — Base, _utcnow
  core.py — ScoreRecord, Idempotency, Jobs, Outbox, DLQ, Source Health, Audit
  platform.py — Tenancy, Policies, Pipeline, Explainability, Usage, Exports, Widgets
  product.py — DataSources, LLM, Digests, Demo
  adaptation.py — Feedback, Evaluation, Adaptive Scoring, Goals, Experiments, Source Trust
  evaluation.py — Benchmarks, Eval Runs, Metrics, Comparisons, Guardrails
  workflows.py — WorkflowRun, WorkflowStep, ScheduledJob
"""
from scoring_service.db.models_pkg._base import Base, _utcnow  # noqa: F401
from scoring_service.db.models_pkg.core import *  # noqa: F401,F403
from scoring_service.db.models_pkg.platform import *  # noqa: F401,F403
from scoring_service.db.models_pkg.product import *  # noqa: F401,F403
from scoring_service.db.models_pkg.adaptation import *  # noqa: F401,F403
from scoring_service.db.models_pkg.evaluation import *  # noqa: F401,F403
from scoring_service.db.models_pkg.workflows import *  # noqa: F401,F403
