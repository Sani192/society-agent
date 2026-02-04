#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 04 10:22:18 2026

@author: anonymous
"""

# app/modules/payments/payment_request_service.py

from datetime import datetime
from sqlalchemy.orm import Session

from app.db.models import (
    Event,
    Flat,
    PaymentRequest,
    EventFoodPass
)
from app.modules.payments.payment_service import PaymentService


class PaymentRequestService:

    @staticmethod
    def request_payment(
        db: Session,
        *,
        event_id,
        flat_id,
        amount,
        payment_mode,
        requested_by
    ):
        if amount <= 0:
            raise Exception("Payment amount must be greater than zero")

        event = db.query(Event).filter(Event.id == event_id).first()
        flat = db.query(Flat).filter(Flat.id == flat_id).first()

        if not event or not flat:
            raise Exception("Invalid event or flat")

        food_pass = (
            db.query(EventFoodPass)
            .filter(
                EventFoodPass.event_id == event_id,
                EventFoodPass.flat_id == flat_id,
                EventFoodPass.is_participating.is_(True)
            )
            .first()
        )

        if not food_pass:
            raise Exception("Food pass not found or flat not participating")

        existing = (
            db.query(PaymentRequest)
            .filter(
                PaymentRequest.event_id == event_id,
                PaymentRequest.flat_id == flat_id,
                PaymentRequest.status == "requested",
                PaymentRequest.amount == amount
            )
            .first()
        )

        if existing:
            return existing

        count = (
            db.query(PaymentRequest)
            .filter(PaymentRequest.society_id == event.society_id)
            .count()
        )
        request_code = f"PAY-{count + 1:03d}"

        request = PaymentRequest(
            event_id=event_id,
            society_id=event.society_id,
            flat_id=flat_id,
            request_code=request_code,
            amount=amount,
            payment_mode=payment_mode,
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
            db.query(PaymentRequest)
            .filter(
                PaymentRequest.event_id == event_id,
                PaymentRequest.flat_id == flat_id,
                PaymentRequest.amount == amount,
                PaymentRequest.status == "requested"
            )
            .order_by(PaymentRequest.requested_at.asc())
            .first()
        )

    @staticmethod
    def approve_request(
        db: Session,
        *,
        request: PaymentRequest,
        performed_by
    ):
        payment = PaymentService.record_payment(
            db=db,
            event_id=request.event_id,
            flat_id=request.flat_id,
            amount=request.amount,
            payment_mode=request.payment_mode or "upi",
            performed_by=performed_by,
            override_reason=f"Approved payment request {request.request_code}"
        )

        request.status = "approved"
        request.approved_by = performed_by
        request.approved_at = datetime.utcnow()

        db.commit()

        return payment
