"""Outbox dispatcher — reads pending events and delivers them."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from scoring_service.config import Settings
from scoring_service.correlation import get_correlation_id

logger = logging.getLogger("scoring_service")


class WebhookDispatcher:
    """Delivers outbox events via webhook with optional HMAC signing."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.url = settings.notification_webhook_url
        self.secret = settings.notification_webhook_secret

    def sign_payload(self, body: bytes) -> str:
        if not self.secret:
            return ""
        return hmac.new(
            self.secret.encode(), body, hashlib.sha256
        ).hexdigest()

    def deliver(self, payload: dict[str, Any]) -> tuple[bool, int | None, str | None]:
        """
        Deliver payload. Returns (success, status_code, error_message).
        """
        if not self.url:
            logger.debug("webhook_skip no_url_configured")
            return True, None, None

        body = json.dumps(payload, default=str).encode()
        headers = {
            "Content-Type": "application/json",
            "X-Correlation-ID": get_correlation_id(),
        }
        signature = self.sign_payload(body)
        if signature:
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(self.url, content=body, headers=headers)
            if resp.status_code < 400:
                return True, resp.status_code, None
            return False, resp.status_code, f"HTTP {resp.status_code}: {resp.text[:200]}"
        except httpx.TimeoutException:
            return False, None, "timeout"
        except Exception as exc:
            return False, None, str(exc)[:300]
