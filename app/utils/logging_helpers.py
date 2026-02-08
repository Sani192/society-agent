#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logging helpers for consistent service entry/exit and contextual fields.
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable, Dict, Iterable, Optional

CONTEXT_FIELDS: Iterable[str] = (
    "event_id",
    "flat_id",
    "society_id",
    "performed_by",
    "request_code",
)


def build_log_context(**kwargs: Any) -> Dict[str, Any]:
    return {
        key: kwargs[key]
        for key in CONTEXT_FIELDS
        if key in kwargs and kwargs[key] is not None
    }


def log_entry(logger: logging.Logger, action: str, context: Dict[str, Any]) -> None:
    logger.info("Entering %s | context=%s", action, context)


def log_exit(logger: logging.Logger, action: str, context: Dict[str, Any]) -> None:
    logger.info("Exiting %s | context=%s", action, context)


def log_service_call(logger: logging.Logger, action: str) -> Callable[..., Any]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            context = build_log_context(**kwargs)
            log_entry(logger, action, context)
            try:
                result = func(*args, **kwargs)
            except Exception:
                logger.exception("Exception in %s | context=%s", action, context)
                raise
            log_exit(logger, action, context)
            return result

        return wrapper

    return decorator
