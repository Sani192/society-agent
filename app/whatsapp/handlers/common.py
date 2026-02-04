#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 04 10:29:20 2026

@author: anonymous
"""

# app/whatsapp/handlers/common.py

from app.db.models import Event, Flat
from app.utils.guards import ensure_member_of_society


def get_latest_event(db):
    return db.query(Event).order_by(Event.created_at.desc()).first()


def resolve_flat(
    db,
    *,
    phone_number,
    society_id,
    flat_number=None
):
    if flat_number:
        flat = (
            db.query(Flat)
            .filter(
                Flat.flat_number == flat_number,
                Flat.society_id == society_id
            )
            .first()
        )
        if not flat:
            raise Exception("Flat not found in society.")
        return flat

    mappings = ensure_member_of_society(phone_number, db, society_id)
    return db.query(Flat).get(mappings[0].flat_id)
