"""Tenancy CRUD service."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from scoring_service.db.models import (
    ApiClient, Tenant, TenantMembership, TenantStatus, Workspace,
)


class TenancyService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Tenants ─────────────────────────────────────────────

    def create_tenant(
        self, *, id: str, name: str, slug: str, plan: str = "free",
        settings: dict | None = None,
    ) -> Tenant:
        tenant = Tenant(
            id=id, name=name, slug=slug, plan=plan,
            settings_json=settings or {},
        )
        self.db.add(tenant)
        # Create default workspace
        ws = Workspace(
            id=f"{id}-default", tenant_id=id, name="Default",
            slug="default", is_default=True,
        )
        self.db.add(ws)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        return self.db.get(Tenant, tenant_id)

    def list_tenants(self, *, limit: int = 50, offset: int = 0) -> list[Tenant]:
        return (
            self.db.query(Tenant)
            .order_by(Tenant.created_at.desc())
            .offset(offset).limit(limit).all()
        )

    def update_tenant(self, tenant_id: str, **kwargs: object) -> Tenant | None:
        tenant = self.db.get(Tenant, tenant_id)
        if not tenant:
            return None
        if "name" in kwargs and kwargs["name"]:
            tenant.name = kwargs["name"]  # type: ignore[assignment]
        if "plan" in kwargs and kwargs["plan"]:
            tenant.plan = kwargs["plan"]  # type: ignore[assignment]
        if "status" in kwargs and kwargs["status"]:
            tenant.status = TenantStatus(kwargs["status"])  # type: ignore[assignment]
        if "settings" in kwargs and kwargs["settings"] is not None:
            tenant.settings_json = kwargs["settings"]  # type: ignore[assignment]
        tenant.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def count_tenants(self) -> int:
        return self.db.query(Tenant).count()

    # ── Workspaces ──────────────────────────────────────────

    def create_workspace(
        self, tenant_id: str, *, id: str, name: str, slug: str,
        settings: dict | None = None, is_default: bool = False,
    ) -> Workspace:
        ws = Workspace(
            id=id, tenant_id=tenant_id, name=name, slug=slug,
            settings_json=settings or {}, is_default=is_default,
        )
        self.db.add(ws)
        self.db.commit()
        self.db.refresh(ws)
        return ws

    def list_workspaces(self, tenant_id: str) -> list[Workspace]:
        return (
            self.db.query(Workspace)
            .filter(Workspace.tenant_id == tenant_id)
            .order_by(Workspace.created_at).all()
        )

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        return self.db.get(Workspace, workspace_id)

    # ── API Clients ─────────────────────────────────────────

    def create_api_client(
        self, tenant_id: str, *, api_key: str, name: str = "default",
        scopes: list[str] | None = None,
    ) -> ApiClient:
        client = ApiClient(
            tenant_id=tenant_id, api_key=api_key, name=name,
            scopes=scopes or [],
        )
        self.db.add(client)
        self.db.commit()
        self.db.refresh(client)
        return client

    def list_api_clients(self, tenant_id: str) -> list[ApiClient]:
        return (
            self.db.query(ApiClient)
            .filter(ApiClient.tenant_id == tenant_id)
            .all()
        )

    # ── Memberships ─────────────────────────────────────────

    def add_member(self, tenant_id: str, email: str, role: str = "member") -> TenantMembership:
        m = TenantMembership(tenant_id=tenant_id, user_email=email, role=role)
        self.db.add(m)
        self.db.commit()
        self.db.refresh(m)
        return m

    def list_members(self, tenant_id: str) -> list[TenantMembership]:
        return (
            self.db.query(TenantMembership)
            .filter(TenantMembership.tenant_id == tenant_id)
            .all()
        )
