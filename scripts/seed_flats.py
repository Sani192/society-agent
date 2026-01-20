#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 20:55:31 2026

@author: anonymous
"""

# scripts/seed_flats.py

from app.db.session import SessionLocal
from app.db.models import Society, Flat

db = SessionLocal()

society = db.query(Society).first()


flats = [
    ("B-1002", "B"),
    ("B-1003", "B"),
    ("B-1004", "B"),
]

for flat_no, block in flats:
    exists = (
        db.query(Flat)
        .filter(Flat.flat_number == flat_no, Flat.society_id == society.id)
        .first()
    )
    if not exists:
        db.add(
            Flat(
                society_id=society.id,
                flat_number=flat_no,
                block=block
            )
        )

db.commit()
db.close()

print("✅ Flats seeded")
