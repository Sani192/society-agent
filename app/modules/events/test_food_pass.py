#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 14:54:11 2026

@author: anonymous
"""

from app.db.session import SessionLocal
from app.db.models import Event, Flat, CommitteeMember
from app.modules.events.food_pass_service import FoodPassService
from app.db.models import EventFoodPass, AuditLog


def run():
    db = SessionLocal()

    event = db.query(Event).first()
    flat = db.query(Flat).first()
    member = db.query(CommitteeMember).first()
    
    # Clean previous test data
    db.query(EventFoodPass).delete()
    db.query(AuditLog).filter(AuditLog.entity_type == "food_pass").delete()
    db.commit()

    FoodPassService.add_or_update_pass(
        db=db,
        event_id=event.id,
        flat_id=flat.id,
        veg_count=2,
        jain_count=1,
        kids_count=0,
        charge_per_person=300,
        performed_by=member.id,
        override_reason="Late guest added after event closure"
    )

    print("✅ Food pass added")

    FoodPassService.mark_not_participating(
        db=db,
        event_id=event.id,
        flat_id=flat.id,
        performed_by=member.id,
        override_reason="Family traveling"
    )

    print("✅ Marked not participating")

    db.close()

if __name__ == "__main__":
    run()
