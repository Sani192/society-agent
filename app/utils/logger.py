#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 21:42:26 2026

@author: anonymous
"""

# app/utils/logger.py

import logging
import os
from logging.handlers import TimedRotatingFileHandler

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "society-agent.log")

logger = logging.getLogger("society-agent")
logger.setLevel(logging.INFO)

if not any(isinstance(existing, TimedRotatingFileHandler) for existing in logger.handlers):
    handler = TimedRotatingFileHandler(
        LOG_FILE,
        when="midnight",
        backupCount=5
    )
    handler.suffix = "%Y-%m-%d"

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
