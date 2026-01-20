#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 17 12:01:15 2026

@author: anonymous
"""

# app/modules/reminders/reminder_service.py

from datetime import date
from sqlalchemy.orm import Session

from app.db.models import Payment, Flat, PaymentReminder


class ReminderService:

    @staticmethod
    def generate_pending_payment_reminders(
        db: Session,
        *,
        society_id,
        event_id
    ):
        today = date.today()

        pending_payments = (
            db.query(Payment)
            .join(Flat)
            .filter(
                Flat.society_id == society_id,
                Payment.event_id == event_id,
                Payment.expected_amount > Payment.paid_amount
            )
            .all()
        )

        generated = []

        for payment in pending_payments:
            exists = (
                db.query(PaymentReminder)
                .filter(
                    PaymentReminder.flat_id == payment.flat_id,
                    PaymentReminder.event_id == event_id,
                    PaymentReminder.reminder_date == today
                )
                .first()
            )

            if exists:
                continue

            reminder = PaymentReminder(
                society_id=society_id,
                event_id=event_id,
                flat_id=payment.flat_id,
                pending_amount=payment.expected_amount - payment.paid_amount,
                reminder_date=today
            )

            db.add(reminder)
            generated.append(reminder)

        db.commit()
        return generated
