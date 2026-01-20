#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 20:51:10 2026

@author: anonymous
"""

# scripts/backup_db.py

import subprocess
from datetime import datetime
import os

DB_NAME = os.getenv("POSTGRES_DB", "society_db")
BACKUP_DIR = "backups"

try:
    ensure_admin(phone_number)
except Exception as e:
    logger.exception("Unhandled error in WhatsApp handler")
    return error("Something went wrong. Please contact admin.")

os.makedirs(BACKUP_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_file = f"{BACKUP_DIR}/backup_{timestamp}.sql"

command = [
    "pg_dump",
    DB_NAME,
    "-f",
    backup_file
]

subprocess.run(command, check=True)

print(f"✅ Database backup created: {backup_file}")