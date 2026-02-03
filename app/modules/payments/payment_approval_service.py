#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 31 17:11:04 2026

@author: anonymous
"""

from sqlalchemy.orm import Session

from app.db.models import Payment, PaymentRequest, Event, AuditLog
from app.modules.workflow.engine import WorkflowEngine


class PaymentApprovalService:

    @staticmethod
    def approve_payment_request(
        db: Session,
        *,
        event_id,
        request_id,
        approved_by,        # CommitteeMember.id (Treasurer / Chairman)
        override_reason=None
    ):
        
        event = db.query(Event).filter(Event.id == event_id).first()

        if not event:
            raise Exception("Invalid event")
            
        # 1️ Load request
        request = (
            db.query(PaymentRequest)
            .filter(PaymentRequest.id == request_id)
            .first()
        )

        if not request:
            raise Exception("Payment request not found.")

        if request.status != "pending":
            raise Exception("Payment request already processed.")

        # 2️ Workflow check (Treasurer / Chairman)
        WorkflowEngine.check_action(
            action="APPROVE_PAYMENT",
            performed_by=approved_by
        )

        # 3️ Load payment
        payment = (
            db.query(Payment)
            .filter(
                Payment.event_id == request.event_id,
                Payment.flat_id == request.flat_id
            )
            .first()
        )

        if not payment:
            raise Exception("Payment record not found.")

        # 4️ Apply money
        payment.paid_amount += request.amount
        payment.status = (
            "paid"
            if payment.paid_amount >= payment.expected_amount
            else "partial"
        )

        # 5️ Mark request approved
        request.status = "approved"

        # 6️ Audit
        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="payment_request",
            entity_id=request.id,
            action="PAYMENT_APPROVED",
            reason="Payment received member",
            performed_by=approved_by
        ))

        db.commit()
