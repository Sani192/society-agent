#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 17 10:55:29 2026

@author: anonymous
"""

# scripts/map_user_to_flat.py
# python -m scripts.map_user_to_flat

from app.db.session import SessionLocal
from app.db.models import Society, Flat
from app.modules.users.user_flat_service import UserFlatService

db = SessionLocal()

society = db.query(Society).first()

flat = (
    db.query(Flat)
    .filter(Flat.flat_number == "D-204", Flat.society_id == society.id)
    .first()
)

UserFlatService.assign_user_to_flat(
    db=db,
    society_id=society.id,
    flat_id=flat.id,
    user_identifier="915555555555"
)

db.close()
print("✅ User mapped to flat")
