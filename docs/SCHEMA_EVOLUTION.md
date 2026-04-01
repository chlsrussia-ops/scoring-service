# Schema Evolution Policy

## Migration Chain

    0001_init                          -- ScoreRecord (original table)
    0002_production_hardening          -- Jobs, Outbox, DLQ, Failures, Sources, Audit
    0003_stage3_platform               -- Tenancy, Policies, Pipeline, Explainability, Usage
    0004_stage4_product                -- DataSources, LLM, Digests, Demo
    0005_outbox_dedup                  -- Outbox dedup_key column
    bb614cd4019d (stage5_adaptation)   -- Adaptation models (15 tables)
    0006_schema_reconciliation         -- Index name alignment, phantom column cleanup

All migrations are linear (no branches). Single head.

## Clean Bootstrap

    alembic upgrade head
    alembic check
    make schema-audit

## Writing New Migrations

1. One concern per migration
2. Explicit constraint names (fk_table_column, uq_table_desc)
3. Explicit index names via Index() in __table_args__
4. No try/except/pass
5. No IF NOT EXISTS as workaround
6. Always write downgrade
7. Test with alembic check after every model change

## Index Naming Convention

- Single column: ix_{table}_{column}
- Composite: ix_{table}_{col1}_{col2}
- Unique constraint: uq_{description}
- Foreign key: fk_{table}_{column}

## Data Migrations

- Separate file from schema migrations
- Name: NNNN_backfill_description.py
- Must be idempotent
- Document pre/post conditions

## CI Checks

- alembic upgrade head on clean PostgreSQL
- alembic check for drift detection
- Single head verification
- Migration tests (tests/test_migrations.py)
