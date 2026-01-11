#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 06:07:33 2026

@author: anonymous
"""

# app/whatsapp/handler.py

from app.db.session import SessionLocal
from app.db.models import CommitteeMember, Event, Flat

from app.whatsapp.router import detect_intent

from app.modules.events.food_pass_service import FoodPassService
from app.modules.payments.payment_service import PaymentService
from app.modules.payments.refund_service import RefundService
from app.modules.expenses.expense_service import ExpenseService
from app.modules.reports.event_summary import EventSummaryReport


def handle_message(phone_number: str, message: str):
    db = SessionLocal()

    member = (
        db.query(CommitteeMember)
        .filter(CommitteeMember.phone_number == phone_number)
        .first()
    )

    if not member or not member.is_active:
        return "❌ You are not authorized."

    event = db.query(Event).order_by(Event.created_at.desc()).first()

    intent = detect_intent(message)
    if not intent:
        return "❓ Sorry, I didn’t understand this command."

    try:
        # ---------- ADD PASS ----------
        if intent == "ADD_PASS":
            flat = db.query(Flat).first()  # demo: auto-pick
            FoodPassService.add_or_update_pass(
                db=db,
                event_id=event.id,
                flat_id=flat.id,
                veg_count=2,
                jain_count=0,
                kids_count=0,
                charge_per_person=300,
                performed_by=member.id,
                override_reason="Via WhatsApp"
            )
            return "✅ Food pass updated."

        # ---------- PAYMENT ----------
        if intent == "PAY":
            flat = db.query(Flat).first()
            PaymentService.record_payment(
                db=db,
                event_id=event.id,
                flat_id=flat.id,
                amount=300,
                payment_mode="upi",
                performed_by=member.id,
                override_reason="Via WhatsApp"
            )
            return "💰 Payment recorded."

        # ---------- REFUND ----------
        if intent == "REFUND":
            flat = db.query(Flat).first()
            RefundService.process_refund(
                db=db,
                event_id=event.id,
                flat_id=flat.id,
                amount=100,
                performed_by=member.id,
                reason="WhatsApp refund",
                override_reason="Via WhatsApp"
            )
            return "↩️ Refund processed."

        # ---------- EXPENSE ----------
        if intent == "ADD_EXPENSE":
            ExpenseService.add_expense(
                db=db,
                event_id=event.id,
                description="WhatsApp expense",
                amount=500,
                performed_by=member.id,
                override_reason="Via WhatsApp"
            )
            return "🧾 Expense added."

        # ---------- SUMMARY ----------
        if intent == "SUMMARY":
            summary = EventSummaryReport.generate(db=db, event_id=event.id)
            return (
                f"📊 *{summary['event']}*\n"
                f"Income: ₹{summary['income']['flats']}\n"
                f"Expenses: ₹{summary['expenses']}\n"
                f"Closing Balance: ₹{summary['closing_balance']}"
            )

    except Exception as e:
        return f"⚠️ Error: {str(e)}"

    finally:
        db.close()
