"""Tenant context — extracted from API key or header."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from scoring_service.db.models import ApiClient, Tenant


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant_id: str
    tenant_name: str
    workspace_id: str | None
    plan: str
    settings: dict[str, Any]
    is_admin: bool = False


# Default tenant for backward compatibility
DEFAULT_TENANT_ID = "default"


def _get_db(request: Request) -> Session | None:
    factory = getattr(request.app.state, "session_factory", None)
    if factory:
        return factory()
    return None


async def get_tenant_context(
    request: Request,
    x_api_key: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
    x_workspace_id: str | None = Header(default=None),
) -> TenantContext:
    """Resolve tenant from API key lookup or explicit header."""
    db = _get_db(request)
    if not db:
        # No DB — return default tenant
        return TenantContext(
            tenant_id=DEFAULT_TENANT_ID,
            tenant_name="Default",
            workspace_id=x_workspace_id,
            plan="free",
            settings={},
        )
    try:
        # 1) Try API key lookup
        if x_api_key:
            client = db.query(ApiClient).filter(
                ApiClient.api_key == x_api_key,
                ApiClient.is_active == True,
            ).first()
            if client:
                tenant = db.get(Tenant, client.tenant_id)
                if tenant and str(tenant.status) == "active":
                    return TenantContext(
                        tenant_id=tenant.id,
                        tenant_name=tenant.name,
                        workspace_id=x_workspace_id,
                        plan=tenant.plan,
                        settings=tenant.settings_json or {},
                    )

        # 2) Explicit tenant header
        if x_tenant_id:
            tenant = db.get(Tenant, x_tenant_id)
            if tenant and str(tenant.status) == "active":
                return TenantContext(
                    tenant_id=tenant.id,
                    tenant_name=tenant.name,
                    workspace_id=x_workspace_id,
                    plan=tenant.plan,
                    settings=tenant.settings_json or {},
                )

        # 3) Check legacy API keys from settings
        settings = request.app.state.settings
        if x_api_key and x_api_key in settings.api_key_list:
            # Legacy key — use default tenant
            default = db.get(Tenant, DEFAULT_TENANT_ID)
            if default:
                return TenantContext(
                    tenant_id=default.id,
                    tenant_name=default.name,
                    workspace_id=x_workspace_id,
                    plan=default.plan,
                    settings=default.settings_json or {},
                )
            return TenantContext(
                tenant_id=DEFAULT_TENANT_ID,
                tenant_name="Default",
                workspace_id=x_workspace_id,
                plan="free",
                settings={},
            )
    finally:
        db.close()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid or missing credentials",
    )


async def get_admin_context(
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> TenantContext:
    """Admin context — requires admin API key."""
    settings = request.app.state.settings
    if x_api_key and x_api_key in settings.api_key_list:
        return TenantContext(
            tenant_id="__admin__",
            tenant_name="Admin",
            workspace_id=None,
            plan="internal",
            settings={},
            is_admin=True,
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="admin access required",
    )
