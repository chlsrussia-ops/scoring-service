"""Correlation / Request ID middleware and context."""
from __future__ import annotations

import contextvars
import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)

HEADER_NAME = "X-Correlation-ID"


def get_correlation_id() -> str:
    return _correlation_id_var.get() or ""


def set_correlation_id(cid: str) -> None:
    _correlation_id_var.set(cid)


def new_correlation_id() -> str:
    cid = uuid.uuid4().hex[:16]
    set_correlation_id(cid)
    return cid


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        cid = request.headers.get(HEADER_NAME) or uuid.uuid4().hex[:16]
        set_correlation_id(cid)
        response = await call_next(request)
        response.headers[HEADER_NAME] = cid
        return response
