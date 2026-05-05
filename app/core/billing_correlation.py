"""
Billing correlation middleware and logging filter.

Behaviour
---------
For every request whose path starts with ``/api/subscriptions`` or ``/api/stripe/webhook``:

1. Reads ``X-Billing-Correlation-Id`` from the incoming request.
2. Generates a UUID4 when the header is absent.
3. Stores it on ``request.state.billing_correlation_id``.
4. Echoes the header on the response.

A ``logging.Filter`` (``BillingCorrelationFilter``) injects the current correlation-id into
structured log records emitted during that request so that ``apple_verify_*``,
``stripe_webhook_*``, and ``entitlement_recompute_*`` events are automatically correlated.
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

CORRELATION_ID_HEADER = "X-Billing-Correlation-Id"

# Per-request context variable so the log filter can read it without passing it explicitly.
_billing_correlation_id: ContextVar[str] = ContextVar(
    "_billing_correlation_id", default=""
)

_BILLING_PATH_PREFIXES = ("/api/subscriptions", "/api/stripe/webhook")


class BillingCorrelationMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that attaches a billing correlation id to billing routes."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path

        # Only activate on billing paths.
        if not any(path.startswith(prefix) for prefix in _BILLING_PATH_PREFIXES):
            return await call_next(request)

        correlation_id = (
            request.headers.get(CORRELATION_ID_HEADER)
            or str(uuid.uuid4())
        )
        request.state.billing_correlation_id = correlation_id

        # Inject into context var so the log filter picks it up.
        token = _billing_correlation_id.set(correlation_id)
        try:
            response = await call_next(request)
        finally:
            _billing_correlation_id.reset(token)

        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response


class BillingCorrelationFilter(logging.Filter):
    """Injects ``billing_correlation_id`` into every ``LogRecord`` emitted during a billing
    request.  Safe to attach globally — it is a no-op outside billing request context."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.billing_correlation_id = _billing_correlation_id.get("") or "-"
        return True
