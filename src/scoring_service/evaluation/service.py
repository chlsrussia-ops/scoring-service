"""Evaluation services: benchmark execution, comparison, regression detection."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from scoring_service.config import Settings
from scoring_service.evaluation.metrics import compute_all_metrics, score_distribution_stats
from scoring_service.evaluation.repository import (
    BenchmarkRepository, ComparisonRepository, EvalRunRepository, GuardrailRepository,
)

logger = logging.getLogger("scoring_service")


class BenchmarkService:
    """Manages benchmark datasets and items."""

    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.repo = BenchmarkRepository(db)

    def create_dataset(
        self, tenant_id: str | None, name: str, benchmark_type: str = "ranking",
        description: str | None = None, version: int = 1, tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> Any:
        return self.repo.create_dataset(
            tenant_id=tenant_id, name=name, benchmark_type=benchmark_type,
            description=description, version=version,
            tags=tags or [], metadata_json=metadata or {},
        )

    def import_items(self, dataset_id: int, items: list[dict[str, Any]]) -> dict[str, Any]:
        ds = self.repo.get_dataset(dataset_id)
        if not ds:
            return {"error": "dataset not found"}
        if ds.is_frozen:
            return {"error": "dataset is frozen, cannot add items"}
        count = self.repo.add_items(dataset_id, items)
        self.db.commit()
        return {"imported": count, "dataset_id": dataset_id, "total_items": ds.item_count}

    def list_datasets(self, tenant_id: str | None = None) -> list[Any]:
        return self.repo.list_datasets(tenant_id)

    def get_dataset(self, dataset_id: int) -> Any:
        return self.repo.get_dataset(dataset_id)

    def freeze(self, dataset_id: int) -> Any:
        return self.repo.freeze_dataset(dataset_id)

    def get_segments(self, dataset_id: int) -> list[dict[str, Any]]:
        return self.repo.get_segments(dataset_id)


class EvaluationExecutionService:
    """Executes evaluation runs against benchmark datasets."""

    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.bench_repo = BenchmarkRepository(db)
        self.run_repo = EvalRunRepository(db)

    def execute_run(
        self, dataset_id: int, strategy_name: str, strategy_version: str = "v1",
        tenant_id: str | None = None, config: dict | None = None,
        scorer_fn: Any = None,
    ) -> dict[str, Any]:
        """Execute a full evaluation run.
        
        scorer_fn: callable(input_json) -> {"score": float, "rank": int, "label": str}
        If not provided, uses the built-in scoring engine.
        """
        ds = self.bench_repo.get_dataset(dataset_id)
        if not ds:
            return {"error": "dataset not found"}

        items = self.bench_repo.get_items(dataset_id)
        if not items:
            return {"error": "dataset has no items"}

        run = self.run_repo.create_run(
            tenant_id=tenant_id, dataset_id=dataset_id,
            strategy_name=strategy_name, strategy_version=strategy_version,
            config_json=config or {}, status="running",
            started_at=datetime.now(timezone.utc),
        )
        self.db.flush()

        start_time = time.time()
        eval_items = []

        try:
            for item in items:
                if scorer_fn:
                    result = scorer_fn(item.input_json)
                else:
                    result = self._default_score(item.input_json)

                predicted_score = result.get("score", 0.0)
                predicted_rank = result.get("rank")
                predicted_label = result.get("label")
                
                is_hit = self._compute_hit(item, predicted_score, predicted_rank, predicted_label)
                rank_delta = (predicted_rank - item.expected_rank) if predicted_rank and item.expected_rank else None

                self.run_repo.save_item_result(
                    run_id=run.id, benchmark_item_id=item.id,
                    predicted_score=predicted_score, predicted_rank=predicted_rank,
                    predicted_label=predicted_label, is_hit=is_hit,
                    rank_delta=rank_delta,
                    details_json={"input_id": item.external_id},
                )

                eval_items.append({
                    "predicted_score": predicted_score,
                    "predicted_rank": predicted_rank,
                    "is_hit": is_hit,
                    "relevance_grade": item.relevance_grade or (1 if is_hit else 0),
                    "segment_category": item.segment_category,
                    "segment_value": item.segment_value,
                })

            # Compute global metrics
            global_metrics = compute_all_metrics(eval_items)
            for name, value in global_metrics.items():
                if isinstance(value, (int, float)):
                    self.run_repo.save_metric(
                        run_id=run.id, metric_name=name,
                        metric_value=float(value), sample_count=len(eval_items),
                    )

            # Compute segment metrics
            segments = {}
            for ei in eval_items:
                key = (ei.get("segment_category"), ei.get("segment_value"))
                if key[0]:
                    segments.setdefault(key, []).append(ei)
            
            for (seg_cat, seg_val), seg_items in segments.items():
                seg_metrics = compute_all_metrics(seg_items)
                for name, value in seg_metrics.items():
                    if isinstance(value, (int, float)):
                        self.run_repo.save_metric(
                            run_id=run.id, metric_name=name,
                            metric_value=float(value), sample_count=len(seg_items),
                            segment_category=seg_cat, segment_value=seg_val,
                        )

            elapsed = int((time.time() - start_time) * 1000)
            run.status = "completed"
            run.item_count = len(items)
            run.duration_ms = elapsed
            run.completed_at = datetime.now(timezone.utc)
            self.db.commit()

            logger.info(
                "eval_run_completed run_id=%d dataset=%d strategy=%s items=%d duration_ms=%d",
                run.id, dataset_id, strategy_name, len(items), elapsed,
            )
            return {
                "run_id": run.id, "status": "completed",
                "items": len(items), "duration_ms": elapsed,
                "metrics": global_metrics,
            }

        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)[:500]
            self.db.commit()
            logger.exception("eval_run_failed run_id=%d", run.id)
            return {"error": str(exc)[:500], "run_id": run.id}

    def _default_score(self, input_json: dict) -> dict[str, Any]:
        """Use built-in scoring engine as default strategy."""
        from scoring_service.contracts import ScoreRequest
        from scoring_service.services.scoring_service import ScoringService
        
        request = ScoreRequest(
            payload=input_json, request_id="eval", source="benchmark",
        )
        service = ScoringService(self.settings)
        result, review = service.execute(request)
        return {
            "score": result.final_score,
            "label": review.label,
        }

    def _compute_hit(self, item, predicted_score, predicted_rank, predicted_label) -> bool:
        if item.expected_label and predicted_label:
            return predicted_label == item.expected_label
        if item.expected_rank and predicted_rank:
            return predicted_rank <= item.expected_rank
        if item.expected_score is not None and predicted_score is not None:
            return predicted_score >= item.expected_score * 0.8
        if item.relevance_grade is not None:
            return item.relevance_grade > 0
        return False

    def get_run_result(self, run_id: int) -> dict[str, Any]:
        run = self.run_repo.get_run(run_id)
        if not run:
            return {"error": "run not found"}
        metrics = self.run_repo.get_metrics(run_id)
        return {
            "run_id": run.id, "status": run.status,
            "strategy": run.strategy_name, "version": run.strategy_version,
            "items": run.item_count, "duration_ms": run.duration_ms,
            "metrics": {m.metric_name: {"value": m.metric_value, "k": m.k, "segment": m.segment_category, "segment_value": m.segment_value, "samples": m.sample_count} for m in metrics},
            "error": run.error_message,
        }

    def get_failures(self, run_id: int, limit: int = 50) -> list[dict[str, Any]]:
        failures = self.run_repo.get_failures(run_id, limit)
        return [
            {
                "item_id": f.benchmark_item_id, "predicted_score": f.predicted_score,
                "predicted_rank": f.predicted_rank, "predicted_label": f.predicted_label,
                "rank_delta": f.rank_delta,
            }
            for f in failures
        ]


class ComparisonService:
    """Compares evaluation runs and detects regressions."""

    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.run_repo = EvalRunRepository(db)
        self.comp_repo = ComparisonRepository(db)
        self.guardrail_repo = GuardrailRepository(db)

    def compare_runs(self, baseline_run_id: int, candidate_run_id: int) -> dict[str, Any]:
        baseline = self.run_repo.get_run(baseline_run_id)
        candidate = self.run_repo.get_run(candidate_run_id)
        if not baseline or not candidate:
            return {"error": "run not found"}
        if baseline.dataset_id != candidate.dataset_id:
            return {"error": "runs must be on the same dataset"}

        base_metrics = {m.metric_name: m.metric_value for m in self.run_repo.get_metrics(baseline_run_id) if not m.segment_category}
        cand_metrics = {m.metric_name: m.metric_value for m in self.run_repo.get_metrics(candidate_run_id) if not m.segment_category}

        metric_diffs = {}
        regression_flags = []
        improvement_flags = []

        for name in set(base_metrics) | set(cand_metrics):
            bv = base_metrics.get(name)
            cv = cand_metrics.get(name)
            if bv is not None and cv is not None:
                delta = cv - bv
                pct = (delta / abs(bv) * 100) if bv != 0 else 0
                metric_diffs[name] = {"baseline": round(bv, 4), "candidate": round(cv, 4), "delta": round(delta, 4), "pct": round(pct, 1)}
                if delta < -0.01 and name.startswith(("precision", "recall", "ndcg", "hit_rate", "map")):
                    regression_flags.append(f"{name}: {bv:.4f} -> {cv:.4f} ({pct:+.1f}%)")
                elif delta > 0.01 and name.startswith(("precision", "recall", "ndcg", "hit_rate", "map")):
                    improvement_flags.append(f"{name}: {bv:.4f} -> {cv:.4f} ({pct:+.1f}%)")

        # Segment diffs
        base_seg = {}
        for m in self.run_repo.get_metrics(baseline_run_id):
            if m.segment_category:
                key = f"{m.segment_category}:{m.segment_value}:{m.metric_name}"
                base_seg[key] = m.metric_value
        cand_seg = {}
        for m in self.run_repo.get_metrics(candidate_run_id):
            if m.segment_category:
                key = f"{m.segment_category}:{m.segment_value}:{m.metric_name}"
                cand_seg[key] = m.metric_value

        segment_diffs = {}
        for key in set(base_seg) | set(cand_seg):
            bv = base_seg.get(key)
            cv = cand_seg.get(key)
            if bv is not None and cv is not None:
                segment_diffs[key] = {"baseline": round(bv, 4), "candidate": round(cv, 4), "delta": round(cv - bv, 4)}

        # Guardrail check
        guardrails = self.guardrail_repo.list_active(baseline.tenant_id)
        violations = []
        for g in guardrails:
            val = cand_metrics.get(g.metric_name)
            if val is None:
                continue
            if g.min_value is not None and val < g.min_value:
                violations.append(f"{g.severity}: {g.metric_name}={val:.4f} below min {g.min_value}")
            if g.max_regression_delta is not None:
                bv = base_metrics.get(g.metric_name)
                if bv is not None:
                    delta = bv - val
                    if delta > g.max_regression_delta:
                        violations.append(f"{g.severity}: {g.metric_name} regressed by {delta:.4f} (max allowed: {g.max_regression_delta})")

        # Verdict
        if violations and any(v.startswith("error") for v in violations):
            verdict = "regression"
            verdict_reason = f"Guardrail violations: {'; '.join(violations)}"
        elif regression_flags and not improvement_flags:
            verdict = "worse"
            verdict_reason = f"Regressions in: {', '.join(f.split(':')[0] for f in regression_flags)}"
        elif improvement_flags and not regression_flags:
            verdict = "better"
            verdict_reason = f"Improvements in: {', '.join(f.split(':')[0] for f in improvement_flags)}"
        elif not regression_flags and not improvement_flags:
            verdict = "neutral"
            verdict_reason = "No significant changes"
        else:
            verdict = "mixed"
            verdict_reason = f"Improvements: {len(improvement_flags)}, Regressions: {len(regression_flags)}"

        comp = self.comp_repo.create(
            baseline_run_id=baseline_run_id, candidate_run_id=candidate_run_id,
            dataset_id=baseline.dataset_id, verdict=verdict, verdict_reason=verdict_reason,
            metric_diffs_json=metric_diffs, segment_diffs_json=segment_diffs,
            regression_flags=regression_flags, improvement_flags=improvement_flags,
            guardrail_violations=violations,
        )
        self.db.commit()

        return {
            "comparison_id": comp.id, "verdict": verdict, "verdict_reason": verdict_reason,
            "metric_diffs": metric_diffs, "regression_flags": regression_flags,
            "improvement_flags": improvement_flags, "guardrail_violations": violations,
            "ci_pass": verdict not in ("regression",),
        }
