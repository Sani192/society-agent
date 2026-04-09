#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 21:42:26 2026

@author: anonymous
"""

# app/utils/logger.py

import json
import logging
from logging.config import dictConfig
import os
import re
from logging.handlers import TimedRotatingFileHandler
from typing import Any

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "society-agent.log")

_DEFAULT_LOG_RECORD_FIELDS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "taskName",
}
_SENSITIVE_KEY_TOKENS = ("phone", "token", "secret", "authorization", "otp", "request")
_PHONE_DIGITS_RE = re.compile(r"\d{10,15}")


def _mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 6:
        return "***REDACTED***"
    return f"{digits[:2]}******{digits[-2:]}"


def _redact_string(value: str) -> str:
    redacted = value
    for pattern in _PHONE_DIGITS_RE.findall(redacted):
        redacted = redacted.replace(pattern, _mask_phone(pattern))
    return redacted


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(token in normalized for token in _SENSITIVE_KEY_TOKENS)


def _redact_value(value: Any, *, key: str | None = None) -> Any:
    if value is None:
        return None
    if key and _is_sensitive_key(key):
        return "***REDACTED***"
    if isinstance(value, dict):
        return {k: _redact_value(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    if isinstance(value, str):
        return _redact_string(value)
    return value


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact_value(record.msg)
        record.args = _redact_value(record.args)
        for key, value in list(record.__dict__.items()):
            if key in _DEFAULT_LOG_RECORD_FIELDS:
                continue
            record.__dict__[key] = _redact_value(value, key=key)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", None),
            "correlation_id": getattr(record, "correlation_id", None),
            "action": getattr(record, "action", None),
            "result": getattr(record, "result", None),
        }
        for key, value in record.__dict__.items():
            if key in _DEFAULT_LOG_RECORD_FIELDS or key in payload:
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)

dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"redaction": {"()": RedactionFilter}},
        "formatters": {
            "default": {
                "()": JsonFormatter,
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "filters": ["redaction"],
                "level": "INFO",
            },
            "file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "formatter": "default",
                "filters": ["redaction"],
                "filename": LOG_FILE,
                "when": "midnight",
                "backupCount": 5,
                "level": "INFO",
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["console", "file"],
        },
    }
)

for handler in logging.getLogger().handlers:
    if isinstance(handler, TimedRotatingFileHandler):
        handler.suffix = "%Y-%m-%d.log"

logger = logging.getLogger("society-agent")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
