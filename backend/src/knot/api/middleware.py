"""Rate-limiting middleware for the KNOT API."""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from knot.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP, per-route in-memory rate limiter.

    Tracks request timestamps per ``(client_ip, route_path)`` key and
    rejects requests that exceed the configured limit within a 60-second
    sliding window.

    WebSocket endpoints (paths starting with ``/api/v1/ws``) are excluded
    from rate limiting.
    """

    def __init__(self, app, rate_limit_per_minute: int | None = None) -> None:
        super().__init__(app)
        self._limit = rate_limit_per_minute or settings.rate_limit_per_minute
        # Mapping: f"{client_ip}:{route}" -> list[timestamp_in_seconds]
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip WebSocket endpoints
        if request.url.path.startswith("/api/v1/ws"):
            return await call_next(request)

        # Skip health checks to avoid starving health probes
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        # Group by method + path (different HTTP methods on the same path
        # are treated as separate rate-limit buckets).
        route_key = f"{client_ip}:{request.method}:{request.url.path}"
        now = time.time()

        # Prune entries older than 60 seconds
        timestamps = self._requests[route_key]
        cutoff = now - 60.0
        self._requests[route_key] = [t for t in timestamps if t > cutoff]

        # Check limit
        if len(self._requests[route_key]) >= self._limit:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too Many Requests",
                    "retry_after_seconds": 60,
                },
                headers={"Retry-After": "60"},
            )

        self._requests[route_key].append(now)
        return await call_next(request)
