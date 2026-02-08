#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 20:55:31 2026

@author: anonymous
"""

# scripts/seed_flats.py
# python -m scripts.seed_flats

from app.db.session import SessionLocal
from app.db.models import Society, Flat

db = SessionLocal()

society = db.query(Society).first()


flats = [
    ("A-804", "A", "JK")
]

for flat_no, block, owner_name in flats:
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
                block=block,
                owner_name=owner_name
            )
        )

db.commit()
db.close()

print("✅ Flats seeded")
