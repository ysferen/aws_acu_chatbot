import time

from django.core.cache import cache

from .auth import ROLE_ANONYMOUS, ROLE_INTERNAL_SERVICE, ensure_session_key


def _identity_for_request(request, context) -> str:
    if context.role == ROLE_INTERNAL_SERVICE and context.service_token:
        return f"service:{context.service_token.id}"

    if context.user and getattr(context.user, "is_authenticated", False):
        return f"user:{context.user.id}"

    if context.role == ROLE_ANONYMOUS:
        return f"anon:{ensure_session_key(request)}"

    return "anonymous"


def check_rate_limit(request, context, scope: str, limit: int, window_seconds: int = 60) -> int | None:
    now = int(time.time())
    window_index = now // window_seconds
    identity = _identity_for_request(request, context)
    key = f"rl:{scope}:{identity}:{window_index}"

    if cache.add(key, 1, timeout=window_seconds):
        return None

    current = cache.incr(key)
    if current <= limit:
        return None

    next_window_start = (window_index + 1) * window_seconds
    return max(next_window_start - now, 1)
