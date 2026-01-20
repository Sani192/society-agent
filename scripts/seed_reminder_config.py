#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 17 12:08:46 2026

@author: anonymous
"""

# scripts/seed_reminder_config.py

from app.db.session import SessionLocal
from app.db.models import Society, ReminderConfig

db = SessionLocal()

society = db.query(Society).first()

existing = (
    db.query(ReminderConfig)
    .filter(ReminderConfig.society_id == society.id)
    .first()
)

if not existing:
    config = ReminderConfig(
        society_id=society.id,
        enabled=True,
        run_hour=10,
        run_minute=0,
        frequency="daily"
    )
    db.add(config)
    db.commit()
    print("✅ Reminder config created")
else:
    print("ℹ️ Reminder config already exists")

db.close()
