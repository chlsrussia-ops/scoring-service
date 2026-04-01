"""Seed / demo data for multi-tenant platform."""
from __future__ import annotations

from scoring_service.config import Settings
from scoring_service.db.session import create_session_factory
from scoring_service.plugins.registry import plugin_registry
from scoring_service.plugins.builtin import register_builtins


def seed():
    settings = Settings()
    engine, SF = create_session_factory(settings)
    register_builtins(plugin_registry)

    # 1. Seed plans
    print("Seeding plans...")
    db = SF()
    try:
        from scoring_service.usage.service import UsageService
        UsageService(db).seed_plans()
        db.commit()
        print("  Plans seeded")
    except Exception as e:
        db.rollback()
        print(f"  Plans: {e}")
    finally:
        db.close()

    # 2. Create tenants (keep existing demo, add default/acme/globex)
    print("Creating tenants...")
    tenants_data = [
        {"id": "default", "name": "Default Tenant", "slug": "default", "plan": "internal"},
        {"id": "demo", "name": "Demo Tenant", "slug": "demo", "plan": "pro"},
        {"id": "acme", "name": "Acme Corp", "slug": "acme", "plan": "pro"},
        {"id": "globex", "name": "Globex Industries", "slug": "globex", "plan": "team"},
    ]
    for td in tenants_data:
        db = SF()
        try:
            from scoring_service.tenancy.service import TenancyService
            svc = TenancyService(db)
            existing = svc.get_tenant(td["id"])
            if existing:
                # Update plan if needed
                if existing.plan != td["plan"]:
                    svc.update_tenant(td["id"], plan=td["plan"])
                    print(f"  Updated tenant '{td['id']}' plan -> {td['plan']}")
                else:
                    print(f"  Tenant '{td['id']}' exists")
                continue
            svc.create_tenant(**td)
            print(f"  Created tenant: {td['id']}")
        except Exception as e:
            db.rollback()
            print(f"  Tenant {td['id']}: {e}")
        finally:
            db.close()

    # 3. Workspaces
    print("Creating workspaces...")
    ws_data = [
        ("acme", "acme-marketing", "Marketing", "marketing"),
        ("acme", "acme-product", "Product", "product"),
        ("globex", "globex-research", "Research", "research"),
    ]
    for tenant_id, ws_id, ws_name, ws_slug in ws_data:
        db = SF()
        try:
            from scoring_service.tenancy.service import TenancyService
            svc = TenancyService(db)
            if svc.get_workspace(ws_id):
                continue
            svc.create_workspace(tenant_id, id=ws_id, name=ws_name, slug=ws_slug)
            print(f"  Created workspace: {ws_id}")
        except Exception as e:
            db.rollback()
        finally:
            db.close()

    # 4. API clients
    print("Creating API clients...")
    clients = [
        ("default", "dev-key-1", "Legacy Dev Key"),
        ("default", "dev-key-2", "Legacy Dev Key 2"),
        ("demo", "demo-key-1", "Demo Key"),
        ("acme", "acme-key-1", "Acme Production"),
        ("globex", "globex-key-1", "Globex Production"),
    ]
    for tenant_id, key, name in clients:
        db = SF()
        try:
            from scoring_service.tenancy.service import TenancyService
            svc = TenancyService(db)
            svc.create_api_client(tenant_id, api_key=key, name=name)
            print(f"  Created client: {key} -> {tenant_id}")
        except Exception as e:
            db.rollback()
        finally:
            db.close()

    # 5. Policies
    print("Creating policies...")
    db = SF()
    try:
        from scoring_service.policies.service import PolicyService
        psvc = PolicyService(db)
        if not psvc.list_bundles(limit=1):
            b1 = psvc.create_bundle(
                tenant_id=None, name="Global Default Detection",
                policy_type="detection", is_global=True, priority=1000,
                description="Default global detection rules",
                config={
                    "rules": [
                        {"name": "high_event_count",
                         "conditions": [{"field": "event_count", "operator": "gte", "value": 5}],
                         "action": "flag", "weight": 2.0, "enabled": True},
                        {"name": "growth_spike",
                         "conditions": [{"field": "growth_rate", "operator": "gte", "value": 3.0}],
                         "action": "flag", "weight": 3.0, "enabled": True},
                    ],
                    "weights": {"event_count": 2.0, "growth_rate": 5.0, "total_value": 1.0},
                    "thresholds": {"min_score": 10.0, "alert_score": 50.0},
                },
            )
            psvc.activate_version(b1.id)
            print(f"  Created global detection policy (id={b1.id})")

            b2 = psvc.create_bundle(
                tenant_id="acme", name="Acme Custom Scoring",
                policy_type="scoring", priority=50,
                description="Custom scoring weights for Acme",
                config={
                    "rules": [],
                    "weights": {"event_count": 3.0, "growth_rate": 8.0, "total_value": 2.0},
                    "thresholds": {"min_score": 5.0},
                },
            )
            psvc.activate_version(b2.id)
            print(f"  Created Acme scoring policy (id={b2.id})")
        else:
            print("  Policies already exist")
    except Exception as e:
        db.rollback()
        print(f"  Policies error: {e}")
    finally:
        db.close()

    # 6. Run pipelines
    print("Running demo pipelines...")
    from scoring_service.pipeline.orchestrator import PipelineOrchestrator
    from scoring_service.usage.service import UsageService

    for tenant_id in ["default", "demo", "acme", "globex"]:
        db = SF()
        try:
            orch = PipelineOrchestrator(db, plugin_registry)
            run = orch.run(tenant_id, run_type="seed")
            usage = UsageService(db)
            usage.increment(tenant_id, "analysis_runs_per_month")
            usage.increment(tenant_id, "events_per_month", run.stats_json.get("events_ingested", 0))
            print(f"  {tenant_id}: run={run.id}, status={run.status}, stats={run.stats_json}")
        except Exception as e:
            db.rollback()
            print(f"  {tenant_id} pipeline: {e}")
        finally:
            db.close()

    print("\nSeed completed!")


if __name__ == "__main__":
    seed()
