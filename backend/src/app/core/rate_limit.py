"""Per-IP rate limiting for the expensive LLM endpoints.

The chat model runs on CPU, so one client hammering summarize / ask /
draft could starve every other researcher. This is an in-memory
sliding-window limiter (one process, no Redis dependency): each
(client IP, endpoint family) gets a bounded number of requests per
window. When the limit is hit the request is rejected with HTTP 429
and a Retry-After header before any LLM work starts.

Limits come from Settings:
- summarize and ask (any source): RATE_LIMIT_SUMMARIZE_PER_MINUTE
  requests per minute per IP.
- POST /chat/ask: RATE_LIMIT_CHAT_PER_MINUTE per minute per IP.
- POST /draft/generate: RATE_LIMIT_DRAFT_PER_HOUR per hour per IP
  (a draft takes minutes of CPU per call).

The client IP is the first X-Forwarded-For entry when the request
came through a proxy, otherwise the direct peer address. In
production the host must only trust X-Forwarded-For from its own
reverse proxy; on a single-host docker-compose setup the proxy is
nginx inside the same compose network.
"""

import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Request

from .config import settings

# (endpoint family, ip) -> deque of request timestamps (epoch seconds)
_windows: dict[tuple[str, str], deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _limits_for_path(path: str) -> Optional[tuple[str, int, int]]:
    """Return (family, max_requests, window_seconds) for an LLM path."""
    if path.endswith("/draft/generate"):
        return ("draft", settings.RATE_LIMIT_DRAFT_PER_HOUR, 3600)
    if path.endswith("/chat/ask"):
        return ("chat", settings.RATE_LIMIT_CHAT_PER_MINUTE, 60)
    if path.endswith("/summarize") or path.endswith("/ask"):
        return ("llm", settings.RATE_LIMIT_SUMMARIZE_PER_MINUTE, 60)
    return None


def check_rate_limit(request: Request) -> tuple[bool, int]:
    """Check the limit for this request.

    Returns (allowed, retry_after_seconds). When not allowed,
    retry_after_seconds is how long the caller should wait.
    Paths that are not LLM endpoints are always allowed.
    """
    limits = _limits_for_path(request.url.path)
    if limits is None:
        return True, 0
    family, max_requests, window = limits
    key = (family, _client_ip(request))
    now = time.time()
    queue = _windows[key]
    while queue and queue[0] <= now - window:
        queue.popleft()
    if len(queue) >= max_requests:
        retry_after = int(queue[0] + window - now) + 1
        return False, max(retry_after, 1)
    queue.append(now)
    return True, 0


def reset_rate_limits() -> None:
    """Clear all limiter state (used by tests)."""
    _windows.clear()
