#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 04 10:22:18 2026

@author: anonymous
"""

# app/modules/payments/payment_request_service.py

from datetime import datetime
import logging
from sqlalchemy.orm import Session

from app.db.models import (
    Event,
    Flat,
    PaymentRequest,
    EventFoodPass,
    AuditLog
)
from app.modules.payments.payment_service import PaymentService
from app.workflows.engine import WorkflowEngine
from app.utils.logging_helpers import build_log_context, log_entry, log_exit, log_service_call

logger = logging.getLogger(__name__)


class PaymentRequestService:

    @staticmethod
    def request_payment(
        db: Session,
        *,
        event_id,
        flat_id,
        amount,
        payment_mode,
        requested_by_mapping_id,
        override_reason=None
    ):
        context = build_log_context(
            event_id=event_id,
            flat_id=flat_id,
            performed_by=requested_by_mapping_id
        )
        log_entry(logger, "PaymentRequestService.request_payment", context)
        if amount <= 0:
            logger.warning(
                "Validation failed for payment request: amount <= 0 | context=%s",
                context
            )
            raise Exception("Payment amount must be greater than zero")

        event = db.query(Event).filter(Event.id == event_id).first()
        flat = db.query(Flat).filter(Flat.id == flat_id).first()

        if not event or not flat:
            logger.warning(
                "Validation failed for payment request: invalid event/flat | context=%s",
                context
            )
            raise Exception("Invalid event or flat")

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="REQUEST_PAYMENT",
            performed_by=requested_by_mapping_id,
            override_reason=override_reason
        )

        is_override = False

        if not decision.allowed:
            if not decision.requires_override:
                raise Exception(decision.message)
            if not override_reason:
                raise Exception(decision.message)
            is_override = True

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
            logger.warning(
                "Validation failed for payment request: missing food pass | context=%s",
                context
            )
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
            logger.info(
                "Workflow decision: returning existing payment request | context=%s",
                {
                    **context,
                    "request_code": existing.request_code
                }
            )
            log_exit(logger, "PaymentRequestService.request_payment", context)
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
            requested_by_mapping_id=requested_by_mapping_id
        )

        logger.info(
            "DB write: creating payment request | context=%s",
            {
                **context,
                "society_id": event.society_id,
                "request_code": request_code
            }
        )
        db.add(request)
        db.flush()

        if is_override:
            WorkflowEngine.apply_override(
                db=db,
                society_id=event.society_id,
                event_id=event_id,
                entity_type="payment_request",
                entity_id=request.id,
                action="REQUEST_PAYMENT",
                reason=override_reason,
                performed_by=requested_by_mapping_id
            )

        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="payment_request",
            entity_id=request.id,
            action="REQUEST_PAYMENT",
            reason=(
                f"OVERRIDE: {override_reason}"
                if is_override
                else f"Request {request.request_code} for ₹{amount} by mapping {requested_by_mapping_id}"
            ),
            performed_by=None
        ))
        try:
            db.commit()
            logger.info(
                "Commit success: payment request created | context=%s",
                {
                    **context,
                    "society_id": event.society_id,
                    "request_code": request_code
                }
            )
        except Exception:
            logger.exception(
                "Commit failure: payment request create | context=%s",
                {
                    **context,
                    "society_id": event.society_id,
                    "request_code": request_code
                }
            )
            db.rollback()
            raise

        log_exit(logger, "PaymentRequestService.request_payment", context)
        return request

    @staticmethod
    @log_service_call(logger, "PaymentRequestService.find_matching_request")
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
        context = build_log_context(
            event_id=request.event_id,
            flat_id=request.flat_id,
            society_id=request.society_id,
            performed_by=performed_by,
            request_code=request.request_code
        )
        log_entry(logger, "PaymentRequestService.approve_request", context)
        logger.info(
            "Workflow decision: approving payment request | context=%s",
            context
        )
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

        db.add(AuditLog(
            society_id=request.society_id,
            entity_type="payment_request",
            entity_id=request.id,
            action="APPROVE_PAYMENT_REQUEST",
            reason=(
                "Approved "
                f"{request.request_code} for ₹{request.amount} "
                f"requested by mapping {request.requested_by_mapping_id}"
            ),
            performed_by=performed_by
        ))
        logger.info("DB write: updating payment request status | context=%s", context)
        try:
            db.commit()
            logger.info(
                "Commit success: payment request approved | context=%s",
                context
            )
        except Exception:
            logger.exception(
                "Commit failure: payment request approve | context=%s",
                context
            )
            db.rollback()
            raise

        log_exit(logger, "PaymentRequestService.approve_request", context)
        return payment

    @staticmethod
    def reject_request(
        db: Session,
        *,
        request: PaymentRequest,
        performed_by,
        rejection_reason=None
    ):
        request.status = "rejected"

        reason = (
            f"Rejected {request.request_code} for ₹{request.amount} "
            f"requested by mapping {request.requested_by_mapping_id}"
        )
        if rejection_reason:
            reason = f"{reason} | {rejection_reason}"

        db.add(AuditLog(
            society_id=request.society_id,
            entity_type="payment_request",
            entity_id=request.id,
            action="REJECT_PAYMENT_REQUEST",
            reason=reason,
            performed_by=performed_by
        ))
        db.commit()

    @staticmethod
    @log_service_call(logger, "PaymentRequestService.get_request_by_code")
    def get_request_by_code(db: Session, *, request_code):
        return (
            db.query(PaymentRequest)
            .filter(PaymentRequest.request_code == request_code)
            .first()
        )

    @staticmethod
    @log_service_call(logger, "PaymentRequestService.list_requests")
    def list_requests(
        db: Session,
        *,
        event_id,
        status=None,
        requested_by_mapping_ids=None
    ):
        query = (
            db.query(PaymentRequest, Flat)
            .join(Flat, PaymentRequest.flat_id == Flat.id)
            .filter(PaymentRequest.event_id == event_id)
        )

        if status:
            query = query.filter(PaymentRequest.status == status)
        else:
            query = query.filter(PaymentRequest.status != "approved")

        if requested_by_mapping_ids:
            query = query.filter(PaymentRequest.requested_by_mapping_id.in_(requested_by_mapping_ids))

        return (
            query
            .order_by(PaymentRequest.requested_at.desc())
            .all()
        )
