#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 21:42:26 2026

@author: anonymous
"""

# app/utils/logger.py

import logging
from logging.config import dictConfig
import os
from logging.handlers import TimedRotatingFileHandler

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "society-agent.log")

dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "level": "INFO",
            },
            "file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "formatter": "default",
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
