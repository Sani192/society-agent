#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 04 10:23:02 2026

@author: anonymous
"""

# app/modules/payments/refund_request_service.py

from datetime import datetime
from sqlalchemy.orm import Session

from app.db.models import (
    Event,
    Flat,
    RefundRequest,
    Payment
)
from app.modules.payments.refund_service import RefundService
from app.workflows.engine import WorkflowEngine


class RefundRequestService:

    @staticmethod
    def request_refund(
        db: Session,
        *,
        event_id,
        flat_id,
        amount,
        reason,
        requested_by
    ):
        if amount <= 0:
            raise Exception("Refund amount must be greater than zero")

        event = db.query(Event).filter(Event.id == event_id).first()
        flat = db.query(Flat).filter(Flat.id == flat_id).first()

        if not event or not flat:
            raise Exception("Invalid event or flat")

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="REQUEST_REFUND"
        )

        if not decision.allowed:
            raise Exception(decision.message)

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

        existing = (
            db.query(RefundRequest)
            .filter(
                RefundRequest.event_id == event_id,
                RefundRequest.flat_id == flat_id,
                RefundRequest.status == "requested",
                RefundRequest.amount == amount
            )
            .first()
        )

        if existing:
            return existing

        count = (
            db.query(RefundRequest)
            .filter(RefundRequest.society_id == event.society_id)
            .count()
        )
        request_code = f"REF-{count + 1:03d}"

        request = RefundRequest(
            event_id=event_id,
            society_id=event.society_id,
            flat_id=flat_id,
            request_code=request_code,
            amount=amount,
            reason=reason,
            status="requested",
            requested_by=requested_by
        )

        db.add(request)
        db.commit()

        return request

    @staticmethod
    def find_matching_request(
        db: Session,
        *,
        event_id,
        flat_id,
        amount
    ):
        return (
            db.query(RefundRequest)
            .filter(
                RefundRequest.event_id == event_id,
                RefundRequest.flat_id == flat_id,
                RefundRequest.amount == amount,
                RefundRequest.status == "requested"
            )
            .order_by(RefundRequest.requested_at.asc())
            .first()
        )

    @staticmethod
    def approve_request(
        db: Session,
        *,
        request: RefundRequest,
        performed_by
    ):
        refund = RefundService.process_refund(
            db=db,
            event_id=request.event_id,
            flat_id=request.flat_id,
            amount=request.amount,
            performed_by=performed_by,
            reason=request.reason,
            override_reason=f"Approved refund request {request.request_code}"
        )

        request.status = "approved"
        request.approved_by = performed_by
        request.approved_at = datetime.utcnow()

        db.commit()

        return refund
