#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 17 12:01:15 2026

@author: anonymous
"""

# app/modules/reminders/reminder_service.py

from datetime import date
import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import Event, Payment, Flat, PaymentReminder
from app.utils.logging_helpers import build_log_context, log_entry, log_exit

logger = logging.getLogger(__name__)


class ReminderService:

    @staticmethod
    def generate_pending_payment_reminders(
        db: Session,
        *,
        event_id
    ):
        context = build_log_context(event_id=event_id)
        log_entry(logger, "ReminderService.generate_pending_payment_reminders", context)
        today = date.today()

        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise Exception("Invalid event")

        authoritative_society_id = event.society_id

        context = build_log_context(
            society_id=authoritative_society_id,
            event_id=event_id
        )

        pending_payments = (
            db.query(Payment)
            .join(Flat)
            .filter(
                Flat.society_id == authoritative_society_id,
                Payment.event_id == event_id,
                Payment.expected_amount > Payment.paid_amount
            )
            .all()
        )

        generated = []
        if not pending_payments:
            logger.info(
                "Workflow decision: no pending payments to remind | context=%s",
                context
            )

        bind = db.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""

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
                logger.info(
                    "Workflow decision: reminder already exists | context=%s",
                    {
                        **context,
                        "flat_id": payment.flat_id
                    }
                )
                continue

            reminder_values = {
                "society_id": authoritative_society_id,
                "event_id": event_id,
                "flat_id": payment.flat_id,
                "pending_amount": payment.expected_amount - payment.paid_amount,
                "reminder_date": today,
            }

            if dialect_name == "sqlite":
                insert_stmt = (
                    sqlite_insert(PaymentReminder)
                    .values(**reminder_values)
                    .on_conflict_do_nothing(
                        index_elements=["event_id", "flat_id", "reminder_date"]
                    )
                )
            else:
                insert_stmt = (
                    pg_insert(PaymentReminder)
                    .values(**reminder_values)
                    .on_conflict_do_nothing(
                        index_elements=["event_id", "flat_id", "reminder_date"]
                    )
                    .returning(PaymentReminder.id)
                )

            insert_result = db.execute(insert_stmt)
            inserted = insert_result.rowcount and insert_result.rowcount > 0

            if inserted:
                generated.append(
                    PaymentReminder(
                        society_id=authoritative_society_id,
                        event_id=event_id,
                        flat_id=payment.flat_id,
                        pending_amount=payment.expected_amount - payment.paid_amount,
                        reminder_date=today,
                    )
                )
            else:
                logger.info(
                    "Workflow decision: reminder conflicted and was ignored | context=%s",
                    {
                        **context,
                        "flat_id": payment.flat_id,
                    },
                )

        if generated:
            logger.info(
                "DB write: creating %d payment reminders | context=%s",
                len(generated),
                context
            )
        try:
            db.commit()
            logger.info(
                "Commit success: reminders generated | context=%s",
                context
            )
        except Exception:
            logger.exception(
                "Commit failure: reminder generation | context=%s",
                context
            )
            db.rollback()
            raise
        log_exit(logger, "ReminderService.generate_pending_payment_reminders", context)
        return generated
