#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 04 10:23:02 2026

@author: anonymous
"""

# app/modules/payments/refund_request_service.py

import logging
from sqlalchemy.orm import Session

from app.db.models import (
    Event,
    Flat,
    RefundRequest,
    Payment,
    AuditLog,
    UserFlatMapping
)
from app.modules.payments.refund_service import RefundService
from app.modules.security.access_control import require_committee_action
from app.workflows.engine import WorkflowEngine
from app.utils.logging_helpers import build_log_context, log_entry, log_exit, log_service_call
from app.utils.time import utc_now
from app.utils.currency import format_currency
from app.utils.validation import validate_uuid

logger = logging.getLogger(__name__)


class RefundRequestService:
    @staticmethod
    def _authorize_requester_mapping(*, mapping, event, flat_id):
        if not mapping:
            raise Exception("Invalid requester mapping")
        if mapping.society_id != event.society_id or not mapping.is_active:
            raise Exception("Requester mapping is not active for this society")
        if mapping.flat_id != flat_id:
            raise Exception("Requester is not authorized for the selected flat")

    @staticmethod
    def _get_event_society_id(db: Session, event_id):
        event_id = validate_uuid(event_id, field_name="event_id")
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise Exception("Invalid event")
        return event.society_id

    @staticmethod
    def request_refund(
        db: Session,
        *,
        event_id,
        flat_id,
        amount,
        reason,
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
        log_entry(logger, "RefundRequestService.request_refund", context)
        if amount <= 0:
            logger.warning(
                "Validation failed for refund request: amount <= 0",
                extra={"action": "REQUEST_REFUND", "result": "invalid_amount", "context": context},
            )
            raise Exception("Refund amount must be greater than zero")

        event = db.query(Event).filter(Event.id == event_id).first()
        flat = db.query(Flat).filter(Flat.id == flat_id).first()

        if not event or not flat:
            logger.warning(
                "Validation failed for refund request: invalid event/flat",
                extra={"action": "REQUEST_REFUND", "result": "invalid_event_or_flat", "context": context},
            )
            raise Exception("Invalid event or flat")

        if flat.society_id != event.society_id:
            logger.warning(
                "Validation failed for refund request: flat/event society mismatch",
                extra={
                    "action": "REQUEST_REFUND",
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
        RefundRequestService._authorize_requester_mapping(
            mapping=mapping,
            event=event,
            flat_id=flat_id,
        )

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="REQUEST_REFUND",
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

        payment = (
            db.query(Payment)
            .filter(
                Payment.event_id == event_id,
                Payment.flat_id == flat_id
            )
            .first()
        )

        if not payment or payment.paid_amount <= 0:
            logger.warning(
                "Validation failed for refund request: no payment available",
                extra={"action": "REQUEST_REFUND", "result": "payment_missing", "context": context},
            )
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
            logger.info(
                "Workflow decision: returning existing refund request",
                extra={
                    "action": "REQUEST_REFUND",
                    "result": "existing_request_reused",
                    "context": {**context, "request_code": existing.request_code},
                },
            )
            log_exit(logger, "RefundRequestService.request_refund", context)
            return existing

        count = (
            db.query(RefundRequest)
            .join(Event, RefundRequest.event_id == Event.id)
            .filter(Event.society_id == event.society_id)
            .count()
        )
        request_code = f"REF-{count + 1:03d}"

        request = RefundRequest(
            event_id=event_id,
            flat_id=flat_id,
            request_code=request_code,
            amount=amount,
            reason=reason,
            status="requested",
            requested_by_mapping_id=requested_by_mapping_id,
            member_identity_id=mapping.member_identity_id
        )

        logger.info(
            "DB write: creating refund request",
            extra={
                "action": "REQUEST_REFUND",
                "result": "db_create_pending",
                "context": {
                    **context,
                    "society_id": event.society_id,
                    "request_code": request_code,
                },
            },
        )
        db.add(request)
        db.flush()

        if is_override:
            RefundRequestService._authorize_requester_mapping(
                mapping=mapping,
                event=event,
                flat_id=flat_id,
            )
            WorkflowEngine.apply_override(
                db=db,
                society_id=event.society_id,
                event_id=event_id,
                entity_type="refund_request",
                entity_id=request.id,
                action="REQUEST_REFUND",
                reason=override_reason,
                performed_by=None
            )

        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="refund_request",
            entity_id=request.id,
            action="REQUEST_REFUND",
            reason=(
                f"OVERRIDE: {override_reason}"
                if is_override
                else (
                    f"Request {request.request_code} for {format_currency(amount)} "
                    f"by mapping {requested_by_mapping_id}"
                )
            ),
            performed_by=None
        ))
        try:
            db.commit()
            logger.info(
                "Commit success: refund request created",
                extra={
                    "action": "REQUEST_REFUND",
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
                "Commit failure: refund request create",
                extra={
                    "action": "REQUEST_REFUND",
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

        log_exit(logger, "RefundRequestService.request_refund", context)
        return request

    @staticmethod
    @log_service_call(logger, "RefundRequestService.find_matching_request")
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
        request,
        performed_by
    ):
        performed_by = validate_uuid(performed_by, field_name="member_id")
        if request.status != "requested":
            raise Exception("Refund request is no longer pending")
        event_society_id = RefundRequestService._get_event_society_id(db, request.event_id)
        require_committee_action(
            db,
            society_id=event_society_id,
            performed_by=performed_by,
            action="REFUND",
        )
        context = build_log_context(
            event_id=request.event_id,
            flat_id=request.flat_id,
            society_id=event_society_id,
            performed_by=performed_by,
            request_code=request.request_code
        )
        log_entry(logger, "RefundRequestService.approve_request", context)
        logger.info(
            "Workflow decision: approving refund request",
            extra={"action": "APPROVE_REFUND_REQUEST", "result": "started", "context": context},
        )
        refund = RefundService.process_refund(
            db=db,
            event_id=request.event_id,
            flat_id=request.flat_id,
            amount=request.amount,
            performed_by=performed_by,
            reason=request.reason,
            override_reason=f"Approved refund request {request.request_code}",
            require_approved_request_context=True,
            approved_request_id=request.id,
        )

        request.status = "approved"
        request.approved_by = performed_by
        request.approved_at = utc_now()

        db.add(AuditLog(
            society_id=event_society_id,
            entity_type="refund_request",
            entity_id=request.id,
            action="APPROVE_REFUND_REQUEST",
            reason=(
                "Approved "
                f"{request.request_code} for {format_currency(request.amount)} "
                f"requested by mapping {request.requested_by_mapping_id}"
            ),
            performed_by=performed_by
        ))
        logger.info(
            "DB write: updating refund request status",
            extra={"action": "APPROVE_REFUND_REQUEST", "result": "db_update_pending", "context": context},
        )
        try:
            db.commit()
            logger.info(
                "Commit success: refund request approved",
                extra={"action": "APPROVE_REFUND_REQUEST", "result": "committed", "context": context},
            )
        except Exception:
            logger.exception(
                "Commit failure: refund request approve",
                extra={"action": "APPROVE_REFUND_REQUEST", "result": "commit_failed", "context": context},
            )
            db.rollback()
            raise

        log_exit(logger, "RefundRequestService.approve_request", context)
        return refund

    @staticmethod
    def reject_request(
        db: Session,
        *,
        request,
        performed_by,
        rejection_reason=None
    ):
        performed_by = validate_uuid(performed_by, field_name="member_id")
        event_society_id = RefundRequestService._get_event_society_id(db, request.event_id)
        require_committee_action(
            db,
            society_id=event_society_id,
            performed_by=performed_by,
            action="REFUND",
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
            entity_type="refund_request",
            entity_id=request.id,
            action="REJECT_REFUND_REQUEST",
            reason=reason,
            performed_by=performed_by
        ))
        db.commit()

    @staticmethod
    @log_service_call(logger, "RefundRequestService.get_request_by_code")
    def get_request_by_code(db: Session, *, request_code):
        return (
            db.query(RefundRequest)
            .filter(RefundRequest.request_code == request_code)
            .first()
        )

    @staticmethod
    @log_service_call(logger, "RefundRequestService.list_requests")
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
            db.query(RefundRequest, Flat)
            .join(Flat, RefundRequest.flat_id == Flat.id)
            .filter(RefundRequest.event_id == event_id)
        )

        if status:
            query = query.filter(RefundRequest.status == status)
        else:
            query = query.filter(RefundRequest.status != "approved")

        if requested_by_mapping_ids:
            query = query.filter(RefundRequest.requested_by_mapping_id.in_(requested_by_mapping_ids))

        if flat_id:
            query = query.filter(RefundRequest.flat_id == flat_id)

        return (
            query
            .order_by(RefundRequest.requested_at.desc())
            .all()
        )
