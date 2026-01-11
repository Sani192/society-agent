#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:45:22 2026

@author: anonymous
"""

from app.db.session import SessionLocal
from app.db.models import Event, Flat, CommitteeMember, Refund, Payment
from app.modules.payments.refund_service import RefundService

def run():
    db = SessionLocal()

    event = db.query(Event).first()
    flat = db.query(Flat).first()
    member = db.query(CommitteeMember).first()

    # Clean previous refunds for test
    db.query(Refund).delete()
    db.commit()

    RefundService.process_refund(
        db=db,
        event_id=event.id,
        flat_id=flat.id,
        amount=300,
        performed_by=member.id,
        reason="Food quality issue",
        override_reason="Complaint raised after event"
    )

    print("✅ Refund processed")

    db.close()

if __name__ == "__main__":
    run()
