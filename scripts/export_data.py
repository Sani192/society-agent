#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 20:53:27 2026

@author: anonymous
"""

# scripts/export_data.py

import json
from app.db.session import SessionLocal
from app.db import models

EXPORT_FILE = "export_all.json"

try:
    ensure_admin(phone_number)
except Exception as e:
    logger.exception("Unhandled error in WhatsApp handler")
    return error("Something went wrong. Please contact admin.")

db = SessionLocal()

data = {}

for model in [
    models.Society,
    models.CommitteeMember,
    models.Flat,
    models.Event,
    models.EventFoodPass,
    models.Payment,
    models.Refund,
    models.EventExpense,
    models.EventContribution,
    models.SocietyBalance,
    models.AuditLog
]:
    rows = db.query(model).all()
    data[model.__tablename__] = [
        {c.name: str(getattr(row, c.name)) for c in model.__table__.columns}
        for row in rows
    ]

db.close()

with open(EXPORT_FILE, "w") as f:
    json.dump(data, f, indent=2)

print(f"✅ Data exported to {EXPORT_FILE}")
