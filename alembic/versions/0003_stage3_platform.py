"""Stage 3: Platform tables — tenancy, policies, pipeline, explanations, usage."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_stage3_platform"
down_revision = "0002_production_hardening"


def upgrade() -> None:
    # ── Tenancy ────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("plan", sa.String(64), nullable=False, server_default="free"),
        sa.Column("settings_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("settings_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_workspace_tenant_slug"),
    )
    op.create_index("ix_workspaces_tenant_id", "workspaces", ["tenant_id"])

    op.create_table(
        "api_clients",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("api_key", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False, server_default="default"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("scopes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_api_clients_tenant_id", "api_clients", ["tenant_id"])

    op.create_table(
        "tenant_memberships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(64), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "user_email", name="uq_membership_tenant_user"),
    )

    # Add tenant_id/workspace_id to score_records
    op.add_column("score_records", sa.Column("tenant_id", sa.String(64), nullable=True))
    op.add_column("score_records", sa.Column("workspace_id", sa.String(64), nullable=True))
    op.create_index("ix_score_records_tenant_id", "score_records", ["tenant_id"])
    op.create_index("ix_score_records_workspace_id", "score_records", ["workspace_id"])
    op.create_foreign_key("fk_score_records_tenant", "score_records", "tenants", ["tenant_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_score_records_workspace", "score_records", "workspaces", ["workspace_id"], ["id"], ondelete="SET NULL")

    # ── Policies ───────────────────────────────────────────────
    op.create_table(
        "policy_bundles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("policy_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("is_global", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_policy_bundles_tenant_id", "policy_bundles", ["tenant_id"])

    op.create_table(
        "policy_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bundle_id", sa.Integer(), sa.ForeignKey("policy_bundles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("bundle_id", "version", name="uq_policy_version"),
    )
    op.create_index("ix_policy_versions_bundle_id", "policy_versions", ["bundle_id"])

    op.create_table(
        "detection_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("policy_version_id", sa.Integer(), sa.ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("conditions_json", sa.JSON(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False, server_default="flag"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_detection_rules_pv", "detection_rules", ["policy_version_id"])

    op.create_table(
        "scoring_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("policy_version_id", sa.Integer(), sa.ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("weights_json", sa.JSON(), nullable=False),
        sa.Column("min_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("max_score", sa.Float(), nullable=False, server_default="100.0"),
    )
    op.create_index("ix_scoring_profiles_pv", "scoring_profiles", ["policy_version_id"])

    op.create_table(
        "alert_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("policy_version_id", sa.Integer(), sa.ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("conditions_json", sa.JSON(), nullable=False),
        sa.Column("channels", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_alert_policies_pv", "alert_policies", ["policy_version_id"])

    op.create_table(
        "suppression_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("policy_version_id", sa.Integer(), sa.ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("match_json", sa.JSON(), nullable=False),
        sa.Column("suppress_action", sa.String(64), nullable=False, server_default="drop"),
        sa.Column("ttl_seconds", sa.Integer(), nullable=False, server_default="3600"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_suppression_policies_pv", "suppression_policies", ["policy_version_id"])

    # ── Pipeline / Processing ──────────────────────────────────
    op.create_table(
        "processing_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("run_type", sa.String(64), nullable=False, server_default="scheduled"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("source_filter", sa.String(255), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("stats_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_processing_runs_tenant_id", "processing_runs", ["tenant_id"])

    op.create_table(
        "processing_stages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("processing_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("items_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_error", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_processing_stages_run_id", "processing_stages", ["run_id"])

    op.create_table(
        "processing_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("checkpoint_key", sa.String(255), nullable=False),
        sa.Column("checkpoint_value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "source", "checkpoint_key", name="uq_checkpoint"),
    )
    op.create_index("ix_processing_checkpoints_tenant", "processing_checkpoints", ["tenant_id"])

    op.create_table(
        "backfill_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("processing_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_filter", sa.String(255), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_backfill_requests_tenant", "backfill_requests", ["tenant_id"])

    op.create_table(
        "rebuild_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("processing_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target", sa.String(64), nullable=False, server_default="all"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_rebuild_requests_tenant", "rebuild_requests", ["tenant_id"])

    op.create_table(
        "pipeline_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=True),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(512), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("normalized_json", sa.JSON(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pipeline_events_tenant_source", "pipeline_events", ["tenant_id", "source"])
    op.create_index("ix_pipeline_events_ingested", "pipeline_events", ["tenant_id", "ingested_at"])

    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=True),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("topic", sa.String(255), nullable=False),
        sa.Column("value", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("run_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_signals_tenant_category", "signals", ["tenant_id", "category"])
    op.create_index("ix_signals_tenant_topic", "signals", ["tenant_id", "topic"])

    op.create_table(
        "trends",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=True),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("topic", sa.String(255), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("direction", sa.String(32), nullable=False, server_default="rising"),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("growth_rate", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("run_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_trends_tenant_score", "trends", ["tenant_id", "score"])
    op.create_index("ix_trends_tenant_category", "trends", ["tenant_id", "category"])

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=True),
        sa.Column("trend_id", sa.Integer(), sa.ForeignKey("trends.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(32), nullable=False, server_default="medium"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("run_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_recs_tenant_priority", "recommendations", ["tenant_id", "priority"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=True),
        sa.Column("trend_id", sa.Integer(), sa.ForeignKey("trends.id", ondelete="SET NULL"), nullable=True),
        sa.Column("alert_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False, server_default="info"),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("run_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_alerts_tenant", "alerts", ["tenant_id"])

    # ── Explainability ─────────────────────────────────────────
    op.create_table(
        "decision_traces",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("policy_version_id", sa.Integer(), nullable=True),
        sa.Column("input_summary_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("matched_rules_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("factor_contributions_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("explanation_text", sa.Text(), nullable=True),
        sa.Column("explanation_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_decision_trace_entity", "decision_traces", ["tenant_id", "entity_type", "entity_id"])

    op.create_table(
        "signal_lineage_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("from_type", sa.String(64), nullable=False),
        sa.Column("from_id", sa.Integer(), nullable=False),
        sa.Column("to_type", sa.String(64), nullable=False),
        sa.Column("to_id", sa.Integer(), nullable=False),
        sa.Column("relationship_type", sa.String(64), nullable=False, server_default="derived_from"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lineage_from", "signal_lineage_links", ["tenant_id", "from_type", "from_id"])
    op.create_index("ix_lineage_to", "signal_lineage_links", ["tenant_id", "to_type", "to_id"])

    op.create_table(
        "trend_evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trend_id", sa.Integer(), sa.ForeignKey("trends.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("signal_id", sa.Integer(), nullable=True),
        sa.Column("evidence_type", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("data_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_trend_evidence_trend", "trend_evidence", ["trend_id"])

    # ── Usage / Quotas ─────────────────────────────────────────
    op.create_table(
        "plan_definitions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("limits_json", sa.JSON(), nullable=False),
        sa.Column("features_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "usage_counters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric", sa.String(128), nullable=False),
        sa.Column("period", sa.String(32), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "metric", "period", name="uq_usage_counter"),
    )

    op.create_table(
        "quota_enforcement_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("metric", sa.String(128), nullable=False),
        sa.Column("current_value", sa.Integer(), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_quota_log_tenant", "quota_enforcement_log", ["tenant_id"])

    # ── Exports / Widgets ──────────────────────────────────────
    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("export_type", sa.String(64), nullable=False),
        sa.Column("format", sa.String(16), nullable=False, server_default="json"),
        sa.Column("filters_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_export_jobs_tenant", "export_jobs", ["tenant_id"])

    op.create_table(
        "widget_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("widget_type", sa.String(64), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_widget_configs_tenant", "widget_configs", ["tenant_id"])


def downgrade() -> None:
    for table in [
        "widget_configs", "export_jobs",
        "quota_enforcement_log", "usage_counters", "plan_definitions",
        "trend_evidence", "signal_lineage_links", "decision_traces",
        "alerts", "recommendations", "trends", "signals", "pipeline_events",
        "rebuild_requests", "backfill_requests", "processing_checkpoints",
        "processing_stages", "processing_runs",
        "suppression_policies", "alert_policies", "scoring_profiles",
        "detection_rules", "policy_versions", "policy_bundles",
        "tenant_memberships", "api_clients", "workspaces",
    ]:
        op.drop_table(table)
    op.drop_column("score_records", "workspace_id")
    op.drop_column("score_records", "tenant_id")
    op.drop_table("tenants")
