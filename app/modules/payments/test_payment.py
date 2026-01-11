#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 15:23:26 2026

@author: anonymous
"""

from app.db.session import SessionLocal
from app.db.models import Event, Flat, CommitteeMember, Payment
from app.modules.events.food_pass_service import FoodPassService
from app.modules.payments.payment_service import PaymentService

def run():
    db = SessionLocal()

    event = db.query(Event).first()
    flat = db.query(Flat).first()
    member = db.query(CommitteeMember).first()

    # Clean previous payments for test
    db.query(Payment).delete()
    db.commit()
    
    # Ensure flat is participating before payment
    FoodPassService.add_or_update_pass(
        db=db,
        event_id=event.id,
        flat_id=flat.id,
        veg_count=2,
        jain_count=0,
        kids_count=0,
        charge_per_person=300,
        performed_by=member.id,
        override_reason="Re-added participation for payment test"
    )

    PaymentService.record_payment(
        db=db,
        event_id=event.id,
        flat_id=flat.id,
        amount=300,
        payment_mode="upi",
        performed_by=member.id,
        override_reason="Late payment after event"
    )

    PaymentService.record_payment(
        db=db,
        event_id=event.id,
        flat_id=flat.id,
        amount=300,
        payment_mode="cash",
        performed_by=member.id,
        override_reason="Second installment collected"
    )

    print("✅ Payments recorded")

    db.close()

if __name__ == "__main__":
    run()
