#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:51:13 2026

@author: anonymous
"""

from app.db.session import SessionLocal
from app.db.models import Event, CommitteeMember
from app.modules.expenses.expense_service import ExpenseService
from app.modules.ledger.ledger_service import LedgerService

def run():
    db = SessionLocal()

    event = db.query(Event).first()
    member = db.query(CommitteeMember).first()

    ExpenseService.add_expense(
        db=db,
        event_id=event.id,
        description="Extra water tanker",
        amount=1200,
        performed_by=member.id,
        override_reason="Water shortage on event night"
    )

    balance = LedgerService.calculate_event_balance(
        db=db,
        event_id=event.id,
        opening_balance=12500,
        performed_by=member.id
    )

    print("✅ Ledger calculated")
    print("Opening:", balance.opening_balance)
    print("Closing:", balance.closing_balance)

    db.close()

if __name__ == "__main__":
    run()
