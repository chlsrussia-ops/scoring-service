"""Security: API key auth, admin auth, payload redaction, request size limits."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import Header, HTTPException, Request, status

from scoring_service.config import Settings

logger = logging.getLogger("scoring_service")

# ── Sensitive field redaction ────────────────────────────────────────

_DEFAULT_REDACT = {"password", "secret", "token", "api_key", "authorization"}


def redact_dict(data: dict[str, Any], redact_fields: set[str] | None = None) -> dict[str, Any]:
    """Return a copy with sensitive fields masked."""
    fields = redact_fields or _DEFAULT_REDACT
    result: dict[str, Any] = {}
    for k, v in data.items():
        if k.lower() in fields:
            result[k] = "***REDACTED***"
        elif isinstance(v, dict):
            result[k] = redact_dict(v, fields)
        else:
            result[k] = v
    return result


# ── API key auth ─────────────────────────────────────────────────────

async def require_api_key(
    request: Request, x_api_key: str | None = Header(default=None)
) -> str:
    settings: Settings = request.app.state.settings
    if x_api_key is None or x_api_key not in settings.api_key_list:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing api key",
        )
    return x_api_key


# ── Admin auth ───────────────────────────────────────────────────────

async def require_admin_key(
    request: Request, x_admin_key: str | None = Header(default=None)
) -> str:
    settings: Settings = request.app.state.settings
    if x_admin_key is None or x_admin_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin access denied",
        )
    return x_admin_key


# ── Request body size guard ──────────────────────────────────────────

async def check_body_size(request: Request) -> None:
    settings: Settings = request.app.state.settings
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_request_body_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"request body exceeds {settings.max_request_body_bytes} bytes",
        )
