from __future__ import annotations

import time
import uuid
from collections import deque

from fastapi import Request
from starlette.responses import JSONResponse

from app.config import settings
from app.core.state import _rate_buckets, bump_request_stats


async def request_middleware(request: Request, call_next):
    """Request context + optional auth + basic in-memory rate limiting."""

    # API key auth (optional)
    if settings.api_key:
        provided = request.headers.get("x-api-key")
        if not provided or provided != settings.api_key:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

    # Rate limiting (optional)
    if settings.enable_rate_limiting and request.url.path not in ("/health", "/readiness", "/metrics"):
        host = request.client.host if request.client else "unknown"
        key = f"{host}:{request.url.path.split('?')[0]}"
        now = time.time()
        bucket = _rate_buckets.setdefault(key, deque())

        window_start = now - settings.rate_limit_window_sec
        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= settings.rate_limit_requests:
            return JSONResponse(
                {
                    "detail": "Rate limit exceeded",
                    "limit": settings.rate_limit_requests,
                    "window_sec": settings.rate_limit_window_sec,
                },
                status_code=429,
            )

        bucket.append(now)

    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start = time.time()
    bump_request_stats(True)
    try:
        response = await call_next(request)
    finally:
        bump_request_stats(False)

    response.headers["x-request-id"] = request_id
    response.headers["x-response-time-ms"] = f"{(time.time() - start) * 1000:.2f}"
    return response
