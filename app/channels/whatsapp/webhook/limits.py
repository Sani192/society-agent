from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException, Request, status
import redis

from app.channels.core.audit_events import NormalizedAuditEvent, persist_audit_events
from app.config import settings
from app.utils.logger import logger
from app.utils.operational_metrics import increment_counter

RATE_LIMIT_REASON_WEBHOOK_IP = "WHATSAPP_WEBHOOK_IP_RATE_LIMIT_EXCEEDED"
RATE_LIMIT_REASON_SENDER_SPAM = "WHATSAPP_SENDER_SPAM_RATE_LIMIT_EXCEEDED"

_REDIS_CLIENT: redis.Redis | None = None


def _redis_client() -> redis.Redis:
    global _REDIS_CLIENT
    if _REDIS_CLIENT is None:
        _REDIS_CLIENT = redis.from_url(str(settings.REDIS_URL), decode_responses=False)
    return _REDIS_CLIENT


def increment_sliding_window(*, key: str, now_ts: float, window_seconds: int) -> int:
    pipe = _redis_client().pipeline(transaction=True)
    pipe.zremrangebyscore(key, 0, now_ts - float(window_seconds))
    pipe.zadd(key, {f"{now_ts:.6f}:{uuid4()}": now_ts})
    pipe.zcard(key)
    pipe.expire(key, max(1, int(window_seconds)))
    *_ignore, count, _ttl = pipe.execute()
    return int(count)


def _persist_event(*, reason_code: str, limit_scope: str, key: str, window_seconds: int, max_allowed: int, observed_count: int) -> None:
    persist_audit_events([
        NormalizedAuditEvent(
            channel="whatsapp",
            direction="system",
            event_type="exception",
            provider_error_code=reason_code,
            provider_error_message="Rate limit exceeded",
            external_user_id=key if limit_scope == "sender" else None,
            chat_id_or_phone=key if limit_scope == "sender" else None,
            payload_json={"reason_code": reason_code, "limit_scope": limit_scope, "key": key, "window_seconds": window_seconds, "max_allowed": max_allowed, "observed_count": observed_count},
            occurred_at=datetime.now(timezone.utc),
        )
    ])


def _client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or "unknown"
    return getattr(getattr(request, "client", SimpleNamespace(host=None)), "host", None) or f"object:{id(request)}"


def enforce_webhook_rate_limit(request: Request) -> None:
    window_seconds = max(1, int(settings.WHATSAPP_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS))
    max_requests = max(1, int(settings.WHATSAPP_WEBHOOK_RATE_LIMIT_MAX_REQUESTS))
    key = _client_key(request)
    try:
        observed_count = increment_sliding_window(key=f"whatsapp:webhook:rate_limit:ip:{key[:120]}", now_ts=datetime.now(timezone.utc).timestamp(), window_seconds=window_seconds)
    except Exception:
        logger.exception("WhatsApp webhook rate limit backend unavailable")
        return
    if observed_count > max_requests:
        increment_counter("whatsapp.webhook.rate_limited")
        _persist_event(reason_code=RATE_LIMIT_REASON_WEBHOOK_IP, limit_scope="ip", key=key[:64], window_seconds=window_seconds, max_allowed=max_requests, observed_count=observed_count)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")


def enforce_sender_spam_limit(sender_id: str | None) -> None:
    sender_key = (sender_id or "").strip()
    if not sender_key:
        return
    window_seconds = max(1, int(settings.WHATSAPP_SENDER_SPAM_WINDOW_SECONDS))
    max_messages = max(1, int(settings.WHATSAPP_SENDER_SPAM_MAX_MESSAGES))
    try:
        observed_count = increment_sliding_window(key=f"whatsapp:webhook:rate_limit:sender:{sender_key[:120]}", now_ts=datetime.now(timezone.utc).timestamp(), window_seconds=window_seconds)
    except Exception:
        logger.exception("WhatsApp sender spam limit backend unavailable")
        return
    if observed_count > max_messages:
        increment_counter("whatsapp.webhook.sender_rate_limited")
        _persist_event(reason_code=RATE_LIMIT_REASON_SENDER_SPAM, limit_scope="sender", key=sender_key, window_seconds=window_seconds, max_allowed=max_messages, observed_count=observed_count)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Sender rate limit exceeded")
