"""Schema reconciliation: align index names, add missing indexes, remove phantom columns.

Fixes drift between SQLAlchemy models and DB state accumulated over stages 1-5.

Issues resolved:
- 15 indexes renamed to match SQLAlchemy auto-naming convention
- 2 missing indexes added (data_sources.tenant_id, llm_generations.tenant_id)
- 2 phantom columns removed from score_records (tenant_id, workspace_id —
  added in 0003 but no longer in model; FK constraints already absent)
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_schema_reconciliation"
down_revision = "bb614cd4019d"


def upgrade() -> None:
    # ── Rename indexes to match SQLAlchemy model auto-naming ──────
    _rename_index("alert_policies", "ix_alert_policies_pv", "ix_alert_policies_policy_version_id")
    _rename_index("alerts", "ix_alerts_tenant", "ix_alerts_tenant_id")
    _rename_index("backfill_requests", "ix_backfill_requests_tenant", "ix_backfill_requests_tenant_id")
    _rename_index("demo_runs", "ix_demo_runs_tenant", "ix_demo_runs_tenant_id")
    _rename_index("detection_rules", "ix_detection_rules_pv", "ix_detection_rules_policy_version_id")
    _rename_index("digest_reports", "ix_digest_reports_tenant", "ix_digest_reports_tenant_id")
    _rename_index("export_jobs", "ix_export_jobs_tenant", "ix_export_jobs_tenant_id")
    _rename_index("processing_checkpoints", "ix_processing_checkpoints_tenant", "ix_processing_checkpoints_tenant_id")
    _rename_index("quota_enforcement_log", "ix_quota_log_tenant", "ix_quota_enforcement_log_tenant_id")
    _rename_index("rebuild_requests", "ix_rebuild_requests_tenant", "ix_rebuild_requests_tenant_id")
    _rename_index("scoring_profiles", "ix_scoring_profiles_pv", "ix_scoring_profiles_policy_version_id")
    _rename_index("suppression_policies", "ix_suppression_policies_pv", "ix_suppression_policies_policy_version_id")
    _rename_index("trend_evidence", "ix_trend_evidence_trend", "ix_trend_evidence_trend_id")
    _rename_index("widget_configs", "ix_widget_configs_tenant", "ix_widget_configs_tenant_id")

    # ── Add missing indexes ──────────────────────────────────────
    op.create_index("ix_data_sources_tenant_id", "data_sources", ["tenant_id"])
    op.create_index("ix_llm_generations_tenant_id", "llm_generations", ["tenant_id"])

    # ── Remove phantom columns from score_records ────────────────
    # Added in 0003 but model no longer defines them.
    # FK constraints were never materialized (absent in pg_constraint).
    op.drop_index("ix_score_records_workspace_id", table_name="score_records")
    op.drop_index("ix_score_records_tenant_id", table_name="score_records")
    op.drop_column("score_records", "workspace_id")
    op.drop_column("score_records", "tenant_id")


def downgrade() -> None:
    # Restore phantom columns
    op.add_column("score_records", sa.Column("tenant_id", sa.String(64), nullable=True))
    op.add_column("score_records", sa.Column("workspace_id", sa.String(64), nullable=True))
    op.create_index("ix_score_records_tenant_id", "score_records", ["tenant_id"])
    op.create_index("ix_score_records_workspace_id", "score_records", ["workspace_id"])

    # Drop added indexes
    op.drop_index("ix_llm_generations_tenant_id", table_name="llm_generations")
    op.drop_index("ix_data_sources_tenant_id", table_name="data_sources")

    # Rename indexes back to original short names
    _rename_index("widget_configs", "ix_widget_configs_tenant_id", "ix_widget_configs_tenant")
    _rename_index("trend_evidence", "ix_trend_evidence_trend_id", "ix_trend_evidence_trend")
    _rename_index("suppression_policies", "ix_suppression_policies_policy_version_id", "ix_suppression_policies_pv")
    _rename_index("scoring_profiles", "ix_scoring_profiles_policy_version_id", "ix_scoring_profiles_pv")
    _rename_index("rebuild_requests", "ix_rebuild_requests_tenant_id", "ix_rebuild_requests_tenant")
    _rename_index("quota_enforcement_log", "ix_quota_enforcement_log_tenant_id", "ix_quota_log_tenant")
    _rename_index("processing_checkpoints", "ix_processing_checkpoints_tenant_id", "ix_processing_checkpoints_tenant")
    _rename_index("export_jobs", "ix_export_jobs_tenant_id", "ix_export_jobs_tenant")
    _rename_index("digest_reports", "ix_digest_reports_tenant_id", "ix_digest_reports_tenant")
    _rename_index("detection_rules", "ix_detection_rules_policy_version_id", "ix_detection_rules_pv")
    _rename_index("demo_runs", "ix_demo_runs_tenant_id", "ix_demo_runs_tenant")
    _rename_index("backfill_requests", "ix_backfill_requests_tenant_id", "ix_backfill_requests_tenant")
    _rename_index("alerts", "ix_alerts_tenant_id", "ix_alerts_tenant")
    _rename_index("alert_policies", "ix_alert_policies_policy_version_id", "ix_alert_policies_pv")


def _rename_index(table: str, old_name: str, new_name: str) -> None:
    """Rename index via raw DDL. IF EXISTS makes it safe for partial reruns."""
    op.execute(f'ALTER INDEX IF EXISTS "{old_name}" RENAME TO "{new_name}"')
