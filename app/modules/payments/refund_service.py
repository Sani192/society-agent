#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:44:25 2026

@author: anonymous
"""

# app/modules/payments/refund_service.py

from sqlalchemy.orm import Session
from datetime import datetime

from app.db.models import (
    Event,
    Flat,
    Payment,
    Refund,
    AuditLog
)
from app.workflows.engine import WorkflowEngine


class RefundService:

    @staticmethod
    def process_refund(
        db: Session,
        *,
        event_id,
        flat_id,
        amount,
        performed_by,
        reason,
        override_reason=None
    ):
        """
        Process a partial or full refund for a flat.
        """

        if amount <= 0:
            raise Exception("Refund amount must be greater than zero")

        event = db.query(Event).filter(Event.id == event_id).first()
        flat = db.query(Flat).filter(Flat.id == flat_id).first()

        if not event or not flat:
            raise Exception("Invalid event or flat")

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="REQUEST_REFUND",
            performed_by=performed_by,
            override_reason=override_reason
        )

        if not decision.allowed:
            if not decision.requires_override:
                raise Exception(decision.message)
            if not override_reason:
                raise Exception(decision.message)
            WorkflowEngine.apply_override(
                db=db,
                society_id=event.society_id,
                event_id=event_id,
                entity_type="refund",
                entity_id=flat_id,
                action="REQUEST_REFUND",
                reason=override_reason,
                performed_by=performed_by
            )

        payment = (
            db.query(Payment)
            .filter(
                Payment.event_id == event_id,
                Payment.flat_id == flat_id
            )
            .first()
        )

        if not payment or payment.paid_amount <= 0:
            raise Exception("No payment available for refund")

        refunded_total = (
            db.query(Refund)
            .filter(
                Refund.event_id == event_id,
                Refund.flat_id == flat_id,
                Refund.status == "refunded"
            )
            .all()
        )
        total_refunded = sum(r.amount for r in refunded_total)

        if amount + total_refunded > payment.paid_amount:
            raise Exception("Refund amount exceeds paid amount")

        # Create refund record
        refund = Refund(
            event_id=event_id,
            flat_id=flat_id,
            amount=amount,
            reason=reason,
            status="refunded",
            created_by=performed_by
        )

        db.add(refund)

        payment.status = "refunded"

        # Audit log (ONE entry only)
        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="refund",
            entity_id=flat_id,
            action="PROCESS_REFUND",
            reason=(
                f"OVERRIDE: {override_reason} | {reason}"
                if override_reason
                else reason
            ),
            performed_by=performed_by
        ))

        db.commit()

        return refund
