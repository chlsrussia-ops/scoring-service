"""Stage 4: Product layer — data sources, LLM generations, digests, demo runs."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_stage4_product"
down_revision = "0003_stage3_platform"


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("items_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_normalized", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_data_sources_tenant_type", "data_sources", ["tenant_id", "source_type"])

    op.create_table(
        "llm_generations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("prompt_template", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("input_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_llm_gen_entity", "llm_generations", ["tenant_id", "entity_type", "entity_id"])
    op.create_index("ix_llm_gen_dedup", "llm_generations", ["tenant_id", "entity_type", "entity_id", "prompt_template", "input_hash"])

    op.create_table(
        "digest_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("top_trends_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("top_recommendations_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("key_risks_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("stats_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("llm_generation_id", sa.Integer(), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_digest_reports_tenant", "digest_reports", ["tenant_id"])

    op.create_table(
        "demo_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="running"),
        sa.Column("result_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_demo_runs_tenant", "demo_runs", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("demo_runs")
    op.drop_table("digest_reports")
    op.drop_table("llm_generations")
    op.drop_table("data_sources")
