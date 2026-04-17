#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 04 10:22:18 2026

@author: anonymous
"""

# app/modules/payments/payment_request_service.py

import logging
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.models import UserFlatMapping as UserFlatMappingModel

from app.db.models import (
    Event,
    Flat,
    PaymentRequest,
    EventFoodPass,
    AuditLog,
    UserFlatMapping
)
from app.modules.payments.payment_service import PaymentService
from app.modules.security.access_control import require_committee_action
from app.workflows.engine import WorkflowEngine
from app.utils.logging_helpers import build_log_context, log_entry, log_exit, log_service_call
from app.utils.time import utc_now
from app.utils.currency import format_currency
from app.utils.validation import validate_uuid
from app.utils.request_codes import (
    MAX_REQUEST_CODE_GENERATION_ATTEMPTS,
    generate_request_code,
)

logger = logging.getLogger(__name__)


class PaymentRequestService:
    @staticmethod
    def _authorize_requester_mapping(*, mapping, event, flat_id) -> UserFlatMappingModel:
        if not mapping:
            raise Exception("Invalid requester mapping")
        if mapping.society_id != event.society_id or not mapping.is_active:
            raise Exception("Requester mapping is not active for this society")
        if mapping.flat_id != flat_id:
            raise Exception("Requester is not authorized for the selected flat")
        return mapping

    @staticmethod
    def _get_event_society_id(db: Session, event_id):
        event_id = validate_uuid(event_id, field_name="event_id")
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise Exception("Invalid event")
        return event.society_id

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
        event_id = validate_uuid(event_id, field_name="event_id")
        flat_id = validate_uuid(flat_id, field_name="flat_id")
        context = build_log_context(
            event_id=event_id,
            flat_id=flat_id,
            performed_by=None,
            requested_by_mapping_id=requested_by_mapping_id,
        )
        log_entry(logger, "PaymentRequestService.request_payment", context)
        if amount <= 0:
            logger.warning(
                "Validation failed for payment request: amount <= 0",
                extra={"action": "REQUEST_PAYMENT", "result": "invalid_amount", "context": context},
            )
            raise Exception("Payment amount must be greater than zero")

        event = db.query(Event).filter(Event.id == event_id).first()
        flat = db.query(Flat).filter(Flat.id == flat_id).first()

        if not event or not flat:
            logger.warning(
                "Validation failed for payment request: invalid event/flat",
                extra={"action": "REQUEST_PAYMENT", "result": "invalid_event_or_flat", "context": context},
            )
            raise Exception("Invalid event or flat")

        if flat.society_id != event.society_id:
            logger.warning(
                "Validation failed for payment request: flat/event society mismatch",
                extra={
                    "action": "REQUEST_PAYMENT",
                    "result": "society_mismatch",
                    "context": {
                        **context,
                        "event_society_id": event.society_id,
                        "flat_society_id": flat.society_id,
                    },
                },
            )
            raise Exception("Flat does not belong to the event society")

        mapping = db.query(UserFlatMapping).filter(UserFlatMapping.id == requested_by_mapping_id).first()
        mapping = PaymentRequestService._authorize_requester_mapping(
            mapping=mapping,
            event=event,
            flat_id=flat_id,
        )

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="REQUEST_PAYMENT",
            performed_by=None,
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
                "Validation failed for payment request: missing food pass",
                extra={"action": "REQUEST_PAYMENT", "result": "food_pass_missing", "context": context},
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
                "Workflow decision: returning existing payment request",
                extra={
                    "action": "REQUEST_PAYMENT",
                    "result": "existing_request_reused",
                    "context": {**context, "request_code": existing.request_code},
                },
            )
            log_exit(logger, "PaymentRequestService.request_payment", context)
            return existing

        request = None
        request_code = None
        for _ in range(MAX_REQUEST_CODE_GENERATION_ATTEMPTS):
            request_code = generate_request_code(prefix="PAY")
            request = PaymentRequest(
                event_id=event_id,
                flat_id=flat_id,
                request_code=request_code,
                amount=amount,
                payment_mode=payment_mode,
                status="requested",
                requested_by_mapping_id=requested_by_mapping_id,
                member_identity_id=mapping.member_identity_id
            )

            logger.info(
                "DB write: creating payment request",
                extra={
                    "action": "REQUEST_PAYMENT",
                    "result": "db_create_pending",
                    "context": {
                        **context,
                        "society_id": event.society_id,
                        "request_code": request_code,
                    },
                },
            )
            db.add(request)
            try:
                db.flush()
                break
            except IntegrityError:
                db.rollback()
                logger.warning(
                    "Payment request code conflict; retrying generation",
                    extra={
                        "action": "REQUEST_PAYMENT",
                        "result": "request_code_conflict_retry",
                        "context": {**context, "request_code": request_code},
                    },
                )
                request = None
        if request is None:
            raise Exception("Could not generate a unique payment request code. Please retry.")

        if is_override:
            PaymentRequestService._authorize_requester_mapping(
                mapping=mapping,
                event=event,
                flat_id=flat_id,
            )
            WorkflowEngine.apply_override(
                db=db,
                society_id=event.society_id,
                event_id=event_id,
                entity_type="payment_request",
                entity_id=request.id,
                action="REQUEST_PAYMENT",
                reason=override_reason,
                performed_by=None
            )

        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="payment_request",
            entity_id=request.id,
            action="REQUEST_PAYMENT",
            reason=(
                f"OVERRIDE: {override_reason}"
                if is_override
                else f"Request {request.request_code} for {format_currency(amount)} by mapping {requested_by_mapping_id}"
            ),
            performed_by=None
        ))
        try:
            db.commit()
            logger.info(
                "Commit success: payment request created",
                extra={
                    "action": "REQUEST_PAYMENT",
                    "result": "committed",
                    "context": {
                        **context,
                        "society_id": event.society_id,
                        "request_code": request_code,
                    },
                },
            )
        except Exception:
            logger.exception(
                "Commit failure: payment request create",
                extra={
                    "action": "REQUEST_PAYMENT",
                    "result": "commit_failed",
                    "context": {
                        **context,
                        "society_id": event.society_id,
                        "request_code": request_code,
                    },
                },
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
        event_id = validate_uuid(event_id, field_name="event_id")
        flat_id = validate_uuid(flat_id, field_name="flat_id")
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
        request,
        performed_by
    ):
        performed_by = validate_uuid(performed_by, field_name="member_id")
        if request.status != "requested":
            raise Exception("Payment request is no longer pending")
        event_society_id = PaymentRequestService._get_event_society_id(db, request.event_id)
        require_committee_action(
            db,
            society_id=event_society_id,
            performed_by=performed_by,
            action="PAY",
        )
        context = build_log_context(
            event_id=request.event_id,
            flat_id=request.flat_id,
            society_id=event_society_id,
            performed_by=performed_by,
            request_code=request.request_code
        )
        log_entry(logger, "PaymentRequestService.approve_request", context)
        logger.info(
            "Workflow decision: approving payment request",
            extra={"action": "APPROVE_PAYMENT_REQUEST", "result": "started", "context": context},
        )
        payment = PaymentService.record_payment(
            db=db,
            event_id=request.event_id,
            flat_id=request.flat_id,
            amount=request.amount,
            payment_mode=request.payment_mode or "upi",
            performed_by=performed_by,
            override_reason=f"Approved payment request {request.request_code}",
            require_approved_request_context=True,
            approved_request_id=request.id,
        )

        request.status = "approved"
        request.approved_by = performed_by
        request.approved_at = utc_now()

        db.add(AuditLog(
            society_id=event_society_id,
            entity_type="payment_request",
            entity_id=request.id,
            action="APPROVE_PAYMENT_REQUEST",
            reason=(
                "Approved "
                f"{request.request_code} for {format_currency(request.amount)} "
                f"requested by mapping {request.requested_by_mapping_id}"
            ),
            performed_by=performed_by
        ))
        logger.info(
            "DB write: updating payment request status",
            extra={"action": "APPROVE_PAYMENT_REQUEST", "result": "db_update_pending", "context": context},
        )
        try:
            db.commit()
            logger.info(
                "Commit success: payment request approved",
                extra={"action": "APPROVE_PAYMENT_REQUEST", "result": "committed", "context": context},
            )
        except Exception:
            logger.exception(
                "Commit failure: payment request approve",
                extra={"action": "APPROVE_PAYMENT_REQUEST", "result": "commit_failed", "context": context},
            )
            db.rollback()
            raise

        log_exit(logger, "PaymentRequestService.approve_request", context)
        return payment

    @staticmethod
    def reject_request(
        db: Session,
        *,
        request,
        performed_by,
        rejection_reason=None
    ):
        performed_by = validate_uuid(performed_by, field_name="member_id")
        event_society_id = PaymentRequestService._get_event_society_id(db, request.event_id)
        require_committee_action(
            db,
            society_id=event_society_id,
            performed_by=performed_by,
            action="PAY",
        )
        request.status = "rejected"

        reason = (
            f"Rejected {request.request_code} for {format_currency(request.amount)} "
            f"requested by mapping {request.requested_by_mapping_id}"
        )
        if rejection_reason:
            reason = f"{reason} | {rejection_reason}"

        db.add(AuditLog(
            society_id=event_society_id,
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
        requested_by_mapping_ids=None,
        flat_id=None
    ):
        event_id = validate_uuid(event_id, field_name="event_id")
        if flat_id is not None:
            flat_id = validate_uuid(flat_id, field_name="flat_id")
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

        if flat_id:
            query = query.filter(PaymentRequest.flat_id == flat_id)

        return (
            query
            .order_by(PaymentRequest.requested_at.desc())
            .all()
        )
