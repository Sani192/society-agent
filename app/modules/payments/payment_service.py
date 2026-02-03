#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 15:19:25 2026

@author: anonymous
"""

# app/modules/payments/payment_service.py

import uuid

from sqlalchemy.orm import Session
from datetime import datetime

from app.db.models import (
    Event,
    Flat,
    Payment,
    PaymentRequest,
    UserFlatMapping,
    EventFoodPass,
    AuditLog
)
from app.workflows.engine import WorkflowEngine


class PaymentService:

    @staticmethod
    def record_payment(
        db: Session,
        *,
        event_id,
        flat_id,
        amount,
        payment_mode,
        performed_by,
        override_reason=None
    ):
        """
        Record a payment (partial or full) for a flat in an event.
        """

        if amount <= 0:
            raise Exception("Payment amount must be greater than zero")

        event = db.query(Event).filter(Event.id == event_id).first()
        flat = db.query(Flat).filter(Flat.id == flat_id).first()

        if not event or not flat:
            raise Exception("Invalid event or flat")
            
        
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
        
            request = PaymentRequest(
                id=uuid.uuid4(),
                event_id=event_id,
                flat_id=flat_id,
                requested_by=mapping.id,
                amount=amount,
                status="pending"
            )
        
            db.add(request)
        
            # IMPORTANT: do NOT touch payment.paid_amount here
            # IMPORTANT: do NOT call WorkflowEngine
            # IMPORTANT: do NOT mark payment as paid/partial
            
            db.add(AuditLog(
                society_id=event.society_id,
                entity_type="payment_request",
                entity_id=request.id,
                action="PAYMENT_REQUESTED",
                reason="Member payment request",
                performed_by=performed_by
            ))
        
            db.commit()
            return
        

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="MARK_PAID"
        )

        if not decision.allowed:
            if not override_reason:
                raise Exception(decision.message)
            # Override permission only – no audit here
            WorkflowEngine.apply_override(
                db=db,
                society_id=event.society_id,
                event_id=event_id,
                entity_type="payment",
                entity_id=flat_id,
                action="MARK_PAID",
                reason=override_reason,
                performed_by=performed_by
            )

        food_pass = (
            db.query(EventFoodPass)
            .filter(
                EventFoodPass.event_id == event_id,
                EventFoodPass.flat_id == flat_id,
                EventFoodPass.is_participating == True
            )
            .first()
        )

        if not food_pass:
            raise Exception("Food pass not found or flat not participating")

        payment = (
            db.query(Payment)
            .filter(
                Payment.event_id == event_id,
                Payment.flat_id == flat_id
            )
            .first()
        )

        expected_amount = food_pass.total_amount

        if not payment:
            payment = Payment(
                event_id=event_id,
                flat_id=flat_id,
                expected_amount=expected_amount,
                paid_amount=0,
                status="pending"
            )
            db.add(payment)

        payment.paid_amount += amount
        payment.payment_mode = payment_mode
        payment.paid_at = datetime.utcnow()

        if payment.paid_amount >= expected_amount:
            payment.status = "paid"
            payment.paid_amount = expected_amount
        else:
            payment.status = "partial"

        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="payment",
            entity_id=flat_id,
            action="MARK_PAID",
            reason=(
                f"OVERRIDE: {override_reason}"
                if override_reason
                else f"Payment received via {payment_mode}"
            ),
            performed_by=performed_by
        ))

        db.commit()

        return payment
