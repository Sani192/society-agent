#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:44:25 2026

@author: anonymous
"""

# app/modules/payments/refund_service.py
import uuid

from sqlalchemy.orm import Session
from datetime import datetime

from app.db.models import (
    Event,
    Flat,
    Payment,
    PaymentRequest,
    Refund,
    UserFlatMapping,
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

        if amount > payment.paid_amount:
            raise Exception("Refund amount exceeds paid amount")    
            
        # --------------------------------------------------
        # STEP 1: MEMBER PAYMENT → CREATE PAYMENT REQUEST
        # --------------------------------------------------
        if performed_by is None:
            # member payment should not mark paid directly
        
            mapping = (
                db.query(UserFlatMapping)
                .filter(
                    UserFlatMapping.flat_id == flat_id,
                    UserFlatMapping.is_active.is_(True)
                )
                .first()
            )
        
            if not mapping:
                raise Exception("User is not mapped to this flat.")
        
            # Create refund record
            refund = Refund(
                id=uuid.uuid4(),
                event_id=event_id,
                flat_id=flat_id,
                amount=amount,
                reason=reason,
                status="refunded",
                created_by=performed_by
            )

            db.add(refund)
            
            db.add(AuditLog(
                society_id=event.society_id,
                entity_type="refund_request",
                entity_id=refund.id,
                action="REFUND_REQUESTED",
                reason="Member refund request",
                performed_by=performed_by
            ))
        
            db.commit()
            return
            

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="REQUEST_REFUND"
        )

        if not decision.allowed:
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

        # Adjust payment
        payment.paid_amount -= amount

        if payment.paid_amount == 0:
            payment.status = "refunded"
        elif payment.paid_amount < payment.expected_amount:
            payment.status = "partial"

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
