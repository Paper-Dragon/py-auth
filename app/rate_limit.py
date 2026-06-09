from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.coerce import coerce_boolish
from app.database import get_db
from app.models import Config

RATE_LIMIT_CONFIG_KEY = "rate_limit"

DEFAULT_RATE_LIMIT: dict[str, Any] = {
    "enabled": True,
    "login": {"max_requests": 10, "window_seconds": 60},
    "heartbeat": {"max_requests": 120, "window_seconds": 60},
    "payment_order": {"max_requests": 20, "window_seconds": 60},
}

RATE_LIMIT_SCOPES = ("login", "heartbeat", "payment_order")

_config_cache: dict[str, Any] | None = None
_config_lock = threading.Lock()


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= max_requests:
                retry_after = int(window_seconds - (now - bucket[0])) + 1
                return False, max(1, retry_after)
            bucket.append(now)
            return True, 0


_limiter = SlidingWindowLimiter()


def _normalize_rule(raw: Any, fallback: dict[str, int]) -> dict[str, int]:
    data = raw if isinstance(raw, dict) else {}
    try:
        max_requests = int(data.get("max_requests", fallback["max_requests"]))
    except (TypeError, ValueError):
        max_requests = fallback["max_requests"]
    try:
        window_seconds = int(data.get("window_seconds", fallback["window_seconds"]))
    except (TypeError, ValueError):
        window_seconds = fallback["window_seconds"]
    return {
        "max_requests": max(1, min(max_requests, 10_000)),
        "window_seconds": max(1, min(window_seconds, 3600)),
    }


def normalize_rate_limit_config(raw: Any) -> dict[str, Any]:
    base = {
        "enabled": coerce_boolish(DEFAULT_RATE_LIMIT["enabled"], if_none=True),
        "login": dict(DEFAULT_RATE_LIMIT["login"]),
        "heartbeat": dict(DEFAULT_RATE_LIMIT["heartbeat"]),
        "payment_order": dict(DEFAULT_RATE_LIMIT["payment_order"]),
    }
    if not isinstance(raw, dict):
        return base

    base["enabled"] = coerce_boolish(raw.get("enabled"), if_none=base["enabled"])
    for scope in RATE_LIMIT_SCOPES:
        base[scope] = _normalize_rule(raw.get(scope), DEFAULT_RATE_LIMIT[scope])
    return base


def load_rate_limit_config(db: Session) -> dict[str, Any]:
    row = db.query(Config).filter(Config.key == RATE_LIMIT_CONFIG_KEY).first()
    if row and isinstance(row.value, dict):
        return normalize_rate_limit_config(row.value)
    return normalize_rate_limit_config(None)


def save_rate_limit_config(db: Session, updates: dict[str, Any]) -> dict[str, Any]:
    current = load_rate_limit_config(db)
    if "enabled" in updates and updates["enabled"] is not None:
        current["enabled"] = coerce_boolish(updates["enabled"], if_none=current["enabled"])
    for scope in RATE_LIMIT_SCOPES:
        if scope in updates and isinstance(updates[scope], dict):
            current[scope] = _normalize_rule(updates[scope], current[scope])

    row = db.query(Config).filter(Config.key == RATE_LIMIT_CONFIG_KEY).first()
    if row:
        row.value = current
    else:
        db.add(Config(key=RATE_LIMIT_CONFIG_KEY, value=current))
    set_rate_limit_cache(current)
    return current


def set_rate_limit_cache(config: dict[str, Any]) -> None:
    global _config_cache
    with _config_lock:
        _config_cache = normalize_rate_limit_config(config)


def get_rate_limit_config(db: Session) -> dict[str, Any]:
    global _config_cache
    with _config_lock:
        if _config_cache is not None:
            return _config_cache
    config = load_rate_limit_config(db)
    set_rate_limit_cache(config)
    return config


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def check_rate_limit(scope: str, request: Request, db: Session) -> None:
    if scope not in RATE_LIMIT_SCOPES:
        return

    config = get_rate_limit_config(db)
    if not config.get("enabled"):
        return

    rule = config.get(scope) or DEFAULT_RATE_LIMIT[scope]
    max_requests = int(rule["max_requests"])
    window_seconds = int(rule["window_seconds"])
    key = f"{scope}:{client_ip(request)}"

    allowed, retry_after = _limiter.allow(key, max_requests, window_seconds)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试",
            headers={"Retry-After": str(retry_after)},
        )


def require_rate_limit(scope: str):
    async def _dependency(request: Request, db: Session = Depends(get_db)) -> None:
        check_rate_limit(scope, request, db)

    return _dependency
