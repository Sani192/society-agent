from __future__ import annotations

import logging
from typing import Any


def log_security_event(
    logger: logging.Logger,
    *,
    event: str,
    actor_id: str | None = None,
    society_id: str | None = None,
    action: str,
    resource_id: str | None = None,
    method: str | None = None,
    result: str,
    reason_code: str | None = None,
    trace_id: str | None = None,
    level: int = logging.WARNING,
    **extra_fields: Any,
) -> None:
    payload: dict[str, Any] = {
        "event": event,
        "actor_id": actor_id,
        "society_id": society_id,
        "action": action,
        "resource_id": resource_id,
        "method": method,
        "result": result,
        "reason_code": reason_code,
        "trace_id": trace_id,
    }
    payload.update(extra_fields)
    logger.log(level, "Security event", extra=payload)
